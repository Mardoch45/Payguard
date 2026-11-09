"""Adaptateur PayPal Sandbox.

L'adaptateur est la seule couche autorisée à parler à PayPal. Il
n'accepte que les actions prévues par la politique locale, refuse tout
outil inconnu, vérifie que l'URL cible est exactement l'hôte sandbox
officiel en HTTPS et refuse de suivre les redirections.

Endpoints utilisés (API REST PayPal v2) :
- ``GET  /v2/invoicing/invoices``                    lister les factures
- ``GET  /v2/invoicing/invoices/{id}``               lire une facture
- ``POST /v2/invoicing/invoices``                    créer un brouillon
- ``POST /v2/invoicing/invoices/{id}/send``          envoyer la facture
- ``POST /v2/payments/captures/{id}/refund``         rembourser un paiement
"""

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import quote

import requests

from guard.models import ProposedAction
from guard.settings import SANDBOX_BASE_URL, validate_sandbox_base_url

TOKEN_PATH = "/v1/oauth2/token"
INVOICES_PATH = "/v2/invoicing/invoices"
CAPTURES_PATH = "/v2/payments/captures"


class PayPalAPIError(RuntimeError):
    """Réponse PayPal en erreur ou inutilisable."""

    def __init__(
        self,
        status_code: int,
        message: str,
        payload: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(f"PayPal a répondu {status_code} : {message}")
        self.status_code = status_code
        self.payload = dict(payload or {})


class UnsupportedActionError(ValueError):
    """Action que l'adaptateur ne sait pas ou ne veut pas exécuter."""


@dataclass(frozen=True)
class PayPalResponse:
    status_code: int
    payload: dict[str, Any]
    headers: Mapping[str, str]


class PayPalClient:
    """Client REST minimal avec jeton OAuth mis en cache."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        base_url: str = SANDBOX_BASE_URL,
        *,
        session: requests.Session | None = None,
        timeout: float = 20.0,
    ) -> None:
        # Hôte exact et HTTPS : un sous-texte « sandbox » ne suffit pas.
        validate_sandbox_base_url(base_url)
        if not client_id or not client_secret:
            raise ValueError("Identifiants PayPal Sandbox manquants.")

        self._client_id = client_id
        self._client_secret = client_secret
        self._base_url = base_url.rstrip("/")
        self._session = session or requests.Session()
        self._timeout = timeout
        self._access_token = ""
        self._token_expires_at = 0.0

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> PayPalResponse:
        headers = {
            "Authorization": f"Bearer {self._token()}",
            "Accept": "application/json",
        }
        if request_id:
            headers["PayPal-Request-Id"] = request_id
        if json_body is not None:
            headers["Content-Type"] = "application/json"

        response = self._session.request(
            method,
            f"{self._base_url}{path}",
            json=json_body,
            params=params,
            headers=headers,
            timeout=self._timeout,
            # Une redirection vers un autre hôte divulguerait le jeton Bearer.
            allow_redirects=False,
        )
        payload = _safe_json(response)

        if not 200 <= response.status_code < 300:
            message = str(payload.get("message") or payload.get("error") or "erreur")
            raise PayPalAPIError(response.status_code, message, payload)
        return PayPalResponse(response.status_code, payload, response.headers)

    def _token(self) -> str:
        if self._access_token and time.time() < self._token_expires_at - 30:
            return self._access_token

        response = self._session.post(
            f"{self._base_url}{TOKEN_PATH}",
            auth=(self._client_id, self._client_secret),
            # Les droits activés récemment peuvent manquer dans un jeton
            # conservé par PayPal. Le cache local reste utilisé ensuite.
            data={"grant_type": "client_credentials", "ignoreCache": "true"},
            headers={"Accept": "application/json"},
            timeout=self._timeout,
            allow_redirects=False,
        )
        payload = _safe_json(response)
        if response.status_code != 200 or "access_token" not in payload:
            raise PayPalAPIError(
                response.status_code,
                str(payload.get("error_description") or "jeton OAuth refusé"),
                payload,
            )

        self._access_token = str(payload["access_token"])
        expires_in = float(payload.get("expires_in", 32400))
        self._token_expires_at = time.time() + expires_in
        return self._access_token


class PayPalSandboxAdapter:
    """Implémente ``PaymentAdapter`` au-dessus de l'API PayPal Sandbox."""

    def __init__(self, client: PayPalClient) -> None:
        self._client = client

    def execute(self, action: ProposedAction) -> dict[str, Any]:
        handlers = {
            "list_invoices": self._list_invoices,
            "read_invoice": self._read_invoice,
            "create_invoice": self._create_invoice,
            "refund_payment": self._refund_payment,
        }
        handler = handlers.get(action.tool)
        if handler is None:
            raise UnsupportedActionError(
                f"L'adaptateur PayPal ne gère pas l'action {action.tool!r}."
            )

        result = handler(action)
        return {"tool": action.tool, "sandbox": True, **result}

    def _list_invoices(self, action: ProposedAction) -> dict[str, Any]:
        response = self._client.request(
            "GET",
            INVOICES_PATH,
            params={
                "page": int(action.metadata.get("page", 1)),
                "page_size": int(action.metadata.get("page_size", 10)),
                "total_required": "true",
            },
        )
        items = response.payload.get("items", [])
        return {
            "invoices": [_summarize_invoice(invoice) for invoice in items],
            "total_items": response.payload.get("total_items"),
            "total_pages": response.payload.get("total_pages"),
        }

    def _read_invoice(self, action: ProposedAction) -> dict[str, Any]:
        invoice_id = _require_metadata(action, "invoice_id")
        response = self._client.request(
            "GET", f"{INVOICES_PATH}/{quote(invoice_id, safe='')}"
        )
        return {"invoice": _summarize_invoice(response.payload)}

    def _create_invoice(self, action: ProposedAction) -> dict[str, Any]:
        if action.amount is None or not action.currency:
            raise UnsupportedActionError(
                "create_invoice exige un montant et une devise."
            )

        recipient_email = str(
            action.metadata.get("recipient_email") or action.beneficiary or ""
        )
        if "@" not in recipient_email:
            raise UnsupportedActionError(
                "create_invoice exige metadata['recipient_email'] (adresse "
                "e-mail du destinataire de la facture)."
            )

        currency = action.currency
        body = {
            "detail": {
                "currency_code": currency,
                "note": str(action.metadata.get("note") or action.reason)[:1000],
                "invoice_number": str(
                    action.metadata.get("invoice_number")
                    or _invoice_number(action)
                ),
            },
            "primary_recipients": [
                {"billing_info": {"email_address": recipient_email}}
            ],
            "items": [
                {
                    "name": str(action.metadata.get("item_name", "PayGuard demo")),
                    "quantity": "1",
                    "unit_amount": {
                        "currency_code": currency,
                        "value": f"{action.amount:.2f}",
                    },
                }
            ],
        }

        response = self._client.request(
            "POST",
            INVOICES_PATH,
            json_body=body,
            request_id=action.idempotency_key,
        )
        invoice_id = response.payload.get("id") or _invoice_id_from_location(
            response.headers
        )
        if not invoice_id:
            raise PayPalAPIError(
                response.status_code,
                "PayPal n'a renvoyé aucun identifiant de facture.",
                response.payload,
            )

        sent = False
        if action.metadata.get("send", False):
            self._client.request(
                "POST",
                f"{INVOICES_PATH}/{quote(invoice_id, safe='')}/send",
                json_body={},
            )
            sent = True

        return {
            "invoice_id": invoice_id,
            "status": response.payload.get("status", "DRAFT"),
            "sent": sent,
            "recipient_email": recipient_email,
        }

    def _refund_payment(self, action: ProposedAction) -> dict[str, Any]:
        capture_id = _require_metadata(action, "capture_id")
        if action.amount is None or not action.currency:
            raise UnsupportedActionError(
                "refund_payment exige un montant et une devise."
            )

        response = self._client.request(
            "POST",
            f"{CAPTURES_PATH}/{quote(capture_id, safe='')}/refund",
            json_body={
                "amount": {
                    "value": f"{action.amount:.2f}",
                    "currency_code": action.currency,
                },
                "note_to_payer": str(action.reason or "Remboursement PayGuard")[:255],
            },
            request_id=action.idempotency_key,
        )
        return {
            "refund_id": response.payload.get("id"),
            "status": response.payload.get("status"),
            "capture_id": capture_id,
            "amount": f"{action.amount:.2f}",
            "currency": action.currency,
        }


def _require_metadata(action: ProposedAction, key: str) -> str:
    value = action.metadata.get(key)
    if not value:
        raise UnsupportedActionError(
            f"{action.tool} exige metadata[{key!r}] pour joindre PayPal."
        )
    return str(value)


def _safe_json(response: requests.Response) -> dict[str, Any]:
    if not response.content:
        return {}
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {"data": payload}


def _summarize_invoice(invoice: Mapping[str, Any]) -> dict[str, Any]:
    amount = invoice.get("amount") or {}
    detail = invoice.get("detail") or {}
    return {
        "id": invoice.get("id"),
        "status": invoice.get("status"),
        "currency": amount.get("currency_code"),
        "amount": amount.get("value"),
        "invoice_number": detail.get("invoice_number"),
        "note": detail.get("note"),
        "recipient_email": _primary_recipient_email(invoice),
    }


def _primary_recipient_email(invoice: Mapping[str, Any]) -> str | None:
    recipients = invoice.get("primary_recipients") or []
    if not recipients:
        return None
    billing_info = recipients[0].get("billing_info") or {}
    return billing_info.get("email_address")


def _invoice_number(action: ProposedAction) -> str:
    source = action.idempotency_key or f"{action.tool}-{action.amount}-{action.beneficiary}"
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()[:10].upper()
    return f"PG-{digest}"


def _invoice_id_from_location(headers: Mapping[str, str]) -> str | None:
    location = headers.get("Location") or headers.get("location")
    if not location:
        return None
    return location.rstrip("/").rsplit("/", 1)[-1] or None
