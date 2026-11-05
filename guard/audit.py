import json
from pathlib import Path
from typing import Any


FORBIDDEN_FIELD_NAMES = frozenset(
    {
        "access_token",
        "api_key",
        "authorization",
        "client_secret",
        "password",
        "paypal_secret",
        "refresh_token",
        "secret",
        "token",
    }
)

REQUIRED_FIELDS = frozenset(
    {
        "timestamp",
        "request_id",
        "proposed_tool",
        "decision",
        "rule_id",
        "paypal_called",
    }
)


def write_audit_event(path: str | Path, event: dict[str, Any]) -> None:
    """Append one validated event as JSON Lines without accepting secrets."""

    missing_fields = REQUIRED_FIELDS - event.keys()
    if missing_fields:
        missing = ", ".join(sorted(missing_fields))
        raise ValueError(f"Audit event is missing required fields: {missing}")

    forbidden_paths = _find_forbidden_fields(event)
    if forbidden_paths:
        fields = ", ".join(forbidden_paths)
        raise ValueError(f"Audit event contains forbidden fields: {fields}")

    if event["decision"] == "BLOCK" and event["paypal_called"] is not False:
        raise ValueError("A blocked action cannot be marked as sent to PayPal")

    if not isinstance(event["rule_id"], str) or not event["rule_id"].strip():
        raise ValueError("Audit event must include a non-empty rule_id")

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    serialized_event = json.dumps(
        event,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    with destination.open("a", encoding="utf-8") as audit_file:
        audit_file.write(serialized_event + "\n")


def _find_forbidden_fields(value: Any, path: str = "") -> list[str]:
    forbidden_paths: list[str] = []
    if isinstance(value, dict):
        for key, nested_value in value.items():
            normalized_key = str(key).lower()
            field_path = f"{path}.{key}" if path else str(key)
            if normalized_key in FORBIDDEN_FIELD_NAMES:
                forbidden_paths.append(field_path)
            forbidden_paths.extend(_find_forbidden_fields(nested_value, field_path))
    elif isinstance(value, (list, tuple)):
        for index, nested_value in enumerate(value):
            field_path = f"{path}[{index}]"
            forbidden_paths.extend(_find_forbidden_fields(nested_value, field_path))
    return forbidden_paths
