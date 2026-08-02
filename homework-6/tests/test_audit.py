"""Tests for the append-only audit trail.

Covers specification.md sections C6 and C7: one line per status change, never
rewritten, and no account number in plaintext.
"""

from __future__ import annotations

import json

from agents import audit


def test_record_event_writes_the_six_specified_fields(tmp_path, iso_utc):
    """Section C6 fixes the event shape."""
    event = audit.record_event(
        tmp_path, "fraud_detector", "TXN002", "held", "m-1", "ACC-****02 -> ACC-****01"
    )

    assert set(event) == {
        "timestamp",
        "agent",
        "transaction_id",
        "outcome",
        "message_id",
        "detail",
    }
    assert event["agent"] == "fraud_detector"
    assert event["transaction_id"] == "TXN002"
    assert event["outcome"] == "held"
    assert event["message_id"] == "m-1"
    assert iso_utc.match(event["timestamp"])


def test_record_event_appends_one_line_per_call(tmp_path):
    """The trail grows; it is never truncated or rewritten by a later event."""
    audit.record_event(tmp_path, "integrator", "TXN001", "received", "m-1")
    audit.record_event(tmp_path, "transaction_validator", "TXN001", "validated", "m-2")

    lines = audit.audit_path(tmp_path).read_text(encoding="utf-8").splitlines()

    assert len(lines) == 2
    assert json.loads(lines[0])["outcome"] == "received"
    assert json.loads(lines[1])["outcome"] == "validated"


def test_record_event_creates_the_shared_directory_when_absent(tmp_path):
    """The first event of a run must not fail on a missing shared/ tree."""
    audit.record_event(tmp_path, "integrator", "TXN001", "received", "m-1")
    assert audit.audit_path(tmp_path).is_file()


def test_no_unmasked_account_reaches_the_audit_file(tmp_path):
    """Section C7: the audit log carries masked accounts only."""
    audit.record_event(
        tmp_path,
        "integrator",
        "TXN001",
        "received",
        "m-1",
        detail="routing ACC-1001 -> ACC-2001",
    )

    text = audit.audit_path(tmp_path).read_text(encoding="utf-8")

    assert "ACC-1001" not in text
    assert "ACC-2001" not in text
    assert "ACC-****01" in text


def test_detail_is_null_when_the_caller_supplies_none(tmp_path):
    """An event without a detail records an explicit null, not the string 'None'."""
    event = audit.record_event(tmp_path, "integrator", "TXN001", "received", "m-1")
    assert event["detail"] is None
    assert audit.read_events(tmp_path)[0]["detail"] is None


def test_read_events_returns_empty_before_any_run(tmp_path):
    """No log file means no events, not an exception."""
    assert audit.read_events(tmp_path) == []


def test_read_events_parses_every_line_back(tmp_path):
    """The trail round-trips through JSON Lines."""
    audit.record_event(tmp_path, "integrator", "TXN001", "received", "m-1")
    audit.record_event(tmp_path, "settlement_processor", "TXN001", "settled", "m-2")

    events = audit.read_events(tmp_path)

    assert [event["outcome"] for event in events] == ["received", "settled"]
    assert [event["agent"] for event in events] == [
        "integrator",
        "settlement_processor",
    ]


def test_read_events_skips_blank_lines(tmp_path):
    """A stray newline in the log is not a parse failure."""
    path = audit.audit_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"outcome": "settled"}\n\n   \n', encoding="utf-8")

    assert audit.read_events(tmp_path) == [{"outcome": "settled"}]
