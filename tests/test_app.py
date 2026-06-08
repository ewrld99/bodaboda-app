import os
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

import backend.app as app_module
import backend.mqtt_client as mqtt_client
from backend.app import RideRequest, Rider, User, app, db


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
    customer_response = client.post(
        "/api/register",
        json={
            "name": "Amina Hassan",
            "email": "amina.request@example.com",
            "password": "pass1234",
            "role": "customer",
        },
    )
    customer_token = customer_response.get_json()["token"]
    rider_response = client.post(
        "/api/register",
        json={
            "name": "Brian Rider",
            "email": "brian.request@example.com",
            "password": "pass1234",
            "role": "rider",
        },
    )
    rider_id = rider_response.get_json()["account"]["rider_id"]

    response = client.post(
        "/api/request-ride",
        json={"pickup": "CBD", "destination": "Westlands", "rider_id": rider_id},
        headers={"Authorization": f"Bearer {customer_token}"},
    )

    data = response.get_json()

    assert response.status_code == 201
    assert data["pickup"] == "CBD"
    assert data["destination"] == "Westlands"
    assert data["status"] == "pending"
    assert data["rider_id"] == rider_id
    assert data["rider_name"] == "Brian Rider"
    assert data["customer_id"] == customer_response.get_json()["account"]["id"]
    assert data["customer_username"] == "amina.request"


def test_riders_endpoint_lists_registered_riders(client):
    client.post(
        "/api/register",
        json={
            "name": "Brian Rider",
            "email": "brian.list@example.com",
            "password": "pass1234",
            "role": "rider",
        },
    )

    response = client.get("/api/riders")
    data = response.get_json()

    assert response.status_code == 200
    assert data["riders"] == [{"id": 1, "name": "Brian Rider"}]


def test_site_stats_counts_trips_and_riders(client):
    rider_response = client.post(
        "/api/register",
        json={
            "name": "Brian Rider",
            "email": "brian.stats@example.com",
            "password": "pass1234",
            "role": "rider",
        },
    )
    rider_id = rider_response.get_json()["account"]["rider_id"]
    client.post(
        "/api/request-ride",
        json={"pickup": "CBD", "destination": "Westlands", "rider_id": rider_id},
    )

    response = client.get("/api/site-stats")
    data = response.get_json()

    assert response.status_code == 200
    assert data["total_trips"] == 1
    assert data["total_riders"] == 1


def test_ride_status_can_be_completed(client, monkeypatch):
    monkeypatch.setattr(app_module, "publish_ride_status_update", lambda message: True)

    with app.app_context():
        ride_request = RideRequest(pickup="CBD", destination="Westlands")
        db.session.add(ride_request)
        db.session.commit()
        ride_id = ride_request.id

    response = client.patch(
        f"/api/ride-requests/{ride_id}/status",
        json={"status": "completed"},
    )

    data = response.get_json()

    assert response.status_code == 200
    assert data["status"] == "completed"


def test_ride_status_update_publishes_mqtt_message(client, monkeypatch):
    published_messages = []
    monkeypatch.setattr(
        app_module,
        "publish_ride_status_update",
        lambda message: published_messages.append(message) or True,
    )

    customer_response = client.post(
        "/api/register",
        json={
            "name": "Amina Hassan",
            "email": "amina.mqtt@example.com",
            "password": "pass1234",
            "role": "customer",
        },
    )
    customer_data = customer_response.get_json()
    rider_response = client.post(
        "/api/register",
        json={
            "name": "Brian Rider",
            "email": "brian.mqtt@example.com",
            "password": "pass1234",
            "role": "rider",
        },
    )
    rider_data = rider_response.get_json()

    ride_response = client.post(
        "/api/request-ride",
        json={
            "pickup": "Nyerere Square",
            "destination": "Posta Dar es Salaam",
            "rider_id": rider_data["account"]["rider_id"],
        },
        headers={"Authorization": f"Bearer {customer_data['token']}"},
    )
    ride_id = ride_response.get_json()["id"]

    response = client.patch(
        f"/api/ride-requests/{ride_id}/status",
        json={"status": "accepted"},
    )
    data = response.get_json()

    assert app_module.RIDE_STATUS_TOPIC == "ride/status"
    assert response.status_code == 200
    assert data["status"] == "accepted"
    assert len(published_messages) == 1

    message = published_messages[0]
    assert message == {
        "ride_id": ride_id,
        "status": "accepted",
    }


def test_mqtt_publisher_sends_json_to_configured_broker(monkeypatch):
    publish_calls = []

    class FakePublish:
        @staticmethod
        def single(*args, **kwargs):
            publish_calls.append((args, kwargs))

    monkeypatch.setattr(mqtt_client, "mqtt_publish", FakePublish)
    monkeypatch.setenv("MQTT_ENABLED", "true")
    monkeypatch.setenv("MQTT_HOST", "broker.example")
    monkeypatch.setenv("MQTT_PORT", "1884")
    monkeypatch.setenv("MQTT_QOS", "1")
    monkeypatch.setenv("MQTT_RETAIN", "true")
    monkeypatch.setenv("MQTT_KEEPALIVE", "30")
    monkeypatch.setenv("MQTT_USERNAME", "backend")
    monkeypatch.setenv("MQTT_PASSWORD", "secret")
    monkeypatch.setenv("MQTT_RIDE_STATUS_TOPIC", "rides/status")
    monkeypatch.delenv("MQTT_TOPIC", raising=False)

    published = mqtt_client.publish_ride_status_update(
        {
            "ride_id": 12,
            "status": "accepted",
        }
    )

    assert published is True
    assert len(publish_calls) == 1

    args, kwargs = publish_calls[0]
    assert args == ("rides/status",)
    assert kwargs["payload"] == '{"ride_id":12,"status":"accepted"}'
    assert kwargs["hostname"] == "broker.example"
    assert kwargs["port"] == 1884
    assert kwargs["qos"] == 1
    assert kwargs["retain"] is True
    assert kwargs["keepalive"] == 30
    assert kwargs["auth"] == {"username": "backend", "password": "secret"}


def test_mqtt_publisher_can_be_disabled(monkeypatch):
    publish_calls = []

    class FakePublish:
        @staticmethod
        def single(*args, **kwargs):
            publish_calls.append((args, kwargs))

    monkeypatch.setattr(mqtt_client, "mqtt_publish", FakePublish)
    monkeypatch.setenv("MQTT_ENABLED", "false")

    published = mqtt_client.publish_ride_status_update({"ride_id": 12})

    assert published is False
    assert publish_calls == []


def test_completed_ride_can_be_deleted(client):
    with app.app_context():
        ride_request = RideRequest(
            pickup="CBD",
            destination="Westlands",
            status="completed",
        )
        db.session.add(ride_request)
        db.session.commit()
        ride_id = ride_request.id

    response = client.delete(f"/api/ride-requests/{ride_id}")

    with app.app_context():
        deleted_ride = db.session.get(RideRequest, ride_id)

    assert response.status_code == 200
    assert deleted_ride is None


def test_unfinished_ride_cannot_be_deleted(client):
    with app.app_context():
        ride_request = RideRequest(
            pickup="CBD",
            destination="Westlands",
            status="pending",
        )
        db.session.add(ride_request)
        db.session.commit()
        ride_id = ride_request.id

    response = client.delete(f"/api/ride-requests/{ride_id}")

    with app.app_context():
        existing_ride = db.session.get(RideRequest, ride_id)

    assert response.status_code == 400
    assert existing_ride is not None


def test_customer_dashboard_shows_customer_ride_status(client):
    customer_response = client.post(
        "/api/register",
        json={
            "name": "Amina Hassan",
            "email": "amina.dashboard@example.com",
            "password": "pass1234",
            "role": "customer",
        },
    )
    customer_token = customer_response.get_json()["token"]
    rider_response = client.post(
        "/api/register",
        json={
            "name": "Brian Rider",
            "email": "brian.dashboard@example.com",
            "password": "pass1234",
            "role": "rider",
        },
    )
    rider_id = rider_response.get_json()["account"]["rider_id"]

    client.post(
        "/api/request-ride",
        json={"pickup": "CBD", "destination": "Westlands", "rider_id": rider_id},
        headers={"Authorization": f"Bearer {customer_token}"},
    )

    dashboard_response = client.get(
        "/api/customer-dashboard",
        headers={"Authorization": f"Bearer {customer_token}"},
    )
    data = dashboard_response.get_json()

    assert dashboard_response.status_code == 200
    assert len(data["assigned_trips"]) == 1
    assert data["assigned_trips"][0]["status"] == "pending"
    assert data["assigned_trips"][0]["rider_name"] == "Brian Rider"
    assert data["assigned_trips"][0]["customer_username"] == "amina.dashboard"


def test_customer_can_register_and_login(client):
    register_response = client.post(
        "/api/register",
        json={
            "name": "Amina Hassan",
            "email": "amina@example.com",
            "password": "pass1234",
            "role": "customer",
        },
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/api/login",
        json={
            "email": "amina@example.com",
            "password": "pass1234",
            "role": "customer",
        },
    )
    data = login_response.get_json()

    assert login_response.status_code == 200
    assert data["token"].count(".") == 2
    assert data["account"]["name"] == "Amina Hassan"
    assert data["account"]["role"] == "customer"
    assert data["account"]["rider_id"] is None

    me_response = client.get(
        "/api/me",
        headers={"Authorization": f"Bearer {data['token']}"},
    )
    me_data = me_response.get_json()

    assert me_response.status_code == 200
    assert me_data["account"]["email"] == "amina@example.com"


def test_rider_register_creates_rider_profile(client):
    response = client.post(
        "/api/register",
        json={
            "name": "Brian Rider",
            "email": "brian@example.com",
            "password": "pass1234",
            "role": "rider",
        },
    )

    with app.app_context():
        user = User.query.filter_by(email="brian@example.com").first()
        rider = Rider.query.filter_by(name="Brian Rider").first()
        rider_user_email = rider.user.email if rider else None

    assert response.status_code == 201
    assert response.get_json()["token"].count(".") == 2
    assert user is not None
    assert rider is not None
    assert rider.user_id == user.id
    assert rider_user_email == "brian@example.com"
