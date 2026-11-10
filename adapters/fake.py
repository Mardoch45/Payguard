"""Local adapter: simulates PayPal without any network call.

Used by the offline demonstration and by the tests. It records every
action it receives, which makes it possible to prove that an action
blocked by the policy never reaches the adapter.
"""

from typing import Any

from guard.models import ProposedAction


class FakePayPalAdapter:
    """Deterministic adapter with no credentials and no network."""

    def __init__(self) -> None:
        self.calls: list[ProposedAction] = []

    def execute(self, action: ProposedAction) -> dict[str, Any]:
        self.calls.append(action)
        result: dict[str, Any] = {
            "tool": action.tool,
            "status": "SIMULATED",
            "sandbox": True,
            "simulated": True,
            "id": f"FAKE-{len(self.calls):04d}",
        }
        if action.amount is not None:
            result["amount"] = f"{action.amount:.2f}"
        if action.currency:
            result["currency"] = action.currency
        if action.beneficiary:
            result["beneficiary"] = action.beneficiary
        return result
