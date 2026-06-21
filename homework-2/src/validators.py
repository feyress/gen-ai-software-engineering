"""Validation logic and shared constants for the support-ticket API.

All functions here are pure: they take plain data and return a list of
``{field, message}`` errors. They never touch Flask or the store, which keeps
them trivial to unit-test.
"""
import re

# --- Enumerations (exact values from TASKS.md) --------------------------
CATEGORIES = {
    "account_access", "technical_issue", "billing_question",
    "feature_request", "bug_report", "other",
}
PRIORITIES = {"urgent", "high", "medium", "low"}
STATUSES = {"new", "in_progress", "waiting_customer", "resolved", "closed"}
SOURCES = {"web_form", "email", "api", "chat", "phone"}
DEVICE_TYPES = {"desktop", "mobile", "tablet"}

# Pragmatic email check — good enough to reject obviously malformed addresses
# without trying to fully implement RFC 5322.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Required fields on ticket creation.
REQUIRED_FIELDS = (
    "customer_id", "customer_email", "customer_name", "subject", "description",
)

SUBJECT_MIN, SUBJECT_MAX = 1, 200
DESCRIPTION_MIN, DESCRIPTION_MAX = 10, 2000


def _err(field, message):
    return {"field": field, "message": message}


def _is_nonempty_str(value):
    return isinstance(value, str) and value.strip() != ""


def _string_field_errors(payload, field, lo, hi):
    """Validate a present string field against a length range."""
    value = payload.get(field)
    if not isinstance(value, str):
        return [_err(field, f"{field} must be a string")]
    length = len(value)
    if length < lo or length > hi:
        return [_err(field, f"{field} must be between {lo} and {hi} characters")]
    return []


def _enum_errors(payload, field, allowed):
    """Validate an *optional* enum field; absent is fine."""
    if field not in payload or payload[field] is None:
        return []
    if payload[field] not in allowed:
        allowed_str = ", ".join(sorted(allowed))
        return [_err(field, f"{field} must be one of: {allowed_str}")]
    return []


def _metadata_errors(payload):
    meta = payload.get("metadata")
    if meta is None:
        return []
    if not isinstance(meta, dict):
        return [_err("metadata", "metadata must be an object")]
    errors = []
    errors += _enum_errors(meta, "source", SOURCES)
    errors += _enum_errors(meta, "device_type", DEVICE_TYPES)
    # Re-key the nested errors so callers see metadata.<field>.
    return [_err(f"metadata.{e['field']}", e["message"]) for e in errors]


def _email_errors(payload):
    email = payload.get("customer_email")
    if isinstance(email, str) and not EMAIL_RE.match(email):
        return [_err("customer_email", "customer_email must be a valid email address")]
    return []


def _tags_errors(payload):
    tags = payload.get("tags")
    if tags is None:
        return []
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        return [_err("tags", "tags must be a list of strings")]
    return []


def _common_field_errors(payload):
    """Field-level rules shared by create and update (only for present fields)."""
    errors = []
    if "subject" in payload:
        errors += _string_field_errors(payload, "subject", SUBJECT_MIN, SUBJECT_MAX)
    if "description" in payload:
        errors += _string_field_errors(
            payload, "description", DESCRIPTION_MIN, DESCRIPTION_MAX
        )
    errors += _email_errors(payload)
    errors += _enum_errors(payload, "category", CATEGORIES)
    errors += _enum_errors(payload, "priority", PRIORITIES)
    errors += _enum_errors(payload, "status", STATUSES)
    errors += _tags_errors(payload)
    errors += _metadata_errors(payload)
    return errors


def validate_create(payload):
    """Validate a ticket creation payload. Returns a list of errors (empty = ok)."""
    if not isinstance(payload, dict):
        return [_err("body", "Request body must be a JSON object")]

    errors = []
    for field in REQUIRED_FIELDS:
        if not _is_nonempty_str(payload.get(field)):
            errors.append(_err(field, f"{field} is required"))

    # Only run format/length checks on fields that are present, to avoid
    # piling redundant messages on top of "is required".
    errors += _common_field_errors(payload)
    return errors


def validate_update(payload):
    """Validate a partial update payload. All fields optional, but at least one."""
    if not isinstance(payload, dict):
        return [_err("body", "Request body must be a JSON object")]
    if not payload:
        return [_err("body", "Request body must contain at least one field")]

    errors = []
    # Required fields, if supplied, must still be non-empty strings.
    for field in REQUIRED_FIELDS:
        if field in payload and not _is_nonempty_str(payload.get(field)):
            errors.append(_err(field, f"{field} must be a non-empty string"))

    errors += _common_field_errors(payload)
    return errors
