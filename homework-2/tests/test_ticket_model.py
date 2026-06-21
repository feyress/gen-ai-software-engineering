"""Data-validation and model-construction tests (9 tests)."""
from src.models import build_ticket
from src.validators import validate_create, validate_update


def test_valid_payload_has_no_errors(valid_payload):
    assert validate_create(valid_payload) == []


def test_missing_required_fields_are_reported():
    errors = validate_create({})
    fields = {e["field"] for e in errors}
    assert {"customer_id", "customer_email", "customer_name",
            "subject", "description"} <= fields


def test_invalid_email_rejected(valid_payload):
    valid_payload["customer_email"] = "not-an-email"
    errors = validate_create(valid_payload)
    assert any(e["field"] == "customer_email" for e in errors)


def test_subject_length_bounds(valid_payload):
    valid_payload["subject"] = "x" * 201
    assert any(e["field"] == "subject" for e in validate_create(valid_payload))


def test_description_too_short(valid_payload):
    valid_payload["description"] = "short"
    assert any(e["field"] == "description" for e in validate_create(valid_payload))


def test_invalid_enum_values_rejected(valid_payload):
    valid_payload["category"] = "nonsense"
    valid_payload["priority"] = "nope"
    errors = {e["field"] for e in validate_create(valid_payload)}
    assert {"category", "priority"} <= errors


def test_invalid_metadata_enum(valid_payload):
    valid_payload["metadata"] = {"source": "carrier_pigeon"}
    errors = {e["field"] for e in validate_create(valid_payload)}
    assert "metadata.source" in errors


def test_build_ticket_applies_defaults_and_ids(valid_payload):
    ticket = build_ticket(valid_payload)
    assert ticket["id"]
    assert ticket["status"] == "new"
    assert ticket["priority"] == "medium"
    assert ticket["category"] == "other"
    assert ticket["resolved_at"] is None
    assert ticket["created_at"] == ticket["updated_at"]
    assert ticket["tags"] == []


def test_validate_update_requires_at_least_one_field():
    assert any(e["field"] == "body" for e in validate_update({}))
    assert validate_update({"status": "resolved"}) == []
