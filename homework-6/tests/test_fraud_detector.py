"""Tests for the fraud detector.

Covers specification.md section C4: nine additive weights, the two band edges,
and the rule that high risk is held for a human and terminal for this batch.
"""

from __future__ import annotations

import copy

import pytest

from agents import fraud_detector
from agents.envelope import Reason, RiskLevel, Status


def _scored(make_envelope, record) -> dict:
    return fraud_detector.process_message(
        make_envelope(
            record,
            status=Status.VALIDATED,
            source_agent="transaction_validator",
            target_agent="fraud_detector",
        )
    )["data"]


@pytest.mark.parametrize(
    ("transaction_id", "expected_score", "expected_level"),
    [
        ("TXN001", 8, RiskLevel.LOW),
        ("TXN002", 70, RiskLevel.HIGH),
        ("TXN003", 48, RiskLevel.MEDIUM),
        ("TXN004", 45, RiskLevel.MEDIUM),
        ("TXN005", 85, RiskLevel.HIGH),
        ("TXN008", 5, RiskLevel.LOW),
    ],
)
def test_sample_records_score_exactly_as_the_outcome_table_says(
    sample_record, make_envelope, transaction_id, expected_score, expected_level
):
    """Section D fixes the score and band of every record that reaches the detector."""
    data = _scored(make_envelope, sample_record(transaction_id))

    assert data["risk_score"] == expected_score
    assert data["risk_level"] == expected_level
    assert isinstance(data["risk_score"], int)


@pytest.mark.parametrize(
    ("transaction_id", "expected_signals"),
    [
        ("TXN001", ["channel_risk"]),
        ("TXN002", ["high_value"]),
        ("TXN003", ["channel_risk", "structuring"]),
        ("TXN004", ["channel_risk", "cross_border", "unusual_timing"]),
        ("TXN005", ["high_value", "very_high_value"]),
        ("TXN008", ["channel_risk"]),
    ],
)
def test_the_signals_that_fired_are_recorded_sorted(
    sample_record, make_envelope, transaction_id, expected_signals
):
    """`risk_signals` is the audit trail of the score and is deterministic."""
    data = _scored(make_envelope, sample_record(transaction_id))
    assert data["risk_signals"] == expected_signals


@pytest.mark.parametrize("transaction_id", ["TXN002", "TXN005"])
def test_high_risk_is_held_for_manual_review(
    sample_record, make_envelope, transaction_id
):
    """A score in the high band stops the transaction and routes it to results."""
    envelope = fraud_detector.process_message(
        make_envelope(sample_record(transaction_id), status=Status.VALIDATED)
    )

    assert envelope["data"]["status"] == Status.HELD
    assert envelope["data"]["reason"] == Reason.MANUAL_REVIEW_REQUIRED
    assert envelope["target_agent"] == "results"
    assert envelope["message_type"] == "result"


@pytest.mark.parametrize("transaction_id", ["TXN001", "TXN003", "TXN004", "TXN008"])
def test_anything_below_high_continues_to_compliance(
    sample_record, make_envelope, transaction_id
):
    """Low and medium risk carry on as `risk_scored`."""
    envelope = fraud_detector.process_message(
        make_envelope(sample_record(transaction_id), status=Status.VALIDATED)
    )

    assert envelope["data"]["status"] == Status.RISK_SCORED
    assert envelope["target_agent"] == "compliance_checker"
    assert envelope["message_type"] == "transaction"
    assert "reason" not in envelope["data"]


@pytest.mark.parametrize(
    ("amount", "expected_score", "expected_signals"),
    [
        ("8999.99", 0, []),
        ("9000.00", 40, ["structuring"]),
        ("9999.99", 40, ["structuring"]),
        ("10000.00", 70, ["high_value"]),
        ("49999.99", 70, ["high_value"]),
        ("50000.00", 85, ["high_value", "very_high_value"]),
    ],
)
def test_the_value_bands_fire_on_their_exact_thresholds(
    sample_record, make_envelope, amount, expected_score, expected_signals
):
    """TXN002 arrives over the zero-weight `branch` channel, isolating the value signal."""
    data = _scored(make_envelope, sample_record("TXN002", amount=amount))

    assert data["risk_score"] == expected_score
    assert data["risk_signals"] == expected_signals


@pytest.mark.parametrize(
    ("timestamp", "expected_score"),
    [
        ("2026-03-16T00:00:00Z", 20),
        ("2026-03-16T02:47:00Z", 20),
        ("2026-03-16T04:59:59Z", 20),
        ("2026-03-16T05:00:00Z", 0),
        ("2026-03-16T09:15:00Z", 0),
        ("2026-03-16T02:00:00", 20),
    ],
)
def test_the_unusual_timing_window_closes_at_five_utc(
    sample_record, make_envelope, timestamp, expected_score
):
    """The window is 00:00:00 to 04:59:59 UTC; a naive timestamp is read as UTC."""
    data = _scored(
        make_envelope, sample_record("TXN002", amount="100.00", timestamp=timestamp)
    )
    assert data["risk_score"] == expected_score


@pytest.mark.parametrize("timestamp", ["not-a-timestamp", 1742100000, None])
def test_an_unusable_timestamp_scores_no_timing_points(
    sample_record, make_envelope, timestamp
):
    """The detector never crashes on a timestamp the validator would have stopped."""
    data = _scored(
        make_envelope, sample_record("TXN002", amount="100.00", timestamp=timestamp)
    )
    assert data["risk_score"] == 0


def test_a_record_without_a_timestamp_scores_no_timing_points(
    sample_record, make_envelope
):
    """An absent timestamp is not an unusual hour."""
    record = sample_record("TXN002", amount="100.00")
    del record["timestamp"]

    assert _scored(make_envelope, record)["risk_score"] == 0


def test_absent_metadata_scores_the_worst_case_on_country_and_channel(
    sample_record, make_envelope
):
    """Fail closed: no metadata means cross-border at 15 and the worst channel at 10."""
    record = sample_record("TXN001", amount="100.00")
    del record["metadata"]

    data = _scored(make_envelope, record)

    assert data["risk_score"] == 25
    assert data["risk_signals"] == ["channel_risk", "cross_border"]


def test_metadata_of_the_wrong_type_scores_the_worst_case(sample_record, make_envelope):
    """A metadata value that is not an object is treated as absent, not trusted."""
    data = _scored(
        make_envelope, sample_record("TXN001", amount="100.00", metadata="online")
    )

    assert data["risk_score"] == 25


def test_an_unrecognised_channel_scores_the_worst_known_weight(
    sample_record, make_envelope
):
    """A channel outside the four named in section C4 scores 10, like `api`."""
    data = _scored(
        make_envelope,
        sample_record(
            "TXN001", amount="100.00", metadata={"channel": "atm", "country": "US"}
        ),
    )

    assert data["risk_score"] == 10
    assert data["risk_signals"] == ["channel_risk"]


@pytest.mark.parametrize(
    ("channel", "expected_score"),
    [("api", 10), ("online", 8), ("mobile", 5), ("branch", 0)],
)
def test_each_named_channel_carries_its_specified_weight(
    sample_record, make_envelope, channel, expected_score
):
    """The four channel weights of section C4."""
    data = _scored(
        make_envelope,
        sample_record(
            "TXN001", amount="100.00", metadata={"channel": channel, "country": "US"}
        ),
    )

    assert data["risk_score"] == expected_score


def test_the_branch_channel_records_no_signal(sample_record, make_envelope):
    """A zero-weight channel contributed nothing, so it is not listed as a signal."""
    data = _scored(
        make_envelope,
        sample_record(
            "TXN001", amount="100.00", metadata={"channel": "branch", "country": "US"}
        ),
    )

    assert data["risk_signals"] == []


@pytest.mark.parametrize(
    ("score", "expected_level", "amount", "timestamp", "channel"),
    [
        (28, RiskLevel.LOW, "100.00", "2026-03-16T02:00:00Z", "online"),
        (30, RiskLevel.MEDIUM, "100.00", "2026-03-16T02:00:00Z", "api"),
        (68, RiskLevel.MEDIUM, "9500.00", "2026-03-16T02:00:00Z", "online"),
        (70, RiskLevel.HIGH, "9500.00", "2026-03-16T02:00:00Z", "api"),
    ],
)
def test_the_band_edges_sit_at_thirty_and_seventy(
    sample_record, make_envelope, score, expected_level, amount, timestamp, channel
):
    """Low is 0..29, medium is 30..69, high is 70..100."""
    data = _scored(
        make_envelope,
        sample_record(
            "TXN001",
            amount=amount,
            timestamp=timestamp,
            metadata={"channel": channel, "country": "US"},
        ),
    )

    assert data["risk_score"] == score
    assert data["risk_level"] == expected_level


def test_the_score_is_clamped_at_one_hundred(sample_record, make_envelope):
    """Every signal firing sums to 130, which is reported as the ceiling."""
    data = _scored(
        make_envelope,
        sample_record(
            "TXN005",
            timestamp="2026-03-16T02:00:00Z",
            metadata={"channel": "api", "country": "DE"},
        ),
    )

    assert data["risk_score"] == 100
    assert data["risk_level"] == RiskLevel.HIGH


@pytest.mark.parametrize(
    ("amount", "currency", "expected_score", "expected_signals"),
    [
        ("9300.00", "EUR", 70, ["high_value"]),
        ("8500.00", "EUR", 40, ["structuring"]),
        ("1400000", "JPY", 40, ["structuring"]),
    ],
)
def test_the_value_bands_are_measured_on_the_usd_equivalent(
    sample_record, make_envelope, amount, currency, expected_score, expected_signals
):
    """9,300.00 EUR is 10,044.00 USD and so crosses the reporting threshold."""
    data = _scored(
        make_envelope, sample_record("TXN002", amount=amount, currency=currency)
    )

    assert data["risk_score"] == expected_score
    assert data["risk_signals"] == expected_signals


def test_the_detector_carries_the_validated_payload_forward(
    sample_record, make_envelope
):
    """Section C2: keys written upstream survive to the terminal result."""
    record = sample_record("TXN004")
    data = _scored(make_envelope, record)

    for field, value in record.items():
        assert data[field] == value


def test_the_detector_does_not_mutate_its_input_envelope(sample_record, make_envelope):
    """A caller must be able to diff the input against the output."""
    incoming = make_envelope(sample_record("TXN002"), status=Status.VALIDATED)
    before = copy.deepcopy(incoming)

    fraud_detector.process_message(incoming)

    assert incoming == before


def test_the_detector_mints_a_new_message_id(sample_record, make_envelope):
    """An agent never reuses the identifier of the envelope it received."""
    incoming = make_envelope(sample_record("TXN001"), status=Status.VALIDATED)
    outgoing = fraud_detector.process_message(incoming)

    assert outgoing["message_id"] != incoming["message_id"]
