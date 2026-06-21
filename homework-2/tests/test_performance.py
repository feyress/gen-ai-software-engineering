"""Performance / benchmark tests (5 tests).

These assert generous upper bounds — they guard against accidental quadratic
blow-ups rather than pin exact timings.
"""
import io
import time

from src.classifier import classify
from tests.conftest import read_fixture


def _make_csv(n):
    header = ("customer_id,customer_email,customer_name,subject,description,"
              "tags,metadata_source,metadata_device_type\n")
    rows = "".join(
        f"CUST-{i},user{i}@example.com,User {i},Subject line {i},"
        f"This is description number {i} which is comfortably long enough.,"
        f"tag{i},web_form,desktop\n"
        for i in range(n)
    )
    return header + rows


def test_bulk_import_500_under_2s(client):
    data = {"file": (io.BytesIO(_make_csv(500).encode()), "big.csv")}
    start = time.perf_counter()
    resp = client.post("/tickets/import", data=data,
                       content_type="multipart/form-data")
    elapsed = time.perf_counter() - start
    assert resp.status_code == 201
    assert resp.get_json()["successful"] == 500
    assert elapsed < 2.0


def test_classify_throughput():
    start = time.perf_counter()
    for _ in range(1000):
        classify("Cannot access account", "Password reset failing, this is critical.")
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0


def test_list_after_many_inserts_is_fast(client, valid_payload):
    for _ in range(200):
        client.post("/tickets", json=valid_payload)
    start = time.perf_counter()
    resp = client.get("/tickets")
    elapsed = time.perf_counter() - start
    assert resp.status_code == 200
    assert len(resp.get_json()) == 200
    assert elapsed < 0.5


def test_filter_scales(client, valid_payload):
    for _ in range(200):
        client.post("/tickets", json=valid_payload)
    start = time.perf_counter()
    client.get("/tickets?status=new")
    assert time.perf_counter() - start < 0.5


def test_get_by_id_lookup_fast(client, valid_payload):
    created = client.post("/tickets", json=valid_payload).get_json()
    for _ in range(200):
        client.post("/tickets", json=valid_payload)
    start = time.perf_counter()
    resp = client.get(f"/tickets/{created['id']}")
    assert resp.status_code == 200
    assert time.perf_counter() - start < 0.2
