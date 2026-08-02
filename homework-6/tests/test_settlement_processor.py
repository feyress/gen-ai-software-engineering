"""Tests for the settlement processor.

Covers specification.md sections C5 and D: conversion through the static FX
table, one quantization with ROUND_HALF_UP, and a deterministic reference.
"""

from __future__ import annotations

import copy
from decimal import ROUND_HALF_EVEN, Decimal

import pytest

from agents import settlement_processor
from agents.envelope import FX_RATES_AS_OF, Status

FIXED_MESSAGE_ID = "3f2c8b1e-9a4d-4f61-8b3a-0d5c7e2a1b44"


def _settled(make_envelope, record, message_id=None) -> dict:
    return settlement_processor.process_message(
        make_envelope(
            record,
            status=Status.CLEARED,
            source_agent="compliance_checker",
            target_agent="settlement_processor",
            message_id=message_id,
        )
    )


def _contains_float(value: object) -> bool:
    if isinstance(value, float):
        return True
    if isinstance(value, dict):
        return any(_contains_float(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_float(item) for item in value)
    return False


def test_txn004_settles_to_exactly_540_00_usd(sample_record, make_envelope):
    """Section B4: 500.00 EUR at rate 1.080000 is 540.00 USD, to the cent."""
    data = _settled(make_envelope, sample_record("TXN004"))["data"]

    assert data["settled_amount"] == "540.00"
    assert Decimal(data["settled_amount"]) == Decimal("540.00")
    assert data["fx_rate"] == "1.080000"
    assert data["base_currency"] == "USD"
    assert data["fx_rate_as_of"] == FX_RATES_AS_OF


@pytest.mark.parametrize(
    ("transaction_id", "expected"),
    [("TXN001", "1500.00"), ("TXN003", "9999.99"), ("TXN008", "3200.00")],
)
def test_a_usd_transaction_settles_at_its_own_amount(
    sample_record, make_envelope, transaction_id, expected
):
    """The USD rate is 1.000000, so the settled amount is the original amount."""
    data = _settled(make_envelope, sample_record(transaction_id))["data"]
    assert data["settled_amount"] == expected


def test_rounding_is_half_up_where_half_even_would_round_down(
    sample_record, make_envelope
):
    """1.50 GBP is 1.905000 USD: ROUND_HALF_UP gives 1.91, the default would give 1.90."""
    data = _settled(
        make_envelope, sample_record("TXN001", amount="1.50", currency="GBP")
    )["data"]

    assert data["settled_amount"] == "1.91"
    assert (Decimal("1.50") * Decimal("1.270000")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_EVEN
    ) == Decimal("1.90")


@pytest.mark.parametrize(
    ("amount", "expected"),
    [("10000", "67.00"), ("1", "0.01"), ("1500", "10.05")],
)
def test_a_zero_minor_unit_currency_settles_into_two_place_usd(
    sample_record, make_envelope, amount, expected
):
    """JPY carries no minor unit of its own; the base currency still takes two places."""
    data = _settled(
        make_envelope, sample_record("TXN001", amount=amount, currency="JPY")
    )["data"]

    assert data["settled_amount"] == expected


def test_the_settled_envelope_is_terminal(sample_record, make_envelope):
    """Settled is the end of the road; it routes to results."""
    envelope = _settled(make_envelope, sample_record("TXN004"))

    assert envelope["data"]["status"] == Status.SETTLED
    assert envelope["target_agent"] == "results"
    assert envelope["message_type"] == "result"
    assert envelope["source_agent"] == "settlement_processor"


def test_the_settlement_reference_is_derived_from_the_incoming_envelope(
    sample_record, make_envelope
):
    """A fixed message id reproduces the reference exactly."""
    envelope = _settled(
        make_envelope, sample_record("TXN004"), message_id=FIXED_MESSAGE_ID
    )

    assert envelope["data"]["settlement_reference"] == "SET-TXN004-3F2C8B1E"


def test_the_settled_envelope_records_when_it_settled(
    sample_record, make_envelope, iso_utc
):
    """`settled_at` comes from `utc_now_iso()`, so only its shape is asserted."""
    envelope = _settled(make_envelope, sample_record("TXN004"))
    assert iso_utc.match(envelope["data"]["settled_at"])


def test_no_float_reaches_the_money_path(sample_record, make_envelope):
    """Every money value on the settled envelope is a string, never a binary float."""
    data = _settled(make_envelope, sample_record("TXN004"))["data"]

    assert isinstance(data["settled_amount"], str)
    assert isinstance(data["fx_rate"], str)
    assert not _contains_float(data)


def test_the_processor_carries_the_cleared_payload_forward(
    sample_record, make_envelope
):
    """Section C2: keys written upstream survive to the terminal result."""
    record = sample_record("TXN004")
    data = _settled(make_envelope, record)["data"]

    for field, value in record.items():
        assert data[field] == value


def test_the_processor_does_not_mutate_its_input_envelope(sample_record, make_envelope):
    """A caller must be able to diff the input against the output."""
    incoming = make_envelope(sample_record("TXN004"), status=Status.CLEARED)
    before = copy.deepcopy(incoming)

    settlement_processor.process_message(incoming)

    assert incoming == before


def test_the_processor_mints_a_new_message_id(sample_record, make_envelope):
    """An agent never reuses the identifier of the envelope it received."""
    incoming = make_envelope(sample_record("TXN004"), status=Status.CLEARED)
    outgoing = settlement_processor.process_message(incoming)

    assert outgoing["message_id"] != incoming["message_id"]
