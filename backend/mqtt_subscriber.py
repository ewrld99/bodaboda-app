import json
import os
import time

import paho.mqtt.client as mqtt

try:
    from .mqtt_client import RIDE_STATUS_TOPIC
except ImportError:
    from mqtt_client import RIDE_STATUS_TOPIC


class PassengerSubscriber:
    def __init__(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(RIDE_STATUS_TOPIC, qos=1)
            print(f"Customer subscriber subscribed to {RIDE_STATUS_TOPIC}")
        else:
            print(f"Could not connect to MQTT broker. Return code: {rc}")

    def on_message(self, client, userdata, message):
        try:
            update = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(f"Invalid ride status message: {exc}")
            return

        print("\nRide status update received")
        print(f"Topic: {message.topic}")
        print(f"Ride: {update.get('ride_id')}")
        print(f"Status: {update.get('status')}")

    def connect_to_broker(self):
        host = os.getenv("MQTT_HOST", "localhost")
        port = int(os.getenv("MQTT_PORT", "1883"))
        self.client.connect(host, port, 60)
        self.client.loop_start()
        print(f"Connected to MQTT broker at {host}:{port}")

    def run(self):
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.client.loop_stop()
            print("\nCustomer subscriber stopped.")


if __name__ == "__main__":
    passenger = PassengerSubscriber()
    passenger.connect_to_broker()
    passenger.run()
