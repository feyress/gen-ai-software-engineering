"""Transaction construction — turning a validated payload into a stored record."""
import uuid
from datetime import datetime, timezone


def build_transaction(payload):
    """Build a complete transaction dict from a *validated* create payload.

    Auto-generates ``id`` and ``timestamp``; defaults ``status`` to ``completed``.
    Assumes the payload already passed ``validate_create``.
    """
    return {
        "id": str(uuid.uuid4()),
        "fromAccount": payload.get("fromAccount"),
        "toAccount": payload.get("toAccount"),
        "amount": float(payload["amount"]),
        "currency": payload["currency"],
        "type": payload["type"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": payload.get("status", "completed"),
    }
