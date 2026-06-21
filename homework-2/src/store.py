"""In-memory storage for support tickets.

The store owns all mutable ticket state. Routes reach state only through this
class — they never touch the underlying list. Mirrors the design used in
homework-1's ``TransactionStore``.
"""
from datetime import datetime, timezone

# Fields a client is allowed to change via update; everything else (id,
# created_at, classification, ...) is managed by the server.
UPDATABLE_FIELDS = {
    "customer_id", "customer_email", "customer_name", "subject", "description",
    "category", "priority", "status", "assigned_to", "tags", "metadata",
}


class TicketStore:
    def __init__(self):
        self._tickets = []

    # --- writes ---------------------------------------------------------
    def add(self, ticket):
        self._tickets.append(ticket)
        return ticket

    def update(self, ticket_id, changes):
        """Apply ``changes`` to a ticket. Returns the ticket, or None if absent."""
        ticket = self.get(ticket_id)
        if ticket is None:
            return None
        for key, value in changes.items():
            if key in UPDATABLE_FIELDS:
                ticket[key] = value
        ticket["updated_at"] = datetime.now(timezone.utc).isoformat()
        # Stamp resolved_at the first time a ticket reaches "resolved".
        if ticket["status"] == "resolved" and ticket["resolved_at"] is None:
            ticket["resolved_at"] = ticket["updated_at"]
        return ticket

    def set_classification(self, ticket_id, classification):
        """Store a classifier result and apply its category/priority."""
        ticket = self.get(ticket_id)
        if ticket is None:
            return None
        ticket["classification"] = classification
        ticket["category"] = classification["category"]
        ticket["priority"] = classification["priority"]
        ticket["updated_at"] = datetime.now(timezone.utc).isoformat()
        return ticket

    def delete(self, ticket_id):
        ticket = self.get(ticket_id)
        if ticket is None:
            return False
        self._tickets.remove(ticket)
        return True

    # --- reads ----------------------------------------------------------
    def all(self):
        return list(self._tickets)

    def get(self, ticket_id):
        return next((t for t in self._tickets if t["id"] == ticket_id), None)

    def filter(self, category=None, priority=None, status=None, assigned_to=None):
        results = []
        for ticket in self._tickets:
            if category is not None and ticket["category"] != category:
                continue
            if priority is not None and ticket["priority"] != priority:
                continue
            if status is not None and ticket["status"] != status:
                continue
            if assigned_to is not None and ticket["assigned_to"] != assigned_to:
                continue
            results.append(ticket)
        return results
