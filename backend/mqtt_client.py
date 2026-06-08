import json
import logging
import os
from pathlib import Path

try:
    import paho.mqtt.publish as mqtt_publish
except ImportError:  # pragma: no cover - keeps the app importable without extras
    mqtt_publish = None


RIDE_STATUS_TOPIC = "ride/status"
MQTT_DISABLED_VALUES = {"0", "false", "no", "off"}
RIDE_STATUS_MESSAGE_FORMAT = {
    "ride_id": "integer ride request id",
    "status": "accepted | started | completed",
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
