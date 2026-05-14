import os
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from backend.app import app, db


@pytest.fixture
def client():
    app.config["TESTING"] = True

    with app.app_context():
        db.drop_all()
        db.create_all()

    with app.test_client() as test_client:
        yield test_client

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_request_ride_creates_trip(client):
    response = client.post(
        "/api/request-ride",
        json={"pickup": "CBD", "destination": "Westlands"},
    )

    data = response.get_json()

    assert response.status_code == 201
    assert data["pickup"] == "CBD"
    assert data["destination"] == "Westlands"

