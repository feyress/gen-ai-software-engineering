"""Decides a risk score and risk level, and holds high risk for a human.

Governed by specification.md section C4. Scoring is deterministic and additive
over the USD equivalent of the amount, the hour of the transaction, the
counterparty country and the channel. Expected scores for the sample records:
TXN001 8, TXN002 70, TXN003 48, TXN004 45, TXN005 85, TXN008 5.
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from decimal import Decimal

from agents.envelope import (
    DOMESTIC_COUNTRY,
    MessageType,
    Reason,
    RiskLevel,
    Status,
    build_envelope,
    usd_equivalent,
)

AGENT_NAME = "fraud_detector"

HIGH_VALUE_THRESHOLD = Decimal("10000.00")
VERY_HIGH_VALUE_THRESHOLD = Decimal("50000.00")
STRUCTURING_FLOOR = Decimal("9000.00")
UNUSUAL_HOUR_END = 5

# The high-value weight sits exactly on the `high` band edge so that any
# transaction at or above the reporting threshold is held whatever channel it
# arrived through: TXN002 comes in over the lowest-risk channel and must still
# be held. The structuring weight sits mid-band for the opposite reason —
# suspicious enough to score, not enough to stop.
WEIGHT_HIGH_VALUE = 70
WEIGHT_VERY_HIGH_VALUE = 15
WEIGHT_STRUCTURING = 40
WEIGHT_UNUSUAL_TIMING = 20
WEIGHT_CROSS_BORDER = 15

CHANNEL_WEIGHTS: dict[str, int] = {"api": 10, "online": 8, "mobile": 5, "branch": 0}
# Fail closed: an unrecognised or absent channel is scored as the worst known one.
DEFAULT_CHANNEL_WEIGHT = 10

MEDIUM_BAND_FLOOR = 30
HIGH_BAND_FLOOR = 70

MIN_SCORE = 0
MAX_SCORE = 100


def process_message(message: dict) -> dict:
    """Score one validated envelope and return a held or risk-scored envelope."""
    data = copy.deepcopy(message.get("data", {}))
    amount_usd = usd_equivalent(Decimal(data["amount"]), data["currency"])
    score, signals = _score(amount_usd, data)
    level = _risk_level(score)

    data["risk_score"] = score
    data["risk_level"] = level
    data["risk_signals"] = signals

    if level == RiskLevel.HIGH:
        data["status"] = Status.HELD
        data["reason"] = Reason.MANUAL_REVIEW_REQUIRED
        data["reason_detail"] = (
            f"risk score {score} ({level}) from signals: {', '.join(signals) or 'none'}"
        )
        return build_envelope(
            source_agent=AGENT_NAME,
            target_agent="results",
            message_type=MessageType.RESULT,
            data=data,
        )

    data["status"] = Status.RISK_SCORED
    return build_envelope(
        source_agent=AGENT_NAME,
        target_agent="compliance_checker",
        message_type=MessageType.TRANSACTION,
        data=data,
    )


def _score(amount_usd: Decimal, data: dict) -> tuple[int, list[str]]:
    """Return the clamped score and the sorted identifiers of the signals that fired."""
    metadata = data.get("metadata")
    signals: list[str] = []
    total = 0

    if amount_usd >= HIGH_VALUE_THRESHOLD:
        total += WEIGHT_HIGH_VALUE
        signals.append("high_value")
        if amount_usd >= VERY_HIGH_VALUE_THRESHOLD:
            total += WEIGHT_VERY_HIGH_VALUE
            signals.append("very_high_value")
    elif amount_usd >= STRUCTURING_FLOOR:
        total += WEIGHT_STRUCTURING
        signals.append("structuring")

    if _is_unusual_hour(data.get("timestamp")):
        total += WEIGHT_UNUSUAL_TIMING
        signals.append("unusual_timing")

    if _is_cross_border(metadata):
        total += WEIGHT_CROSS_BORDER
        signals.append("cross_border")

    channel_weight = _channel_weight(metadata)
    if channel_weight:
        total += channel_weight
        signals.append("channel_risk")

    return max(MIN_SCORE, min(MAX_SCORE, total)), sorted(signals)


def _is_unusual_hour(timestamp: str | None) -> bool:
    """Return True when the transaction happened between 00:00:00 and 04:59:59 UTC."""
    if not isinstance(timestamp, str):
        return False
    try:
        moment = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return False
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).hour < UNUSUAL_HOUR_END


def _is_cross_border(metadata: dict | None) -> bool:
    """Return True when the country is not domestic, or is unknown."""
    if not isinstance(metadata, dict):
        return True
    return metadata.get("country") != DOMESTIC_COUNTRY


def _channel_weight(metadata: dict | None) -> int:
    """Return the weight of the origination channel, worst case when unknown."""
    if not isinstance(metadata, dict):
        return DEFAULT_CHANNEL_WEIGHT
    return CHANNEL_WEIGHTS.get(metadata.get("channel"), DEFAULT_CHANNEL_WEIGHT)


def _risk_level(score: int) -> str:
    """Map a score to its band: low 0..29, medium 30..69, high 70..100."""
    if score >= HIGH_BAND_FLOOR:
        return RiskLevel.HIGH
    if score >= MEDIUM_BAND_FLOOR:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW
