"""End-to-end tests for the orchestrator.

Runs all eight sample records through the real file-based transport under
`tmp_path` and asserts the outcome table of specification.md section D file by
file, plus the resilience and invariant rules of sections B1 and C2.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import integrator
from agents import (
    audit,
    compliance_checker,
    fraud_detector,
    mailbox,
    results_store,
    settlement_processor,
    transaction_validator,
)
from agents.envelope import STATUS, Status

SAMPLE_TRANSACTIONS = Path(__file__).resolve().parent.parent / "sample-transactions.json"

SECTION_D = [
    ("TXN001", "settled", 8, "low", None, "1500.00"),
    ("TXN002", "held", 70, "high", "manual_review_required", None),
    ("TXN003", "settled", 48, "medium", None, "9999.99"),
    ("TXN004", "settled", 45, "medium", None, "540.00"),
    ("TXN005", "held", 85, "high", "manual_review_required", None),
    ("TXN006", "rejected", None, None, "invalid_currency", None),
    ("TXN007", "rejected", None, None, "non_positive_amount", None),
    ("TXN008", "settled", 5, "low", None, "3200.00"),
]

STAGE_INPUT_STATUS = {
    transaction_validator: Status.RECEIVED,
    fraud_detector: Status.VALIDATED,
    compliance_checker: Status.RISK_SCORED,
    settlement_processor: Status.CLEARED,
}


def _write_source(root: Path, records: list) -> Path:
    source = root / "sample-transactions.json"
    source.write_text(json.dumps(records, indent=2), encoding="utf-8")
    return source


def _run_with(root: Path, records: list) -> dict:
    _write_source(root, records)
    return integrator.run(root=root, source=Path("sample-transactions.json"))


def _no_json_floats(text: str) -> object:
    def _reject(_: str) -> float:
        raise AssertionError("a JSON float reached a result file")

    return json.loads(text, parse_float=_reject)


@pytest.fixture(scope="module")
def completed_run(tmp_path_factory):
    """One clean run of the eight sample records inside a temporary root."""
    root = tmp_path_factory.mktemp("pipeline")
    (root / "sample-transactions.json").write_text(
        SAMPLE_TRANSACTIONS.read_text(encoding="utf-8"), encoding="utf-8"
    )
    summary = integrator.run(root=root, source=Path("sample-transactions.json"))
    return root, summary


@pytest.mark.parametrize(
    ("transaction_id", "status", "risk_score", "risk_level", "reason", "settled_amount"),
    SECTION_D,
)
def test_each_sample_record_ends_as_the_outcome_table_says(
    completed_run, transaction_id, status, risk_score, risk_level, reason, settled_amount
):
    """Section D is the acceptance criterion, asserted file by file."""
    root, _ = completed_run
    envelope = mailbox.read_message(
        results_store.results_dir(root) / f"{transaction_id}.json"
    )
    data = envelope["data"]

    assert data["status"] == status
    assert data.get("risk_score") == risk_score
    assert data.get("risk_level") == risk_level
    assert data.get("reason") == reason
    assert data.get("settled_amount") == settled_amount
    assert envelope["target_agent"] == "results"


def test_every_input_record_reaches_exactly_one_terminal_file(completed_run):
    """Section B1: eight records, eight results, plus the summary."""
    root, _ = completed_run
    results = results_store.results_dir(root)

    assert sorted(path.name for path in results.glob("*.json")) == [
        "TXN001.json",
        "TXN002.json",
        "TXN003.json",
        "TXN004.json",
        "TXN005.json",
        "TXN006.json",
        "TXN007.json",
        "TXN008.json",
        "pipeline-summary.json",
    ]


def test_the_working_directories_are_empty_when_the_run_ends(completed_run):
    """Section B1: nothing is left in flight."""
    root, _ = completed_run
    shared = mailbox.shared_root(root)

    for name in ("input", "processing", "output"):
        assert list((shared / name).glob("*.json")) == []
        assert list((shared / name).glob("*.tmp")) == []


def test_the_summary_reports_the_section_d_totals(completed_run):
    """Section B5 fixes every figure of the run summary."""
    _, summary = completed_run

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


def test_the_summary_names_the_four_exceptions_with_their_reasons(completed_run):
    """The exception list is the human-facing account of what did not settle."""
    _, summary = completed_run

    assert [(entry["transaction_id"], entry["reason"]) for entry in summary["exceptions"]] == [
        ("TXN002", "manual_review_required"),
        ("TXN005", "manual_review_required"),
        ("TXN006", "invalid_currency"),
        ("TXN007", "non_positive_amount"),
    ]


def test_the_summary_is_written_to_the_results_directory(completed_run):
    """The returned payload and the file on disk are the same document."""
    root, summary = completed_run
    assert results_store.latest_summary(root) == summary


def test_no_result_file_contains_a_json_float(completed_run):
    """Section B4: no float appears anywhere in the money path."""
    root, _ = completed_run
    for path in results_store.results_dir(root).glob("*.json"):
        _no_json_floats(path.read_text(encoding="utf-8"))


def test_every_status_change_is_audited_exactly_once(completed_run):
    """Eight seeds, eight validations, six scorings, four screenings, four settlements."""
    root, _ = completed_run
    events = audit.read_events(root)

    assert len(events) == 30
    assert [event["outcome"] for event in events].count("received") == 8
    assert [event["outcome"] for event in events].count("settled") == 4
    assert [event["outcome"] for event in events].count("held") == 2
    assert [event["outcome"] for event in events].count("rejected") == 2
    for event in events:
        assert event["outcome"] in STATUS
        assert event["message_id"]


def test_every_transaction_appears_in_the_audit_trail(completed_run):
    """A status change without a line in the trail is a defect."""
    root, _ = completed_run
    audited = {event["transaction_id"] for event in audit.read_events(root)}

    assert audited == {row[0] for row in SECTION_D}


def test_no_unmasked_account_reaches_the_audit_log(completed_run, sample_records):
    """Section C7: the audit log is a log, so it carries masked accounts only."""
    root, _ = completed_run
    text = audit.audit_path(root).read_text(encoding="utf-8")

    for record in sample_records:
        assert record["source_account"] not in text
        assert record["destination_account"] not in text
    assert "ACC-****01" in text


def test_no_unmasked_account_reaches_stdout(tmp_path, sample_records, capsys):
    """Section C7: every line the integrator prints uses the masked form."""
    _run_with(tmp_path, sample_records)
    printed = capsys.readouterr().out

    for record in sample_records:
        assert record["source_account"] not in printed
        assert record["destination_account"] not in printed
    assert "settled total in USD base: 15239.99" in printed


def test_a_record_with_a_numeric_amount_does_not_stop_the_others(
    tmp_path, sample_records
):
    """Section B1: a poisoned record fails closed and the other seven finish."""
    records = copy.deepcopy(sample_records)
    records[0]["amount"] = 1500.00

    summary = _run_with(tmp_path, records)
    poisoned = results_store.status_of(tmp_path, "TXN001")

    assert poisoned["status"] == "rejected"
    assert poisoned["reason"] == "malformed_amount"
    assert summary["counts_by_status"] == {
        "rejected": 3,
        "held": 2,
        "blocked": 0,
        "settled": 3,
    }
    assert summary["settled_total_base"] == "13739.99"


def test_a_record_without_a_transaction_id_does_not_stop_the_others(
    tmp_path, sample_records
):
    """An unroutable record is failed closed under a synthetic id."""
    orphan = copy.deepcopy(sample_records[0])
    del orphan["transaction_id"]
    records = [orphan] + copy.deepcopy(sample_records)

    summary = _run_with(tmp_path, records)
    recovered = results_store.status_of(tmp_path, "UNIDENTIFIED-000")

    assert recovered["status"] == "rejected"
    assert recovered["reason"] == "missing_field"
    assert summary["counts_by_status"]["settled"] == 4
    assert summary["counts_by_status"]["rejected"] == 3
    assert list((mailbox.shared_root(tmp_path) / "processing").glob("*.json")) == []


def test_a_record_that_is_not_an_object_does_not_stop_the_others(
    tmp_path, sample_records
):
    """The seeding guard catches a record the loader cannot even copy."""
    records = ["not-a-transaction"] + copy.deepcopy(sample_records)

    summary = _run_with(tmp_path, records)

    assert results_store.status_of(tmp_path, "UNIDENTIFIED-000")["status"] == "rejected"
    assert summary["counts_by_status"]["settled"] == 4


def test_a_sanctioned_destination_is_blocked_end_to_end(tmp_path, sample_records):
    """The `blocked` path no sample record reaches, driven through the real transport."""
    records = copy.deepcopy(sample_records)
    records[0]["destination_account"] = "ACC-4242"

    summary = _run_with(tmp_path, records)
    blocked = results_store.status_of(tmp_path, "TXN001")

    assert blocked["status"] == "blocked"
    assert blocked["reason"] == "sanctioned_counterparty"
    assert summary["counts_by_status"]["blocked"] == 1
    assert summary["settled_total_base"] == "13739.99"


def test_recovering_an_unreadable_claim_yields_an_empty_payload(tmp_path):
    """A failure guard must not fail; an unreadable claim degrades to no payload."""
    assert integrator._recover_data(tmp_path / "absent.json") == {}
    assert integrator._recover_data(None) == {}


def test_main_runs_the_pipeline_from_the_current_directory(
    tmp_path, sample_records, monkeypatch
):
    """The CLI entry point reports success and leaves the results behind it."""
    _write_source(tmp_path, sample_records)
    monkeypatch.chdir(tmp_path)

    assert integrator.main() == 0
    assert results_store.status_of(tmp_path, "TXN004")["settled_amount"] == "540.00"


def test_main_reports_failure_when_the_source_file_is_missing(tmp_path, monkeypatch):
    """A run that cannot start exits non-zero rather than raising."""
    monkeypatch.chdir(tmp_path)
    assert integrator.main() == 1


AGENT_IDS = [agent.AGENT_NAME for agent in STAGE_INPUT_STATUS]


@pytest.mark.parametrize("agent", list(STAGE_INPUT_STATUS), ids=AGENT_IDS)
def test_no_agent_mutates_its_input_envelope(agent, sample_record, make_envelope):
    """Section C2: a caller must be able to diff the input against the output."""
    incoming = make_envelope(sample_record("TXN004"), status=STAGE_INPUT_STATUS[agent])
    before = copy.deepcopy(incoming)

    agent.process_message(incoming)

    assert incoming == before


@pytest.mark.parametrize("agent", list(STAGE_INPUT_STATUS), ids=AGENT_IDS)
def test_no_agent_reuses_its_input_message_id(agent, sample_record, make_envelope):
    """Every hop mints a fresh identifier, so the trail cannot collide."""
    incoming = make_envelope(sample_record("TXN004"), status=STAGE_INPUT_STATUS[agent])
    outgoing = agent.process_message(incoming)

    assert outgoing["message_id"] != incoming["message_id"]
    assert outgoing["timestamp"]


def test_the_terminal_envelope_keeps_every_field_written_upstream(completed_run):
    """The result file is auditable because no agent dropped an upstream key."""
    root, _ = completed_run
    data = mailbox.read_message(results_store.results_dir(root) / "TXN004.json")["data"]

    assert data["risk_signals"] == ["channel_risk", "cross_border", "unusual_timing"]
    assert data["ctr_required"] is False
    assert data["settlement_reference"].startswith("SET-TXN004-")
    assert data["source_account"] == "ACC-1004"
