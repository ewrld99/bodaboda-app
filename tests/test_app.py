import os

import pytest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret"

from backend.app import Rider, app, db


@pytest.fixture
def client():
    app.config["TESTING"] = True

    with app.app_context():
        db.drop_all()
        db.create_all()
        db.session.add(Rider(name="John"))
        db.session.commit()

    with app.test_client() as test_client:
        yield test_client

    with app.app_context():
        db.session.remove()
        db.drop_all()


def test_home_returns_welcome_message(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "Welcome to BodaConnect Platform"


def test_request_ride_requires_pickup_and_destination(client):
    response = client.post("/api/request-ride", json={"pickup": "CBD"})

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "pickup and destination are required"
    }


def test_request_ride_creates_trip(client):
    response = client.post(
        "/api/request-ride",
        json={"pickup": "CBD", "destination": "Westlands"},
    )

    assert response.status_code == 201
    assert response.get_json()["pickup"] == "CBD"
    assert response.get_json()["destination"] == "Westlands"


def test_rider_dashboard_returns_assigned_trips(client):
    client.post(
        "/api/request-ride",
        json={"pickup": "CBD", "destination": "Westlands"},
    )

    response = client.get("/api/rider-dashboard")
    data = response.get_json()

    assert response.status_code == 200
    assert data["rider"] == "John"
    assert data["assigned_trips"] == [
        {
            "id": 1,
            "pickup": "CBD",
            "destination": "Westlands",
        }
    ]
