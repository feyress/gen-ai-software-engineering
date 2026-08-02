"""Tests for the reporting agent.

Covers specification.md sections B5, C7 and D: the counts, the per-currency and
base-currency totals, the exception list, and the PII rules on the summary.
"""

from __future__ import annotations

import json

from agents import reporting_agent
from agents.envelope import MessageType, Status, build_envelope


def _terminal(transaction_id, status, **extra) -> dict:
    data = {"transaction_id": transaction_id, "status": status, **extra}
    return build_envelope("agent", "results", MessageType.RESULT, data)


def test_the_sample_run_summarises_to_the_section_d_figures(terminal_envelopes):
    """Section B5 fixes every figure the summary reports for the sample data."""
    summary = reporting_agent.build_summary(terminal_envelopes)

    assert summary["total_transactions"] == 8
    assert summary["counts_by_status"] == {
        "rejected": 2,
        "held": 2,
        "blocked": 0,
        "settled": 4,
    }
    assert summary["settled_totals_by_currency"] == {
        "USD": "14699.99",
        "EUR": "500.00",
    }
    assert summary["settled_total_base"] == "15239.99"


def test_the_exception_list_names_every_non_settled_transaction(terminal_envelopes):
    """TXN002 and TXN005 are held, TXN006 and TXN007 rejected, sorted by id."""
    summary = reporting_agent.build_summary(terminal_envelopes)

    assert [entry["transaction_id"] for entry in summary["exceptions"]] == [
        "TXN002",
        "TXN005",
        "TXN006",
        "TXN007",
    ]
    assert [entry["reason"] for entry in summary["exceptions"]] == [
        "manual_review_required",
        "manual_review_required",
        "invalid_currency",
        "non_positive_amount",
    ]
    assert [entry["status"] for entry in summary["exceptions"]] == [
        "held",
        "held",
        "rejected",
        "rejected",
    ]


def test_no_account_number_reaches_the_summary(terminal_envelopes, sample_records):
    """Section C7: the summary is a human-facing artefact and carries no raw PII."""
    text = json.dumps(reporting_agent.build_summary(terminal_envelopes))

    for record in sample_records:
        assert record["source_account"] not in text
        assert record["destination_account"] not in text
        assert record["description"] not in text


def test_an_account_in_a_reason_detail_is_masked():
    """A blocked transaction names its counterparty only through `mask_account`."""
    blocked = _terminal(
        "TXN900",
        Status.BLOCKED,
        reason="sanctioned_counterparty",
        reason_detail="destination ACC-4242 is on the sanctions deny-list",
    )

    entry = reporting_agent.build_summary([blocked])["exceptions"][0]

    assert "ACC-4242" not in entry["reason_detail"]


def test_an_exception_without_a_detail_reports_null():
    """A missing detail is an explicit null, not the string 'None'."""
    rejected = _terminal("TXN900", Status.REJECTED, reason="missing_field")

    entry = reporting_agent.build_summary([rejected])["exceptions"][0]

    assert entry["reason_detail"] is None


def test_an_empty_run_still_reports_every_count_key():
    """Section B5 requires the four status keys present and defaulting to zero."""
    summary = reporting_agent.build_summary([])

    assert summary["total_transactions"] == 0
    assert summary["counts_by_status"] == {
        "rejected": 0,
        "held": 0,
        "blocked": 0,
        "settled": 0,
    }
    assert summary["settled_totals_by_currency"] == {}
    assert summary["settled_total_base"] == "0.00"
    assert summary["exceptions"] == []


def test_a_non_terminal_status_is_counted_without_being_treated_as_an_exception():
    """A stray in-flight envelope is counted honestly rather than dropped."""
    summary = reporting_agent.build_summary([_terminal("TXN900", Status.CLEARED)])

    assert summary["counts_by_status"]["cleared"] == 1
    assert summary["exceptions"] == []


def test_totals_are_summed_per_currency_before_any_conversion():
    """Section C5: two currencies never meet inside one arithmetic expression."""
    results = [
        _terminal(
            "TXN901", Status.SETTLED, currency="EUR", amount="10.10", settled_amount="10.91"
        ),
        _terminal(
            "TXN902", Status.SETTLED, currency="EUR", amount="0.90", settled_amount="0.97"
        ),
        _terminal(
            "TXN903", Status.SETTLED, currency="GBP", amount="2.00", settled_amount="2.54"
        ),
    ]

    summary = reporting_agent.build_summary(results)

    assert summary["settled_totals_by_currency"] == {"EUR": "11.00", "GBP": "2.00"}
    assert summary["settled_total_base"] == "14.42"


def test_a_yen_total_is_quantized_to_whole_units():
    """JPY has a zero minor unit, so its total carries no decimal places."""
    results = [
        _terminal(
            "TXN904", Status.SETTLED, currency="JPY", amount="1200", settled_amount="8.04"
        ),
        _terminal(
            "TXN905", Status.SETTLED, currency="JPY", amount="35", settled_amount="0.23"
        ),
    ]

    summary = reporting_agent.build_summary(results)

    assert summary["settled_totals_by_currency"] == {"JPY": "1235"}
    assert summary["settled_total_base"] == "8.27"


def test_generated_at_has_the_utc_timestamp_shape(iso_utc):
    """The summary records when it was produced; only its shape is asserted."""
    assert iso_utc.match(reporting_agent.build_summary([])["generated_at"])


def test_process_message_wraps_the_summary_in_a_summary_envelope(terminal_envelopes):
    """The agent does no file I/O; it hands the payload back for the caller to write."""
    envelope = reporting_agent.process_message(
        build_envelope(
            "integrator",
            "reporting_agent",
            MessageType.SUMMARY,
            {"results": terminal_envelopes},
        )
    )

    assert envelope["message_type"] == MessageType.SUMMARY
    assert envelope["source_agent"] == "reporting_agent"
    assert envelope["target_agent"] == "results"
    assert envelope["data"]["settled_total_base"] == "15239.99"


def test_process_message_tolerates_a_message_with_no_results():
    """An empty run still produces a well-formed summary envelope."""
    envelope = reporting_agent.process_message(
        build_envelope("integrator", "reporting_agent", MessageType.SUMMARY, {})
    )

    assert envelope["data"]["total_transactions"] == 0
