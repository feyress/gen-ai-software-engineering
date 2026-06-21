"""Ticket construction — turning a validated payload into a stored record."""
import uuid
from datetime import datetime, timezone

# Default metadata when none is supplied. Keeps the stored shape consistent.
_DEFAULT_METADATA = {"source": "api", "browser": None, "device_type": None}


def _now():
    return datetime.now(timezone.utc).isoformat()


def build_ticket(payload):
    """Build a complete ticket dict from a *validated* create payload.

    Auto-generates ``id`` and timestamps; applies defaults for ``status``,
    ``priority``, ``tags`` and ``metadata``. Assumes the payload already passed
    ``validate_create``.
    """
    now = _now()
    metadata = {**_DEFAULT_METADATA, **(payload.get("metadata") or {})}
    return {
        "id": str(uuid.uuid4()),
        "customer_id": payload["customer_id"],
        "customer_email": payload["customer_email"],
        "customer_name": payload["customer_name"],
        "subject": payload["subject"],
        "description": payload["description"],
        "category": payload.get("category", "other"),
        "priority": payload.get("priority", "medium"),
        "status": payload.get("status", "new"),
        "created_at": now,
        "updated_at": now,
        "resolved_at": None,
        "assigned_to": payload.get("assigned_to"),
        "tags": list(payload.get("tags") or []),
        "metadata": metadata,
        # Populated by the classifier (Task 2); None until classified.
        "classification": None,
    }
