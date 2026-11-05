"""Schémas d'outils exposés au modèle.

``sources`` permet à l'agent d'expliquer les documents cités. La provenance
de sécurité est établie côté application à partir des documents fournis.
"""

SOURCES_SCHEMA = {
    "type": "array",
    "items": {"type": "string"},
    "description": "Identifiants des documents ayant motivé cette action.",
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_invoices",
            "description": "Liste les factures PayPal du compte.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_size": {"type": "integer", "minimum": 1, "maximum": 50},
                    "sources": SOURCES_SCHEMA,
                },
                "required": ["sources"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_invoice",
            "description": "Lit le détail d'une facture PayPal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_id": {"type": "string"},
                    "sources": SOURCES_SCHEMA,
                },
                "required": ["invoice_id", "sources"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_invoice",
            "description": "Crée une facture PayPal pour un montant donné.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "exclusiveMinimum": 0},
                    "currency": {"type": "string"},
                    "beneficiary": {"type": "string"},
                    "recipient_email": {"type": "string"},
                    "item_name": {"type": "string"},
                    "reason": {"type": "string"},
                    "idempotency_key": {"type": "string"},
                    "sources": SOURCES_SCHEMA,
                },
                "required": ["amount", "currency", "beneficiary", "sources"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "refund_payment",
            "description": "Rembourse un paiement capturé sur PayPal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "exclusiveMinimum": 0},
                    "currency": {"type": "string"},
                    "beneficiary": {"type": "string"},
                    "capture_id": {"type": "string"},
                    "reason": {"type": "string"},
                    "idempotency_key": {"type": "string"},
                    "sources": SOURCES_SCHEMA,
                },
                "required": ["amount", "currency", "beneficiary", "sources"],
            },
        },
    },
]
