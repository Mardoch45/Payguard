from dataclasses import dataclass

from guard.models import ProposedAction, ProvenanceContext, UserRequest
from guard.provenance import DataSource, SourceType


@dataclass(frozen=True)
class Document:
    """Text read by the agent, labeled with its provenance."""

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
    """Action proposed by the agent, before any PayGuard decision."""

    request: UserRequest
    action: ProposedAction
    provenance: ProvenanceContext
    reasoning: str = ""
    mode: str = "llm"
