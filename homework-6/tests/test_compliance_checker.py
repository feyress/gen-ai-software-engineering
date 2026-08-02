"""Tests for the compliance checker.

Covers specification.md sections C3 and C9: sanctions screening on the
destination account and the currency-transaction-report flag at 10,000 USD.
"""

from __future__ import annotations

import copy

import pytest

from agents import compliance_checker
from agents.envelope import Reason, Status


def _screened(make_envelope, record) -> dict:
    return compliance_checker.process_message(
        make_envelope(
            record,
            status=Status.RISK_SCORED,
            source_agent="fraud_detector",
            target_agent="compliance_checker",
        )
    )


def test_the_deny_list_holds_the_three_documented_test_values():
    """Section C9: invented test-only data, frozen so no caller can extend it."""
    assert compliance_checker.SANCTIONS_DENY_LIST == frozenset(
        {"ACC-4242", "ACC-6666", "ACC-7000"}
    )
    assert isinstance(compliance_checker.SANCTIONS_DENY_LIST, frozenset)


def test_no_sample_destination_account_is_on_the_deny_list(sample_records):
    """An empty `blocked` count for the sample run is the expected result, not a gap."""
    destinations = {record["destination_account"] for record in sample_records}
    assert destinations & compliance_checker.SANCTIONS_DENY_LIST == set()


@pytest.mark.parametrize("destination", ["ACC-4242", "ACC-6666", "ACC-7000"])
def test_a_sanctioned_counterparty_is_blocked(
    sample_record, make_envelope, destination
):
    """A deny-list hit is terminal and routes to results."""
    envelope = _screened(
        make_envelope, sample_record("TXN001", destination_account=destination)
    )

    assert envelope["data"]["status"] == Status.BLOCKED
    assert envelope["data"]["reason"] == Reason.SANCTIONED_COUNTERPARTY
    assert envelope["target_agent"] == "results"
    assert envelope["message_type"] == "result"
    assert envelope["source_agent"] == "compliance_checker"


def test_a_blocked_counterparty_is_never_named_in_full(sample_record, make_envelope):
    """Section C7: the reason detail carries the masked account only."""
    envelope = _screened(
        make_envelope, sample_record("TXN001", destination_account="ACC-4242")
    )

    assert "ACC-4242" not in envelope["data"]["reason_detail"]


def test_screening_happens_before_the_amount_is_parsed(sample_record, make_envelope):
    """Fail closed: a sanctioned counterparty is blocked whatever the amount looks like."""
    envelope = _screened(
        make_envelope,
        sample_record("TXN001", destination_account="ACC-6666", amount="not-a-number"),
    )

    assert envelope["data"]["status"] == Status.BLOCKED


def test_a_clean_counterparty_is_cleared_for_settlement(sample_record, make_envelope):
    """A deny-list miss continues to the settlement processor."""
    envelope = _screened(make_envelope, sample_record("TXN001"))

    assert envelope["data"]["status"] == Status.CLEARED
    assert envelope["target_agent"] == "settlement_processor"
    assert envelope["message_type"] == "transaction"
    assert "reason" not in envelope["data"]


def test_a_cleared_envelope_records_when_it_was_screened(
    sample_record, make_envelope, iso_utc
):
    """`screened_at` comes from `utc_now_iso()`, so only its shape is asserted."""
    envelope = _screened(make_envelope, sample_record("TXN001"))
    assert iso_utc.match(envelope["data"]["screened_at"])


@pytest.mark.parametrize(
    ("amount", "currency", "expected_flag"),
    [
        ("9999.99", "USD", False),
        ("10000.00", "USD", True),
        ("10000.01", "USD", True),
        ("9259.25", "EUR", False),
        ("9259.26", "EUR", True),
        ("1500.00", "USD", False),
    ],
)
def test_the_report_flag_turns_on_at_ten_thousand_usd_equivalent(
    sample_record, make_envelope, amount, currency, expected_flag
):
    """9,259.26 EUR is 10,000.0008 USD, one hundredth of a cent over the threshold."""
    envelope = _screened(
        make_envelope, sample_record("TXN003", amount=amount, currency=currency)
    )

    assert envelope["data"]["ctr_required"] is expected_flag


def test_the_checker_carries_the_scored_payload_forward(sample_record, make_envelope):
    """Section C2: an agent extends `data`, it does not replace it."""
    record = sample_record("TXN003")
    envelope = _screened(make_envelope, record)

    for field, value in record.items():
        assert envelope["data"][field] == value


def test_the_checker_does_not_mutate_its_input_envelope(sample_record, make_envelope):
    """A caller must be able to diff the input against the output."""
    incoming = make_envelope(sample_record("TXN003"), status=Status.RISK_SCORED)
    before = copy.deepcopy(incoming)

    compliance_checker.process_message(incoming)

    assert incoming == before


def test_the_checker_mints_a_new_message_id(sample_record, make_envelope):
    """An agent never reuses the identifier of the envelope it received."""
    incoming = make_envelope(sample_record("TXN003"), status=Status.RISK_SCORED)
    outgoing = compliance_checker.process_message(incoming)

    assert outgoing["message_id"] != incoming["message_id"]
