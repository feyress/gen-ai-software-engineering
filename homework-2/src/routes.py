"""HTTP routes. Thin layer: parse the request, delegate to store / validators /
importers / classifier, then shape the JSON response and status code.
"""
import logging

from flask import Blueprint, jsonify, request

from . import importers
from .classifier import classify
from .models import build_ticket
from .validators import validate_create, validate_update

logger = logging.getLogger("support.classification")


def _truthy(value):
    return str(value).lower() in ("1", "true", "yes", "on")


def _classify_ticket(store, ticket):
    """Run the classifier on a ticket, persist the result, and log the decision."""
    result = classify(ticket["subject"], ticket["description"])
    store.set_classification(ticket["id"], result)
    logger.info(
        "classified ticket=%s category=%s priority=%s confidence=%.2f keywords=%s",
        ticket["id"], result["category"], result["priority"],
        result["confidence"], result["keywords"],
    )
    return result


def create_blueprint(store):
    bp = Blueprint("api", __name__)

    @bp.post("/tickets")
    def create_ticket():
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({"error": "Invalid or missing JSON body"}), 400

        errors = validate_create(data)
        if errors:
            return jsonify({"error": "Validation failed", "details": errors}), 400

        ticket = build_ticket(data)
        store.add(ticket)
        if _truthy(request.args.get("auto_classify", "")):
            _classify_ticket(store, ticket)
        return jsonify(ticket), 201

    @bp.post("/tickets/import")
    def import_tickets():
        # Accept either an uploaded file or a raw request body.
        upload = request.files.get("file")
        explicit_fmt = request.args.get("format") or request.form.get("format")
        auto_classify = _truthy(request.args.get("auto_classify", ""))

        if upload is not None:
            filename = upload.filename
            text = upload.read().decode("utf-8", errors="replace")
        else:
            filename = None
            text = request.get_data(as_text=True)

        if not (text or "").strip():
            return jsonify({"error": "No import data provided"}), 400

        try:
            fmt = importers.detect_format(filename, explicit_fmt)
            records = importers.parse(fmt, text)
        except importers.ImportError_ as exc:
            return jsonify({"error": str(exc)}), 400

        summary = {
            "format": fmt,
            "total": len(records),
            "successful": 0,
            "failed": 0,
            "errors": [],
            "created_ids": [],
        }
        for index, record in enumerate(records):
            record_errors = validate_create(record)
            if record_errors:
                summary["failed"] += 1
                summary["errors"].append({"index": index, "messages": record_errors})
                continue
            ticket = build_ticket(record)
            store.add(ticket)
            if auto_classify:
                _classify_ticket(store, ticket)
            summary["successful"] += 1
            summary["created_ids"].append(ticket["id"])

        status = 201 if summary["successful"] else 400
        return jsonify(summary), status

    @bp.get("/tickets")
    def list_tickets():
        filters = {
            key: request.args.get(key)
            for key in ("category", "priority", "status", "assigned_to")
            if request.args.get(key) is not None
        }
        return jsonify(store.filter(**filters)), 200

    @bp.get("/tickets/<ticket_id>")
    def get_ticket(ticket_id):
        ticket = store.get(ticket_id)
        if ticket is None:
            return jsonify({"error": "Ticket not found"}), 404
        return jsonify(ticket), 200

    @bp.put("/tickets/<ticket_id>")
    def update_ticket(ticket_id):
        if store.get(ticket_id) is None:
            return jsonify({"error": "Ticket not found"}), 404
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({"error": "Invalid or missing JSON body"}), 400

        errors = validate_update(data)
        if errors:
            return jsonify({"error": "Validation failed", "details": errors}), 400

        ticket = store.update(ticket_id, data)
        return jsonify(ticket), 200

    @bp.delete("/tickets/<ticket_id>")
    def delete_ticket(ticket_id):
        if not store.delete(ticket_id):
            return jsonify({"error": "Ticket not found"}), 404
        return "", 204

    @bp.post("/tickets/<ticket_id>/auto-classify")
    def auto_classify(ticket_id):
        ticket = store.get(ticket_id)
        if ticket is None:
            return jsonify({"error": "Ticket not found"}), 404
        result = _classify_ticket(store, ticket)
        return jsonify({"ticket_id": ticket_id, **result}), 200

    return bp
