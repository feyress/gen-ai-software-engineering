"""End-to-end tests for the banking transactions API.

Each test gets a fresh app (and therefore a fresh in-memory store) via the
`client` fixture, so tests are independent of ordering.
"""
import sys
from pathlib import Path

import pytest

# Make the project root importable so `from src.app import create_app` works
# whether pytest is run from the repo root or elsewhere.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


# --- helpers ---------------------------------------------------------------

def valid_transfer(**overrides):
    payload = {
        "fromAccount": "ACC-12345",
        "toAccount": "ACC-67890",
        "amount": 100.50,
        "currency": "USD",
        "type": "transfer",
    }
    payload.update(overrides)
    return payload


def post(client, payload):
    return client.post("/transactions", json=payload)


# --- POST /transactions: happy path ---------------------------------------

def test_create_transaction_returns_201_and_generated_fields(client):
    resp = post(client, valid_transfer())
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["id"]                      # auto-generated, non-empty
    assert body["timestamp"]               # auto-generated
    assert body["status"] == "completed"   # default
    assert body["fromAccount"] == "ACC-12345"
    assert body["toAccount"] == "ACC-67890"
    assert body["amount"] == 100.50
    assert body["currency"] == "USD"
    assert body["type"] == "transfer"


def test_created_ids_are_unique(client):
    id1 = post(client, valid_transfer()).get_json()["id"]
    id2 = post(client, valid_transfer()).get_json()["id"]
    assert id1 != id2


def test_create_accepts_explicit_valid_status(client):
    resp = post(client, valid_transfer(status="pending"))
    assert resp.status_code == 201
    assert resp.get_json()["status"] == "pending"


def test_deposit_without_from_account_is_allowed(client):
    resp = post(client, {
        "toAccount": "ACC-11111",
        "amount": 50,
        "currency": "EUR",
        "type": "deposit",
    })
    assert resp.status_code == 201


def test_withdrawal_without_to_account_is_allowed(client):
    resp = post(client, {
        "fromAccount": "ACC-11111",
        "amount": 50,
        "currency": "EUR",
        "type": "withdrawal",
    })
    assert resp.status_code == 201


# --- POST /transactions: validation (400) ---------------------------------

def _details_fields(resp):
    body = resp.get_json()
    assert body["error"] == "Validation failed"
    return {d["field"] for d in body["details"]}


def test_negative_amount_rejected(client):
    resp = post(client, valid_transfer(amount=-5))
    assert resp.status_code == 400
    assert "amount" in _details_fields(resp)


def test_zero_amount_rejected(client):
    resp = post(client, valid_transfer(amount=0))
    assert resp.status_code == 400
    assert "amount" in _details_fields(resp)


def test_non_numeric_amount_rejected(client):
    resp = post(client, valid_transfer(amount="lots"))
    assert resp.status_code == 400
    assert "amount" in _details_fields(resp)


def test_more_than_two_decimal_places_rejected(client):
    resp = post(client, valid_transfer(amount=10.123))
    assert resp.status_code == 400
    assert "amount" in _details_fields(resp)


def test_invalid_currency_rejected(client):
    resp = post(client, valid_transfer(currency="ZZZ"))
    assert resp.status_code == 400
    assert "currency" in _details_fields(resp)


def test_invalid_type_rejected(client):
    resp = post(client, valid_transfer(type="bribe"))
    assert resp.status_code == 400
    assert "type" in _details_fields(resp)


def test_invalid_status_rejected(client):
    resp = post(client, valid_transfer(status="maybe"))
    assert resp.status_code == 400
    assert "status" in _details_fields(resp)


def test_bad_account_format_rejected(client):
    resp = post(client, valid_transfer(fromAccount="12345"))
    assert resp.status_code == 400
    assert "fromAccount" in _details_fields(resp)


def test_transfer_missing_required_account_rejected(client):
    resp = post(client, {
        "fromAccount": "ACC-12345",
        "amount": 10,
        "currency": "USD",
        "type": "transfer",
    })
    assert resp.status_code == 400
    assert "toAccount" in _details_fields(resp)


def test_multiple_errors_reported_together(client):
    resp = post(client, valid_transfer(amount=-1, currency="ZZZ"))
    assert resp.status_code == 400
    fields = _details_fields(resp)
    assert "amount" in fields and "currency" in fields


def test_malformed_json_body_returns_400_json(client):
    resp = client.post("/transactions", data="not json",
                       content_type="application/json")
    assert resp.status_code == 400
    assert resp.is_json


# --- currency consistency (one currency per account) ----------------------

def test_second_transaction_on_account_with_different_currency_rejected(client):
    post(client, valid_transfer(currency="USD"))  # binds both accounts to USD
    resp = post(client, valid_transfer(currency="EUR"))
    assert resp.status_code == 400
    assert "currency" in _details_fields(resp)


def test_same_currency_subsequent_transaction_allowed(client):
    post(client, valid_transfer(currency="USD"))
    resp = post(client, valid_transfer(currency="USD"))
    assert resp.status_code == 201


# --- GET /transactions -----------------------------------------------------

def test_list_returns_all_transactions(client):
    post(client, valid_transfer())
    post(client, valid_transfer())
    resp = client.get("/transactions")
    assert resp.status_code == 200
    assert len(resp.get_json()) == 2


def test_list_empty_initially(client):
    resp = client.get("/transactions")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_filter_by_account(client):
    post(client, valid_transfer(fromAccount="ACC-AAAAA", toAccount="ACC-BBBBB"))
    post(client, valid_transfer(fromAccount="ACC-CCCCC", toAccount="ACC-DDDDD"))
    resp = client.get("/transactions?accountId=ACC-AAAAA")
    body = resp.get_json()
    assert len(body) == 1
    assert body[0]["fromAccount"] == "ACC-AAAAA"


def test_filter_by_type(client):
    post(client, valid_transfer(type="transfer"))
    post(client, {"toAccount": "ACC-99999", "amount": 5, "currency": "USD", "type": "deposit"})
    resp = client.get("/transactions?type=deposit")
    body = resp.get_json()
    assert len(body) == 1
    assert body[0]["type"] == "deposit"


def test_combined_filters(client):
    post(client, valid_transfer(fromAccount="ACC-AAAAA", toAccount="ACC-BBBBB", type="transfer"))
    post(client, {"fromAccount": "ACC-AAAAA", "amount": 5, "currency": "USD", "type": "withdrawal"})
    resp = client.get("/transactions?accountId=ACC-AAAAA&type=withdrawal")
    body = resp.get_json()
    assert len(body) == 1
    assert body[0]["type"] == "withdrawal"


def test_filter_by_date_range(client):
    post(client, valid_transfer())
    # Range entirely in the past => no results
    resp = client.get("/transactions?from=2000-01-01&to=2000-12-31")
    assert resp.status_code == 200
    assert resp.get_json() == []


def test_invalid_date_filter_returns_400(client):
    resp = client.get("/transactions?from=not-a-date")
    assert resp.status_code == 400


def test_invalid_type_filter_returns_400(client):
    resp = client.get("/transactions?type=bribe")
    assert resp.status_code == 400


# --- GET /transactions/<id> -----------------------------------------------

def test_get_transaction_by_id(client):
    created = post(client, valid_transfer()).get_json()
    resp = client.get(f"/transactions/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["id"] == created["id"]


def test_get_unknown_transaction_returns_404(client):
    resp = client.get("/transactions/does-not-exist")
    assert resp.status_code == 404
    assert resp.is_json


# --- GET /accounts/<id>/balance -------------------------------------------

def test_balance_reflects_completed_transactions(client):
    # ACC-12345 sends 100.50 to ACC-67890
    post(client, valid_transfer(amount=100.50))
    sender = client.get("/accounts/ACC-12345/balance").get_json()
    receiver = client.get("/accounts/ACC-67890/balance").get_json()
    assert sender["balance"] == -100.50
    assert sender["currency"] == "USD"
    assert receiver["balance"] == 100.50


def test_balance_ignores_non_completed(client):
    post(client, valid_transfer(amount=100, status="pending"))
    body = client.get("/accounts/ACC-67890/balance").get_json()
    assert body["balance"] == 0


def test_balance_unknown_account_is_zero_null_currency(client):
    resp = client.get("/accounts/ACC-00000/balance")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["balance"] == 0
    assert body["currency"] is None


# --- GET /accounts/<id>/summary (Task 4A) ---------------------------------

def test_summary_totals_and_count(client):
    # Account ACC-50000: one incoming deposit (200) and one outgoing withdrawal (30)
    post(client, {"toAccount": "ACC-50000", "amount": 200, "currency": "USD", "type": "deposit"})
    post(client, {"fromAccount": "ACC-50000", "amount": 30, "currency": "USD", "type": "withdrawal"})
    body = client.get("/accounts/ACC-50000/summary").get_json()
    assert body["totalDeposits"] == 200
    assert body["totalWithdrawals"] == 30
    assert body["transactionCount"] == 2
    assert body["currency"] == "USD"
    assert body["mostRecentTimestamp"] is not None


def test_summary_unknown_account_is_empty(client):
    body = client.get("/accounts/ACC-00000/summary").get_json()
    assert body["transactionCount"] == 0
    assert body["totalDeposits"] == 0
    assert body["totalWithdrawals"] == 0
    assert body["mostRecentTimestamp"] is None
    assert body["currency"] is None


# --- unknown route ---------------------------------------------------------

def test_unknown_route_returns_json_404(client):
    resp = client.get("/nope")
    assert resp.status_code == 404
    assert resp.is_json
