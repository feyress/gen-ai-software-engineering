"""Read side over shared/results/, shared by reporting, the integrator and MCP.

Governed by specification.md sections C8 and D. All reads go through
agents.mailbox so directory scanning and the pipeline-summary.json exclusion
live in one place. A transaction that was never processed is reported as None:
`status` is a closed set, so a missing result may not be answered with an
invented member.
"""

from __future__ import annotations

import re
from pathlib import Path

from agents import mailbox
from agents.envelope import mask_account

# A transaction id becomes a file name, so it may not carry a path.
_SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")

PROJECTION_FIELDS: tuple[str, ...] = (
    "transaction_id",
    "status",
    "risk_score",
    "risk_level",
    "reason",
    "settled_amount",
)


def results_dir(root: Path) -> Path:
    """Return the results directory under `root`."""
    return mailbox.shared_root(root) / "results"


def get_transaction(root: Path, transaction_id: str) -> dict | None:
    """Return the terminal envelope for `transaction_id`, or None if there is none."""
    if not transaction_id or not _SAFE_ID.match(transaction_id):
        return None
    path = results_dir(root) / f"{transaction_id}.json"
    if not path.is_file():
        return None
    return mailbox.read_message(path)


def list_results(root: Path) -> list[dict]:
    """Return every terminal envelope, sorted by transaction id."""
    envelopes = [
        mailbox.read_message(path) for path in mailbox.list_messages(results_dir(root))
    ]
    return sorted(
        envelopes, key=lambda envelope: envelope.get("data", {}).get("transaction_id", "")
    )


def latest_summary(root: Path) -> dict | None:
    """Return the parsed pipeline summary, or None when the pipeline has not run."""
    path = results_dir(root) / mailbox.SUMMARY_FILENAME
    if not path.is_file():
        return None
    return mailbox.read_message(path)


def status_of(root: Path, transaction_id: str) -> dict | None:
    """Return a compact projection of one result, or None when it does not exist.

    Fields a transaction never acquired — a risk score it was rejected before
    reaching, a settled amount it was held before earning — are None. The
    projection deliberately carries no account number; anything account-shaped
    that does reach it is masked.
    """
    envelope = get_transaction(root, transaction_id)
    if envelope is None:
        return None
    data = envelope.get("data", {})
    return {field: _safe(field, data.get(field)) for field in PROJECTION_FIELDS}


def _safe(field: str, value: object) -> object:
    """Mask a value whose field name marks it as an account number."""
    if field.endswith("_account") and isinstance(value, str):
        return mask_account(value)
    return value
