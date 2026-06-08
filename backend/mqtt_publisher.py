import os
import time
import json

import paho.mqtt.client as mqtt

try:
    from .mqtt_client import RIDE_STATUS_TOPIC
except ImportError:
    from mqtt_client import RIDE_STATUS_TOPIC


class DriverSimulator:
    def __init__(self, driver_id, driver_name):
        self.driver_id = driver_id
        self.driver_name = driver_name
        self.client = mqtt.Client()

    def connect_to_broker(self):
        host = os.getenv("MQTT_HOST", "localhost")
        port = int(os.getenv("MQTT_PORT", "1883"))
        self.client.connect(host, port, 60)
        self.client.loop_start()
        print(f"Driver {self.driver_name} connected to MQTT broker at {host}:{port}")

    def publish_ride_status(self, ride_id, status):
        message = {
            "ride_id": ride_id,
            "status": status,
        }

        self.client.publish(RIDE_STATUS_TOPIC, json.dumps(message), qos=1)
        print(f"Published {status} for ride {ride_id} to {RIDE_STATUS_TOPIC}")

    def simulate_ride_flow(self):
        ride_id = int(time.time())

        print("\nRide status MQTT contract")
        print(f"Topic: {RIDE_STATUS_TOPIC}")
        print("Statuses: accepted, started, completed")
        print(f"Ride ID: {ride_id}")
        print("Message: {\"ride_id\": <id>, \"status\": <status>}\n")

        input("Press ENTER to publish ride accepted...")
        self.publish_ride_status(ride_id, "accepted")
        time.sleep(1)

        input("Press ENTER to publish ride started...")
        self.publish_ride_status(ride_id, "started")
        time.sleep(1)

        input("Press ENTER to publish ride completed...")
        self.publish_ride_status(ride_id, "completed")


if __name__ == "__main__":
    driver = DriverSimulator(driver_id=89, driver_name="John Mwinyi")
    driver.connect_to_broker()
    driver.simulate_ride_flow()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        driver.client.loop_stop()
        print("\nDriver simulator stopped.")
