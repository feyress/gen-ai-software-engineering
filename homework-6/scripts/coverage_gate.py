#!/usr/bin/env python3
"""Coverage gate: measure test coverage and refuse a push below the threshold.

One implementation, two callers:

* ``--from-hook`` is the Claude Code ``PreToolUse`` hook. It reads the tool
  payload on stdin, ignores every Bash command that is not a ``git push``, and
  exits 2 to deny the call when coverage is short. Exit code 2 is what Claude
  Code treats as a block, and stderr is what it shows the model.
* ``--from-git`` is the ``pre-push`` git hook. Exit 1 aborts the push.

Both paths run the same measurement, so the gate cannot pass in one tool and
fail in the other. The threshold is 80 percent, overridable with the
``COVERAGE_MIN`` environment variable, which is how the block can be
demonstrated without weakening the real gate:

    COVERAGE_MIN=100 git push
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MINIMUM = 80.0

EXIT_ALLOW = 0
EXIT_GIT_BLOCK = 1
EXIT_HOOK_BLOCK = 2

# Claude Code hooks run with an inherited environment, so an interpreter is not
# guaranteed to be on PATH. The project venv is the one that has pytest-cov.
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"

_TOTAL_PATTERN = re.compile(r"^TOTAL\s+.*?(\d+(?:\.\d+)?)%\s*$", re.MULTILINE)


def minimum() -> float:
    """Return the coverage floor, from ``COVERAGE_MIN`` or the 80 percent default."""
    raw = os.environ.get("COVERAGE_MIN", "").strip()
    if not raw:
        return DEFAULT_MINIMUM
    try:
        return float(raw)
    except ValueError:
        print(
            f"coverage-gate: COVERAGE_MIN={raw!r} is not a number, "
            f"falling back to {DEFAULT_MINIMUM:.0f}",
            file=sys.stderr,
        )
        return DEFAULT_MINIMUM


def interpreter() -> str:
    """Return the interpreter to run pytest with, preferring the project venv."""
    return str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable


def measure() -> tuple[float | None, str]:
    """Run the suite under coverage and return the total percentage and the report."""
    completed = subprocess.run(
        [
            interpreter(),
            "-m",
            "pytest",
            "--cov",
            "--cov-report=term-missing",
            "-q",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    report = completed.stdout + completed.stderr

    if completed.returncode != 0:
        return None, report

    match = _TOTAL_PATTERN.search(report)
    if match is None:
        return None, report
    return float(match.group(1)), report


def is_git_push(payload: dict) -> bool:
    """Return True when a Claude Code tool payload is a Bash ``git push``."""
    if payload.get("tool_name") != "Bash":
        return False
    command = payload.get("tool_input", {}).get("command", "")
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()
    # Catches `git push`, `git -C dir push`, and a push chained after `&&`.
    for index, token in enumerate(tokens):
        if token == "git" and "push" in tokens[index + 1 :]:
            return True
    return False


def enforce(block_exit_code: int) -> int:
    """Measure coverage and return the process exit code for this caller."""
    floor = minimum()
    percent, report = measure()

    if percent is None:
        print(
            "coverage-gate: BLOCKED — the test suite did not complete, so coverage "
            "could not be measured. Push refused.\n",
            file=sys.stderr,
        )
        print(report[-4000:], file=sys.stderr)
        return block_exit_code

    if percent < floor:
        print(
            f"coverage-gate: BLOCKED — total test coverage is {percent:.2f}%, "
            f"below the required {floor:.2f}%.\n"
            f"Push refused. Add tests for the uncovered lines below, "
            f"then push again.\n",
            file=sys.stderr,
        )
        print(_coverage_table(report), file=sys.stderr)
        return block_exit_code

    print(
        f"coverage-gate: PASS — total test coverage is {percent:.2f}%, "
        f"at or above the required {floor:.2f}%.",
        file=sys.stderr,
    )
    return EXIT_ALLOW


def _coverage_table(report: str) -> str:
    """Return just the coverage table from a pytest report, for a readable message."""
    lines = report.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("Name") and "Cover" in line:
            return "\n".join(lines[index:])
    return report[-4000:]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--from-hook",
        action="store_true",
        help="Claude Code PreToolUse hook: read the tool payload on stdin.",
    )
    source.add_argument(
        "--from-git",
        action="store_true",
        help="git pre-push hook: always measure, exit 1 to abort the push.",
    )
    args = parser.parse_args(argv)

    if args.from_hook:
        raw = sys.stdin.read()
        try:
            payload = json.loads(raw) if raw.strip() else {}
        except json.JSONDecodeError:
            # A payload we cannot parse is not evidence of a push. Allow it
            # rather than blocking every Bash call in the session.
            return EXIT_ALLOW
        if not is_git_push(payload):
            return EXIT_ALLOW
        return enforce(EXIT_HOOK_BLOCK)

    return enforce(EXIT_GIT_BLOCK if args.from_git else EXIT_GIT_BLOCK)


if __name__ == "__main__":
    sys.exit(main())
