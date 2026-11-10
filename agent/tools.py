"""Tool schemas exposed to the model.

``sources`` lets the agent explain the documents it cited. The security
provenance is established on the application side from the provided
documents. The idempotency key is never exposed: the proxy derives it
itself.
"""

SOURCES_SCHEMA = {
    "type": "array",
    "items": {"type": "string"},
    "description": "Identifiers of the documents that motivated this action.",
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_invoices",
            "description": "Lists the PayPal invoices of the account.",
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
            "description": "Reads the details of a PayPal invoice.",
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
            "description": "Creates a PayPal invoice for a given amount.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "exclusiveMinimum": 0},
                    "currency": {"type": "string"},
                    "beneficiary": {"type": "string"},
                    "recipient_email": {"type": "string"},
                    "item_name": {"type": "string"},
                    "reason": {"type": "string"},
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
            "description": "Refunds a captured payment on PayPal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "exclusiveMinimum": 0},
                    "currency": {"type": "string"},
                    "beneficiary": {"type": "string"},
                    "capture_id": {"type": "string"},
                    "reason": {"type": "string"},
                    "sources": SOURCES_SCHEMA,
                },
                "required": ["amount", "currency", "beneficiary", "sources"],
            },
        },
    },
]
