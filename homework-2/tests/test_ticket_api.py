"""API endpoint tests (11 tests)."""
from tests.conftest import create_ticket


def test_create_ticket_returns_201(client, valid_payload):
    resp = client.post("/tickets", json=valid_payload)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["id"]
    assert body["status"] == "new"


def test_create_ticket_validation_error_returns_400(client):
    resp = client.post("/tickets", json={"subject": "x"})
    assert resp.status_code == 400
    assert "details" in resp.get_json()


def test_create_ticket_missing_body_returns_400(client):
    resp = client.post("/tickets", data="not json",
                       content_type="application/json")
    assert resp.status_code == 400


def test_get_ticket_by_id(client, valid_payload):
    created = create_ticket(client, valid_payload)
    resp = client.get(f"/tickets/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["id"] == created["id"]


def test_get_missing_ticket_returns_404(client):
    resp = client.get("/tickets/does-not-exist")
    assert resp.status_code == 404


def test_list_tickets(client, valid_payload):
    create_ticket(client, valid_payload)
    create_ticket(client, valid_payload)
    resp = client.get("/tickets")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 2


def test_list_tickets_filter_by_status(client, valid_payload):
    created = create_ticket(client, valid_payload)
    client.put(f"/tickets/{created['id']}", json={"status": "resolved"})
    create_ticket(client, valid_payload)
    resp = client.get("/tickets?status=resolved")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 1


def test_update_ticket(client, valid_payload):
    created = create_ticket(client, valid_payload)
    resp = client.put(f"/tickets/{created['id']}", json={"status": "resolved"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "resolved"
    assert body["resolved_at"] is not None


def test_update_missing_ticket_returns_404(client):
    resp = client.put("/tickets/nope", json={"status": "closed"})
    assert resp.status_code == 404


def test_delete_ticket(client, valid_payload):
    created = create_ticket(client, valid_payload)
    resp = client.delete(f"/tickets/{created['id']}")
    assert resp.status_code == 204
    assert client.get(f"/tickets/{created['id']}").status_code == 404


def test_delete_missing_ticket_returns_404(client):
    assert client.delete("/tickets/nope").status_code == 404
