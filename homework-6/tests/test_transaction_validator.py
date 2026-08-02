"""Tests for the transaction validator.

Covers specification.md section C4: five checks in a fixed order where the first
failure wins, so exactly one member of the closed `reason` set is ever emitted.
"""

from __future__ import annotations

import copy

import pytest

from agents import transaction_validator
from agents.envelope import REASON, Reason, Status


def _validate(make_envelope, record):
    return transaction_validator.process_message(
        make_envelope(record, status=Status.RECEIVED)
    )


@pytest.mark.parametrize(
    "transaction_id", ["TXN001", "TXN002", "TXN003", "TXN004", "TXN005", "TXN008"]
)
def test_well_formed_sample_records_are_validated(
    sample_record, make_envelope, transaction_id
):
    """Six of the eight sample records pass validation and go on to be scored."""
    outgoing = _validate(make_envelope, sample_record(transaction_id))

    assert outgoing["data"]["status"] == Status.VALIDATED
    assert outgoing["target_agent"] == "fraud_detector"
    assert outgoing["source_agent"] == "transaction_validator"
    assert outgoing["message_type"] == "transaction"
    assert "reason" not in outgoing["data"]


def test_validated_envelope_keeps_the_amount_as_its_original_string(
    sample_record, make_envelope
):
    """The amount stays a decimal string; nothing coerces it through float."""
    outgoing = _validate(make_envelope, sample_record("TXN003"))

    assert outgoing["data"]["amount"] == "9999.99"
    assert isinstance(outgoing["data"]["amount"], str)


def test_validated_envelope_carries_every_original_field_forward(
    sample_record, make_envelope
):
    """Section C2: an agent extends `data`, it never drops an upstream key."""
    record = sample_record("TXN001")
    outgoing = _validate(make_envelope, record)

    for field, value in record.items():
        assert outgoing["data"][field] == value


def test_validator_rejects_unknown_currency(sample_record, make_envelope):
    """TXN006 carries currency XYZ and is stopped with `invalid_currency`."""
    outgoing = _validate(make_envelope, sample_record("TXN006"))

    assert outgoing["data"]["status"] == Status.REJECTED
    assert outgoing["data"]["reason"] == Reason.INVALID_CURRENCY
    assert outgoing["target_agent"] == "results"
    assert outgoing["message_type"] == "result"


def test_validator_rejects_non_positive_amount(sample_record, make_envelope):
    """TXN007 carries -100.00 and is stopped with `non_positive_amount`."""
    outgoing = _validate(make_envelope, sample_record("TXN007"))

    assert outgoing["data"]["status"] == Status.REJECTED
    assert outgoing["data"]["reason"] == Reason.NON_POSITIVE_AMOUNT


@pytest.mark.parametrize(
    "field",
    [
        "transaction_id",
        "timestamp",
        "source_account",
        "destination_account",
        "amount",
        "currency",
        "transaction_type",
    ],
)
def test_each_absent_required_field_produces_missing_field(
    sample_record, make_envelope, field
):
    """Check 1 covers all seven required fields of section C4."""
    record = sample_record("TXN001")
    del record[field]

    outgoing = _validate(make_envelope, record)

    assert outgoing["data"]["status"] == Status.REJECTED
    assert outgoing["data"]["reason"] == Reason.MISSING_FIELD


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_account", ""),
        ("source_account", "   "),
        ("amount", ""),
        ("currency", ""),
        ("transaction_id", 1001),
        ("transaction_type", ["transfer"]),
        ("timestamp", "not-a-timestamp"),
        ("timestamp", "2026-13-45T99:00:00Z"),
    ],
)
def test_a_present_but_unusable_required_field_produces_missing_field(
    sample_record, make_envelope, field, value
):
    """An empty string, a non-string identifier or an unparseable timestamp all fail check 1."""
    record = sample_record("TXN001", **{field: value})

    outgoing = _validate(make_envelope, record)

    assert outgoing["data"]["status"] == Status.REJECTED
    assert outgoing["data"]["reason"] == Reason.MISSING_FIELD


@pytest.mark.parametrize(
    "amount",
    [
        1500.00,
        1500,
        "1,500.00",
        "abc",
        "1500.0000001",
        "1234567890123456",
        "1500.",
        " 1500.00",
    ],
)
def test_an_amount_outside_the_decimal_string_pattern_is_malformed(
    sample_record, make_envelope, amount
):
    """Check 2: a JSON number is rejected rather than coerced through float."""
    outgoing = _validate(make_envelope, sample_record("TXN001", amount=amount))

    assert outgoing["data"]["status"] == Status.REJECTED
    assert outgoing["data"]["reason"] == Reason.MALFORMED_AMOUNT


@pytest.mark.parametrize("amount", ["-100.00", "0.00", "0", "-0.01"])
def test_an_amount_at_or_below_zero_is_non_positive(
    sample_record, make_envelope, amount
):
    """Check 3 runs on the parsed Decimal, so 0.00 fails as surely as -100.00."""
    outgoing = _validate(make_envelope, sample_record("TXN001", amount=amount))

    assert outgoing["data"]["status"] == Status.REJECTED
    assert outgoing["data"]["reason"] == Reason.NON_POSITIVE_AMOUNT


@pytest.mark.parametrize("currency", ["XYZ", "usd", "US", "USDD", "EURO"])
def test_a_currency_outside_the_allow_list_is_invalid(
    sample_record, make_envelope, currency
):
    """Check 4: uppercase alpha-3 and a member of {USD, EUR, GBP, JPY}."""
    outgoing = _validate(make_envelope, sample_record("TXN001", currency=currency))

    assert outgoing["data"]["status"] == Status.REJECTED
    assert outgoing["data"]["reason"] == Reason.INVALID_CURRENCY


@pytest.mark.parametrize(
    ("amount", "currency"),
    [("100.001", "USD"), ("100.5", "JPY"), ("0.12345", "EUR")],
)
def test_an_amount_finer_than_the_currency_minor_unit_is_malformed(
    sample_record, make_envelope, amount, currency
):
    """Check 5: JPY takes no minor unit, the others take two places."""
    outgoing = _validate(
        make_envelope, sample_record("TXN001", amount=amount, currency=currency)
    )

    assert outgoing["data"]["status"] == Status.REJECTED
    assert outgoing["data"]["reason"] == Reason.MALFORMED_AMOUNT


def test_a_whole_yen_amount_passes_the_minor_unit_check(sample_record, make_envelope):
    """JPY at zero decimal places is well formed."""
    outgoing = _validate(
        make_envelope, sample_record("TXN001", amount="10000", currency="JPY")
    )

    assert outgoing["data"]["status"] == Status.VALIDATED


@pytest.mark.parametrize(
    ("overrides", "expected_reason"),
    [
        ({"source_account": "", "amount": "not-a-number"}, Reason.MISSING_FIELD),
        ({"source_account": "", "currency": "XYZ"}, Reason.MISSING_FIELD),
        ({"amount": "not-a-number", "currency": "XYZ"}, Reason.MALFORMED_AMOUNT),
        ({"amount": "-100.00", "currency": "XYZ"}, Reason.NON_POSITIVE_AMOUNT),
        ({"amount": "-100.001", "currency": "XYZ"}, Reason.NON_POSITIVE_AMOUNT),
        ({"amount": "100.001", "currency": "XYZ"}, Reason.INVALID_CURRENCY),
    ],
)
def test_the_first_failing_check_wins(
    sample_record, make_envelope, overrides, expected_reason
):
    """A record that trips several checks reports only the earliest, per section C4."""
    outgoing = _validate(make_envelope, sample_record("TXN001", **overrides))

    assert outgoing["data"]["reason"] == expected_reason


def test_every_rejection_reason_is_a_member_of_the_closed_set(
    sample_record, make_envelope
):
    """The validator may not invent a reason outside section C3."""
    broken = [
        sample_record("TXN001", amount="oops"),
        sample_record("TXN001", currency="XYZ"),
        sample_record("TXN001", amount="-1.00"),
        sample_record("TXN001", source_account=""),
    ]
    for record in broken:
        outgoing = _validate(make_envelope, record)
        assert outgoing["data"]["reason"] in REASON


def test_a_rejected_envelope_still_carries_a_human_readable_detail(
    sample_record, make_envelope
):
    """Every reason is paired with prose for a human; its wording is not asserted."""
    outgoing = _validate(make_envelope, sample_record("TXN006"))

    assert isinstance(outgoing["data"]["reason_detail"], str)
    assert outgoing["data"]["reason_detail"]


def test_the_validator_does_not_mutate_its_input_envelope(sample_record, make_envelope):
    """Section C2: a caller must be able to diff the input against the output."""
    incoming = make_envelope(sample_record("TXN001"), status=Status.RECEIVED)
    before = copy.deepcopy(incoming)

    transaction_validator.process_message(incoming)

    assert incoming == before


def test_the_validator_mints_a_new_message_id(sample_record, make_envelope):
    """An agent never reuses the identifier of the envelope it received."""
    incoming = make_envelope(sample_record("TXN001"), status=Status.RECEIVED)
    outgoing = transaction_validator.process_message(incoming)

    assert outgoing["message_id"] != incoming["message_id"]


def test_an_empty_payload_is_rejected_rather_than_crashing():
    """Fail closed: an envelope with no data at all is a missing-field rejection."""
    outgoing = transaction_validator.process_message({})

    assert outgoing["data"]["status"] == Status.REJECTED
    assert outgoing["data"]["reason"] == Reason.MISSING_FIELD
