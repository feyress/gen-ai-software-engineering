"""Auto-classification tests (10 tests)."""
from src.classifier import classify
from tests.conftest import create_ticket


def test_account_access_category():
    result = classify("Cannot log in", "My password reset and 2FA are not working.")
    assert result["category"] == "account_access"


def test_billing_category():
    result = classify("Invoice problem", "I was charged twice and need a refund.")
    assert result["category"] == "billing_question"


def test_technical_issue_category():
    result = classify("App error", "The app crashes with a 500 error and a stack trace.")
    assert result["category"] == "technical_issue"


def test_feature_request_category():
    result = classify("Feature request", "It would be nice if you could add dark mode.")
    assert result["category"] == "feature_request"


def test_bug_report_category():
    result = classify("Bug", "Here are steps to reproduce the defect in the export.")
    assert result["category"] == "bug_report"


def test_other_category_low_confidence():
    result = classify("Hello", "Just saying hi to the wonderful support team here.")
    assert result["category"] == "other"
    assert result["confidence"] < 0.5


def test_urgent_priority():
    result = classify("Help", "Production down and this is a critical security issue.")
    assert result["priority"] == "urgent"


def test_high_and_low_priority():
    assert classify("X", "This is blocking and important, please fix asap.")["priority"] == "high"
    assert classify("X", "Just a minor cosmetic typo, nothing urgent.")["priority"] == "low"


def test_default_priority_is_medium():
    assert classify("Question", "I have a general question about the dashboard layout.")["priority"] == "medium"


def test_auto_classify_endpoint_updates_ticket(client, valid_payload):
    valid_payload["subject"] = "Cannot access account"
    valid_payload["description"] = "Locked out, password reset failing, this is critical."
    created = create_ticket(client, valid_payload)
    resp = client.post(f"/tickets/{created['id']}/auto-classify")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["category"] == "account_access"
    assert body["priority"] == "urgent"
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["keywords"]
    # The stored ticket reflects the classification.
    stored = client.get(f"/tickets/{created['id']}").get_json()
    assert stored["category"] == "account_access"
    assert stored["classification"]["confidence"] == body["confidence"]
