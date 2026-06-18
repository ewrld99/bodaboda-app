"""
MQTT Driver Publisher - Simulates a driver app publishing ride status changes.

This script demonstrates the driver-side MQTT integration:
1. Connects to the MQTT broker
2. Simulates accepting a ride
3. Simulates starting the ride (in progress)
4. Simulates completing the ride

The published messages follow the ride/status/{ride_id} topic pattern and
include driver_id, passenger_id, and timestamp for complete tracking.
"""
import os
import time
import json
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

try:
    from .mqtt_client import RIDE_STATUS_TOPIC
except ImportError:
    from mqtt_client import RIDE_STATUS_TOPIC


class DriverSimulator:
    """Simulates a driver accepting and completing rides via MQTT."""
    
    def __init__(self, driver_id, driver_name):
        """
        Initialize the driver simulator.
        
        Args:
            driver_id (int): Unique driver/rider ID
            driver_name (str): Driver's display name
        """
        self.driver_id = driver_id
        self.driver_name = driver_name
        self.client = mqtt.Client()
        # Register callbacks for connection and disconnection
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish = self._on_publish

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when client connects to MQTT broker."""
        if rc == 0:
            print(f"[{self.driver_name}] ✓ Connected to MQTT broker")
        else:
            print(f"[{self.driver_name}] ✗ Failed to connect to MQTT broker (rc={rc})")

    def _on_disconnect(self, client, userdata, rc):
        """Callback when client disconnects from MQTT broker."""
        if rc != 0:
            print(f"[{self.driver_name}] ✗ Unexpected disconnection (rc={rc})")
        else:
            print(f"[{self.driver_name}] ✓ Disconnected from MQTT broker")

    def _on_publish(self, client, userdata, mid):
        """Callback when a message is published."""
        pass  # Silent success for cleaner output

    def connect_to_broker(self):
        """Connect to the MQTT broker using environment variables."""
        host = os.getenv("MQTT_HOST", "localhost")
        port = int(os.getenv("MQTT_PORT", "1883"))
        
        try:
            self.client.connect(host, port, keepalive=60)
            self.client.loop_start()  # Start background loop
            time.sleep(0.5)  # Brief pause for connection
            print(f"[{self.driver_name}] Connecting to MQTT broker at {host}:{port}...")
        except Exception as e:
            print(f"[{self.driver_name}] ✗ Connection error: {e}")
            raise

    def publish_ride_status(self, ride_id, status, passenger_id):
        """
        Publish a ride status update.
        
        Args:
            ride_id (int): Unique ride request ID
            status (str): Status update (accepted, started, completed)
            passenger_id (int): Customer/passenger ID
        """
        # Build complete message with all required fields
        message = {
            "ride_id": ride_id,
            "status": status,
            "driver_id": self.driver_id,
            "passenger_id": passenger_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Publish to topic with ride_id suffix for selective subscription
        topic = f"{RIDE_STATUS_TOPIC}/{ride_id}"
        payload = json.dumps(message)
        
        try:
            self.client.publish(topic, payload, qos=1)
            print(f"[{self.driver_name}] ✓ Published '{status}' for ride #{ride_id}")
            print(f"  └─ Topic: {topic}")
            print(f"  └─ Payload: {payload}\n")
        except Exception as e:
            print(f"[{self.driver_name}] ✗ Failed to publish: {e}")

    def simulate_ride_flow(self, ride_id=None, passenger_id=1, auto_play=False):
        """
        Simulate the full ride lifecycle.
        
        Args:
            ride_id (int, optional): Ride ID. If None, uses current timestamp.
            passenger_id (int): Customer/passenger ID (default: 1)
            auto_play (bool): If True, automatically proceed; if False, prompt user
        """
        if ride_id is None:
            ride_id = int(time.time())

        print("\n" + "="*70)
        print("RIDE STATUS UPDATE - MQTT Contract Demonstration")
        print("="*70)
        print(f"Driver:      {self.driver_name} (ID: {self.driver_id})")
        print(f"Passenger:   Customer #{passenger_id}")
        print(f"Ride ID:     {ride_id}")
        print(f"Topic:       {RIDE_STATUS_TOPIC}/{ride_id}")
        print("-"*70)
        print("Message Format:")
        print("  {")
        print('    "ride_id": <ride_id>,')
        print('    "status": "accepted|started|completed",')
        print('    "driver_id": <driver_id>,')
        print('    "passenger_id": <passenger_id>,')
        print('    "timestamp": "ISO8601"')
        print("  }")
        print("="*70 + "\n")

        # Simulate ride state transitions with delays
        statuses = [
            ("accepted", "Driver accepted the ride request"),
            ("started", "Pickup complete, ride has started"),
            ("completed", "Ride completed and passenger dropped off"),
        ]

        for status, description in statuses:
            if not auto_play:
                input(f"Press ENTER to publish '{status}' ({description})... ")
            else:
                print(f"Publishing '{status}' ({description})...")
            
            self.publish_ride_status(ride_id, status, passenger_id)
            
            # Add realistic delay between state changes (except last)
            if status != "completed":
                if not auto_play:
                    time.sleep(0.5)
                else:
                    time.sleep(2)  # 2 second delay in auto mode

    def disconnect(self):
        """Disconnect from the MQTT broker."""
        self.client.loop_stop()
        self.client.disconnect()


if __name__ == "__main__":
    import sys
    
    # Support command-line arguments for automation
    auto_play = "--auto" in sys.argv
    
    # Create driver simulator
    driver = DriverSimulator(driver_id=89, driver_name="John Mwinyi")
    
    try:
        driver.connect_to_broker()
        
        # Run ride flow simulation
        driver.simulate_ride_flow(passenger_id=1, auto_play=auto_play)
        
        # Keep running to observe any incoming messages
        print("\n[Monitoring for messages... Press Ctrl+C to exit]\n")
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n[Shutting down...]")
    finally:
        driver.disconnect()
        print("[Driver simulator stopped]")

