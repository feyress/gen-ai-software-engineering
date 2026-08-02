"""Decides whether a raw transaction is well formed enough to be scored.

Governed by specification.md sections C3 and C4. The five checks run in a fixed
order and the first failure wins, so exactly one `reason` is ever emitted.
Rejection is terminal: TXN006 is stopped here with `invalid_currency` and
TXN007 with `non_positive_amount`, and neither reaches the fraud detector.
"""

from __future__ import annotations

import copy
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from agents.envelope import (
    CURRENCY_ALLOW_LIST,
    MINOR_UNITS,
    MessageType,
    Reason,
    Status,
    build_envelope,
)

AGENT_NAME = "transaction_validator"

REQUIRED_FIELDS: tuple[str, ...] = (
    "transaction_id",
    "timestamp",
    "source_account",
    "destination_account",
    "amount",
    "currency",
    "transaction_type",
)

# [ASSUMED] specification.md C4: at most fifteen integer digits and six decimal
# places. A JSON number never matches, which is deliberate — coercing one would
# route it through float.
AMOUNT_PATTERN = re.compile(r"^-?\d{1,15}(\.\d{1,6})?$")

CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


def process_message(message: dict) -> dict:
    """Validate one received envelope and return a new validated or rejected one."""
    data = copy.deepcopy(message.get("data", {}))
    failure = _first_failure(data)
    if failure is not None:
        reason, detail = failure
        return _rejected(data, reason, detail)
    data["status"] = Status.VALIDATED
    return build_envelope(
        source_agent=AGENT_NAME,
        target_agent="fraud_detector",
        message_type=MessageType.TRANSACTION,
        data=data,
    )


def _first_failure(data: dict) -> tuple[str, str] | None:
    """Return the first `(reason, reason_detail)` the record trips, or None."""
    missing = _missing_field(data)
    if missing is not None:
        return Reason.MISSING_FIELD, f"field '{missing}' is missing or unusable"

    amount = data.get("amount")
    if not isinstance(amount, str) or not AMOUNT_PATTERN.match(amount):
        return (
            Reason.MALFORMED_AMOUNT,
            "amount must be a decimal string such as '1500.00'",
        )

    try:
        parsed = Decimal(amount)
    except InvalidOperation:
        return Reason.MALFORMED_AMOUNT, "amount could not be parsed as a decimal"
    if parsed <= 0:
        return Reason.NON_POSITIVE_AMOUNT, "amount must be greater than zero"

    currency = data.get("currency")
    if not CURRENCY_PATTERN.match(currency) or currency not in CURRENCY_ALLOW_LIST:
        return (
            Reason.INVALID_CURRENCY,
            f"currency '{currency}' is not in the ISO 4217 allow-list",
        )

    scale = -parsed.as_tuple().exponent
    minor_unit = MINOR_UNITS[currency]
    if scale > minor_unit:
        return (
            Reason.MALFORMED_AMOUNT,
            f"amount has {scale} decimal places, {currency} allows {minor_unit}",
        )
    return None


def _missing_field(data: dict) -> str | None:
    """Return the first required field that is absent, empty or unusable."""
    for field in REQUIRED_FIELDS:
        value = data.get(field)
        if value is None:
            return field
        if field == "amount":
            # Amount type and format are checked separately: they carry their
            # own reasons, malformed_amount and non_positive_amount.
            if isinstance(value, str) and not value.strip():
                return field
            continue
        if not isinstance(value, str) or not value.strip():
            return field
        if field == "timestamp" and not _is_iso_timestamp(value):
            return field
    return None


def _is_iso_timestamp(value: str) -> bool:
    """Return True when `value` parses as an ISO 8601 timestamp."""
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _rejected(data: dict, reason: str, detail: str) -> dict:
    """Build the terminal rejected envelope for a failed check."""
    data = dict(data)
    data["status"] = Status.REJECTED
    data["reason"] = reason
    data["reason_detail"] = detail
    return build_envelope(
        source_agent=AGENT_NAME,
        target_agent="results",
        message_type=MessageType.RESULT,
        data=data,
    )
