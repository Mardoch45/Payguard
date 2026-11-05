"""Adaptateur local : simule PayPal sans aucun appel réseau.

Utilisé par la démonstration hors-ligne et par les tests. Il enregistre
chaque action reçue, ce qui permet de prouver qu'une action bloquée par
la politique n'atteint jamais l'adaptateur.
"""

from typing import Any

from guard.models import ProposedAction


class FakePayPalAdapter:
    """Adaptateur déterministe, sans identifiants ni réseau."""

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
