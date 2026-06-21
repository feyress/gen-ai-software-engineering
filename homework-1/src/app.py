"""Application factory and entry point for the banking transactions API."""
from flask import Flask, jsonify

from .routes import create_blueprint
from .store import TransactionStore


def create_app():
    """Build a Flask app with its own fresh in-memory store."""
    app = Flask(__name__)
    store = TransactionStore()
    app.register_blueprint(create_blueprint(store))

    # Always answer with JSON, even for framework-level errors.
    @app.errorhandler(404)
    def not_found(_err):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(_err):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def server_error(_err):
        return jsonify({"error": "Internal server error"}), 500

    return app


app = create_app()


if __name__ == "__main__":
    # Port 3000 matches the sample curl commands in TASKS.md.
    app.run(host="0.0.0.0", port=3000, debug=True)
