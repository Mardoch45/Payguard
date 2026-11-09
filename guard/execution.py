from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from guard.audit import write_audit_event
from guard.idempotency import (
    IdempotencyConflictError,
    IdempotencyRegistry,
    derive_idempotency_key,
)
from guard.models import (
    Decision,
    PolicyDecision,
    ProposedAction,
    ProvenanceContext,
    UserRequest,
)
from guard.policy import evaluate_action


READ_ONLY_TOOLS = frozenset({"list_invoices", "read_invoice"})


class PaymentAdapter(Protocol):
    """Small interface implemented by fake and PayPal Sandbox adapters."""

    def execute(self, action: ProposedAction) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ExecutionOutcome:
    policy_decision: PolicyDecision
    executed: bool
    result: dict[str, Any] | None = None
    duplicate: bool = False


def process_action(
    user_request: UserRequest,
    proposed_action: ProposedAction,
    policy: dict[str, Any],
    provenance: ProvenanceContext,
    adapter: PaymentAdapter,
    idempotency_registry: IdempotencyRegistry,
    audit_path: str | Path,
    *,
    human_confirmed: bool = False,
) -> ExecutionOutcome:
    """Apply policy and execute only actions that have sufficient authorization."""

    decision = evaluate_action(user_request, proposed_action, policy, provenance)
    if decision.decision is Decision.BLOCK:
        _audit(
            audit_path,
            user_request,
            proposed_action,
            decision,
            provenance,
            paypal_called=False,
            result="blocked_before_execution",
        )
        return ExecutionOutcome(decision, executed=False)

    if decision.decision is Decision.CONFIRM and not human_confirmed:
        _audit(
            audit_path,
            user_request,
            proposed_action,
            decision,
            provenance,
            paypal_called=False,
            result="awaiting_human_confirmation",
        )
        return ExecutionOutcome(decision, executed=False)

    read_only = proposed_action.tool in READ_ONLY_TOOLS
    if not read_only:
        # La clé effective est toujours dérivée par l'application à partir
        # de la demande autorisée : une clé fournie par le modèle ne peut
        # pas contourner la protection contre les doubles exécutions.
        proposed_action = replace(
            proposed_action,
            idempotency_key=derive_idempotency_key(user_request, proposed_action),
        )
    try:
        previous_result = None if read_only else idempotency_registry.find(proposed_action)
    except IdempotencyConflictError as error:
        conflict_decision = PolicyDecision(
            Decision.BLOCK,
            str(error),
            "idempotency.key_conflict",
        )
        _audit(
            audit_path,
            user_request,
            proposed_action,
            conflict_decision,
            provenance,
            paypal_called=False,
            result="idempotency_conflict",
        )
        return ExecutionOutcome(conflict_decision, executed=False)

    if previous_result is not None:
        _audit(
            audit_path,
            user_request,
            proposed_action,
            decision,
            provenance,
            paypal_called=False,
            result="duplicate_result_reused",
        )
        return ExecutionOutcome(
            decision,
            executed=False,
            result=previous_result,
            duplicate=True,
        )

    try:
        execution_result = adapter.execute(proposed_action)
    except Exception as error:
        # Une tentative qui échoue doit rester visible. On journalise le type
        # d'erreur uniquement : le message brut peut contenir des données PayPal.
        _audit(
            audit_path,
            user_request,
            proposed_action,
            decision,
            provenance,
            paypal_called=True,
            result="execution_error",
            error=type(error).__name__,
        )
        raise
    if not read_only:
        idempotency_registry.record(proposed_action, execution_result)
    _audit(
        audit_path,
        user_request,
        proposed_action,
        decision,
        provenance,
        paypal_called=True,
        result="executed",
    )
    return ExecutionOutcome(decision, executed=True, result=execution_result)


def record_human_refusal(
    user_request: UserRequest,
    proposed_action: ProposedAction,
    policy_decision: PolicyDecision,
    provenance: ProvenanceContext,
    audit_path: str | Path,
) -> None:
    """Journalise le refus d'une opération confirmable avant tout appel adaptateur."""

    write_audit_event(
        audit_path,
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "request_id": user_request.request_id,
            "user_request": user_request.text,
            "proposed_tool": proposed_action.tool,
            "amount": proposed_action.amount,
            "currency": proposed_action.currency,
            "beneficiary": proposed_action.beneficiary,
            "decision": policy_decision.decision.value,
            "rule_id": policy_decision.rule_id,
            "risk_factors": list(policy_decision.risk_factors),
            "untrusted_source_ids": list(provenance.untrusted_source_ids),
            "paypal_called": False,
            "result": "refused_by_human",
        },
    )


def _audit(
    audit_path: str | Path,
    user_request: UserRequest,
    proposed_action: ProposedAction,
    decision: PolicyDecision,
    provenance: ProvenanceContext,
    *,
    paypal_called: bool,
    result: str,
    error: str | None = None,
) -> None:
    event = {
        "timestamp": datetime.now(UTC).isoformat(),
        "request_id": user_request.request_id,
        "user_request": user_request.text,
        "proposed_tool": proposed_action.tool,
        "amount": proposed_action.amount,
        "currency": proposed_action.currency,
        "beneficiary": proposed_action.beneficiary,
        "decision": decision.decision.value,
        "rule_id": decision.rule_id,
        "risk_factors": list(decision.risk_factors),
        "untrusted_source_ids": list(provenance.untrusted_source_ids),
        "paypal_called": paypal_called,
        "result": result,
    }
    if error is not None:
        event["error"] = error
    write_audit_event(audit_path, event)
