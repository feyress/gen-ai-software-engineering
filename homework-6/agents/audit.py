"""Append-only audit trail: one JSON line per status change.

Governed by specification.md sections C6 and C7. This module decides nothing
about a transaction; it records that a status changed, who changed it, and
which envelope carried the change. The file is only ever appended to, never
truncated or rewritten, so the trail of a run cannot be edited by a later one.
"""

from __future__ import annotations

import json
from pathlib import Path

from agents.envelope import mask_accounts, utc_now_iso

AUDIT_FILENAME = "audit-log.jsonl"


def audit_path(root: Path) -> Path:
    """Return the path of the audit log under `root`."""
    return Path(root) / "shared" / AUDIT_FILENAME


def record_event(
    root: Path,
    agent: str,
    transaction_id: str,
    outcome: str,
    message_id: str,
    detail: str | None = None,
) -> dict:
    """Append one audit event and return it.

    Callers must not put raw PII into `detail`: it is human-facing text that
    ends up in a log file. Any account-shaped token is masked here as a second
    line of defence, but a caller that passes a customer name or a transaction
    description has already leaked it.
    """
    event = {
        "timestamp": utc_now_iso(),
        "agent": agent,
        "transaction_id": transaction_id,
        "outcome": outcome,
        "message_id": message_id,
        "detail": mask_accounts(detail) if detail else None,
    }
    path = audit_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return event


def read_events(root: Path) -> list[dict]:
    """Return every recorded event, or an empty list when no run has written one."""
    path = audit_path(root)
    if not path.is_file():
        return []
    events: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events
