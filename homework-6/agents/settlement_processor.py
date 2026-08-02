"""Decides the settled base-currency amount and closes the transaction.

Governed by specification.md sections C5 and D. Converts through the static FX
table and quantizes exactly once, at settlement, with ROUND_HALF_UP. TXN004 at
500.00 EUR and rate 1.080000 must settle to exactly '540.00' USD.
"""

from __future__ import annotations

import copy
from decimal import Decimal

from agents.envelope import (
    BASE_CURRENCY,
    FX_RATES_AS_OF,
    FX_TABLE,
    MessageType,
    Status,
    build_envelope,
    quantize_money,
    utc_now_iso,
)

AGENT_NAME = "settlement_processor"

REFERENCE_HEX_LENGTH = 8


def process_message(message: dict) -> dict:
    """Settle one cleared envelope and return the terminal settled envelope."""
    data = copy.deepcopy(message.get("data", {}))
    currency = data["currency"]
    rate = FX_TABLE[currency]
    settled = quantize_money(Decimal(data["amount"]) * rate, BASE_CURRENCY)

    data["status"] = Status.SETTLED
    data["base_currency"] = BASE_CURRENCY
    data["fx_rate"] = str(rate)
    data["fx_rate_as_of"] = FX_RATES_AS_OF
    data["settled_amount"] = str(settled)
    data["settled_at"] = utc_now_iso()
    data["settlement_reference"] = _reference(
        data["transaction_id"], message.get("message_id", "")
    )

    return build_envelope(
        source_agent=AGENT_NAME,
        target_agent="results",
        message_type=MessageType.RESULT,
        data=data,
    )


def _reference(transaction_id: str, message_id: str) -> str:
    """Derive the settlement reference from the envelope that carried the transaction.

    Deterministic for a given envelope, so a test that fixes `message_id` can
    reproduce the reference exactly.
    """
    digits = message_id.replace("-", "")[:REFERENCE_HEX_LENGTH].upper()
    return f"SET-{transaction_id}-{digits}"
