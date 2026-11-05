from dataclasses import dataclass
from enum import StrEnum

from guard.models import ProvenanceContext


class SourceType(StrEnum):
    """Origin categories used to separate instructions from external data."""

    USER = "USER"
    SYSTEM = "SYSTEM"
    PAYPAL_DATA = "PAYPAL_DATA"
    THIRD_PARTY = "THIRD_PARTY"


@dataclass(frozen=True)
class DataSource:
    """A piece of information that contributed to a proposed action."""

    source_id: str
    source_type: SourceType

    @property
    def is_trusted_for_authorization(self) -> bool:
        return self.source_type in {SourceType.USER, SourceType.SYSTEM}


def build_provenance_context(
    sources: tuple[DataSource, ...],
    injection_risk_score: float = 0.0,
) -> ProvenanceContext:
    """Build the policy context while treating external sources as untrusted."""

    if not 0.0 <= injection_risk_score <= 1.0:
        raise ValueError("Injection risk score must be between 0.0 and 1.0")

    untrusted_source_ids = tuple(
        source.source_id
        for source in sources
        if not source.is_trusted_for_authorization
    )
    return ProvenanceContext(
        influenced_by_untrusted_content=bool(untrusted_source_ids),
        untrusted_source_ids=untrusted_source_ids,
        injection_risk_score=injection_risk_score,
    )
