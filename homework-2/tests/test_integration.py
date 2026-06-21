"""End-to-end integration tests (5 tests)."""
import io

from tests.conftest import create_ticket, read_fixture


def test_full_ticket_lifecycle(client, valid_payload):
    created = create_ticket(client, valid_payload)
    tid = created["id"]
    # progress through statuses
    client.put(f"/tickets/{tid}", json={"status": "in_progress",
                                         "assigned_to": "agent-1"})
    resolved = client.put(f"/tickets/{tid}", json={"status": "resolved"}).get_json()
    assert resolved["resolved_at"] is not None
    assert resolved["assigned_to"] == "agent-1"
    assert client.delete(f"/tickets/{tid}").status_code == 204
    assert client.get(f"/tickets/{tid}").status_code == 404


def test_bulk_import_with_auto_classification(client):
    data = {"file": (io.BytesIO(read_fixture("valid_tickets.csv").encode()),
                     "valid_tickets.csv")}
    resp = client.post("/tickets/import?auto_classify=true", data=data,
                       content_type="multipart/form-data")
    assert resp.status_code == 201
    # Every imported ticket should now carry a classification.
    for ticket in client.get("/tickets").get_json():
        assert ticket["classification"] is not None
        assert ticket["classification"]["category"] in {
            "account_access", "billing_question", "technical_issue",
            "feature_request", "bug_report", "other",
        }


def test_combined_category_and_priority_filter(client, valid_payload):
    a = create_ticket(client, valid_payload)
    client.put(f"/tickets/{a['id']}",
               json={"category": "billing_question", "priority": "high"})
    b = create_ticket(client, valid_payload)
    client.put(f"/tickets/{b['id']}",
               json={"category": "billing_question", "priority": "low"})
    resp = client.get("/tickets?category=billing_question&priority=high")
    body = resp.get_json()
    assert len(body) == 1
    assert body[0]["id"] == a["id"]


def test_concurrent_ticket_creation(client, valid_payload):
    import threading
    results = []

    def worker():
        resp = client.post("/tickets", json=valid_payload)
        results.append(resp.status_code)

    threads = [threading.Thread(target=worker) for _ in range(25)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 25
    assert all(code == 201 for code in results)
    assert len(client.get("/tickets").get_json()) == 25


def test_multi_format_import_accumulates(client):
    for name, fmt in (("valid_tickets.csv", "csv"),
                      ("valid_tickets.json", "json"),
                      ("valid_tickets.xml", "xml")):
        data = {"file": (io.BytesIO(read_fixture(name).encode()), name)}
        client.post("/tickets/import", data=data,
                    content_type="multipart/form-data")
    # 3 (csv) + 2 (json) + 2 (xml)
    assert len(client.get("/tickets").get_json()) == 7
