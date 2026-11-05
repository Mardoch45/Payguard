from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Decision(StrEnum):
    """Possible outcomes returned by the policy engine."""

    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    CONFIRM = "CONFIRM"


@dataclass(frozen=True)
class RequestConstraints:
    """Parameters authorized by the user/application, never by the model."""

    amount: float | None = None
    currency: str | None = None
    beneficiary: str | None = None
    invoice_id: str | None = None
    capture_id: str | None = None
    recipient_email: str | None = None
    send_invoice: bool = False


@dataclass(frozen=True)
class UserRequest:
    """Original user instruction and the actions it explicitly permits."""

    text: str
    requested_actions: frozenset[str]
    request_id: str
    constraints: RequestConstraints | None = None


@dataclass(frozen=True)
class ProposedAction:
    """Structured action proposed by the agent before execution."""

    tool: str
    amount: float | None = None
    currency: str | None = None
    beneficiary: str | None = None
    reason: str = ""
    source_ids: tuple[str, ...] = ()
    idempotency_key: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProvenanceContext:
    """Security context describing external influence on an action."""

    influenced_by_untrusted_content: bool = False
    untrusted_source_ids: tuple[str, ...] = ()
    injection_risk_score: float = 0.0


@dataclass(frozen=True)
class PolicyDecision:
    """Deterministic policy result returned to the execution proxy."""

    decision: Decision
    reason: str
    rule_id: str
    risk_factors: tuple[str, ...] = ()
