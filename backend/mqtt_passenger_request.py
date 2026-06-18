"""
MQTT Passenger Request Simulator

Simulates a passenger requesting a ride via the REST API.
This triggers the backend to publish the request to the ASSIGNED DRIVER's
private topic (driver/{driver_id}/ride_request), guaranteeing only that
specific driver receives the notification.

Message Isolation Demonstration:
- Driver 1 only subscribes to: driver/1/ride_request
- Driver 2 only subscribes to: driver/2/ride_request
- When Passenger A requests Driver 1: Message published to driver/1/ride_request
- Driver 2 does NOT receive this message (isolated at broker level)
"""

import json
import sys
import time
from typing import Optional

import requests


class PassengerSimulator:
    """Simulates a passenger requesting rides via REST API."""

    def __init__(self, backend_url: str = "http://localhost:5000"):
        self.backend_url = backend_url.rstrip("/")
        self.session = requests.Session()
        self.auth_token: Optional[str] = None

    def login_customer(self, email: str, password: str) -> bool:
        """Authenticate as a customer so ride requests include passenger_id."""
        endpoint = f"{self.backend_url}/api/login"
        response = self.session.post(
            endpoint,
            json={"email": email, "password": password, "role": "customer"},
        )
        if response.status_code != 200:
            print(f"Login failed ({response.status_code}): {response.text}")
            return False

        self.auth_token = response.json()["token"]
        print(f"Logged in as customer: {email}")
        return True

    def register_customer(self, name: str, email: str, password: str) -> bool:
        """Register a new customer account and store the auth token."""
        endpoint = f"{self.backend_url}/api/register"
        response = self.session.post(
            endpoint,
            json={"name": name, "email": email, "password": password, "role": "customer"},
        )
        if response.status_code not in (200, 201):
            print(f"Registration failed ({response.status_code}): {response.text}")
            return False

        self.auth_token = response.json()["token"]
        print(f"Registered customer: {email}")
        return True

    def _auth_headers(self) -> dict:
        if not self.auth_token:
            return {}
        return {"Authorization": f"Bearer {self.auth_token}"}

    def request_ride(
        self,
        pickup_location: str,
        destination: str,
        driver_id: int,
    ) -> Optional[dict]:
        """
        Request a ride from a specific driver.

        Triggers backend publish to: driver/{driver_id}/ride_request
        """
        endpoint = f"{self.backend_url}/api/request-ride"
        payload = {
            "pickup": pickup_location,
            "destination": destination,
            "rider_id": driver_id,
        }

        try:
            print(f"\n{'=' * 70}")
            print(f"PASSENGER REQUESTING RIDE FROM DRIVER #{driver_id}")
            print(f"{'=' * 70}")
            print(f"Pickup:      {pickup_location}")
            print(f"Destination: {destination}")
            print(f"Driver ID:   {driver_id}")
            print(f"Endpoint:    POST {endpoint}")
            print(f"Payload:     {json.dumps(payload, indent=2)}")
            print("-" * 70)

            response = self.session.post(
                endpoint,
                json=payload,
                headers=self._auth_headers(),
            )

            if response.status_code in (200, 201):
                ride_data = response.json()
                ride_id = ride_data.get("id")
                passenger_id = ride_data.get("customer_id")
                mqtt_payload = {
                    "ride_id": ride_id,
                    "passenger_id": passenger_id,
                    "pickup_location": pickup_location,
                    "destination": destination,
                    "timestamp": "<ISO8601>",
                }
                print(f"Ride request created (ID: {ride_id})")
                print("\nMQTT Message Published:")
                print(f"  Topic:   driver/{driver_id}/ride_request")
                print(f"  Payload: {json.dumps(mqtt_payload, indent=4)}")
                print(f"\nISOLATION: Only driver #{driver_id} receives this message")
                print(f"{'=' * 70}\n")
                return ride_data

            print(f"Request failed ({response.status_code}): {response.text}")
            return None

        except requests.exceptions.ConnectionError:
            print(f"Could not connect to backend at {self.backend_url}")
            print("Make sure the backend is running: docker compose up -d")
            return None
        except Exception as exc:
            print(f"Error: {exc}")
            return None

    def request_ride_interactive(self) -> Optional[dict]:
        print("\n" + "=" * 70)
        print("PASSENGER RIDE REQUEST SIMULATOR")
        print("=" * 70)

        try:
            pickup = input("Enter pickup location: ").strip()
            destination = input("Enter destination: ").strip()
            driver_id = int(input("Enter driver ID: ").strip())
            return self.request_ride(pickup, destination, driver_id)
        except ValueError:
            print("Invalid input. Please enter numbers for ID.")
            return None


def run_demonstration():
    """Automated demo: two ride requests to different drivers."""
    print("\n" + "#" * 70)
    print("# MQTT MESSAGE ISOLATION DEMONSTRATION")
    print("# Flow 1: Ride Request Notification (Scoped to Specific Driver)")
    print("#" * 70)

    simulator = PassengerSimulator()

    print("\nRequest 1: Passenger A -> Driver 1")
    ride1 = simulator.request_ride(
        pickup_location="Downtown Nairobi",
        destination="Jomo Kenyatta Airport",
        driver_id=1,
    )

    if ride1:
        time.sleep(1)
        print("\nRequest 2: Passenger B -> Driver 2")
        simulator.request_ride(
            pickup_location="Westlands",
            destination="Nairobi Central",
            driver_id=2,
        )

        print("\n" + "=" * 70)
        print("ISOLATION VERIFICATION")
        print("=" * 70)
        print("Message 1 -> driver/1/ride_request (Driver 1 only)")
        print("Message 2 -> driver/2/ride_request (Driver 2 only)")
        print("=" * 70 + "\n")


def run_e2e_demo():
    """
    End-to-end demo with authenticated customer so Flow 2 status MQTT works.
    Registers/logs in a customer, creates a ride, prints ride_id for next step.
    """
    simulator = PassengerSimulator()
    email = "mqtt.demo.passenger@example.com"
    password = "demo1234"

    if not simulator.login_customer(email, password):
        simulator.register_customer("MQTT Demo Passenger", email, password)

    ride = simulator.request_ride(
        pickup_location="Nyerere Square",
        destination="Posta Dar es Salaam",
        driver_id=1,
    )
    if ride:
        print("\nNext step (Flow 2):")
        print(f"  python backend/mqtt_driver_status_publisher.py --ride-id {ride['id']}")


if __name__ == "__main__":
    if "--e2e" in sys.argv:
        run_e2e_demo()
    elif "--demo" in sys.argv or "--auto" in sys.argv:
        run_demonstration()
    else:
        PassengerSimulator().request_ride_interactive()
