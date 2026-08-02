"""File-based transport: the only module permitted to touch the `shared/` tree.

Governed by specification.md section C8. This module decides which directory an
envelope belongs in — `shared/results/` for a terminal status, `shared/output/`
for anything still in flight — so no decision agent needs to know the layout.
Every write is atomic, so a reader never observes a partial JSON file.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from agents.envelope import TERMINAL_STATUSES

SUMMARY_FILENAME = "pipeline-summary.json"

_SUBDIRECTORIES = ("input", "processing", "output", "results")


class MailboxError(RuntimeError):
    """Raised when the mailbox cannot complete a transport operation."""


class MessageNotFoundError(MailboxError):
    """Raised when a message is expected on disk and is not there."""


def shared_root(root: Path) -> Path:
    """Return the `shared/` tree under `root`."""
    return Path(root) / "shared"


def ensure_directories(root: Path) -> None:
    """Create `shared/{input,processing,output,results}` under `root` if absent."""
    for name in _SUBDIRECTORIES:
        (shared_root(root) / name).mkdir(parents=True, exist_ok=True)


def write_message(directory: Path, name: str, message: dict) -> Path:
    """Write `message` as UTF-8 JSON at `directory/name`, atomically.

    The payload is serialised to a sibling `.tmp` file and flushed to the
    operating system before `os.replace` moves it onto the final name, so a
    concurrent reader sees either the previous file or the complete new one.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    final_path = directory / name
    temporary_path = directory / f"{name}.tmp"
    with temporary_path.open("w", encoding="utf-8") as handle:
        json.dump(message, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary_path, final_path)
    return final_path


def read_message(path: Path) -> dict:
    """Parse the JSON envelope at `path`, raising `MessageNotFoundError` if absent."""
    path = Path(path)
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as error:
        raise MessageNotFoundError(f"no message at {path}") from error


def list_messages(directory: Path) -> list[Path]:
    """Return the `.json` messages in `directory` sorted by name.

    `pipeline-summary.json` is skipped here, in one place, because it is the one
    file in `shared/results/` that is not a transaction result.
    """
    directory = Path(directory)
    if not directory.is_dir():
        return []
    return sorted(
        path
        for path in directory.glob("*.json")
        if path.name != SUMMARY_FILENAME and path.is_file()
    )


def claim(source_dir: Path, processing_dir: Path, name: str) -> Path:
    """Move `name` from `source_dir` into `processing_dir` before an agent runs.

    An interrupted run therefore leaves the in-flight transaction visible in
    `shared/processing/` rather than losing it.
    """
    source_path = Path(source_dir) / name
    if not source_path.is_file():
        raise MessageNotFoundError(f"nothing to claim at {source_path}")
    processing_dir = Path(processing_dir)
    processing_dir.mkdir(parents=True, exist_ok=True)
    claimed_path = processing_dir / name
    os.replace(source_path, claimed_path)
    return claimed_path


def deliver(root: Path, envelope: dict, claimed: Path) -> Path:
    """Route `envelope` by its status and release the claimed file.

    A terminal status lands in `shared/results/`, anything else in
    `shared/output/` for the agent named in `target_agent`.
    """
    data = envelope.get("data", {})
    transaction_id = data.get("transaction_id")
    if not transaction_id:
        raise MailboxError("envelope has no data.transaction_id to route on")
    destination = "results" if data.get("status") in TERMINAL_STATUSES else "output"
    written = write_message(
        shared_root(root) / destination, f"{transaction_id}.json", envelope
    )
    Path(claimed).unlink(missing_ok=True)
    return written
