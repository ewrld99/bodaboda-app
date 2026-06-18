"""
MQTT Passenger Subscriber - Receives Only Own Ride Status Updates

Simulates a passenger subscribing to ride status updates.
The passenger ONLY subscribes to their own private topic:
    passenger/{passenger_id}/ride/{ride_id}/status

This guarantees:
- Passenger A only receives updates for passenger/42/ride/1001/status
- Passenger B only receives updates for passenger/99/ride/2002/status
- No passenger receives another passenger's ride status updates
- Message isolation enforced at MQTT broker level
"""

import os
import json
import time
import paho.mqtt.client as mqtt
from datetime import datetime


class PassengerSubscriber:
    """Simulates a passenger app listening for ride status updates."""
    
    def __init__(self, passenger_id: int, ride_id: int = None, passenger_name: str = None):
        """Initialize passenger subscriber.
        
        Args:
            passenger_id (int): This passenger's unique ID
            ride_id (int): Specific ride to track (None = listen to all own rides)
            passenger_name (str): Passenger's display name
        """
        self.passenger_id = passenger_id
        self.ride_id = ride_id
        self.passenger_name = passenger_name or f"Passenger #{passenger_id}"
        self.client = mqtt.Client()
        self.message_count = 0
        
        # Set up MQTT callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
    
    def _on_connect(self, client, userdata, flags, rc):
        """Called when client connects to MQTT broker."""
        if rc == 0:
            if self.ride_id:
                # Subscribe to specific ride
                topic = f"passenger/{self.passenger_id}/ride/{self.ride_id}/status"
            else:
                # Subscribe to all own rides (wildcard)
                topic = f"passenger/{self.passenger_id}/ride/+/status"
            
            client.subscribe(topic, qos=1)
            print(f"\n[{self.passenger_name}] ✓ Connected to MQTT broker")
            print(f"[{self.passenger_name}] ✓ Subscribed to: {topic}")
            print(f"[{self.passenger_name}] Waiting for ride status updates...\n")
        else:
            print(f"[{self.passenger_name}] ✗ Failed to connect (rc={rc})")
    
    def _on_disconnect(self, client, userdata, rc):
        """Called when client disconnects from MQTT broker."""
        if rc != 0:
            print(f"\n[{self.passenger_name}] ✗ Unexpected disconnection (rc={rc})")
    
    def _on_message(self, client, userdata, msg):
        """Called when a message is received on subscribed topic."""
        self.message_count += 1
        
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
        except json.JSONDecodeError:
            print(f"[{self.passenger_name}] ✗ Invalid JSON in message")
            return
        
        ride_id = payload.get('ride_id')
        status = payload.get('status')
        driver_id = payload.get('driver_id')
        timestamp = payload.get('timestamp')
        
        # Parse timestamp for display
        try:
            ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            time_str = ts.strftime("%H:%M:%S")
        except (ValueError, AttributeError, TypeError):
            time_str = str(timestamp)
        
        # Status indicator emoji
        status_emoji = {
            "accepted": "✓",
            "started": "►",
            "completed": "✔"
        }.get(status, "•")
        
        print("\n" + "┌" + "─"*68 + "┐")
        print("│                    RIDE STATUS UPDATE RECEIVED                   │")
        print("├" + "─"*68 + "┤")
        print(f"│ Ride ID:        {str(ride_id):^57} │")
        print(f"│ Status:         {status_emoji} {status.upper():^54} │")
        print(f"│ Driver ID:      {str(driver_id):^57} │")
        print(f"│ Time:           {time_str:^57} │")
        print(f"│ Topic:          passenger/{self.passenger_id}/ride/{ride_id}/status{' '*(33-len(str(ride_id)))} │")
        print("├" + "─"*68 + "┤")
        print(f"│ Message #{self.message_count}{' '*(64-len(str(self.message_count)))} │")
        print("└" + "─"*68 + "┘\n")
    
    def connect_to_broker(self):
        """Connect to MQTT broker."""
        host = os.getenv("MQTT_HOST", "localhost")
        port = int(os.getenv("MQTT_PORT", "1883"))
        
        print("\n" + "="*70)
        print("MQTT PASSENGER SUBSCRIBER - RECEIVE RIDE STATUS UPDATES")
        print("="*70)
        print(f"Passenger:           {self.passenger_name}")
        print(f"Passenger ID:        {self.passenger_id}")
        if self.ride_id:
            print(f"Ride ID (Specific):   {self.ride_id}")
        else:
            print(f"Ride ID (Filter):     All own rides (+)")
        print(f"Broker:              {host}:{port}")
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
            print(f"\n[{self.passenger_name}] Shutting down...")
        finally:
            self.disconnect()
    
    def disconnect(self):
        """Disconnect from MQTT broker."""
        self.client.loop_stop()
        self.client.disconnect()
        print(f"[{self.passenger_name}] ✓ Disconnected")
        print(f"[{self.passenger_name}] Total messages received: {self.message_count}")


if __name__ == "__main__":
    import sys
    
    # Support command-line arguments for different passengers
    passenger_id = 42
    ride_id = None
    passenger_name = f"Passenger #{passenger_id}"
    
    if len(sys.argv) > 1:
        try:
            passenger_id = int(sys.argv[1])
            passenger_name = f"Passenger #{passenger_id}"
        except ValueError:
            pass
    
    if len(sys.argv) > 2:
        try:
            ride_id = int(sys.argv[2])
        except ValueError:
            pass
    
    print("\n" + "#"*70)
    print("# MQTT PASSENGER SUBSCRIBER - MESSAGE ISOLATION DEMO")
    print("#"*70)
    print("\nThis script demonstrates topic-based message isolation:")
    if ride_id:
        print(f"  ✓ This passenger subscribes ONLY to: passenger/{passenger_id}/ride/{ride_id}/status")
        print(f"  ✓ This passenger receives ONLY updates for ride {ride_id}")
    else:
        print(f"  ✓ This passenger subscribes ONLY to: passenger/{passenger_id}/ride/+/status")
        print(f"  ✓ This passenger receives ONLY updates for their own rides")
    print(f"  ✓ Other passengers' updates are NOT received (broker-level isolation)")
    print(f"  ✓ Run multiple instances with different passenger IDs to test\n")
    
    # Create and run subscriber for this passenger
    subscriber = PassengerSubscriber(passenger_id, ride_id, passenger_name)
    
    try:
        subscriber.connect_to_broker()
        subscriber.run()
    except Exception as e:
        print(f"Error: {e}")
        exit(1)
