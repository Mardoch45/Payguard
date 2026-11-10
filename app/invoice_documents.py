"""Load a user-chosen PayPal document before the LLM call."""

import json
from pathlib import Path
from typing import Any

from agent.models import AgentProposal, Document
from app.demo import Adapter, run_with_protection
from guard.idempotency import IdempotencyRegistry
from guard.models import ProposedAction, ProvenanceContext, RequestConstraints, UserRequest
from guard.provenance import SourceType


def load_invoice_document(
    invoice_id: str,
    policy: dict[str, Any],
    adapter: Adapter,
    registry: IdempotencyRegistry,
    audit_path: str | Path,
) -> Document:
    """Controlled read; the received content never becomes an authorization."""
    invoice_id = invoice_id.strip()
    if not invoice_id:
        raise ValueError("Set the Sandbox invoice identifier.")

    request = UserRequest(
        text=f"Load invoice {invoice_id} to provide it to the model.",
        requested_actions=frozenset({"read_invoice"}),
        request_id=f"invoice-context-{invoice_id}",
        constraints=RequestConstraints(invoice_id=invoice_id),
    )
    action = ProposedAction(
        tool="read_invoice",
        metadata={"invoice_id": invoice_id},
        source_ids=("consigne-utilisateur",),
    )
    outcome = run_with_protection(
        AgentProposal(request, action, ProvenanceContext(), mode="application"),
        policy,
        adapter,
        registry,
        audit_path,
    )
    if not outcome.executed:
        raise ValueError(f"Invoice read denied by policy: {outcome.policy_decision.reason}")

    result = outcome.result or {}
    if result.get("sandbox") is not True:
        raise ValueError("The invoice must come from PayPal Sandbox.")
    invoice = result.get("invoice")
    if not isinstance(invoice, dict) or invoice.get("id") != invoice_id:
        raise ValueError("PayPal did not return the selected invoice.")
    note = invoice.get("note")
    if note is not None and not isinstance(note, str):
        raise ValueError("The PayPal invoice note is invalid.")

    # Customer contact details are not needed for this workflow.
    content = {key: invoice.get(key) for key in (
        "id", "invoice_number", "status", "amount", "currency",
    )}
    content["note"] = note or ""
    return Document(
        source_id=f"paypal-invoice-{invoice_id}",
        source_type=SourceType.PAYPAL_DATA,
        text=json.dumps(content, ensure_ascii=False, indent=2),
    )
