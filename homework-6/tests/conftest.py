"""Shared fixtures for the pipeline suite.

Every fixture that touches the filesystem is rooted in `tmp_path`, so no test
reads or writes the real `shared/` tree. The sample data is read once, and each
test receives a deep copy it is free to mutate.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from agents import (
    compliance_checker,
    fraud_detector,
    mailbox,
    settlement_processor,
    transaction_validator,
)
from agents.envelope import TERMINAL_STATUSES, MessageType, Status, build_envelope

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_TRANSACTIONS = PROJECT_ROOT / "sample-transactions.json"

_RAW_RECORDS = json.loads(SAMPLE_TRANSACTIONS.read_text(encoding="utf-8"))
_RECORDS_BY_ID = {record["transaction_id"]: record for record in _RAW_RECORDS}

_ISO_UTC_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

AGENT_CHAIN = (
    transaction_validator,
    fraud_detector,
    compliance_checker,
    settlement_processor,
)


@pytest.fixture
def iso_utc() -> re.Pattern[str]:
    """The shape a timestamp produced by `utc_now_iso()` must have."""
    return _ISO_UTC_PATTERN


@pytest.fixture
def sample_record():
    """Factory returning a mutable deep copy of one raw sample record."""

    def _record(transaction_id: str = "TXN001", /, **overrides: object) -> dict:
        record = copy.deepcopy(_RECORDS_BY_ID[transaction_id])
        record.update(overrides)
        return record

    return _record


@pytest.fixture
def sample_records() -> list[dict]:
    """A deep copy of all eight raw sample records, in file order."""
    return copy.deepcopy(_RAW_RECORDS)


@pytest.fixture
def make_envelope():
    """Factory building an envelope around a payload, optionally forcing a status."""

    def _make(
        data: dict,
        *,
        status: str | None = None,
        source_agent: str = "integrator",
        target_agent: str = "transaction_validator",
        message_type: str = MessageType.TRANSACTION,
        message_id: str | None = None,
    ) -> dict:
        payload = copy.deepcopy(data)
        if status is not None:
            payload["status"] = status
        return build_envelope(
            source_agent, target_agent, message_type, payload, message_id
        )

    return _make


@pytest.fixture
def drive_agents():
    """Factory running one raw record through the agent chain purely in memory."""

    def _drive(record: dict) -> dict:
        payload = dict(copy.deepcopy(record))
        payload["status"] = Status.RECEIVED
        envelope = build_envelope(
            "integrator", "transaction_validator", MessageType.TRANSACTION, payload
        )
        for agent in AGENT_CHAIN:
            envelope = agent.process_message(envelope)
            if envelope["data"]["status"] in TERMINAL_STATUSES:
                break
        return envelope

    return _drive


@pytest.fixture
def terminal_envelopes(sample_records, drive_agents) -> list[dict]:
    """The eight terminal envelopes the sample data produces, without file I/O."""
    return [drive_agents(record) for record in sample_records]


@pytest.fixture
def pipeline_root(tmp_path) -> Path:
    """An isolated project root with the four `shared/` subdirectories created."""
    mailbox.ensure_directories(tmp_path)
    return tmp_path


@pytest.fixture
def sample_source(tmp_path) -> Path:
    """A copy of `sample-transactions.json` inside the temporary root."""
    destination = tmp_path / SAMPLE_TRANSACTIONS.name
    destination.write_text(
        SAMPLE_TRANSACTIONS.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return destination
