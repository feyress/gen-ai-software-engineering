"""Aggregates the terminal results of a run into the pipeline summary.

Governed by specification.md sections B5, C7 and D. For the sample data this
reports 8 transactions, counts of settled 4, held 2, rejected 2, blocked 0, and
a settled_total_base of '15239.99' USD. The module does no file I/O: the caller
writes shared/results/pipeline-summary.json.
"""

from __future__ import annotations

from decimal import Decimal

from agents.envelope import (
    BASE_CURRENCY,
    MessageType,
    Status,
    build_envelope,
    mask_accounts,
    quantize_money,
    utc_now_iso,
)

AGENT_NAME = "reporting_agent"

EXCEPTION_STATUSES: tuple[str, ...] = (Status.REJECTED, Status.HELD, Status.BLOCKED)

ZERO = Decimal("0")


def build_summary(results: list[dict]) -> dict:
    """Aggregate terminal envelopes into the summary payload.

    Totals are summed per original currency before any conversion, so two
    currencies never meet inside one arithmetic expression. Nothing
    account-shaped or customer-authored is carried into the payload.
    """
    counts_by_status: dict[str, int] = {
        Status.REJECTED: 0,
        Status.HELD: 0,
        Status.BLOCKED: 0,
        Status.SETTLED: 0,
    }
    totals_by_currency: dict[str, Decimal] = {}
    total_base = ZERO
    exceptions: list[dict] = []

    for envelope in results:
        data = envelope.get("data", {})
        status = data.get("status")
        counts_by_status[status] = counts_by_status.get(status, 0) + 1

        if status == Status.SETTLED:
            currency = data["currency"]
            totals_by_currency[currency] = totals_by_currency.get(
                currency, ZERO
            ) + Decimal(data["amount"])
            total_base += Decimal(data["settled_amount"])
        elif status in EXCEPTION_STATUSES:
            exceptions.append(_exception_entry(data))

    return {
        "generated_at": utc_now_iso(),
        "total_transactions": len(results),
        "counts_by_status": counts_by_status,
        "settled_totals_by_currency": {
            currency: str(quantize_money(total, currency))
            for currency, total in sorted(totals_by_currency.items())
        },
        "settled_total_base": str(quantize_money(total_base, BASE_CURRENCY)),
        "exceptions": sorted(exceptions, key=lambda entry: entry["transaction_id"]),
    }


def process_message(message: dict) -> dict:
    """Wrap the summary built from `message['data']['results']` in a summary envelope."""
    results = message.get("data", {}).get("results", [])
    return build_envelope(
        source_agent=AGENT_NAME,
        target_agent="results",
        message_type=MessageType.SUMMARY,
        data=build_summary(results),
    )


def _exception_entry(data: dict) -> dict:
    """Describe one non-settled outcome for a human reader, with accounts masked."""
    detail = data.get("reason_detail")
    return {
        "transaction_id": data.get("transaction_id"),
        "status": data.get("status"),
        "reason": data.get("reason"),
        "reason_detail": mask_accounts(detail) if detail else None,
    }
