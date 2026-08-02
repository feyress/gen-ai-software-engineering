#!/usr/bin/env python3
"""Optional Claude Code PostToolUse hook: log every file the agent writes.

An audit trail for the meta-agents, mirroring what the pipeline does for
transactions. Appends one JSON line per Write or Edit to
``docs/meta-agent-runs/tool-audit.jsonl`` and never blocks: a hook that can fail
a session over its own logging is worse than no hook.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_PATH = PROJECT_ROOT / "docs" / "meta-agent-runs" / "tool-audit.jsonl"


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        target = payload.get("tool_input", {}).get("file_path", "")
        event = {
            "timestamp": datetime.now(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "tool": payload.get("tool_name", "unknown"),
            "file": _relative(target),
        }
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event) + "\n")
    except Exception as error:  # noqa: BLE001 - see module docstring
        print(f"audit-hook: skipped ({error})", file=sys.stderr)
    return 0


def _relative(target: str) -> str:
    """Return `target` relative to the project root when it sits inside it."""
    if not target:
        return ""
    try:
        return str(Path(target).resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return target


if __name__ == "__main__":
    sys.exit(main())
