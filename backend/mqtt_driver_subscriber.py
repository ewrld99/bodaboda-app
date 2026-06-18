"""
MQTT Driver Subscriber - Receives Only Own Ride Requests

Simulates a driver subscribing to ride requests.
The driver ONLY subscribes to their own private topic:
    driver/{driver_id}/ride_request

This guarantees:
- Driver 1 only receives messages from driver/1/ride_request
- Driver 2 only receives messages from driver/2/ride_request
- No driver receives another driver's ride requests
- Message isolation enforced at MQTT broker level
"""

import os
import json
import time
import paho.mqtt.client as mqtt
from datetime import datetime


class DriverSubscriber:
    """Simulates a driver app listening for ride requests."""
    
    def __init__(self, driver_id: int, driver_name: str = None):
        """Initialize driver subscriber.
        
        Args:
            driver_id (int): This driver's unique ID
            driver_name (str): Driver's display name
        """
        self.driver_id = driver_id
        self.driver_name = driver_name or f"Driver #{driver_id}"
        self.client = mqtt.Client()
        self.message_count = 0
        
        # Set up MQTT callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
    
    def _on_connect(self, client, userdata, flags, rc):
        """Called when client connects to MQTT broker."""
        if rc == 0:
            # Subscribe to THIS driver's private topic only
            topic = f"driver/{self.driver_id}/ride_request"
            client.subscribe(topic, qos=1)
            print(f"\n[{self.driver_name}] ✓ Connected to MQTT broker")
            print(f"[{self.driver_name}] ✓ Subscribed to: {topic}")
            print(f"[{self.driver_name}] Waiting for ride requests...\n")
        else:
            print(f"[{self.driver_name}] ✗ Failed to connect (rc={rc})")
    
    def _on_disconnect(self, client, userdata, rc):
        """Called when client disconnects from MQTT broker."""
        if rc != 0:
            print(f"\n[{self.driver_name}] ✗ Unexpected disconnection (rc={rc})")
    
    def _on_message(self, client, userdata, msg):
        """Called when a message is received on subscribed topic."""
        self.message_count += 1
        
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
        except json.JSONDecodeError:
            print(f"[{self.driver_name}] ✗ Invalid JSON in message")
            return
        
        ride_id = payload.get('ride_id')
        passenger_id = payload.get('passenger_id')
        pickup = payload.get('pickup_location')
        destination = payload.get('destination')
        timestamp = payload.get('timestamp')
        
        # Parse timestamp for display
        try:
            ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            time_str = ts.strftime("%H:%M:%S")
        except (ValueError, AttributeError, TypeError):
            time_str = str(timestamp)
        
        print("\n" + "┌" + "─"*68 + "┐")
        print("│                    NEW RIDE REQUEST RECEIVED                     │")
        print("├" + "─"*68 + "┤")
        print(f"│ Ride ID:        {str(ride_id):^57} │")
        print(f"│ Passenger ID:   {str(passenger_id):^57} │")
        print(f"│ Pickup:         {str(pickup)[:57]:^57} │")
        print(f"│ Destination:    {str(destination)[:57]:^57} │")
        print(f"│ Time:           {time_str:^57} │")
        print(f"│ Topic:          driver/{self.driver_id}/ride_request{' '*(50-len(str(self.driver_id)))} │")
        print("├" + "─"*68 + "┤")
        print(f"│ Message #{self.message_count}{' '*(64-len(str(self.message_count)))} │")
        print("└" + "─"*68 + "┘\n")
    
    def connect_to_broker(self):
        """Connect to MQTT broker."""
        host = os.getenv("MQTT_HOST", "localhost")
        port = int(os.getenv("MQTT_PORT", "1883"))
        
        print("\n" + "="*70)
        print("MQTT DRIVER SUBSCRIBER - RECEIVE RIDE REQUESTS")
        print("="*70)
        print(f"Driver:         {self.driver_name}")
        print(f"Driver ID:      {self.driver_id}")
        print(f"Broker:         {host}:{port}")
        print(f"Private Topic:  driver/{self.driver_id}/ride_request")
        print("="*70)
        
        try:
            self.client.connect(host, port, keepalive=60)
            self.client.loop_start()
            time.sleep(0.5)
        except Exception as e:
            print(f"✗ Connection error: {e}")
            raise
    
    def run(self):
        """Keep the subscriber running and waiting for messages."""
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n[{self.driver_name}] Shutting down...")
        finally:
            self.disconnect()
    
    def disconnect(self):
        """Disconnect from MQTT broker."""
        self.client.loop_stop()
        self.client.disconnect()
        print(f"[{self.driver_name}] ✓ Disconnected")
        print(f"[{self.driver_name}] Total messages received: {self.message_count}")


if __name__ == "__main__":
    import sys
    
    # Support command-line arguments for different drivers
    driver_id = 1
    driver_name = "Driver #1"
    
    if len(sys.argv) > 1:
        try:
            driver_id = int(sys.argv[1])
            driver_name = f"Driver #{driver_id}"
        except ValueError:
            pass
    
    print("\n" + "#"*70)
    print("# MQTT DRIVER SUBSCRIBER - MESSAGE ISOLATION DEMO")
    print("#"*70)
    print("\nThis script demonstrates topic-based message isolation:")
    print(f"  ✓ This driver subscribes ONLY to: driver/{driver_id}/ride_request")
    print(f"  ✓ This driver receives ONLY ride requests assigned to them")
    print(f"  ✓ Other drivers' requests are NOT received (broker-level isolation)")
    print(f"  ✓ Run multiple instances with different driver IDs to test\n")
    
    # Create and run subscriber for this driver
    subscriber = DriverSubscriber(driver_id, driver_name)
    
    try:
        subscriber.connect_to_broker()
        subscriber.run()
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
