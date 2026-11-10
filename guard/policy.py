from pathlib import Path
from decimal import Decimal, InvalidOperation
from typing import Any

import yaml

from guard.models import (
    Decision,
    PolicyDecision,
    ProposedAction,
    ProvenanceContext,
    UserRequest,
)


def load_policy(path: str | Path) -> dict[str, Any]:
    """Load a policy file and validate its minimum required structure."""

    with Path(path).open(encoding="utf-8") as policy_file:
        policy = yaml.safe_load(policy_file)

    if not isinstance(policy, dict):
        raise ValueError("Policy must be a mapping")

    actions = policy.get("actions")
    if not isinstance(actions, dict):
        raise ValueError("Policy must define an actions mapping")

    for action_group in ("allowed", "forbidden", "confirmation_required"):
        configured_actions = actions.get(action_group)
        if not isinstance(configured_actions, list):
            raise ValueError(f"Policy actions.{action_group} must be a list")

    return policy


def evaluate_action(
    user_request: UserRequest,
    proposed_action: ProposedAction,
    policy: dict[str, Any],
    provenance: ProvenanceContext,
) -> PolicyDecision:
    """Evaluate an agent action without performing any external operation."""

    actions = policy["actions"]
    security = policy.get("security", {})
    limits = policy.get("limits", {})

    known_actions = {
        *actions.get("allowed", []),
        *actions.get("forbidden", []),
        *actions.get("confirmation_required", []),
    }
    if not proposed_action.tool or proposed_action.tool not in known_actions:
        return PolicyDecision(
            Decision.BLOCK,
            "No policy rule recognizes this action.",
            "default.unknown_action",
        )

    if proposed_action.tool in actions.get("forbidden", []):
        return PolicyDecision(
            Decision.BLOCK,
            "This action is explicitly forbidden by policy.",
            "action.forbidden",
        )

    if (
        security.get("block_unrequested_actions", True)
        and proposed_action.tool not in user_request.requested_actions
    ):
        risk_factors = (
            ("untrusted_content",)
            if provenance.influenced_by_untrusted_content
            else ()
        )
        return PolicyDecision(
            Decision.BLOCK,
            "The proposed action was not requested by the user.",
            "intent.action_not_requested",
            risk_factors,
        )

    validation_error = _validate_sensitive_action(proposed_action, limits, security)
    if validation_error is not None:
        return validation_error

    constraint_error = _validate_request_constraints(user_request, proposed_action)
    if constraint_error is not None:
        return constraint_error

    if proposed_action.tool in actions.get("confirmation_required", []):
        return PolicyDecision(
            Decision.CONFIRM,
            "This action requires explicit human confirmation.",
            "action.confirmation_required",
        )

    if (
        provenance.influenced_by_untrusted_content
        and security.get("confirm_if_untrusted_content", True)
    ):
        return PolicyDecision(
            Decision.CONFIRM,
            "Untrusted external content was provided to the agent; confirmation is required.",
            "provenance.untrusted_influence",
            ("untrusted_content",),
        )

    if proposed_action.tool in actions.get("allowed", []):
        return PolicyDecision(
            Decision.ALLOW,
            "The action is allowed by policy.",
            "action.allowed",
        )

    return PolicyDecision(
        Decision.BLOCK,
        "No policy rule authorizes this action.",
        "default.deny",
    )


def _validate_sensitive_action(
    action: ProposedAction,
    limits: dict[str, Any],
    security: dict[str, Any],
) -> PolicyDecision | None:
    sensitive_limits = {
        "refund_payment": "maximum_refund",
        "create_invoice": "maximum_invoice",
    }
    limit_name = sensitive_limits.get(action.tool)
    if limit_name is None:
        return None

    amount = _money(action.amount)
    if amount is None:
        return PolicyDecision(
            Decision.BLOCK,
            "A finite positive amount with at most two decimal places is required.",
            "limits.invalid_amount",
        )

    maximum_amount = limits.get(limit_name)
    maximum = _money(maximum_amount)
    if maximum is None:
        return PolicyDecision(
            Decision.BLOCK,
            "The policy does not define a valid amount limit.",
            "policy.invalid_amount_limit",
        )
    if amount > maximum:
        return PolicyDecision(
            Decision.BLOCK,
            f"The amount exceeds the configured limit of {maximum_amount:.2f}.",
            "limits.amount_exceeded",
        )

    allowed_currencies = limits.get("allowed_currencies", [])
    if not action.currency or action.currency not in allowed_currencies:
        return PolicyDecision(
            Decision.BLOCK,
            "The currency is not allowed by policy.",
            "limits.currency_not_allowed",
        )

    if not action.beneficiary:
        return PolicyDecision(
            Decision.BLOCK,
            "A beneficiary is required for this action.",
            "beneficiary.missing",
        )

    allowed_beneficiaries = limits.get("allowed_beneficiaries", [])
    if (
        not limits.get("allow_new_beneficiary", False)
        and action.beneficiary not in allowed_beneficiaries
    ):
        return PolicyDecision(
            Decision.BLOCK,
            "The beneficiary is not allowed by policy.",
            "beneficiary.not_allowed",
        )

    idempotent_actions = security.get("require_idempotency_for", [])
    if action.tool in idempotent_actions and not action.idempotency_key:
        return PolicyDecision(
            Decision.BLOCK,
            "An idempotency key is required for this action.",
            "idempotency.key_required",
        )

    return None


def _money(value: Any) -> Decimal | None:
    """Validate the USD/EUR amounts supported by this prototype, without rounding."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or amount <= 0:
            return None
        if amount != amount.quantize(Decimal("0.01")):
            return None
        return amount
    except InvalidOperation:
        return None


def _validate_request_constraints(
    request: UserRequest, action: ProposedAction
) -> PolicyDecision | None:
    constraints = request.constraints
    if action.tool == "read_invoice":
        if constraints and constraints.invoice_id is not None:
            if not constraints.invoice_id:
                return PolicyDecision(
                    Decision.BLOCK, "Select the invoice to read first.", "intent.missing_target"
                )
            if action.metadata.get("invoice_id") != constraints.invoice_id:
                return _intent_block("invoice_id", "The proposed invoice differs from the selected invoice.")
        return None

    if action.tool not in {"refund_payment", "create_invoice"}:
        return None
    if (
        constraints is None
        or _money(constraints.amount) is None
        or not constraints.currency
        or not constraints.beneficiary
    ):
        return PolicyDecision(
            Decision.BLOCK,
            "The request must specify the authorized amount, currency, and beneficiary.",
            "intent.missing_constraints",
        )
    if _money(action.amount) != _money(constraints.amount):
        return _intent_block("amount", "The proposed amount differs from the requested amount.")
    if action.currency != constraints.currency:
        return _intent_block("currency", "The proposed currency differs from the requested currency.")
    if action.beneficiary != constraints.beneficiary:
        return _intent_block("beneficiary", "The proposed beneficiary differs from the requested beneficiary.")

    if action.tool == "refund_payment":
        target_name = "capture_id"
        expected = constraints.capture_id
        actual = action.metadata.get(target_name)
    else:
        target_name = "recipient_email"
        expected = constraints.recipient_email
        # Same effective address as the PayPal adapter; an alias alone grants no rights.
        actual = str(action.metadata.get(target_name) or action.beneficiary or "")
        if action.metadata.get("send", False) and not constraints.send_invoice:
            return PolicyDecision(
                Decision.BLOCK,
                "Sending the invoice was not authorized by the user.",
                "intent.invoice_send_not_requested",
            )
    if not isinstance(expected, str) or not expected.strip():
        return PolicyDecision(
            Decision.BLOCK,
            f"The request must specify the authorized target: {target_name}.",
            "intent.missing_target",
        )
    if actual != expected:
        return _intent_block(target_name, "The proposed PayPal target differs from the selected target.")
    return None


def _intent_block(parameter: str, reason: str) -> PolicyDecision:
    return PolicyDecision(Decision.BLOCK, reason, f"intent.{parameter}_mismatch")
