"""Exécution comparée : avec et sans le garde-fou PayGuard."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from agent.models import AgentProposal
from guard.execution import ExecutionOutcome, process_action
from guard.idempotency import IdempotencyRegistry


class Adapter(Protocol):
    def execute(self, action: Any) -> dict[str, Any]: ...


@dataclass(frozen=True)
class UnprotectedResult:
    dry_run: bool
    executed: bool
    would_call: str
    result: dict[str, Any] | None = None


def run_without_protection(
    proposal: AgentProposal,
    adapter: Adapter,
    *,
    dry_run: bool = True,
) -> UnprotectedResult:
    """Reproduit l'agent branché directement sur PayPal, sans garde-fou."""

    tool = proposal.action.tool
    if dry_run:
        return UnprotectedResult(
            dry_run=True, executed=False, would_call=tool, result=None
        )
    return UnprotectedResult(
        dry_run=False,
        executed=True,
        would_call=tool,
        result=adapter.execute(proposal.action),
    )


def run_with_protection(
    proposal: AgentProposal,
    policy: dict[str, Any],
    adapter: Adapter,
    registry: IdempotencyRegistry,
    audit_path: str | Path,
    *,
    human_confirmed: bool = False,
) -> ExecutionOutcome:
    """Fait passer la même action par la politique puis le proxy d'exécution."""

    return process_action(
        proposal.request,
        proposal.action,
        policy,
        proposal.provenance,
        adapter,
        registry,
        audit_path,
        human_confirmed=human_confirmed,
    )
