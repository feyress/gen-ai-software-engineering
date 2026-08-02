"""Shared kernel: closed constant sets, money tables, time, masking, envelopes.

Governed by specification.md sections C1, C2, C3, C5 and C7. This module decides
nothing about a transaction; it owns the single definition of every value more
than one agent needs, so that no agent imports a downstream agent to reach a
constant. It performs no file I/O, no logging, and imports no other project
module, which keeps the import graph acyclic.
"""

from __future__ import annotations

import copy
import re
import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Final


class Status:
    """The closed `status` set of specification.md C3.

    Plain `str` constants rather than an `Enum`: a status is written into the
    envelope, serialised to JSON and used as a set key, and `Enum` members hash
    by member name rather than by value, which would silently break membership
    tests against `TERMINAL_STATUSES`.
    """

    RECEIVED: Final[str] = "received"
    VALIDATED: Final[str] = "validated"
    REJECTED: Final[str] = "rejected"
    RISK_SCORED: Final[str] = "risk_scored"
    HELD: Final[str] = "held"
    CLEARED: Final[str] = "cleared"
    BLOCKED: Final[str] = "blocked"
    SETTLED: Final[str] = "settled"


class Reason:
    """The closed `reason` set of specification.md C3."""

    MISSING_FIELD: Final[str] = "missing_field"
    INVALID_CURRENCY: Final[str] = "invalid_currency"
    NON_POSITIVE_AMOUNT: Final[str] = "non_positive_amount"
    MALFORMED_AMOUNT: Final[str] = "malformed_amount"
    SANCTIONED_COUNTERPARTY: Final[str] = "sanctioned_counterparty"
    MANUAL_REVIEW_REQUIRED: Final[str] = "manual_review_required"


class RiskLevel:
    """The closed `risk_level` set of specification.md C3."""

    LOW: Final[str] = "low"
    MEDIUM: Final[str] = "medium"
    HIGH: Final[str] = "high"


class MessageType:
    """The closed `message_type` set of specification.md C3."""

    TRANSACTION: Final[str] = "transaction"
    RESULT: Final[str] = "result"
    SUMMARY: Final[str] = "summary"


STATUS: Final[frozenset[str]] = frozenset(
    {
        Status.RECEIVED,
        Status.VALIDATED,
        Status.REJECTED,
        Status.RISK_SCORED,
        Status.HELD,
        Status.CLEARED,
        Status.BLOCKED,
        Status.SETTLED,
    }
)

REASON: Final[frozenset[str]] = frozenset(
    {
        Reason.MISSING_FIELD,
        Reason.INVALID_CURRENCY,
        Reason.NON_POSITIVE_AMOUNT,
        Reason.MALFORMED_AMOUNT,
        Reason.SANCTIONED_COUNTERPARTY,
        Reason.MANUAL_REVIEW_REQUIRED,
    }
)

RISK_LEVEL: Final[frozenset[str]] = frozenset(
    {RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH}
)

MESSAGE_TYPE: Final[frozenset[str]] = frozenset(
    {MessageType.TRANSACTION, MessageType.RESULT, MessageType.SUMMARY}
)

# `held` is terminal for this batch: the system parks it for a human reviewer
# and never resumes it, so it lands in shared/results/ like a final outcome.
TERMINAL_STATUSES: Final[frozenset[str]] = frozenset(
    {Status.REJECTED, Status.BLOCKED, Status.SETTLED, Status.HELD}
)

CURRENCY_ALLOW_LIST: Final[frozenset[str]] = frozenset({"USD", "EUR", "GBP", "JPY"})

MINOR_UNITS: Final[dict[str, int]] = {"USD": 2, "EUR": 2, "GBP": 2, "JPY": 0}

BASE_CURRENCY: Final[str] = "USD"

DOMESTIC_COUNTRY: Final[str] = "US"

# [ASSUMED] Static test rates, specification.md C5. Every rate is built from a
# string so no binary float ever reaches an amount.
FX_TABLE: Final[dict[str, Decimal]] = {
    "USD": Decimal("1.000000"),
    "EUR": Decimal("1.080000"),
    "GBP": Decimal("1.270000"),
    "JPY": Decimal("0.006700"),
}

FX_RATES_AS_OF: Final[str] = "2026-03-16"

_MASK: Final[str] = "****"

# An account number as it appears in this dataset: an alphabetic prefix, a
# hyphen, then digits. Used to scrub free text before it is written anywhere a
# human reads it.
_ACCOUNT_PATTERN: Final[re.Pattern[str]] = re.compile(r"\b[A-Za-z]{2,}-\d{2,}\b")


def utc_now_iso() -> str:
    """Return the current UTC time as ISO 8601 with a `Z` suffix, second precision."""
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return now.isoformat().replace("+00:00", "Z")


def mask_account(account: str) -> str:
    """Return an account number with its middle replaced by exactly four asterisks.

    `ACC-1001` becomes `ACC-****01`. Everything up to and including the final
    hyphen is kept along with the last two characters; the asterisk run is a
    fixed length so the mask does not leak the original one.
    """
    if not isinstance(account, str) or not account:
        return _MASK
    prefix, separator, tail = account.rpartition("-")
    head = prefix + separator
    if len(tail) < 2:
        return head + _MASK
    return head + _MASK + tail[-2:]


def mask_accounts(text: str) -> str:
    """Return free text with every account-shaped token passed through `mask_account`."""
    if not isinstance(text, str) or not text:
        return text
    return _ACCOUNT_PATTERN.sub(lambda match: mask_account(match.group(0)), text)


def usd_equivalent(amount: Decimal, currency: str) -> Decimal:
    """Return the USD value of `amount`, unquantized so no precision is lost early."""
    return amount * FX_TABLE[currency]


def quantize_money(amount: Decimal, currency: str) -> Decimal:
    """Round `amount` to the minor unit of `currency` with ROUND_HALF_UP.

    The exponent is derived from `MINOR_UNITS` as `Decimal(10) ** -places` so the
    same helper serves the two-place currencies and zero-place JPY. The rounding
    mode is passed explicitly because the decimal context defaults to
    ROUND_HALF_EVEN, which is not the rounding this specification requires.
    """
    exponent = Decimal(10) ** -MINOR_UNITS[currency]
    return amount.quantize(exponent, rounding=ROUND_HALF_UP)


def build_envelope(
    source_agent: str,
    target_agent: str,
    message_type: str,
    data: dict,
    message_id: str | None = None,
) -> dict:
    """Build a new envelope carrying a deep copy of `data`, so callers cannot alias it."""
    return {
        "message_id": message_id or str(uuid.uuid4()),
        "timestamp": utc_now_iso(),
        "source_agent": source_agent,
        "target_agent": target_agent,
        "message_type": message_type,
        "data": copy.deepcopy(data),
    }
