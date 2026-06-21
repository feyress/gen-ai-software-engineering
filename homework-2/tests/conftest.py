"""Shared pytest fixtures."""
import os

import pytest

from src.app import create_app

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def valid_payload():
    """A minimal valid ticket-creation payload."""
    return {
        "customer_id": "CUST-001",
        "customer_email": "alice@example.com",
        "customer_name": "Alice Smith",
        "subject": "Cannot log in to my account",
        "description": "I forgot my password and the reset email never arrives.",
        "metadata": {"source": "web_form", "device_type": "desktop"},
    }


def fixture_path(name):
    return os.path.join(FIXTURES_DIR, name)


def read_fixture(name):
    with open(fixture_path(name), encoding="utf-8") as fh:
        return fh.read()


def create_ticket(client, payload):
    """Helper: POST a ticket and return its JSON body."""
    return client.post("/tickets", json=payload).get_json()
