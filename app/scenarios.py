from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml

from guard.models import RequestConstraints

PROJECT_ROOT = Path(__file__).parents[1]
SCENARIOS_DIR = PROJECT_ROOT / "attacks"

SCENARIO_FILES = (
    ("attacks.yaml", "attaque"),
    ("normal_cases.yaml", "cas normal"),
)


@dataclass(frozen=True)
class Scenario:
    id: str
    kind: str
    category: str
    user_request: str
    requested_actions: tuple[str, ...]
    external_text: str
    proposed_action: dict[str, Any]
    provenance: dict[str, Any]
    expected_decision: str
    expected_rule: str
    constraints: RequestConstraints | None = None


def load_all_scenarios() -> list[Scenario]:
    scenarios: list[Scenario] = []
    for filename, kind in SCENARIO_FILES:
        scenarios.extend(load_scenarios(SCENARIOS_DIR / filename, kind))
    return scenarios


def load_scenarios(path: str | Path, kind: str) -> list[Scenario]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} doit contenir une liste de scénarios")

    return [
        Scenario(
            id=item["id"],
            kind=kind,
            category=item["category"],
            user_request=item["user_request"],
            requested_actions=tuple(item["requested_actions"]),
            external_text=item.get("external_text", ""),
            proposed_action=item["proposed_action"],
            provenance=item["provenance"],
            expected_decision=item["expected_decision"],
            expected_rule=item["expected_rule"],
            constraints=RequestConstraints(**item["constraints"])
            if item.get("constraints") else None,
        )
        for item in data
    ]


def prepare_sandbox_scenario(scenario: Scenario, selected_ids: dict[str, str]) -> Scenario:
    """Bind user-selected targets before the model proposes an action.

    Only scripted targets matching their original authorization are remapped.
    A tampered scripted target is kept so the guard can detect the mismatch.
    Empty inputs remove local fixtures: fake IDs must not authorize a real call.
    """
    original = scenario.constraints or RequestConstraints()
    updates: dict[str, str | None] = {}
    if "read_invoice" in scenario.requested_actions:
        updates["invoice_id"] = selected_ids.get("invoice_id") or None
        if not updates["invoice_id"] and original.invoice_id:
            # Keep the specific-read constraint required even without a selection.
            updates["invoice_id"] = ""
    if "refund_payment" in scenario.requested_actions:
        updates["capture_id"] = selected_ids.get("capture_id") or None
    if "create_invoice" in scenario.requested_actions:
        updates["recipient_email"] = selected_ids.get("recipient_email") or None
    constraints = replace(original, **updates)
    action = {**scenario.proposed_action}
    metadata = dict(action.get("metadata") or {})
    for name, selected in updates.items():
        if metadata.get(name) == getattr(original, name):
            if selected:
                metadata[name] = selected
            else:
                metadata.pop(name, None)
    action["metadata"] = metadata
    text = scenario.user_request
    if original.invoice_id and updates.get("invoice_id"):
        text = text.replace(original.invoice_id, updates["invoice_id"])
    return replace(scenario, user_request=text, proposed_action=action, constraints=constraints)
