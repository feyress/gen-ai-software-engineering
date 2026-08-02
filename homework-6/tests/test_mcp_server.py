"""Tests for the FastMCP server over the pipeline results.

The module is loaded by file path because `mcp/` is deliberately not a package.
`PROJECT_ROOT` is redirected at the module level so no test reads the real
`shared/` tree, and the async client is driven from synchronous tests.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest
from fastmcp import Client

from agents import mailbox, results_store
from agents.envelope import MessageType, Status, build_envelope

SERVER_PATH = Path(__file__).resolve().parent.parent / "mcp" / "server.py"
PROJECT_ROOT = SERVER_PATH.parent.parent


def _load_server(name: str):
    spec = importlib.util.spec_from_file_location(name, SERVER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


server = _load_server("pipeline_mcp_server")


def _call_tool(name: str, arguments: dict):
    async def _run():
        async with Client(server.mcp) as client:
            return await client.call_tool(name, arguments)

    return asyncio.run(_run())


def _read_resource(uri: str) -> str:
    async def _run():
        async with Client(server.mcp) as client:
            return await client.read_resource(uri)

    return asyncio.run(_run())[0].text


@pytest.fixture
def served_root(pipeline_root, monkeypatch):
    """Point the server at a temporary root holding one settled and one held result."""
    directory = results_store.results_dir(pipeline_root)
    mailbox.write_message(
        directory,
        "TXN004.json",
        build_envelope(
            "settlement_processor",
            "results",
            MessageType.RESULT,
            {
                "transaction_id": "TXN004",
                "status": Status.SETTLED,
                "risk_score": 45,
                "risk_level": "medium",
                "settled_amount": "540.00",
                "source_account": "ACC-1004",
            },
        ),
    )
    mailbox.write_message(
        directory,
        "TXN005.json",
        build_envelope(
            "fraud_detector",
            "results",
            MessageType.RESULT,
            {
                "transaction_id": "TXN005",
                "status": Status.HELD,
                "risk_score": 85,
                "risk_level": "high",
                "reason": "manual_review_required",
            },
        ),
    )
    mailbox.write_message(
        directory,
        mailbox.SUMMARY_FILENAME,
        {"total_transactions": 2, "settled_total_base": "540.00"},
    )
    monkeypatch.setattr(server, "PROJECT_ROOT", pipeline_root)
    return pipeline_root


@pytest.fixture
def empty_served_root(pipeline_root, monkeypatch):
    """Point the server at a root where no run has completed."""
    monkeypatch.setattr(server, "PROJECT_ROOT", pipeline_root)
    return pipeline_root


def test_the_server_is_named_pipeline_status():
    """The name is what an MCP client lists the server under."""
    assert server.mcp.name == "pipeline-status"


def test_the_server_resolves_the_project_root_from_its_own_location(monkeypatch):
    """It must import `agents` whatever working directory it was launched from."""
    monkeypatch.setattr(
        sys, "path", [entry for entry in sys.path if entry != str(PROJECT_ROOT)]
    )

    reloaded = _load_server("pipeline_mcp_server_reloaded")

    assert reloaded.PROJECT_ROOT == PROJECT_ROOT
    assert str(PROJECT_ROOT) in sys.path


def test_get_transaction_status_answers_a_known_transaction(served_root):
    """The tool returns the results-store projection with a found flag."""
    result = _call_tool("get_transaction_status", {"transaction_id": "TXN004"})

    assert result.data == {
        "found": True,
        "transaction_id": "TXN004",
        "status": "settled",
        "risk_score": 45,
        "risk_level": "medium",
        "reason": None,
        "settled_amount": "540.00",
    }


def test_get_transaction_status_answers_a_held_transaction(served_root):
    """A held transaction reports its reason and no settled amount."""
    result = _call_tool("get_transaction_status", {"transaction_id": "TXN005"})

    assert result.data["status"] == "held"
    assert result.data["reason"] == "manual_review_required"
    assert result.data["settled_amount"] is None


def test_get_transaction_status_never_invents_a_status(served_root):
    """An unknown transaction comes back as `found: false`, not as a status."""
    result = _call_tool("get_transaction_status", {"transaction_id": "TXN999"})

    assert result.data == {"found": False, "transaction_id": "TXN999"}
    assert "status" not in result.data


def test_get_transaction_status_exposes_no_account_number(served_root):
    """The stored envelope holds ACC-1004; the tool response must not."""
    result = _call_tool("get_transaction_status", {"transaction_id": "TXN004"})

    assert "ACC-1004" not in json.dumps(result.data)


def test_list_pipeline_results_returns_every_result_sorted(served_root):
    """The listing counts the results and projects one compact record each."""
    result = _call_tool("list_pipeline_results", {})

    assert result.data["total"] == 2
    assert [record["transaction_id"] for record in result.data["results"]] == [
        "TXN004",
        "TXN005",
    ]
    assert set(result.data["results"][0]) == set(results_store.PROJECTION_FIELDS)


def test_list_pipeline_results_is_empty_before_any_run(empty_served_root):
    """No results means a total of zero, not an error."""
    result = _call_tool("list_pipeline_results", {})

    assert result.data == {"total": 0, "results": []}


def test_the_summary_resource_returns_the_latest_run(served_root):
    """`pipeline://summary` serves the summary the reporting agent produced."""
    payload = json.loads(_read_resource("pipeline://summary"))

    assert payload == {"total_transactions": 2, "settled_total_base": "540.00"}


def test_the_summary_resource_says_so_when_no_run_has_completed(empty_served_root):
    """A reader gets a plain explanation rather than an empty document."""
    text = _read_resource("pipeline://summary")

    assert "No pipeline run has completed yet." in text
