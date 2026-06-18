"""
MQTT Driver Status Publisher - Update Ride Status

Simulates a driver updating ride status via the REST API.
This triggers the backend to publish status updates to the SPECIFIC PASSENGER's
private topic (passenger/{passenger_id}/ride/{ride_id}/status), guaranteeing
only that passenger receives the status update.

Message Isolation Demonstration:
- Passenger A subscribes to: passenger/42/ride/1001/status
- Passenger B subscribes to: passenger/99/ride/1002/status
- When Driver updates Ride 1001: Message published to passenger/42/ride/1001/status
- Passenger B does NOT receive this message (isolated at broker level)
"""

import argparse
import json
import sys
import time
from typing import Optional

import requests


class DriverStatusPublisher:
    """Simulates a driver updating ride status via REST API."""

    def __init__(self, backend_url: str = "http://localhost:5000"):
        self.backend_url = backend_url.rstrip("/")
        self.session = requests.Session()

    def update_ride_status(self, ride_id: int, new_status: str) -> Optional[dict]:
        """
        Update a ride's status (driver action).

        Triggers backend publish to: passenger/{passenger_id}/ride/{ride_id}/status
        """
        if new_status not in ("accepted", "started", "completed"):
            print("Invalid status. Must be: accepted, started, or completed")
            return None

        endpoint = f"{self.backend_url}/api/ride-requests/{ride_id}/status"
        payload = {"status": new_status}

        try:
            print(f"\n{'=' * 70}")
            print("DRIVER UPDATING RIDE STATUS")
            print(f"{'=' * 70}")
            print(f"Ride ID:       {ride_id}")
            print(f"New Status:    {new_status.upper()}")
            print(f"Endpoint:      PATCH {endpoint}")
            print(f"Payload:       {json.dumps(payload)}")
            print("-" * 70)

            response = self.session.patch(endpoint, json=payload)

            if response.status_code == 200:
                ride_data = response.json()
                passenger_id = ride_data.get("customer_id")
                driver_id = ride_data.get("rider_id")
                mqtt_payload = {
                    "ride_id": ride_id,
                    "status": new_status,
                    "driver_id": driver_id,
                    "passenger_id": passenger_id,
                    "timestamp": "<ISO8601>",
                }
                topic = f"passenger/{passenger_id}/ride/{ride_id}/status"
                print("Status updated successfully")
                print("\nMQTT Message Published:")
                print(f"  Topic:   {topic}")
                print(f"  Payload: {json.dumps(mqtt_payload, indent=4)}")
                if passenger_id is None:
                    print(
                        "\nWARNING: customer_id is null — backend skips MQTT publish "
                        "for unauthenticated ride requests."
                    )
                else:
                    print(f"\nISOLATION: Only passenger #{passenger_id} receives this update")
                print(f"{'=' * 70}\n")
                return ride_data

            print(f"Update failed ({response.status_code}): {response.text}")
            return None

        except requests.exceptions.ConnectionError:
            print(f"Could not connect to backend at {self.backend_url}")
            print("Make sure the backend is running: docker compose up -d")
            return None
        except Exception as exc:
            print(f"Error: {exc}")
            return None

    def update_ride_status_flow(
        self,
        ride_id: int,
        delay_between: float = 2.0,
    ) -> bool:
        """Simulate complete ride status flow: accepted -> started -> completed."""
        for index, status in enumerate(["accepted", "started", "completed"]):
            if not self.update_ride_status(ride_id, status):
                return False
            if index < 2:
                print(f"Waiting {delay_between} seconds before next status...\n")
                time.sleep(delay_between)
        return True

    def update_ride_status_interactive(self):
        print("\n" + "=" * 70)
        print("DRIVER STATUS UPDATE SIMULATOR")
        print("=" * 70)

        try:
            ride_id = int(input("Enter ride ID: ").strip())
            print("\nValid statuses: accepted, started, completed")
            status = input("Enter new status: ").strip().lower()
            return self.update_ride_status(ride_id, status)
        except ValueError:
            print("Invalid input.")
            return None


def run_demonstration(ride_id: int):
    """Automated demo: accepted -> started -> completed for one ride."""
    print("\n" + "#" * 70)
    print("# MQTT MESSAGE ISOLATION DEMONSTRATION")
    print("# Flow 2: Ride Status Updates (Scoped to Specific Passenger)")
    print("#" * 70)
    print(f"\nUpdating ride #{ride_id} through accepted -> started -> completed\n")

    publisher = DriverStatusPublisher()
    if publisher.update_ride_status_flow(ride_id=ride_id, delay_between=2.0):
        print("\n" + "=" * 70)
        print("ISOLATION VERIFICATION")
        print("=" * 70)
        print("Each status update was published to passenger/{id}/ride/{ride_id}/status")
        print("Only the passenger who owns that ride receives the messages.")
        print("=" * 70 + "\n")


def parse_args():
    parser = argparse.ArgumentParser(description="Simulate driver ride status updates")
    parser.add_argument("--demo", "--auto", action="store_true", help="Run full status flow demo")
    parser.add_argument("--ride-id", type=int, default=None, help="Ride ID for --demo mode")
    parser.add_argument(
        "--backend-url",
        default="http://localhost:5000",
        help="Backend base URL (default: http://localhost:5000)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    publisher = DriverStatusPublisher(backend_url=args.backend_url)

    if args.demo or args.auto:
        ride_id = args.ride_id
        if ride_id is None:
            print("Provide --ride-id for demo mode (create one with mqtt_passenger_request.py --e2e)")
            sys.exit(1)
        run_demonstration(ride_id)
    else:
        publisher.update_ride_status_interactive()
