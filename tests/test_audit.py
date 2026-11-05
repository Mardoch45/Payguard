import json
from pathlib import Path

import pytest

from guard.audit import write_audit_event


def audit_event(**overrides: object) -> dict[str, object]:
    event: dict[str, object] = {
        "timestamp": "2026-10-28T15:30:00Z",
        "request_id": "req-test-001",
        "proposed_tool": "refund_payment",
        "decision": "BLOCK",
        "rule_id": "intent.action_not_requested",
        "paypal_called": False,
    }
    event.update(overrides)
    return event


def test_audit_event_is_written_as_valid_json_line(tmp_path: Path) -> None:
    audit_path = tmp_path / "nested" / "audit.jsonl"

    write_audit_event(audit_path, audit_event())

    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["request_id"] == "req-test-001"


def test_multiple_events_are_appended(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.jsonl"

    write_audit_event(audit_path, audit_event(request_id="req-001"))
    write_audit_event(audit_path, audit_event(request_id="req-002"))

    lines = audit_path.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["request_id"] for line in lines] == [
        "req-001",
        "req-002",
    ]


def test_secret_field_is_rejected_even_when_nested(tmp_path: Path) -> None:
    event = audit_event(metadata={"client_secret": "must-not-be-stored"})

    with pytest.raises(ValueError, match="metadata.client_secret"):
        write_audit_event(tmp_path / "audit.jsonl", event)


def test_blocked_action_cannot_be_marked_as_called(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="cannot be marked"):
        write_audit_event(
            tmp_path / "audit.jsonl",
            audit_event(paypal_called=True),
        )


def test_required_field_is_enforced(tmp_path: Path) -> None:
    event = audit_event()
    del event["rule_id"]

    with pytest.raises(ValueError, match="rule_id"):
        write_audit_event(tmp_path / "audit.jsonl", event)
