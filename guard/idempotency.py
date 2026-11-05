import hashlib
import json
from dataclasses import asdict
from typing import Any

from guard.models import ProposedAction


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
