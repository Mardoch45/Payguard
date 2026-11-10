"""Authorization regressions: a model cannot expand a user's payment request."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from adapters.fake import FakePayPalAdapter
from app.scenarios import load_all_scenarios, prepare_sandbox_scenario
from guard.execution import process_action
from guard.idempotency import IdempotencyRegistry, derive_idempotency_key
from guard.models import Decision, ProposedAction, ProvenanceContext, RequestConstraints, UserRequest
from guard.policy import evaluate_action, load_policy

POLICY = load_policy(Path(__file__).parents[1] / "policies" / "policy.yaml")
CONSTRAINTS = RequestConstraints(
    amount=5.00, currency="USD", beneficiary="sandbox-buyer-001", capture_id="CAPTURE-SELECTED"
)
REQUEST = UserRequest("Refund exactly 5 USD.", frozenset({"refund_payment"}), "request-5", CONSTRAINTS)
ACTION = ProposedAction(
    "refund_payment", amount=5.00, currency="USD", beneficiary="sandbox-buyer-001",
    idempotency_key="refund-selected", metadata={"capture_id": "CAPTURE-SELECTED"},
)


@pytest.mark.parametrize("human_confirmed", [False, True])
@pytest.mark.parametrize(
    ("changes", "rule"),
    [
        ({"amount": 15.00}, "intent.amount_mismatch"),
        ({"currency": "EUR"}, "intent.currency_mismatch"),
        ({"metadata": {"capture_id": "CAPTURE-OTHER"}}, "intent.capture_id_mismatch"),
        ({"metadata": {}}, "intent.capture_id_mismatch"),
    ],
)
def test_mismatch_cannot_execute_even_with_human_approval(
    changes: dict, rule: str, human_confirmed: bool, tmp_path: Path
) -> None:
    adapter = FakePayPalAdapter()
    audit_path = tmp_path / "audit.jsonl"
    result = process_action(
        REQUEST, replace(ACTION, **changes), POLICY, ProvenanceContext(),
        adapter, IdempotencyRegistry(), audit_path, human_confirmed=human_confirmed,
    )
    assert result.policy_decision.decision is Decision.BLOCK
    assert result.policy_decision.rule_id == rule
    assert not result.executed
    assert adapter.calls == []
    assert json.loads(audit_path.read_text())["paypal_called"] is False


def test_matching_parameters_wait_for_confirmation_then_execute_once(tmp_path: Path) -> None:
    adapter = FakePayPalAdapter()
    registry = IdempotencyRegistry()
    arguments = (REQUEST, ACTION, POLICY, ProvenanceContext(), adapter, registry, tmp_path / "audit.jsonl")
    pending = process_action(*arguments)
    assert pending.policy_decision.decision is Decision.CONFIRM
    assert adapter.calls == []
    approved = process_action(*arguments, human_confirmed=True)
    duplicate = process_action(*arguments, human_confirmed=True)
    assert approved.executed
    assert duplicate.duplicate
    assert adapter.calls == [
        replace(ACTION, idempotency_key=derive_idempotency_key(REQUEST, ACTION))
    ]


@pytest.mark.parametrize("constraints", [None, RequestConstraints(), replace(CONSTRAINTS, amount=None)])
def test_sensitive_requests_need_explicit_parameters(constraints) -> None:
    result = evaluate_action(replace(REQUEST, constraints=constraints), ACTION, POLICY, ProvenanceContext())
    assert result.decision is Decision.BLOCK
    assert result.rule_id == "intent.missing_constraints"


def test_sensitive_request_needs_a_selected_capture() -> None:
    result = evaluate_action(
        replace(REQUEST, constraints=replace(CONSTRAINTS, capture_id=None)),
        ACTION, POLICY, ProvenanceContext(),
    )
    assert result.decision is Decision.BLOCK
    assert result.rule_id == "intent.missing_target"


@pytest.mark.parametrize("amount", [float("nan"), float("inf"), float("-inf"), True, -1, 0, 5.001, "5"])
def test_invalid_money_is_blocked_before_confirmation(amount) -> None:
    result = evaluate_action(REQUEST, replace(ACTION, amount=amount), POLICY, ProvenanceContext())
    assert result.decision is Decision.BLOCK
    assert result.rule_id == "limits.invalid_amount"


def test_a_policy_alias_does_not_authorize_a_different_invoice_email(tmp_path: Path) -> None:
    request = UserRequest(
        "Prepare a draft of 5 USD for buyer@example.test.", frozenset({"create_invoice"}), "invoice-5",
        RequestConstraints(amount=5, currency="USD", beneficiary="sandbox-buyer-001", recipient_email="buyer@example.test"),
    )
    action = ProposedAction(
        "create_invoice", amount=5, currency="USD", beneficiary="sandbox-buyer-001",
        idempotency_key="invoice-5", metadata={"recipient_email": "other@example.test"},
    )
    adapter = FakePayPalAdapter()
    outcome = process_action(
        request, action, POLICY, ProvenanceContext(), adapter, IdempotencyRegistry(),
        tmp_path / "audit.jsonl", human_confirmed=True,
    )
    assert outcome.policy_decision.rule_id == "intent.recipient_email_mismatch"
    assert outcome.policy_decision.decision is Decision.BLOCK
    assert adapter.calls == []


def test_preparing_a_draft_does_not_authorize_sending_it() -> None:
    request = UserRequest(
        "Prepare a draft.", frozenset({"create_invoice"}), "draft",
        RequestConstraints(amount=5, currency="USD", beneficiary="sandbox-buyer-001", recipient_email="buyer@example.test"),
    )
    action = ProposedAction(
        "create_invoice", amount=5, currency="USD", beneficiary="sandbox-buyer-001",
        idempotency_key="draft", metadata={"recipient_email": "buyer@example.test", "send": True},
    )
    result = evaluate_action(request, action, POLICY, ProvenanceContext())
    assert result.decision is Decision.BLOCK
    assert result.rule_id == "intent.invoice_send_not_requested"


@pytest.mark.parametrize("invoice_id", [None, "INV-OTHER"])
def test_specific_invoice_read_cannot_switch_objects(invoice_id) -> None:
    request = UserRequest(
        "Read INV-SELECTED.", frozenset({"read_invoice"}), "read-selected", RequestConstraints(invoice_id="INV-SELECTED")
    )
    result = evaluate_action(
        request, ProposedAction("read_invoice", metadata={"invoice_id": invoice_id}), POLICY, ProvenanceContext()
    )
    assert result.decision is Decision.BLOCK
    assert result.rule_id == "intent.invoice_id_mismatch"


def test_sandbox_binding_preserves_a_tampered_scripted_target() -> None:
    scenario = next(item for item in load_all_scenarios() if item.id == "attack-capture-001")
    resolved = prepare_sandbox_scenario(scenario, {"capture_id": "REAL-SELECTED"})
    assert resolved.constraints.capture_id == "REAL-SELECTED"
    assert resolved.proposed_action["metadata"]["capture_id"] == "CAPTURE-OTHER-001"
    assert scenario.constraints.capture_id == "CAPTURE-DEMO-001"


@pytest.mark.parametrize(
    ("scenario_id", "field", "selected"),
    [("normal-refund-001", "capture_id", "REAL-CAPTURE"),
     ("normal-invoice-001", "recipient_email", "selected@example.test"),
     ("normal-read-001", "invoice_id", "REAL-INVOICE")],
)
def test_legitimate_scripted_targets_use_user_selection(scenario_id, field, selected) -> None:
    scenario = next(item for item in load_all_scenarios() if item.id == scenario_id)
    resolved = prepare_sandbox_scenario(scenario, {field: selected})
    assert getattr(resolved.constraints, field) == selected
    assert resolved.proposed_action["metadata"][field] == selected


def test_empty_sandbox_selection_cannot_reuse_a_fake_capture() -> None:
    scenario = next(item for item in load_all_scenarios() if item.id == "normal-refund-001")
    resolved = prepare_sandbox_scenario(scenario, {})
    assert resolved.constraints.capture_id is None
    assert "capture_id" not in resolved.proposed_action["metadata"]


def test_empty_selection_for_a_specific_read_is_blocked() -> None:
    scenario = next(item for item in load_all_scenarios() if item.id == "normal-read-001")
    resolved = prepare_sandbox_scenario(scenario, {})
    request = UserRequest(resolved.user_request, frozenset(resolved.requested_actions), resolved.id, resolved.constraints)
    result = evaluate_action(
        request, ProposedAction("read_invoice", metadata=resolved.proposed_action["metadata"]), POLICY, ProvenanceContext()
    )
    assert result.decision is Decision.BLOCK
    assert result.rule_id == "intent.missing_target"


def test_beneficiary_must_match_the_request_even_when_both_are_in_policy() -> None:
    policy = {**POLICY, "limits": {**POLICY["limits"], "allowed_beneficiaries": ["sandbox-buyer-001", "other-allowed"]}}
    result = evaluate_action(REQUEST, replace(ACTION, beneficiary="other-allowed"), policy, ProvenanceContext())
    assert result.decision is Decision.BLOCK
    assert result.rule_id == "intent.beneficiary_mismatch"
