"""XML parsing and import tests (5 tests)."""
import io

import pytest

from src import importers
from tests.conftest import read_fixture


def test_parse_xml_returns_records():
    records = importers.parse_xml(read_fixture("valid_tickets.xml"))
    assert len(records) == 2
    assert records[0]["customer_id"] == "CUST-400"


def test_parse_xml_nests_metadata_and_tags():
    first = importers.parse_xml(read_fixture("valid_tickets.xml"))[0]
    assert first["metadata"]["source"] == "email"
    assert first["tags"] == ["billing", "refund"]


def test_parse_malformed_xml_raises():
    with pytest.raises(importers.ImportError_):
        importers.parse_xml(read_fixture("malformed.xml"))


def test_parse_xml_without_tickets_raises():
    with pytest.raises(importers.ImportError_):
        importers.parse_xml("<root></root>")


def test_import_endpoint_xml_upload(client):
    data = {"file": (io.BytesIO(read_fixture("valid_tickets.xml").encode()),
                     "valid_tickets.xml")}
    resp = client.post("/tickets/import", data=data,
                       content_type="multipart/form-data")
    assert resp.status_code == 201
    assert resp.get_json()["successful"] == 2
