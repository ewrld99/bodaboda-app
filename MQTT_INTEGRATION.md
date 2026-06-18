# MQTT Integration

Real-time ride communication for BodaConnect using **Eclipse Mosquitto** and **ID-scoped MQTT topics**. REST APIs remain the source of truth; MQTT delivers instant notifications to the correct driver or passenger only.

## Features Implemented

| Feature | Description |
| -------- | ------------ |
| **Flow 1 — Ride request notification** | Passenger requests a ride → backend publishes to `driver/{driver_id}/ride_request` |
| **Flow 2 — Ride status updates** | Driver updates status → backend publishes to `passenger/{passenger_id}/ride/{ride_id}/status` |
| **Message isolation** | Unique topics per driver/passenger/ride — enforced at the broker, not by client-side filtering |
| **Docker Mosquitto** | Port `1883` (backend TCP), port `9001` (browser WebSockets) |
| **Browser MQTT client** | `mqtt.js` over WebSocket in driver and passenger dashboards with `console.log()` |
| **Simulation scripts** | `mqtt_passenger_request.py`, `mqtt_driver_status_publisher.py` |
| **CI/CD** | Mosquitto service in GitHub Actions + scoped-topic isolation test |

## Architecture

```
Passenger (browser)                Driver (browser)
       |                                  |
       | POST /api/request-ride           | PATCH /api/ride-requests/{id}/status
       v                                  v
              Flask Backend (paho-mqtt publish)
                         |
                         v
              Eclipse Mosquitto (:1883 TCP, :9001 WebSocket)
                 /                    \
driver/{id}/ride_request     passenger/{id}/ride/{ride_id}/status
                 \                    /
              Driver dashboard       Passenger dashboard (mqtt.js + console.log)
```

## Topic Design and Isolation Strategy

Topics are built dynamically from real IDs — never hardcoded shared topics.

| Direction | Topic pattern | Who subscribes | Who publishes |
| --------- | ------------- | -------------- | ------------- |
| Passenger → Driver | `driver/{driver_id}/ride_request` | That driver only | Backend |
| Driver → Passenger | `passenger/{passenger_id}/ride/{ride_id}/status` | That passenger only | Backend |

**Isolation guarantee:** Mosquitto routes each message to subscribers of that exact topic. Driver 2 does not subscribe to `driver/1/ride_request`, so they never see Driver 1's requests. Passenger B does not subscribe to Passenger A's ride topic, so they never see A's status updates.

### Example topics

```
driver/3/ride_request
passenger/42/ride/1001/status
```

## Message Formats (JSON)

### Ride request (`driver/{driver_id}/ride_request`)

Published when `POST /api/request-ride` succeeds.

```json
{
  "ride_id": 1001,
  "passenger_id": 42,
  "pickup_location": "Nyerere Square",
  "destination": "Posta Dar es Salaam",
  "timestamp": "2025-06-15T14:35:22.123456+00:00"
}
```

### Ride status (`passenger/{passenger_id}/ride/{ride_id}/status`)

Published when `PATCH /api/ride-requests/{ride_id}/status` sets `accepted`, `started`, or `completed` (requires `customer_id` on the ride).

```json
{
  "ride_id": 1001,
  "status": "accepted",
  "driver_id": 3,
  "passenger_id": 42,
  "timestamp": "2025-06-15T14:36:01.123456+00:00"
}
```

Valid `status` values: `accepted`, `started`, `completed`.

## Backend Integration

- **Library:** `paho-mqtt` (`backend/requirements.txt`)
- **Publisher module:** `backend/mqtt_client.py`
  - `publish_ride_request_to_driver(driver_id, message)`
  - `publish_ride_status_to_passenger(passenger_id, ride_id, message)`
- **Hooks in** `backend/app.py`:
  - Ride create → `driver/{rider_id}/ride_request`
  - Status update → `passenger/{customer_id}/ride/{ride_id}/status`

Environment variables (Docker sets `MQTT_HOST=mqtt`, `MQTT_PORT=1883`):

| Variable | Default | Purpose |
| -------- | ------- | ------- |
| `MQTT_ENABLED` | `true` | Set `false` to disable publishing |
| `MQTT_HOST` | `localhost` / `mqtt` | Broker hostname |
| `MQTT_PORT` | `1883` | Broker TCP port |

## Browser Console Logging

Both dashboards load **mqtt.js** from CDN and connect via WebSocket (`ws://<host>:9001`).

### Driver dashboard (`rider_dashboard.html`)

Subscribes to `driver/{rider_id}/ride_request`. Expected console output:

```
Connected to MQTT broker
Subscribed to driver ride request topic: driver/3/ride_request
New ride request: {"ride_id":1001,"passenger_id":42,...}
New ride request topic: driver/3/ride_request
```

### Passenger dashboard (`customer_dashboard.html`)

Subscribes to `passenger/{passenger_id}/ride/+/status` (all rides for that passenger). Expected console output:

```
Connected to MQTT broker
Subscribed to passenger status topic: passenger/42/ride/+/status
Ride status update: {"ride_id":1001,"status":"accepted",...}
Ride status update topic: passenger/42/ride/1001/status
```

### Screenshot placeholders

<!-- Screenshot: Driver browser DevTools Console showing "New ride request:" after simulation script -->
![Driver console — ride request received](docs/screenshots/mqtt-driver-console.png)

<!-- Screenshot: Passenger browser DevTools Console showing "Ride status update:" after status flow -->
![Passenger console — status update received](docs/screenshots/mqtt-passenger-console.png)

## Docker Setup

`docker-compose.yml` includes the `mqtt` service:

- **1883** — backend (`MQTT_HOST=mqtt`)
- **9001** — browser WebSocket clients

Config: `mosquitto/mosquitto.conf` (anonymous access enabled for development).

```bash
docker compose up -d
docker compose ps mqtt   # should show healthy
```

## Simulation Scripts

| Script | Purpose |
| ------ | ------- |
| `backend/mqtt_passenger_request.py` | POST ride request → triggers Flow 1 MQTT |
| `backend/mqtt_driver_status_publisher.py` | PATCH status → triggers Flow 2 MQTT |

```bash
# Flow 1 demo (two drivers, two isolated topics)
python backend/mqtt_passenger_request.py --demo

# End-to-end: authenticated passenger + ride_id for Flow 2
python backend/mqtt_passenger_request.py --e2e
python backend/mqtt_driver_status_publisher.py --demo --ride-id <id_from_e2e>
```

> **Note:** Status MQTT requires a logged-in customer (`customer_id` on the ride). Use `--e2e` or log in via the UI before testing Flow 2.

## CI/CD Pipeline

`.github/workflows/ci-cd.yml` runs Mosquitto as a GitHub Actions service and sets `MQTT_HOST=localhost`. Tests include:

- Unit tests mocking scoped publishers (`tests/test_app.py`)
- Broker isolation test (`tests/test_mqtt_scoped_topics.py`) — publish to `driver/1/ride_request`, assert `driver/2` subscriber receives nothing

## Step-by-Step Local Test

### 1. Start the stack

```bash
docker compose up -d
```

### 2. Register accounts (browser)

1. Open `http://localhost/registration.html`
2. Register a **customer** and a **rider** (driver)
3. Note the rider's ID from the rider list on the customer dashboard (usually `1` for first rider)

### 3. Open dashboards with DevTools

1. Log in as **rider** → `http://localhost/rider_dashboard.html` → open **Console**
2. Log in as **customer** (different browser/profile) → `http://localhost/customer_dashboard.html` → open **Console**

Confirm both show `Connected to MQTT broker`.

### 4. Trigger Flow 1 (ride request)

```bash
python backend/mqtt_passenger_request.py --e2e
```

Or request a ride from the customer UI.

**Expected:** Driver console logs `New ride request:` — passenger console does **not**.

### 5. Trigger Flow 2 (status updates)

```bash
python backend/mqtt_driver_status_publisher.py --demo --ride-id <ride_id>
```

Or use Accept / Start / Complete on the rider dashboard.

**Expected:** Passenger console logs `Ride status update:` for each transition — driver console does **not** receive status messages.

### 6. Verify isolation (optional)

In a terminal, subscribe as another driver:

```bash
docker compose exec mqtt mosquitto_sub -h localhost -t "driver/2/ride_request" -v
```

Run a request for driver `1` only — driver `2`'s terminal should stay silent.

## File Reference

```
backend/
  mqtt_client.py                  # Scoped publish helpers
  app.py                            # REST hooks → MQTT publish
  mqtt_passenger_request.py         # Flow 1 simulator
  mqtt_driver_status_publisher.py   # Flow 2 simulator
frontend/
  app.js                            # mqtt.js WebSocket subscriptions + console.log
  rider_dashboard.html              # Driver page
  customer_dashboard.html           # Passenger page
mosquitto/mosquitto.conf            # Broker listeners 1883 + 9001
tests/test_mqtt_scoped_topics.py    # Topic + isolation tests
```

## Troubleshooting

| Issue | Fix |
| ----- | --- |
| Browser cannot connect to MQTT | Ensure port `9001` is exposed; check `docker compose ps mqtt` |
| No status updates in passenger console | Ride must have `customer_id` — use authenticated request (`--e2e` or UI login) |
| Backend publish fails | Verify `MQTT_HOST` / `MQTT_PORT`; check `docker compose logs mqtt` |
| Wrong driver receives request | Confirm topic uses the `rider_id` from the API payload, not a hardcoded ID |
