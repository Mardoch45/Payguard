from pathlib import Path

import pytest

from guard.models import (
    Decision,
    ProposedAction,
    ProvenanceContext,
    RequestConstraints,
    UserRequest,
)
from guard.policy import evaluate_action, load_policy


POLICY_PATH = Path(__file__).parents[1] / "policies" / "policy.yaml"
POLICY = load_policy(POLICY_PATH)


def request(*actions: str) -> UserRequest:
    return UserRequest(
        text="Test request",
        requested_actions=frozenset(actions),
        request_id="req-test-001",
        constraints=RequestConstraints(
            amount=15.00, currency="USD", beneficiary="sandbox-buyer-001",
            capture_id="CAPTURE-TEST-001",
        ),
    )


def test_invoice_read_is_allowed() -> None:
    result = evaluate_action(
        request("read_invoice"),
        ProposedAction(tool="read_invoice"),
        POLICY,
        ProvenanceContext(),
    )

    assert result.decision is Decision.ALLOW
    assert result.rule_id == "action.allowed"


def test_unrequested_refund_is_blocked() -> None:
    result = evaluate_action(
        request("read_invoice"),
        ProposedAction(
            tool="refund_payment",
            amount=15.00,
            currency="USD",
            beneficiary="sandbox-buyer-001",
            idempotency_key="refund-test-001",
        ),
        POLICY,
        ProvenanceContext(influenced_by_untrusted_content=True),
    )

    assert result.decision is Decision.BLOCK
    assert result.rule_id == "intent.action_not_requested"
    assert "untrusted_content" in result.risk_factors


def test_requested_refund_requires_confirmation() -> None:
    result = evaluate_action(
        request("refund_payment"),
        ProposedAction(
            tool="refund_payment",
            amount=15.00,
            currency="USD",
            beneficiary="sandbox-buyer-001",
            idempotency_key="refund-test-002",
            metadata={"capture_id": "CAPTURE-TEST-001"},
        ),
        POLICY,
        ProvenanceContext(),
    )

    assert result.decision is Decision.CONFIRM
    assert result.rule_id == "action.confirmation_required"


def test_forbidden_action_is_blocked_even_if_requested() -> None:
    result = evaluate_action(
        request("send_money"),
        ProposedAction(tool="send_money"),
        POLICY,
        ProvenanceContext(),
    )

    assert result.decision is Decision.BLOCK
    assert result.rule_id == "action.forbidden"


def test_unknown_action_is_blocked_by_default() -> None:
    result = evaluate_action(
        request("delete_account"),
        ProposedAction(tool="delete_account"),
        POLICY,
        ProvenanceContext(),
    )

    assert result.decision is Decision.BLOCK
    assert result.rule_id == "default.unknown_action"


def refund_action(**overrides: object) -> ProposedAction:
    values = {
        "tool": "refund_payment",
        "amount": 15.00,
        "currency": "USD",
        "beneficiary": "sandbox-buyer-001",
        "idempotency_key": "refund-limits-001",
    }
    values.update(overrides)
    return ProposedAction(**values)


def test_refund_above_limit_is_blocked() -> None:
    result = evaluate_action(
        request("refund_payment"),
        refund_action(amount=20.01),
        POLICY,
        ProvenanceContext(),
    )

    assert result.decision is Decision.BLOCK
    assert result.rule_id == "limits.amount_exceeded"


def test_refund_with_disallowed_currency_is_blocked() -> None:
    result = evaluate_action(
        request("refund_payment"),
        refund_action(currency="XOF"),
        POLICY,
        ProvenanceContext(),
    )

    assert result.decision is Decision.BLOCK
    assert result.rule_id == "limits.currency_not_allowed"


def test_refund_to_unknown_beneficiary_is_blocked() -> None:
    result = evaluate_action(
        request("refund_payment"),
        refund_action(beneficiary="unknown-account"),
        POLICY,
        ProvenanceContext(),
    )

    assert result.decision is Decision.BLOCK
    assert result.rule_id == "beneficiary.not_allowed"


def test_refund_without_idempotency_key_is_blocked() -> None:
    result = evaluate_action(
        request("refund_payment"),
        refund_action(idempotency_key=None),
        POLICY,
        ProvenanceContext(),
    )

    assert result.decision is Decision.BLOCK
    assert result.rule_id == "idempotency.key_required"


def test_refund_requires_positive_amount() -> None:
    result = evaluate_action(
        request("refund_payment"),
        refund_action(amount=0),
        POLICY,
        ProvenanceContext(),
    )

    assert result.decision is Decision.BLOCK
    assert result.rule_id == "limits.invalid_amount"


def test_invalid_policy_is_rejected(tmp_path: Path) -> None:
    invalid_policy = tmp_path / "invalid.yaml"
    invalid_policy.write_text("version: 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="actions mapping"):
        load_policy(invalid_policy)
