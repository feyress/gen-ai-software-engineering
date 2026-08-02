"""FastMCP server exposing the pipeline results to an MCP client.

Governed by specification.md section C10 and TASKS.md Task 4. The server
decides nothing about a transaction: it answers questions about a finished run
through agents.results_store, which is the same read layer the reporting agent
uses, so account masking cannot drift between the two. An unknown transaction
is answered with `found: false` rather than a fabricated status, because
`status` is a closed set.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# fastmcp is imported before the project root joins sys.path so that its own
# `mcp` dependency resolves to the installed package rather than to the
# directory this file lives in, which is deliberately not a package.
from fastmcp import FastMCP

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from agents import results_store  # noqa: E402

mcp = FastMCP("pipeline-status")


@mcp.tool
def get_transaction_status(transaction_id: str) -> dict:
    """Return the pipeline outcome of one transaction.

    Answers with the transaction's status, risk score, risk level, rejection or
    hold reason, and settled amount, using null for anything it never acquired.
    A transaction that the pipeline has not processed comes back as
    `{"found": false}` — the server never guesses a status.
    """
    projection = results_store.status_of(PROJECT_ROOT, transaction_id)
    if projection is None:
        return {"found": False, "transaction_id": transaction_id}
    return {"found": True, **projection}


@mcp.tool
def list_pipeline_results() -> dict:
    """Return every transaction the last pipeline run produced a result for.

    Gives the total count and one compact record per transaction — id, status,
    risk score, risk level, reason and settled amount — sorted by transaction
    id. Account numbers are never part of this view.
    """
    records = [
        {
            field: envelope.get("data", {}).get(field)
            for field in results_store.PROJECTION_FIELDS
        }
        for envelope in results_store.list_results(PROJECT_ROOT)
    ]
    return {"total": len(records), "results": records}


@mcp.resource("pipeline://summary")
def pipeline_summary() -> str:
    """Return the latest pipeline run summary as formatted text.

    Contains the counts by status, the settled totals by currency, the settled
    total in the USD base currency, and the exceptions with their reasons. Says
    so plainly when no run has completed yet.
    """
    summary = results_store.latest_summary(PROJECT_ROOT)
    if summary is None:
        return (
            "No pipeline run has completed yet. "
            "Run `python integrator.py` to produce shared/results/pipeline-summary.json."
        )
    return json.dumps(summary, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
