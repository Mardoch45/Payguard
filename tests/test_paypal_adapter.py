import json
from typing import Any

import pytest

from adapters.paypal import (
    PayPalAPIError,
    PayPalClient,
    PayPalSandboxAdapter,
    UnsupportedActionError,
)
from guard.models import ProposedAction


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.payload = payload or {}
        self.headers = headers or {}
        self.content = json.dumps(self.payload).encode("utf-8") if payload else b""

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeSession:
    """Remplace requests.Session pour vérifier les appels sans réseau."""

    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append(("POST", url, kwargs))
        return self.responses.pop(0)

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


def token_response() -> FakeResponse:
    return FakeResponse(200, {"access_token": "sandbox-token", "expires_in": 3600})


def make_adapter(responses: list[FakeResponse]) -> tuple[PayPalSandboxAdapter, FakeSession]:
    session = FakeSession(responses)
    client = PayPalClient("client-id", "client-secret", session=session)
    return PayPalSandboxAdapter(client), session


def refund_action(**overrides: Any) -> ProposedAction:
    values = {
        "tool": "refund_payment",
        "amount": 15.0,
        "currency": "USD",
        "beneficiary": "sandbox-buyer-001",
        "idempotency_key": "refund-adapter-001",
        "metadata": {"capture_id": "CAPTURE-123"},
    }
    values.update(overrides)
    return ProposedAction(**values)


def test_client_rejects_non_sandbox_url() -> None:
    with pytest.raises(ValueError, match="sandbox"):
        PayPalClient("id", "secret", base_url="https://api-m.paypal.com")


def test_invoice_listing_uses_oauth_token() -> None:
    adapter, session = make_adapter(
        [
            token_response(),
            FakeResponse(
                200,
                {
                    "items": [
                        {
                            "id": "INV-001",
                            "status": "SENT",
                            "amount": {"currency_code": "USD", "value": "75.00"},
                            "detail": {"invoice_number": "PG-001"},
                            "primary_recipients": [
                                {"billing_info": {"email_address": "buyer@example.test"}}
                            ],
                        }
                    ],
                    "total_items": 1,
                    "total_pages": 1,
                },
            ),
        ]
    )

    result = adapter.execute(ProposedAction(tool="list_invoices"))

    assert result["sandbox"] is True
    assert result["invoices"][0]["id"] == "INV-001"
    assert result["invoices"][0]["currency"] == "USD"
    assert result["total_items"] == 1
    assert session.calls[0][1].endswith("/v1/oauth2/token")
    method, url, kwargs = session.calls[1]
    assert method == "GET"
    assert url.endswith("/v2/invoicing/invoices")
    assert kwargs["headers"]["Authorization"] == "Bearer sandbox-token"
    assert kwargs["params"]["total_required"] == "true"


def test_refund_sends_amount_and_idempotency_request_id() -> None:
    adapter, session = make_adapter(
        [
            token_response(),
            FakeResponse(201, {"id": "REFUND-9", "status": "COMPLETED"}),
        ]
    )

    result = adapter.execute(refund_action())

    assert result["refund_id"] == "REFUND-9"
    assert result["status"] == "COMPLETED"
    method, url, kwargs = session.calls[1]
    assert method == "POST"
    assert url.endswith("/v2/payments/captures/CAPTURE-123/refund")
    assert kwargs["json"]["amount"] == {"value": "15.00", "currency_code": "USD"}
    assert kwargs["headers"]["PayPal-Request-Id"] == "refund-adapter-001"


def test_unsupported_tool_is_refused() -> None:
    adapter, _ = make_adapter([])

    with pytest.raises(UnsupportedActionError):
        adapter.execute(ProposedAction(tool="send_money", amount=10.0))


def test_refund_without_capture_id_is_refused() -> None:
    adapter, _ = make_adapter([])

    with pytest.raises(UnsupportedActionError, match="capture_id"):
        adapter.execute(refund_action(metadata={}))


def test_api_error_is_raised_with_status() -> None:
    adapter, _ = make_adapter(
        [token_response(), FakeResponse(422, {"message": "INVALID_REQUEST"})]
    )

    with pytest.raises(PayPalAPIError) as error:
        adapter.execute(ProposedAction(tool="list_invoices"))

    assert error.value.status_code == 422


def test_token_is_cached_between_calls() -> None:
    adapter, session = make_adapter(
        [
            token_response(),
            FakeResponse(200, {"items": []}),
            FakeResponse(200, {"items": []}),
        ]
    )

    adapter.execute(ProposedAction(tool="list_invoices"))
    adapter.execute(ProposedAction(tool="list_invoices"))

    token_calls = [call for call in session.calls if call[1].endswith("/token")]
    assert len(token_calls) == 1


def test_new_permissions_are_not_hidden_by_paypal_token_cache() -> None:
    class PermissionCacheSession(FakeSession):
        def post(self, url: str, **kwargs: Any) -> FakeResponse:
            self.calls.append(("POST", url, kwargs))
            refresh = kwargs.get("data", {}).get("ignoreCache") == "true"
            return FakeResponse(
                200,
                {
                    "access_token": "new-permissions" if refresh else "old-permissions",
                    "expires_in": 3600,
                },
            )

        def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
            self.calls.append((method, url, kwargs))
            if kwargs["headers"]["Authorization"] != "Bearer new-permissions":
                return FakeResponse(403, {"message": "Insufficient permissions"})
            return FakeResponse(200, {"items": [], "total_items": 0})

    session = PermissionCacheSession([])
    adapter = PayPalSandboxAdapter(PayPalClient("test-id", "test-secret", session=session))

    first = adapter.execute(ProposedAction(tool="list_invoices"))
    second = adapter.execute(ProposedAction(tool="list_invoices"))

    assert first["total_items"] == second["total_items"] == 0
    assert len([call for call in session.calls if call[1].endswith("/token")]) == 1


def test_creating_an_invoice_keeps_a_draft_without_sending_it() -> None:
    adapter, session = make_adapter([
        token_response(), FakeResponse(201, {"id": "INV-DRAFT", "status": "DRAFT"}),
    ])
    result = adapter.execute(ProposedAction(
        "create_invoice", amount=5.00, currency="USD", beneficiary="sandbox-buyer-001",
        idempotency_key="invoice-draft", metadata={"recipient_email": "buyer@example.test"},
    ))
    assert result["invoice_id"] == "INV-DRAFT"
    assert result["sent"] is False
    assert len(session.calls) == 2
    assert not any(url.endswith("/send") for _, url, _ in session.calls)
    body = session.calls[1][2]["json"]
    assert body["primary_recipients"][0]["billing_info"]["email_address"] == "buyer@example.test"
    assert body["items"][0]["unit_amount"] == {"currency_code": "USD", "value": "5.00"}
