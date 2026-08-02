"""Tests for the file-based transport layer.

Covers specification.md section C8: atomic writes, claiming, routing by terminal
status, and the single-place exclusion of `pipeline-summary.json`.
"""

from __future__ import annotations

import json

import pytest

from agents import mailbox
from agents.envelope import Status


def _envelope(transaction_id: str, status: str) -> dict:
    return {
        "message_id": "m-1",
        "timestamp": "2026-03-16T10:00:00Z",
        "source_agent": "upstream",
        "target_agent": "downstream",
        "message_type": "transaction",
        "data": {"transaction_id": transaction_id, "status": status},
    }


def test_ensure_directories_creates_the_four_shared_subdirectories(tmp_path):
    """A fresh root gains input, processing, output and results under shared/."""
    mailbox.ensure_directories(tmp_path)
    for name in ("input", "processing", "output", "results"):
        assert (tmp_path / "shared" / name).is_dir()


def test_ensure_directories_is_idempotent(pipeline_root):
    """Running the pipeline twice must not fail on existing directories."""
    mailbox.ensure_directories(pipeline_root)
    assert (pipeline_root / "shared" / "input").is_dir()


def test_shared_root_points_at_the_shared_tree(tmp_path):
    """Every path in this module hangs off `<root>/shared`."""
    assert mailbox.shared_root(tmp_path) == tmp_path / "shared"


def test_write_message_leaves_no_temporary_file_behind(tmp_path):
    """The atomic write renames its `.tmp` away; a reader never sees a partial file."""
    written = mailbox.write_message(tmp_path, "TXN001.json", _envelope("TXN001", "held"))

    assert written == tmp_path / "TXN001.json"
    assert written.is_file()
    assert list(tmp_path.glob("*.tmp")) == []


def test_write_message_creates_a_missing_destination_directory(tmp_path):
    """Delivery must not fail because the target directory has not been made yet."""
    target = tmp_path / "shared" / "results"
    written = mailbox.write_message(target, "TXN001.json", _envelope("TXN001", "settled"))
    assert written.is_file()


def test_write_message_serialises_indented_utf8_json(tmp_path):
    """Section 1 of agents.md fixes the on-disk format at UTF-8 JSON, indent 2."""
    mailbox.write_message(tmp_path, "TXN001.json", _envelope("TXN001", "settled"))
    text = (tmp_path / "TXN001.json").read_text(encoding="utf-8")

    assert text.startswith("{\n  ")
    assert json.loads(text)["data"]["transaction_id"] == "TXN001"


def test_write_message_replaces_an_existing_file(tmp_path):
    """A second write on the same name wins outright, with no residue."""
    mailbox.write_message(tmp_path, "TXN001.json", _envelope("TXN001", "validated"))
    mailbox.write_message(tmp_path, "TXN001.json", _envelope("TXN001", "settled"))

    assert mailbox.read_message(tmp_path / "TXN001.json")["data"]["status"] == "settled"
    assert list(tmp_path.glob("*.tmp")) == []


def test_read_message_round_trips_the_written_envelope(tmp_path):
    """What the mailbox writes is what it reads back."""
    original = _envelope("TXN004", "cleared")
    path = mailbox.write_message(tmp_path, "TXN004.json", original)
    assert mailbox.read_message(path) == original


def test_read_message_raises_a_named_error_for_a_missing_file(tmp_path):
    """A missing message is an error, not a silent None."""
    with pytest.raises(mailbox.MessageNotFoundError):
        mailbox.read_message(tmp_path / "absent.json")


def test_list_messages_sorts_by_name_and_skips_the_summary(tmp_path):
    """`pipeline-summary.json` is the one file in results/ that is not a result."""
    for name in ("TXN003.json", "TXN001.json", "TXN002.json"):
        mailbox.write_message(tmp_path, name, _envelope(name[:6], "settled"))
    mailbox.write_message(tmp_path, mailbox.SUMMARY_FILENAME, {"total": 3})
    (tmp_path / "notes.txt").write_text("ignored", encoding="utf-8")

    assert [path.name for path in mailbox.list_messages(tmp_path)] == [
        "TXN001.json",
        "TXN002.json",
        "TXN003.json",
    ]


def test_list_messages_returns_empty_for_a_directory_that_does_not_exist(tmp_path):
    """A stage with nothing waiting is empty, not an error."""
    assert mailbox.list_messages(tmp_path / "never-created") == []


def test_claim_moves_the_message_into_processing(pipeline_root):
    """An interrupted run leaves the in-flight transaction visible in processing/."""
    shared = mailbox.shared_root(pipeline_root)
    mailbox.write_message(shared / "input", "TXN001.json", _envelope("TXN001", "received"))

    claimed = mailbox.claim(shared / "input", shared / "processing", "TXN001.json")

    assert claimed == shared / "processing" / "TXN001.json"
    assert claimed.is_file()
    assert not (shared / "input" / "TXN001.json").exists()


def test_claim_raises_when_there_is_nothing_to_claim(pipeline_root):
    """Claiming an absent message fails loudly rather than inventing one."""
    shared = mailbox.shared_root(pipeline_root)
    with pytest.raises(mailbox.MessageNotFoundError):
        mailbox.claim(shared / "input", shared / "processing", "TXN999.json")


@pytest.mark.parametrize(
    "status", [Status.REJECTED, Status.HELD, Status.BLOCKED, Status.SETTLED]
)
def test_deliver_routes_a_terminal_status_to_results(pipeline_root, status):
    """Section C8: terminal outcomes land in shared/results/."""
    shared = mailbox.shared_root(pipeline_root)
    claimed = mailbox.write_message(
        shared / "processing", "TXN001.json", _envelope("TXN001", status)
    )

    written = mailbox.deliver(pipeline_root, _envelope("TXN001", status), claimed)

    assert written == shared / "results" / "TXN001.json"
    assert not claimed.exists()
    assert not (shared / "output" / "TXN001.json").exists()


@pytest.mark.parametrize(
    "status", [Status.RECEIVED, Status.VALIDATED, Status.RISK_SCORED, Status.CLEARED]
)
def test_deliver_routes_a_non_terminal_status_to_output(pipeline_root, status):
    """Anything still in flight waits in shared/output/ for the next agent."""
    shared = mailbox.shared_root(pipeline_root)
    claimed = mailbox.write_message(
        shared / "processing", "TXN001.json", _envelope("TXN001", status)
    )

    written = mailbox.deliver(pipeline_root, _envelope("TXN001", status), claimed)

    assert written == shared / "output" / "TXN001.json"
    assert not claimed.exists()
    assert not (shared / "results" / "TXN001.json").exists()


def test_deliver_removes_the_claimed_file_even_when_it_is_already_gone(pipeline_root):
    """Releasing a claim twice is not an error the orchestrator needs to handle."""
    shared = mailbox.shared_root(pipeline_root)
    claimed = shared / "processing" / "TXN001.json"

    written = mailbox.deliver(pipeline_root, _envelope("TXN001", "settled"), claimed)

    assert written.is_file()


def test_deliver_refuses_an_envelope_with_no_transaction_id(pipeline_root):
    """There is no file name to route on, so the mailbox raises instead of guessing."""
    envelope = _envelope("TXN001", "settled")
    del envelope["data"]["transaction_id"]

    with pytest.raises(mailbox.MailboxError):
        mailbox.deliver(pipeline_root, envelope, pipeline_root / "claimed.json")


def test_message_not_found_is_a_mailbox_error():
    """One exception family, so a caller can catch the whole transport layer."""
    assert issubclass(mailbox.MessageNotFoundError, mailbox.MailboxError)
    assert issubclass(mailbox.MailboxError, RuntimeError)
