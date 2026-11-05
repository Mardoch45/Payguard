from dataclasses import dataclass

from guard.models import ProposedAction, ProvenanceContext, UserRequest
from guard.provenance import DataSource, SourceType


@dataclass(frozen=True)
class Document:
    """Texte lu par l'agent, étiqueté par sa provenance."""

    source_id: str
    source_type: SourceType
    text: str

    @property
    def is_trusted(self) -> bool:
        return self.as_source().is_trusted_for_authorization

    def as_source(self) -> DataSource:
        return DataSource(self.source_id, self.source_type)


@dataclass(frozen=True)
class AgentProposal:
    """Action proposée par l'agent, avant toute décision de PayGuard."""

    request: UserRequest
    action: ProposedAction
    provenance: ProvenanceContext
    reasoning: str = ""
    mode: str = "llm"
