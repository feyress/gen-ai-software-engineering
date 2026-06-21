"""JSON parsing and import tests (5 tests)."""
import io

import pytest

from src import importers
from tests.conftest import read_fixture


def test_parse_json_array():
    records = importers.parse_json(read_fixture("valid_tickets.json"))
    assert len(records) == 2
    assert records[0]["customer_id"] == "CUST-300"


def test_parse_json_accepts_tickets_wrapper():
    text = '{"tickets": [{"customer_id": "X"}]}'
    assert importers.parse_json(text) == [{"customer_id": "X"}]


def test_parse_malformed_json_raises():
    with pytest.raises(importers.ImportError_):
        importers.parse_json(read_fixture("malformed.json"))


def test_parse_json_non_array_raises():
    with pytest.raises(importers.ImportError_):
        importers.parse_json('{"not": "a ticket list"}')


def test_import_endpoint_json_raw_body(client):
    resp = client.post("/tickets/import?format=json",
                       data=read_fixture("valid_tickets.json"),
                       content_type="application/json")
    assert resp.status_code == 201
    summary = resp.get_json()
    assert summary["successful"] == 2
    assert summary["format"] == "json"
