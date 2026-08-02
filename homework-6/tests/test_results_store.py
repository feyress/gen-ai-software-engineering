"""Tests for the read side over shared/results/.

Covers specification.md sections C8 and D. A transaction the pipeline never
processed is reported as None: `status` is a closed set, so a missing result may
not be answered with an invented member.
"""

from __future__ import annotations

import pytest

from agents import mailbox, results_store
from agents.envelope import MessageType, Status, build_envelope


@pytest.fixture
def populated_root(pipeline_root):
    """A results directory holding two outcomes and a summary."""
    settled = build_envelope(
        "settlement_processor",
        "results",
        MessageType.RESULT,
        {
            "transaction_id": "TXN001",
            "status": Status.SETTLED,
            "risk_score": 8,
            "risk_level": "low",
            "settled_amount": "1500.00",
            "source_account": "ACC-1001",
        },
    )
    rejected = build_envelope(
        "transaction_validator",
        "results",
        MessageType.RESULT,
        {
            "transaction_id": "TXN006",
            "status": Status.REJECTED,
            "reason": "invalid_currency",
        },
    )
    directory = results_store.results_dir(pipeline_root)
    mailbox.write_message(directory, "TXN006.json", rejected)
    mailbox.write_message(directory, "TXN001.json", settled)
    mailbox.write_message(directory, mailbox.SUMMARY_FILENAME, {"total_transactions": 2})
    return pipeline_root


def test_results_dir_hangs_off_the_shared_tree(tmp_path):
    """Every read in this module is rooted in the caller's `root`."""
    assert results_store.results_dir(tmp_path) == tmp_path / "shared" / "results"


def test_get_transaction_returns_the_stored_envelope(populated_root):
    """The full terminal envelope comes back, not a projection."""
    envelope = results_store.get_transaction(populated_root, "TXN001")

    assert envelope["data"]["status"] == Status.SETTLED
    assert envelope["source_agent"] == "settlement_processor"


def test_get_transaction_returns_none_for_a_transaction_that_was_never_processed(
    populated_root,
):
    """A missing result is None, never a fabricated status."""
    assert results_store.get_transaction(populated_root, "TXN999") is None


@pytest.mark.parametrize(
    "transaction_id", ["", "../secrets", "sub/dir", "TXN 001", "TXN001;rm"]
)
def test_get_transaction_refuses_an_id_that_is_not_a_safe_file_name(
    populated_root, transaction_id
):
    """A transaction id becomes a file name, so it may not carry a path."""
    assert results_store.get_transaction(populated_root, transaction_id) is None


def test_list_results_sorts_by_transaction_id_and_skips_the_summary(populated_root):
    """`pipeline-summary.json` is not a transaction result."""
    results = results_store.list_results(populated_root)

    assert [envelope["data"]["transaction_id"] for envelope in results] == [
        "TXN001",
        "TXN006",
    ]


def test_list_results_is_empty_before_any_run(pipeline_root):
    """An empty results directory yields an empty list, not an error."""
    assert results_store.list_results(pipeline_root) == []


def test_latest_summary_returns_the_parsed_summary(populated_root):
    """The summary is read through the same mailbox as everything else."""
    assert results_store.latest_summary(populated_root) == {"total_transactions": 2}


def test_latest_summary_is_none_before_any_run(pipeline_root):
    """No summary file means the pipeline has not completed a run."""
    assert results_store.latest_summary(pipeline_root) is None


def test_status_of_projects_exactly_the_six_documented_fields(populated_root):
    """The projection is the shape the MCP server and the integrator share."""
    projection = results_store.status_of(populated_root, "TXN001")

    assert set(projection) == set(results_store.PROJECTION_FIELDS)
    assert projection == {
        "transaction_id": "TXN001",
        "status": "settled",
        "risk_score": 8,
        "risk_level": "low",
        "reason": None,
        "settled_amount": "1500.00",
    }


def test_status_of_uses_none_for_fields_a_transaction_never_acquired(populated_root):
    """A record rejected at validation never earned a score or a settled amount."""
    projection = results_store.status_of(populated_root, "TXN006")

    assert projection["status"] == "rejected"
    assert projection["reason"] == "invalid_currency"
    assert projection["risk_score"] is None
    assert projection["risk_level"] is None
    assert projection["settled_amount"] is None


def test_status_of_returns_none_for_an_unknown_transaction(populated_root):
    """The caller decides how to report a miss; the store does not guess."""
    assert results_store.status_of(populated_root, "TXN999") is None


def test_the_projection_carries_no_account_number(populated_root):
    """The stored envelope holds an unmasked account; the projection does not expose it."""
    projection = results_store.status_of(populated_root, "TXN001")

    assert "source_account" not in projection
    assert "ACC-1001" not in str(projection)


def test_an_account_shaped_field_would_be_masked_on_the_way_out():
    """The projection masks by field name, so widening it cannot leak an account."""
    assert results_store._safe("source_account", "ACC-1001") == "ACC-****01"
    assert results_store._safe("risk_score", 8) == 8
    assert results_store._safe("source_account", None) is None
