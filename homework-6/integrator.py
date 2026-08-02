"""Orchestrator: seeds the run, drives the agents in order, writes the summary.

Governed by specification.md sections B1, C1, C8 and D. This is the only module
that knows the pipeline order and the only one that writes to stdout. Every
transaction is processed inside its own guard, so one bad record can never stop
the other seven, and every account number printed here is masked.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path

from agents import (
    audit,
    compliance_checker,
    fraud_detector,
    mailbox,
    reporting_agent,
    results_store,
    settlement_processor,
    transaction_validator,
)
from agents.envelope import (
    MessageType,
    Reason,
    Status,
    build_envelope,
    mask_account,
    mask_accounts,
)

AGENT_NAME = "integrator"

PIPELINE: tuple[tuple[str, Callable[[dict], dict]], ...] = (
    ("transaction_validator", transaction_validator.process_message),
    ("fraud_detector", fraud_detector.process_message),
    ("compliance_checker", compliance_checker.process_message),
    ("settlement_processor", settlement_processor.process_message),
)

DEFAULT_SOURCE = Path("sample-transactions.json")


def run(root: Path = Path("."), source: Path = DEFAULT_SOURCE) -> dict:
    """Run the whole pipeline under `root` and return the summary payload."""
    root = Path(root)
    mailbox.ensure_directories(root)
    records = _load_records(root, source)

    print("Multi-agent banking transaction pipeline")
    print(f"  root:   {root.resolve()}")
    print(f"  source: {source}")
    print()

    seeded = _seed(root, records)
    print(f"seeded {seeded} transaction(s) into shared/input/")

    stage_dir = mailbox.shared_root(root) / "input"
    for agent_name, handler in PIPELINE:
        handled = _run_stage(root, stage_dir, agent_name, handler)
        print(f"  {agent_name:<22} processed {handled}")
        stage_dir = mailbox.shared_root(root) / "output"

    results = results_store.list_results(root)
    summary = _write_summary(root, results)
    _print_report(results, summary)
    return summary


def _load_records(root: Path, source: Path) -> list[dict]:
    """Read the raw transaction records, resolving a relative source under `root`."""
    source_path = source if source.is_absolute() else root / source
    with source_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _seed(root: Path, records: list[dict]) -> int:
    """Write one received envelope per raw record into shared/input/."""
    input_dir = mailbox.shared_root(root) / "input"
    seeded = 0
    for index, record in enumerate(records):
        transaction_id = _identify(record, index)
        try:
            data = dict(record)
            data["status"] = Status.RECEIVED
            envelope = build_envelope(
                source_agent=AGENT_NAME,
                target_agent="transaction_validator",
                message_type=MessageType.TRANSACTION,
                data=data,
            )
            mailbox.write_message(input_dir, f"{transaction_id}.json", envelope)
            audit.record_event(
                root,
                AGENT_NAME,
                transaction_id,
                Status.RECEIVED,
                envelope["message_id"],
                _audit_detail(data),
            )
            seeded += 1
        except Exception as error:
            _fail_transaction(root, AGENT_NAME, transaction_id, error, None)
    return seeded


def _run_stage(
    root: Path,
    source_dir: Path,
    agent_name: str,
    handler: Callable[[dict], dict],
) -> int:
    """Drive every message waiting in `source_dir` through one agent."""
    processing_dir = mailbox.shared_root(root) / "processing"
    handled = 0
    for path in mailbox.list_messages(source_dir):
        transaction_id = path.stem
        claimed: Path | None = None
        try:
            claimed = mailbox.claim(source_dir, processing_dir, path.name)
            outgoing = handler(mailbox.read_message(claimed))
            data = outgoing["data"]
            # The event is written after delivery so the trail records status
            # changes that actually landed, exactly one line each.
            mailbox.deliver(root, outgoing, claimed)
            audit.record_event(
                root,
                agent_name,
                data.get("transaction_id", transaction_id),
                data["status"],
                outgoing["message_id"],
                _audit_detail(data),
            )
            handled += 1
        except Exception as error:
            _fail_transaction(root, agent_name, transaction_id, error, claimed)
    return handled


def _fail_transaction(
    root: Path,
    agent_name: str,
    transaction_id: str,
    error: Exception,
    claimed: Path | None,
) -> None:
    """Fail one transaction closed, with a typed reason, leaving the run intact."""
    data = _recover_data(claimed)
    data["transaction_id"] = data.get("transaction_id") or transaction_id
    data["status"] = Status.REJECTED
    data["reason"] = Reason.MISSING_FIELD
    data["reason_detail"] = mask_accounts(
        f"{agent_name} could not process this transaction: "
        f"{type(error).__name__}: {error}"
    )
    envelope = build_envelope(
        source_agent=agent_name,
        target_agent="results",
        message_type=MessageType.RESULT,
        data=data,
    )
    mailbox.write_message(
        results_store.results_dir(root), f"{data['transaction_id']}.json", envelope
    )
    audit.record_event(
        root,
        agent_name,
        data["transaction_id"],
        Status.REJECTED,
        envelope["message_id"],
        data["reason_detail"],
    )
    if claimed is not None:
        claimed.unlink(missing_ok=True)
    print(f"  ! {data['transaction_id']} failed in {agent_name}: {data['reason_detail']}")


def _audit_detail(data: dict) -> str:
    """Describe a status change for the audit trail, counterparties masked.

    Specification C7 requires the masked form to be what appears in the audit
    log, so the route is carried here rather than left to the result files.
    """
    route = (
        f"{mask_account(data.get('source_account', ''))} -> "
        f"{mask_account(data.get('destination_account', ''))}"
    )
    reason = data.get("reason")
    return f"{route} ({reason})" if reason else route


def _recover_data(claimed: Path | None) -> dict:
    """Return the payload of a claimed message, or an empty payload if unreadable."""
    if claimed is None:
        return {}
    try:
        return dict(mailbox.read_message(claimed).get("data", {}))
    except (OSError, json.JSONDecodeError, mailbox.MailboxError):
        return {}


def _identify(record: object, index: int) -> str:
    """Return a usable file name for a raw record, even one with no id of its own."""
    if isinstance(record, dict):
        candidate = record.get("transaction_id")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return f"UNIDENTIFIED-{index:03d}"


def _write_summary(root: Path, results: list[dict]) -> dict:
    """Build the run summary and write it to shared/results/pipeline-summary.json."""
    envelope = reporting_agent.process_message(
        build_envelope(
            source_agent=AGENT_NAME,
            target_agent="reporting_agent",
            message_type=MessageType.SUMMARY,
            data={"results": results},
        )
    )
    summary = envelope["data"]
    mailbox.write_message(
        results_store.results_dir(root), mailbox.SUMMARY_FILENAME, summary
    )
    return summary


def _print_report(results: list[dict], summary: dict) -> None:
    """Print one line per transaction and the run tally, with accounts masked."""
    print()
    print(
        f"  {'id':<8}{'status':<10}{'score':>5} {'risk':<8}"
        f"{'amount':>14}     {'settled USD':>12}  {'reason':<24}route"
    )
    for envelope in results:
        print(_result_line(envelope.get("data", {})))

    counts = summary["counts_by_status"]
    print()
    print(
        "totals by status: "
        + ", ".join(f"{status} {count}" for status, count in sorted(counts.items()))
    )
    print(
        "settled by currency: "
        + (
            ", ".join(
                f"{currency} {total}"
                for currency, total in summary["settled_totals_by_currency"].items()
            )
            or "none"
        )
    )
    print(f"settled total in USD base: {summary['settled_total_base']}")
    exceptions = summary["exceptions"]
    print(f"exceptions: {len(exceptions)}")
    for entry in exceptions:
        print(f"  {entry['transaction_id']} {entry['status']} {entry['reason']}")


def _result_line(data: dict) -> str:
    """Format one terminal outcome for stdout."""
    score = data.get("risk_score")
    settled = data.get("settled_amount")
    amount = f"{data.get('amount', '-')} {data.get('currency', '')}".strip()
    route = (
        f"{mask_account(data.get('source_account', ''))} -> "
        f"{mask_account(data.get('destination_account', ''))}"
    )
    return (
        f"  {data.get('transaction_id', '-'):<8}"
        f"{data.get('status', '-'):<10}"
        f"{'-' if score is None else score:>5} "
        f"{data.get('risk_level') or '-':<8}"
        f"{amount:>14}     "
        f"{settled or '-':>12}  "
        f"{data.get('reason') or '-':<24}"
        f"{route}"
    )


def main() -> int:
    """Run the pipeline from the current directory and report the exit status."""
    try:
        run()
    except (OSError, json.JSONDecodeError) as error:
        print(f"pipeline could not start: {type(error).__name__}: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
