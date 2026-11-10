"""Scripted agent: replays a proposal written in advance.

This mode is only used for the offline demonstration (no LLM key and no
PayPal credentials). It does not replace measurement with a real agent:
executed scenarios must remain identifiable as scripted.
"""

from typing import Any, Mapping, Sequence

from agent.models import AgentProposal, Document
from guard.models import ProposedAction, ProvenanceContext, RequestConstraints, UserRequest


class ScriptedAgent:
    def __init__(self, proposal: AgentProposal) -> None:
        self._proposal = proposal

    @classmethod
    def from_scenario(cls, scenario: Mapping[str, Any]) -> "ScriptedAgent":
        action_data = scenario["proposed_action"]
        provenance_data = scenario["provenance"]

        request = UserRequest(
            text=scenario["user_request"],
            requested_actions=frozenset(scenario["requested_actions"]),
            request_id=scenario["id"],
            constraints=RequestConstraints(**scenario["constraints"])
            if scenario.get("constraints") else None,
        )
        action = ProposedAction(
            tool=action_data["tool"],
            amount=action_data.get("amount"),
            currency=action_data.get("currency"),
            beneficiary=action_data.get("beneficiary"),
            reason=scenario.get("external_text", ""),
            source_ids=tuple(provenance_data.get("untrusted_source_ids", [])),
            idempotency_key=action_data.get("idempotency_key"),
            metadata=dict(action_data.get("metadata") or {}),
        )
        provenance = ProvenanceContext(
            influenced_by_untrusted_content=provenance_data[
                "influenced_by_untrusted_content"
            ],
            untrusted_source_ids=tuple(
                provenance_data.get("untrusted_source_ids", [])
            ),
            injection_risk_score=provenance_data.get("injection_risk_score", 0.0),
        )

        return cls(
            AgentProposal(
                request=request,
                action=action,
                provenance=provenance,
                reasoning=scenario.get("external_text", ""),
                mode="scripted",
            )
        )

    def propose(
        self,
        request: UserRequest,
        documents: Sequence[Document],
    ) -> AgentProposal:
        return self._proposal
