"""CSV parsing and import tests (6 tests)."""
import io

import pytest

from src import importers
from tests.conftest import read_fixture


def test_parse_csv_returns_records():
    records = importers.parse_csv(read_fixture("valid_tickets.csv"))
    assert len(records) == 3
    assert records[0]["customer_id"] == "CUST-100"


def test_parse_csv_nests_metadata_and_tags():
    records = importers.parse_csv(read_fixture("valid_tickets.csv"))
    first = records[0]
    assert first["metadata"]["source"] == "email"
    assert first["metadata"]["device_type"] == "desktop"
    assert first["tags"] == ["login", "urgent"]


def test_parse_csv_skips_blank_rows():
    text = read_fixture("valid_tickets.csv") + "\n\n"
    assert len(importers.parse_csv(text)) == 3


def test_parse_empty_csv_raises():
    with pytest.raises(importers.ImportError_):
        importers.parse_csv("")


def test_import_endpoint_csv_upload(client):
    data = {"file": (io.BytesIO(read_fixture("valid_tickets.csv").encode()),
                     "valid_tickets.csv")}
    resp = client.post("/tickets/import", data=data,
                       content_type="multipart/form-data")
    assert resp.status_code == 201
    summary = resp.get_json()
    assert summary["total"] == 3
    assert summary["successful"] == 3
    assert summary["failed"] == 0


def test_import_endpoint_csv_reports_failures(client):
    data = {"file": (io.BytesIO(read_fixture("invalid_tickets.csv").encode()),
                     "invalid_tickets.csv")}
    resp = client.post("/tickets/import", data=data,
                       content_type="multipart/form-data")
    assert resp.status_code == 400
    summary = resp.get_json()
    assert summary["failed"] == 3
    assert summary["successful"] == 0
    assert len(summary["errors"]) == 3
