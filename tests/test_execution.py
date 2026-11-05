import json
from dataclasses import replace
from pathlib import Path

import pytest

from guard.execution import process_action
from guard.idempotency import IdempotencyRegistry
from guard.models import (
    Decision,
    ProposedAction,
    ProvenanceContext,
    RequestConstraints,
    UserRequest,
)
from guard.policy import load_policy


POLICY = load_policy(Path(__file__).parents[1] / "policies" / "policy.yaml")


class FakePayPalAdapter:
    def __init__(self) -> None:
        self.calls: list[ProposedAction] = []

    def execute(self, action: ProposedAction) -> dict[str, str]:
        self.calls.append(action)
        return {"status": "sandbox_simulation", "tool": action.tool}


def request(*actions: str) -> UserRequest:
    return UserRequest(
        text="Test request",
        requested_actions=frozenset(actions),
        request_id="req-execution-001",
        constraints=RequestConstraints(
            amount=15.00, currency="USD", beneficiary="sandbox-buyer-001",
            capture_id="CAPTURE-TEST-001",
        ),
    )


def refund_action(**overrides: object) -> ProposedAction:
    values = {
        "tool": "refund_payment",
        "amount": 15.00,
        "currency": "USD",
        "beneficiary": "sandbox-buyer-001",
        "idempotency_key": "refund-execution-001",
        "metadata": {"capture_id": "CAPTURE-TEST-001"},
    }
    values.update(overrides)
    return ProposedAction(**values)


def test_blocked_action_never_reaches_adapter(tmp_path: Path) -> None:
    adapter = FakePayPalAdapter()

    outcome = process_action(
        request("read_invoice"),
        refund_action(),
        POLICY,
        ProvenanceContext(influenced_by_untrusted_content=True),
        adapter,
        IdempotencyRegistry(),
        tmp_path / "audit.jsonl",
    )

    assert outcome.policy_decision.decision is Decision.BLOCK
    assert outcome.executed is False
    assert adapter.calls == []
    audit_event = json.loads((tmp_path / "audit.jsonl").read_text().strip())
    assert audit_event["paypal_called"] is False


def test_confirmation_is_not_executed_before_human_approval(tmp_path: Path) -> None:
    adapter = FakePayPalAdapter()

    outcome = process_action(
        request("refund_payment"),
        refund_action(),
        POLICY,
        ProvenanceContext(),
        adapter,
        IdempotencyRegistry(),
        tmp_path / "audit.jsonl",
    )

    assert outcome.policy_decision.decision is Decision.CONFIRM
    assert outcome.executed is False
    assert adapter.calls == []


def test_human_approved_confirmation_is_executed(tmp_path: Path) -> None:
    adapter = FakePayPalAdapter()

    outcome = process_action(
        request("refund_payment"),
        refund_action(),
        POLICY,
        ProvenanceContext(),
        adapter,
        IdempotencyRegistry(),
        tmp_path / "audit.jsonl",
        human_confirmed=True,
    )

    assert outcome.executed is True
    assert outcome.result == {
        "status": "sandbox_simulation",
        "tool": "refund_payment",
    }
    assert len(adapter.calls) == 1


def test_duplicate_action_reuses_result_without_second_call(tmp_path: Path) -> None:
    adapter = FakePayPalAdapter()
    registry = IdempotencyRegistry()
    action = refund_action()

    first = process_action(
        request("refund_payment"),
        action,
        POLICY,
        ProvenanceContext(),
        adapter,
        registry,
        tmp_path / "audit.jsonl",
        human_confirmed=True,
    )
    second = process_action(
        request("refund_payment"),
        action,
        POLICY,
        ProvenanceContext(),
        adapter,
        registry,
        tmp_path / "audit.jsonl",
        human_confirmed=True,
    )

    assert first.executed is True
    assert second.executed is False
    assert second.duplicate is True
    assert second.result == first.result
    assert len(adapter.calls) == 1


def test_reused_key_for_different_action_is_blocked(tmp_path: Path) -> None:
    adapter = FakePayPalAdapter()
    registry = IdempotencyRegistry()

    process_action(
        request("refund_payment"),
        refund_action(),
        POLICY,
        ProvenanceContext(),
        adapter,
        registry,
        tmp_path / "audit.jsonl",
        human_confirmed=True,
    )
    conflict = process_action(
        replace(request("refund_payment"), constraints=replace(
            request("refund_payment").constraints, amount=10.00
        )),
        refund_action(amount=10.00),
        POLICY,
        ProvenanceContext(),
        adapter,
        registry,
        tmp_path / "audit.jsonl",
        human_confirmed=True,
    )

    assert conflict.executed is False
    assert conflict.policy_decision.decision is Decision.BLOCK
    assert conflict.policy_decision.rule_id == "idempotency.key_conflict"
    assert len(adapter.calls) == 1


@pytest.mark.parametrize("tool", ["list_invoices", "read_invoice"])
def test_invoice_reads_refresh_even_with_an_old_idempotency_entry(
    tool: str, tmp_path: Path
) -> None:
    class InvoiceAdapter:
        def __init__(self):
            self.invoices = []
            self.calls = 0

        def execute(self, action):
            self.calls += 1
            return {"invoices": list(self.invoices)}

    adapter = InvoiceAdapter()
    registry = IdempotencyRegistry()
    action = ProposedAction(tool=tool, idempotency_key="same-read-key")
    registry.record(action, {"invoices": []})
    first = process_action(
        request(tool), action, POLICY, ProvenanceContext(), adapter, registry, tmp_path / "audit.jsonl"
    )
    adapter.invoices.append({"id": "INV-NEW"})
    second = process_action(
        request(tool), action, POLICY, ProvenanceContext(), adapter, registry, tmp_path / "audit.jsonl"
    )

    assert first.result == {"invoices": []}
    assert second.result == {"invoices": [{"id": "INV-NEW"}]}
    assert first.executed and second.executed
    assert not second.duplicate
    assert adapter.calls == 2
