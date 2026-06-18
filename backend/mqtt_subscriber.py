"""
MQTT Passenger Subscriber - Simulates a passenger app receiving ride status updates.

This script demonstrates the passenger-side MQTT integration:
1. Connects to the MQTT broker
2. Subscribes to ride status updates (all rides or specific ride)
3. Receives and displays real-time status updates
4. Parses and validates incoming messages

The subscriber listens on the ride/status/+ topic pattern to receive updates
for all rides, or can be configured for a specific ride_id.
"""
import json
import os
import time
from datetime import datetime

import paho.mqtt.client as mqtt

try:
    from .mqtt_client import RIDE_STATUS_TOPIC
except ImportError:
    from mqtt_client import RIDE_STATUS_TOPIC


class PassengerSubscriber:
    """Simulates a passenger app listening for ride status updates."""
    
    def __init__(self, passenger_id=None, specific_ride_id=None):
        """
        Initialize the passenger subscriber.
        
        Args:
            passenger_id (int, optional): This passenger's ID (for filtering)
            specific_ride_id (int, optional): Subscribe to specific ride only
        """
        self.passenger_id = passenger_id
        self.specific_ride_id = specific_ride_id
        self.client = mqtt.Client()
        self.message_count = 0
        
        # Register MQTT callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, rc):
        """Callback when client connects to MQTT broker."""
        if rc == 0:
            print("[Passenger] ✓ Connected to MQTT broker\n")
            
            # Subscribe to ride status updates
            if self.specific_ride_id:
                # Subscribe to specific ride
                topic = f"{RIDE_STATUS_TOPIC}/{self.specific_ride_id}"
            else:
                # Subscribe to all rides (wildcard)
                topic = f"{RIDE_STATUS_TOPIC}/+"
            
            client.subscribe(topic, qos=1)
            print(f"[Passenger] ✓ Subscribed to topic: {topic}\n")
        else:
            print(f"[Passenger] ✗ Failed to connect (rc={rc})\n")

    def _on_disconnect(self, client, userdata, rc):
        """Callback when client disconnects from MQTT broker."""
        if rc != 0:
            print(f"[Passenger] ✗ Unexpected disconnection (rc={rc})")
        else:
            print(f"[Passenger] ✓ Disconnected from MQTT broker")

    def _on_message(self, client, userdata, message):
        """
        Callback when a message is received.
        
        Validates message format and displays ride status updates.
        """
        self.message_count += 1
        
        try:
            # Decode JSON payload
            payload = message.payload.decode("utf-8")
            update = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(f"[Passenger] ✗ Invalid message format: {exc}\n")
            return

        # Extract message fields
        ride_id = update.get("ride_id")
        status = update.get("status")
        driver_id = update.get("driver_id")
        passenger_id = update.get("passenger_id")
        timestamp = update.get("timestamp")

        # Validate essential fields
        if not all([ride_id, status]):
            print(f"[Passenger] ✗ Missing required fields in message\n")
            return

        # Filter by passenger_id if configured
        if self.passenger_id and passenger_id != self.passenger_id:
            return  # Silently ignore messages not for this passenger

        # Parse and format timestamp
        try:
            ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            time_str = ts.strftime("%H:%M:%S")
        except (ValueError, AttributeError):
            time_str = timestamp or "unknown"

        # Display ride status update
        print("┌─────────────────────────────────────────────────┐")
        print("│         RIDE STATUS UPDATE RECEIVED             │")
        print("├─────────────────────────────────────────────────┤")
        print(f"│ Ride ID:       {str(ride_id):^37} │")
        print(f"│ Status:        {status.upper():^37} │")
        print(f"│ Driver ID:     {str(driver_id):^37} │")
        print(f"│ Passenger ID:  {str(passenger_id):^37} │")
        print(f"│ Time:          {time_str:^37} │")
        print(f"│ Topic:         {message.topic:^37} │")
        print("├─────────────────────────────────────────────────┤")
        print(f"│ Message #{self.message_count:^44} │")
        print("└─────────────────────────────────────────────────┘\n")

    def connect_to_broker(self):
        """Connect to the MQTT broker using environment variables."""
        host = os.getenv("MQTT_HOST", "localhost")
        port = int(os.getenv("MQTT_PORT", "1883"))
        
        print("="*70)
        print("MQTT PASSENGER SUBSCRIBER")
        print("="*70)
        print(f"Passenger ID:  {self.passenger_id or 'All'}")
        print(f"Ride Filter:   {self.specific_ride_id or 'All rides'}")
        print(f"Broker:        {host}:{port}")
        print("="*70)
        print()
        
        try:
            self.client.connect(host, port, keepalive=60)
            self.client.loop_start()  # Start background thread
            time.sleep(0.5)  # Brief pause for connection
        except Exception as e:
            print(f"[Passenger] ✗ Connection error: {e}")
            raise

    def run(self):
        """Keep the subscriber running and listening for messages."""
        try:
            print("[Waiting for ride status updates... Press Ctrl+C to exit]\n")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n[Shutting down...]")
        finally:
            self.disconnect()

    def disconnect(self):
        """Disconnect from the MQTT broker."""
        self.client.loop_stop()
        self.client.disconnect()
        print(f"[Passenger] ✓ Subscriber stopped (received {self.message_count} messages)")


if __name__ == "__main__":
    import sys
    
    # Support command-line arguments
    passenger_id = None
    ride_id = None
    
    if "--passenger-id" in sys.argv:
        idx = sys.argv.index("--passenger-id")
        if idx + 1 < len(sys.argv):
            passenger_id = int(sys.argv[idx + 1])
    
    if "--ride-id" in sys.argv:
        idx = sys.argv.index("--ride-id")
        if idx + 1 < len(sys.argv):
            ride_id = int(sys.argv[idx + 1])
    
    # Create and run subscriber
    passenger = PassengerSubscriber(
        passenger_id=passenger_id,
        specific_ride_id=ride_id
    )
    
    try:
        passenger.connect_to_broker()
        passenger.run()
    except Exception as e:
        print(f"Error: {e}")
        exit(1)

