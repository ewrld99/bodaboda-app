"""Tests for scoped MQTT topics and broker-level message isolation."""

import json
import os
import socket
import threading
import time

import pytest

import backend.mqtt_client as mqtt_client


def _broker_available():
    host = os.getenv("MQTT_HOST", "localhost")
    port = int(os.getenv("MQTT_PORT", "1883"))
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except OSError:
        return False


def test_build_driver_ride_request_topic():
    assert mqtt_client.build_driver_ride_request_topic(7) == "driver/7/ride_request"


def test_build_passenger_ride_status_topic():
    assert (
        mqtt_client.build_passenger_ride_status_topic(42, 1001)
        == "passenger/42/ride/1001/status"
    )


def test_publish_ride_request_to_driver_uses_scoped_topic(monkeypatch):
    publish_calls = []

    def fake_publish(topic, message, **kwargs):
        publish_calls.append((topic, message))
        return True

    monkeypatch.setattr(mqtt_client, "publish_mqtt_message", fake_publish)

    message = {
        "ride_id": 5,
        "passenger_id": 2,
        "pickup_location": "CBD",
        "destination": "Airport",
        "timestamp": "2025-06-15T10:00:00+00:00",
    }
    assert mqtt_client.publish_ride_request_to_driver(3, message) is True
    assert publish_calls == [("driver/3/ride_request", message)]


def test_publish_ride_status_to_passenger_uses_scoped_topic(monkeypatch):
    publish_calls = []

    def fake_publish(topic, message, **kwargs):
        publish_calls.append((topic, message))
        return True

    monkeypatch.setattr(mqtt_client, "publish_mqtt_message", fake_publish)

    message = {
        "ride_id": 1001,
        "status": "accepted",
        "driver_id": 7,
        "passenger_id": 42,
        "timestamp": "2025-06-15T10:00:00+00:00",
    }
    assert mqtt_client.publish_ride_status_to_passenger(42, 1001, message) is True
    assert publish_calls == [("passenger/42/ride/1001/status", message)]


@pytest.mark.skipif(
    not _broker_available(),
    reason="MQTT broker not reachable (start Mosquitto or docker compose up mqtt)",
)
def test_mqtt_broker_delivers_only_to_scoped_subscriber():
    """
    Integration test: publish to driver/1/ride_request and verify driver/2
    subscriber does not receive the message (broker-level isolation).
    """
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        pytest.skip("paho-mqtt not installed")

    broker_host = os.getenv("MQTT_HOST", "localhost")
    broker_port = int(os.getenv("MQTT_PORT", "1883"))
    received = {"driver1": [], "driver2": []}
    connected = threading.Event()

    def make_client(name, topic_key, topic):
        # Compatible with paho-mqtt 1.x and 2.x
        try:
            client = mqtt.Client(
                callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
                client_id=f"test_{name}_{time.time_ns()}",
            )
        except (AttributeError, TypeError):
            client = mqtt.Client(client_id=f"test_{name}_{time.time_ns()}")

        def on_connect(_client, _userdata, _flags, rc):
            if rc == 0:
                _client.subscribe(topic, qos=1)
                connected.set()

        def on_message(_client, _userdata, msg):
            received[topic_key].append(msg.payload.decode())

        client.on_connect = on_connect
        client.on_message = on_message
        client.connect(broker_host, broker_port, keepalive=30)
        client.loop_start()
        return client

    client1 = make_client("driver1", "driver1", "driver/1/ride_request")
    client2 = make_client("driver2", "driver2", "driver/2/ride_request")

    assert connected.wait(timeout=10), "MQTT subscribers failed to connect"

    payload = {
        "ride_id": 999,
        "passenger_id": 1,
        "pickup_location": "Test Pickup",
        "destination": "Test Destination",
        "timestamp": "2025-06-15T10:00:00+00:00",
    }
    assert mqtt_client.publish_ride_request_to_driver(1, payload) is True

    deadline = time.time() + 5
    while time.time() < deadline and not received["driver1"]:
        time.sleep(0.1)

    client1.loop_stop()
    client2.loop_stop()
    client1.disconnect()
    client2.disconnect()

    assert len(received["driver1"]) == 1
    assert json.loads(received["driver1"][0])["ride_id"] == 999
    assert received["driver2"] == []
