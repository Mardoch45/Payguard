from collections import Counter
from pathlib import Path
from time import perf_counter
from typing import Any

import yaml

from guard.models import ProposedAction, ProvenanceContext, RequestConstraints, UserRequest
from guard.policy import evaluate_action, load_policy


PROJECT_ROOT = Path(__file__).parents[1]


def load_scenarios(path: str | Path) -> list[dict[str, Any]]:
    scenarios = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(scenarios, list):
        raise ValueError("Scenario file must contain a list")
    return scenarios


def run_scenario(scenario: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    action_data = scenario["proposed_action"]
    provenance_data = scenario["provenance"]
    started_at = perf_counter()
    decision = evaluate_action(
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
        policy,
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
    elapsed_ms = (perf_counter() - started_at) * 1000
    return {
        "id": scenario["id"],
        "expected_decision": scenario["expected_decision"],
        "actual_decision": decision.decision.value,
        "expected_rule": scenario["expected_rule"],
        "actual_rule": decision.rule_id,
        "passed": (
            decision.decision.value == scenario["expected_decision"]
            and decision.rule_id == scenario["expected_rule"]
        ),
        "elapsed_ms": elapsed_ms,
    }


def main() -> None:
    policy = load_policy(PROJECT_ROOT / "policies" / "policy.yaml")
    attack_scenarios = load_scenarios(PROJECT_ROOT / "attacks" / "attacks.yaml")
    normal_scenarios = load_scenarios(
        PROJECT_ROOT / "attacks" / "normal_cases.yaml"
    )

    attack_results = [run_scenario(scenario, policy) for scenario in attack_scenarios]
    normal_results = [run_scenario(scenario, policy) for scenario in normal_scenarios]
    all_results = attack_results + normal_results

    attacks_blocked = sum(
        result["actual_decision"] == "BLOCK" for result in attack_results
    )
    false_positives = sum(
        result["actual_decision"] == "BLOCK" for result in normal_results
    )
    legitimate_successes = sum(result["passed"] for result in normal_results)
    mean_latency = sum(result["elapsed_ms"] for result in all_results) / len(
        all_results
    )
    decision_counts = Counter(
        result["actual_decision"] for result in all_results
    )

    print("PayGuard evaluation")
    print(f"Policy version: {policy.get('version', 'unknown')}")
    print(f"Scenarios: {len(all_results)}")
    print(
        f"Attacks blocked: {attacks_blocked}/{len(attack_results)} "
        f"({attacks_blocked / len(attack_results):.1%})"
    )
    print(
        f"False positives: {false_positives}/{len(normal_results)} "
        f"({false_positives / len(normal_results):.1%})"
    )
    print(
        f"Legitimate scenarios correct: {legitimate_successes}/"
        f"{len(normal_results)} ({legitimate_successes / len(normal_results):.1%})"
    )
    print(f"Mean policy latency: {mean_latency:.3f} ms")
    print(f"Decisions: {dict(decision_counts)}")

    failed_results = [result for result in all_results if not result["passed"]]
    if failed_results:
        print("Failures:")
        for result in failed_results:
            print(
                f"- {result['id']}: expected "
                f"{result['expected_decision']}/{result['expected_rule']}, got "
                f"{result['actual_decision']}/{result['actual_rule']}"
            )
        raise SystemExit(1)


if __name__ == "__main__":
    main()
