import hashlib
import json
from dataclasses import asdict
from typing import Any

from guard.models import ProposedAction, UserRequest


class IdempotencyConflictError(ValueError):
    """Raised when one key is reused for a different action."""


class IdempotencyRegistry:
    """In-memory duplicate protection for the MVP execution proxy."""

    def __init__(self) -> None:
        self._entries: dict[str, tuple[str, dict[str, Any]]] = {}

    def find(self, action: ProposedAction) -> dict[str, Any] | None:
        if not action.idempotency_key:
            return None

        entry = self._entries.get(action.idempotency_key)
        if entry is None:
            return None

        stored_fingerprint, stored_result = entry
        if stored_fingerprint != _action_fingerprint(action):
            raise IdempotencyConflictError(
                "The idempotency key was already used for a different action"
            )
        return stored_result.copy()

    def record(self, action: ProposedAction, result: dict[str, Any]) -> None:
        if not action.idempotency_key:
            return

        existing_result = self.find(action)
        if existing_result is not None:
            return

        self._entries[action.idempotency_key] = (
            _action_fingerprint(action),
            result.copy(),
        )


def derive_idempotency_key(request: UserRequest, action: ProposedAction) -> str:
    """Clé déterministe calculée par l'application, jamais par le modèle.

    La même demande rejouée produit la même clé : l'anti-rejeu ne peut pas
    être contourné en changeant la clé fournie par un appel d'outil.
    """

    material = json.dumps(
        {
            "request_id": request.request_id,
            "tool": action.tool,
            "amount": action.amount,
            "currency": action.currency,
            "beneficiary": action.beneficiary,
            "invoice_id": action.metadata.get("invoice_id"),
            "capture_id": action.metadata.get("capture_id"),
        },
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]
    return f"{request.request_id}-{digest}"


def _action_fingerprint(action: ProposedAction) -> str:
    action_data = asdict(action)
    action_data.pop("idempotency_key", None)
    serialized_action = json.dumps(
        action_data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(serialized_action.encode("utf-8")).hexdigest()
