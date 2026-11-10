import json
from dataclasses import replace
from typing import Any, Mapping, Sequence

from agent.models import Document
from guard.idempotency import derive_idempotency_key
from guard.models import ProposedAction, ProvenanceContext, UserRequest
from guard.provenance import build_provenance_context


def build_action(
    tool: str,
    arguments: Mapping[str, Any],
    request: UserRequest,
) -> ProposedAction:
    """Translate a tool-call's arguments into a structured action.

    The idempotency key is always derived on the application side: the model
    can neither choose it nor omit it to bypass anti-replay.
    """

    metadata = {
        key: str(arguments[key])
        for key in ("invoice_id", "capture_id", "recipient_email", "item_name")
        if arguments.get(key)
    }

    sources = arguments.get("sources") or []
    action = ProposedAction(
        tool=tool,
        amount=_as_amount(arguments.get("amount")),
        currency=_as_text(arguments.get("currency")),
        beneficiary=_as_text(arguments.get("beneficiary")),
        reason=_as_text(arguments.get("reason")) or "",
        source_ids=tuple(str(source) for source in sources),
        metadata=metadata,
    )
    return replace(
        action, idempotency_key=derive_idempotency_key(request, action)
    )


def build_provenance(
    cited_source_ids: Sequence[str],
    documents: Sequence[Document],
) -> ProvenanceContext:
    """Compute external exposure from the documents provided to the model.

    Citations remain explanatory: the model cannot hide an external document
    it received by citing only the user's instruction. The presence of an
    external source indicates possible influence, not proof that the model
    obeyed its content.
    """

    return build_provenance_context(
        tuple(document.as_source() for document in documents)
    )


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _as_amount(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
