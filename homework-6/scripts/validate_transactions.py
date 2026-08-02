#!/usr/bin/env python3
"""Dry-run the validator over the sample file without running the pipeline.

Reports every record's verdict as a table and exits non-zero when any record is
invalid, so the ``/validate-transactions`` skill can be used as a data check.

This lives in ``scripts/`` rather than as a ``__main__`` block inside
``agents/transaction_validator.py`` because ``agents.md`` section 4 forbids file
I/O and printing inside a pipeline agent: the agent stays a pure function of one
envelope to one envelope, and this is the thin shell around it.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents import transaction_validator  # noqa: E402
from agents.envelope import (  # noqa: E402
    MessageType,
    Status,
    build_envelope,
    mask_account,
)

COLUMNS = "  {:<8} {:<8} {:>14}  {:<22} {}"


def verdicts(records: list[dict]) -> list[dict]:
    """Return one verdict row per record by running the validator in isolation."""
    rows = []
    for record in records:
        payload = dict(record)
        payload["status"] = Status.RECEIVED
        envelope = build_envelope(
            source_agent="dry_run",
            target_agent="transaction_validator",
            message_type=MessageType.TRANSACTION,
            data=payload,
        )
        result = transaction_validator.process_message(envelope)["data"]
        rows.append(
            {
                "transaction_id": result.get("transaction_id") or "(none)",
                "status": result.get("status"),
                "amount": f"{record.get('amount')} {record.get('currency')}",
                "reason": result.get("reason") or "-",
                "reason_detail": result.get("reason_detail") or "",
                "destination": mask_account(record.get("destination_account", "")),
            }
        )
    return rows


def render(rows: list[dict]) -> str:
    """Return the verdict table and tallies as printable text."""
    valid = [row for row in rows if row["status"] == Status.VALIDATED]
    invalid = [row for row in rows if row["status"] != Status.VALIDATED]

    lines = [
        "Transaction validation dry run (no pipeline, no files written)",
        "",
        COLUMNS.format("id", "verdict", "amount", "reason", "detail"),
        COLUMNS.format("-" * 8, "-" * 8, "-" * 14, "-" * 22, "-" * 30),
    ]
    for row in rows:
        verdict = "valid" if row["status"] == Status.VALIDATED else "INVALID"
        lines.append(
            COLUMNS.format(
                row["transaction_id"],
                verdict,
                row["amount"],
                row["reason"],
                row["reason_detail"],
            )
        )

    lines += [
        "",
        f"total:   {len(rows)}",
        f"valid:   {len(valid)}",
        f"invalid: {len(invalid)}",
    ]
    if invalid:
        lines.append("")
        lines.append("rejection reasons:")
        for row in invalid:
            lines.append(
                f"  {row['transaction_id']}  {row['reason']}  ({row['reason_detail']})"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=PROJECT_ROOT / "sample-transactions.json",
        help="Transaction file to validate (default: sample-transactions.json).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Accepted for symmetry with the skill; this script never writes.",
    )
    args = parser.parse_args(argv)

    try:
        records = json.loads(args.source.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"error: {args.source} not found", file=sys.stderr)
        return 2
    except json.JSONDecodeError as error:
        print(f"error: {args.source} is not valid JSON ({error})", file=sys.stderr)
        return 2

    rows = verdicts(records)
    print(render(rows))
    return 1 if any(row["status"] != Status.VALIDATED for row in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
