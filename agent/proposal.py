import hashlib
import json
from typing import Any, Mapping, Sequence

from agent.models import Document
from guard.models import ProposedAction, ProvenanceContext, UserRequest
from guard.provenance import build_provenance_context


def build_action(
    tool: str,
    arguments: Mapping[str, Any],
    request: UserRequest,
) -> ProposedAction:
    """Traduit les arguments d'un appel d'outil en action structurée."""

    metadata = {
        key: str(arguments[key])
        for key in ("invoice_id", "capture_id", "recipient_email", "item_name")
        if arguments.get(key)
    }

    sources = arguments.get("sources") or []
    return ProposedAction(
        tool=tool,
        amount=_as_amount(arguments.get("amount")),
        currency=_as_text(arguments.get("currency")),
        beneficiary=_as_text(arguments.get("beneficiary")),
        reason=_as_text(arguments.get("reason")) or "",
        source_ids=tuple(str(source) for source in sources),
        idempotency_key=_as_text(arguments.get("idempotency_key"))
        or derive_idempotency_key(request, tool, arguments),
        metadata=metadata,
    )


def build_provenance(
    cited_source_ids: Sequence[str],
    documents: Sequence[Document],
) -> ProvenanceContext:
    """Établit l'exposition externe à partir des documents fournis au modèle.

    Les citations restent explicatives : le modèle ne peut pas masquer un
    document externe reçu en citant seulement la consigne de l'utilisateur.
    La présence d'une source externe indique une influence possible, pas
    une preuve que le modèle a obéi à son contenu.
    """

    return build_provenance_context(
        tuple(document.as_source() for document in documents)
    )


def derive_idempotency_key(
    request: UserRequest,
    tool: str,
    arguments: Mapping[str, Any],
) -> str:
    """Clé déterministe : rejouer la même demande ne rappelle pas PayPal."""

    material = json.dumps(
        {
            "request_id": request.request_id,
            "tool": tool,
            **{
                key: arguments.get(key)
                for key in ("amount", "currency", "beneficiary", "invoice_id", "capture_id")
            },
        },
        sort_keys=True,
        default=str,
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]
    return f"{request.request_id}-{digest}"


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
