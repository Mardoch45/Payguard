from pathlib import Path

import pytest
import yaml

from guard.models import ProposedAction, ProvenanceContext, RequestConstraints, UserRequest
from guard.policy import evaluate_action, load_policy


PROJECT_ROOT = Path(__file__).parents[1]
POLICY = load_policy(PROJECT_ROOT / "policies" / "policy.yaml")
SCENARIO_FILES = (
    PROJECT_ROOT / "attacks" / "attacks.yaml",
    PROJECT_ROOT / "attacks" / "normal_cases.yaml",
)


def load_scenarios() -> list[dict]:
    scenarios: list[dict] = []
    for scenario_file in SCENARIO_FILES:
        loaded = yaml.safe_load(scenario_file.read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            raise ValueError(f"{scenario_file.name} must contain a list")
        scenarios.extend(loaded)
    return scenarios


SCENARIOS = load_scenarios()


@pytest.mark.parametrize(
    "scenario",
    SCENARIOS,
    ids=[scenario["id"] for scenario in SCENARIOS],
)
def test_scenario_matches_expected_decision(scenario: dict) -> None:
    action_data = scenario["proposed_action"]
    provenance_data = scenario["provenance"]
    result = evaluate_action(
        UserRequest(
            text=scenario["user_request"],
            requested_actions=frozenset(scenario["requested_actions"]),
            request_id=scenario["id"],
            constraints=RequestConstraints(**scenario["constraints"])
            if scenario.get("constraints") else None,
        ),
        ProposedAction(
            tool=action_data["tool"],
            amount=action_data.get("amount"),
            currency=action_data.get("currency"),
            beneficiary=action_data.get("beneficiary"),
            idempotency_key=action_data.get("idempotency_key"),
            metadata=dict(action_data.get("metadata") or {}),
        ),
        POLICY,
        ProvenanceContext(
            influenced_by_untrusted_content=provenance_data[
                "influenced_by_untrusted_content"
            ],
            untrusted_source_ids=tuple(
                provenance_data.get("untrusted_source_ids", [])
            ),
            injection_risk_score=provenance_data.get("injection_risk_score", 0.0),
        ),
    )

    assert result.decision == scenario["expected_decision"]
    assert result.rule_id == scenario["expected_rule"]
