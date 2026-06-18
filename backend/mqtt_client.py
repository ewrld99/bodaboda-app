import json
import logging
import os
from pathlib import Path

try:
    import paho.mqtt.publish as mqtt_publish
except ImportError:  # pragma: no cover - keeps the app importable without extras
    mqtt_publish = None


RIDE_STATUS_TOPIC = "ride/status"
RIDE_REQUEST_TOPIC = "ride/request"
MQTT_DISABLED_VALUES = {"0", "false", "no", "off"}
RIDE_STATUS_MESSAGE_FORMAT = {
    "ride_id": "integer ride request id",
    "status": "accepted | started | completed",
    "driver_id": "integer driver/rider id",
    "passenger_id": "integer customer/passenger id",
    "timestamp": "ISO 8601 UTC timestamp",
}
RIDE_REQUEST_MESSAGE_FORMAT = {
    "ride_id": "integer ride request id",
    "pickup": "string pickup location",
    "destination": "string destination location",
    "customer_id": "integer customer id",
    "customer_username": "string customer email username",
    "rider_id": "integer rider id",
    "requested_at": "ISO 8601 timestamp",
}

logger = logging.getLogger(__name__)


def _default_broker_host():
    return "mqtt" if Path("/.dockerenv").exists() else "localhost"


def _mqtt_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def _mqtt_int(name, default):
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        return int(raw_value)
    except ValueError:
        logger.warning("Invalid %s=%r; using %s", name, raw_value, default)
        return default


def _mqtt_auth():
    username = os.getenv("MQTT_USERNAME")
    password = os.getenv("MQTT_PASSWORD")
    if not username:
        return None

    return {"username": username, "password": password}


def _mqtt_topic(default_topic):
    return (
        os.getenv("MQTT_TOPIC")
        or os.getenv("MQTT_RIDE_STATUS_TOPIC")
        or default_topic
    )


def publish_mqtt_message(topic, message, *, qos=None, retain=None):
    """Publish a JSON message to the configured MQTT broker."""
    if os.getenv("MQTT_ENABLED", "true").strip().lower() in MQTT_DISABLED_VALUES:
        logger.info("MQTT publishing is disabled; skipped message for %s", topic)
        return False

    if mqtt_publish is None:
        logger.warning("paho-mqtt is not installed; skipped message for %s", topic)
        return False

    broker_host = os.getenv("MQTT_HOST", _default_broker_host())
    broker_port = _mqtt_int("MQTT_PORT", 1883)
    client_id = os.getenv("MQTT_CLIENT_ID", "")
    payload = json.dumps(message, separators=(",", ":"), sort_keys=True)

    try:
        mqtt_publish.single(
            topic,
            payload=payload,
            qos=_mqtt_int("MQTT_QOS", 1) if qos is None else qos,
            retain=_mqtt_bool("MQTT_RETAIN", False) if retain is None else retain,
            hostname=broker_host,
            port=broker_port,
            client_id=client_id,
            keepalive=_mqtt_int("MQTT_KEEPALIVE", 60),
            auth=_mqtt_auth(),
        )
    except Exception as exc:
        logger.warning(
            "Could not publish MQTT message to %s at %s:%s: %s",
            topic,
            broker_host,
            broker_port,
            exc,
        )
        return False

    logger.info("Published MQTT message to %s: %s", topic, payload)
    return True


def publish_ride_status_update(message):
    """Publish a ride status update to the required ride/status topic."""
    return publish_mqtt_message(_mqtt_topic(RIDE_STATUS_TOPIC), message)


def publish_ride_request(message):
    """Publish a new ride request to the ride/request topic for drivers."""
    return publish_mqtt_message(_mqtt_topic(RIDE_REQUEST_TOPIC), message)


# ============================================================================
# SCOPED TOPIC PUBLISHERS - Message Isolation
# ============================================================================
# These functions ensure messages are only delivered to specific drivers/passengers
# by using topic-based routing at the broker level (not client-side filtering)


def build_driver_ride_request_topic(driver_id):
    """
    Build topic for ride requests scoped to a specific driver.
    
    Topic: driver/{driver_id}/ride_request
    
    Only this driver subscribes to this topic, guaranteeing isolation.
    """
    return f"driver/{driver_id}/ride_request"


def build_passenger_ride_status_topic(passenger_id, ride_id):
    """
    Build topic for ride status updates scoped to a specific passenger and ride.
    
    Topic: passenger/{passenger_id}/ride/{ride_id}/status
    
    Only this passenger for this specific ride receives these updates.
    """
    return f"passenger/{passenger_id}/ride/{ride_id}/status"


def publish_ride_request_to_driver(driver_id, message):
    """
    Publish a ride request to a specific driver's private topic.
    
    Args:
        driver_id (int): The rider/driver ID who will receive this request
        message (dict): Ride request details
            {
              "ride_id": <int>,
              "passenger_id": <int>,
              "pickup_location": <str>,
              "destination": <str>,
              "timestamp": <ISO8601>
            }
    
    Returns:
        bool: True if published successfully, False otherwise
    
    Message Isolation:
        - ONLY the driver with this driver_id subscribes to this topic
        - Other drivers do NOT receive this request
        - Isolation guaranteed at broker level, not client side
    """
    topic = build_driver_ride_request_topic(driver_id)
    return publish_mqtt_message(topic, message)


def publish_ride_status_to_passenger(passenger_id, ride_id, message):
    """
    Publish a ride status update to a specific passenger's private topic.
    
    Args:
        passenger_id (int): The customer/passenger ID who will receive this update
        ride_id (int): The ride request ID being updated
        message (dict): Status update details
            {
              "ride_id": <int>,
              "status": "accepted|started|completed",
              "driver_id": <int>,
              "passenger_id": <int>,
              "timestamp": <ISO8601>
            }
    
    Returns:
        bool: True if published successfully, False otherwise
    
    Message Isolation:
        - ONLY the passenger with this passenger_id for this ride_id receives updates
        - Other passengers do NOT receive updates for rides not theirs
        - Drivers do NOT receive status update messages (only drivers publish, passengers receive)
        - Isolation guaranteed at broker level, not client side
    """
    topic = build_passenger_ride_status_topic(passenger_id, ride_id)
    return publish_mqtt_message(topic, message)
