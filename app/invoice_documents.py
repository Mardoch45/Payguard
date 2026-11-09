"""Charge un document PayPal choisi par l'utilisateur avant l'appel au LLM."""

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
    """Lecture contrôlée ; le contenu reçu ne devient jamais une autorisation."""
    invoice_id = invoice_id.strip()
    if not invoice_id:
        raise ValueError("Renseigne l'identifiant de la facture Sandbox.")

    request = UserRequest(
        text=f"Charge la facture {invoice_id} pour la fournir au modèle.",
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
        raise ValueError(f"Lecture de la facture refusée : {outcome.policy_decision.reason}")

    result = outcome.result or {}
    if result.get("sandbox") is not True:
        raise ValueError("La facture doit provenir de PayPal Sandbox.")
    invoice = result.get("invoice")
    if not isinstance(invoice, dict) or invoice.get("id") != invoice_id:
        raise ValueError("PayPal n'a pas renvoyé la facture sélectionnée.")
    note = invoice.get("note")
    if note is not None and not isinstance(note, str):
        raise ValueError("La note de la facture PayPal est invalide.")

    # Les coordonnées du client ne sont pas nécessaires à ce parcours.
    content = {key: invoice.get(key) for key in (
        "id", "invoice_number", "status", "amount", "currency",
    )}
    content["note"] = note or ""
    return Document(
        source_id=f"paypal-invoice-{invoice_id}",
        source_type=SourceType.PAYPAL_DATA,
        text=json.dumps(content, ensure_ascii=False, indent=2),
    )
