"""HTTP routes. Thin layer: parse the request, delegate to store/validators,
shape the JSON response and status code."""
from flask import Blueprint, jsonify, request

from .models import build_transaction
from .validators import parse_filters, validate_create


def create_blueprint(store):
    bp = Blueprint("api", __name__)

    @bp.post("/transactions")
    def create_transaction():
        data = request.get_json(silent=True)
        if data is None:
            return jsonify({"error": "Invalid or missing JSON body"}), 400

        errors = validate_create(data, store.account_currency)
        if errors:
            return jsonify({"error": "Validation failed", "details": errors}), 400

        txn = build_transaction(data)
        store.add(txn)
        return jsonify(txn), 201

    @bp.get("/transactions")
    def list_transactions():
        try:
            filters = parse_filters(request.args)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(store.filter(**filters)), 200

    @bp.get("/transactions/<txn_id>")
    def get_transaction(txn_id):
        txn = store.get(txn_id)
        if txn is None:
            return jsonify({"error": "Transaction not found"}), 404
        return jsonify(txn), 200

    @bp.get("/accounts/<account_id>/balance")
    def account_balance(account_id):
        return jsonify(store.balance(account_id)), 200

    @bp.get("/accounts/<account_id>/summary")
    def account_summary(account_id):
        return jsonify(store.summary(account_id)), 200

    return bp
