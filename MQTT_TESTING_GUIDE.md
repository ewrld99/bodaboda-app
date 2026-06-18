# MQTT Integration - Testing & Validation Guide

## Quick Reference: Testing Commands

This guide provides step-by-step commands to test the MQTT integration locally.

---

## Setup Phase (One-time)

### 1. Clone/Navigate to Project

```bash
cd /path/to/boda-connect
```

### 2. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt
```

**Verify installation:**

```bash
python -c "import paho.mqtt; print('✓ paho-mqtt installed')"
```

### 3. Start Docker Services

```bash
# From project root
docker compose up -d

# Verify services
docker compose ps
```

**Expected output:**

```
NAME         STATUS
mqtt         healthy (or Up)
db           healthy (or Up)
backend      Up
nginx        Up
...
```

### 4. Verify MQTT Broker

```bash
# Check Mosquitto logs
docker compose logs mqtt | tail -20

# Expected: "1701234567: mosquitto version X.X.X starting"
```

---

## Test Scenario 1: Manual REST API + Subscriber

**Goal:** Publish status via REST API and verify subscriber receives it

### Terminal 1: Start Passenger Subscriber

```bash
cd backend

# Listen to all ride updates
python mqtt_subscriber.py
```

**Expected output:**

```
======================================================================
MQTT PASSENGER SUBSCRIBER
======================================================================
Passenger ID:  All
Ride Filter:   All rides
Broker:        localhost:1883
======================================================================

[Passenger] ✓ Connected to MQTT broker

[Passenger] ✓ Subscribed to topic: ride/status/+

[Waiting for ride status updates... Press Ctrl+C to exit]
```

### Terminal 2: Publish via REST API

First, create a ride request:

```bash
# Create a ride request
curl -X POST http://localhost:5000/api/request-ride \
  -H "Content-Type: application/json" \
  -d '{
    "pickup": "Nairobi City Center",
    "destination": "Jomo Kenyatta Airport",
    "rider_id": 1
  }'
```

**Response (note the ride_id):**

```json
{
  "id": 1001,
  "pickup": "Nairobi City Center",
  "destination": "Jomo Kenyatta Airport",
  "status": "pending",
  "rider_id": 1,
  "customer_id": null
}
```

Now update the ride status:

```bash
# Accept the ride (replace 1001 with actual ride_id)
curl -X PATCH http://localhost:5000/api/ride-requests/1001/status \
  -H "Content-Type: application/json" \
  -d '{"status": "accepted"}'
```

### Verify: Check Terminal 1

In the passenger subscriber terminal, you should see:

```
┌─────────────────────────────────────────────────┐
│         RIDE STATUS UPDATE RECEIVED             │
├─────────────────────────────────────────────────┤
│ Ride ID:       1001                             │
│ Status:        ACCEPTED                         │
│ Driver ID:     1                                │
│ Passenger ID:  None                             │
│ Time:          14:35:22                         │
│ Topic:         ride/status/1001                 │
├─────────────────────────────────────────────────┤
│ Message #1                                      │
└─────────────────────────────────────────────────┘
```

### Continue Testing

Publish more status updates:

```bash
# Start the ride
curl -X PATCH http://localhost:5000/api/ride-requests/1001/status \
  -H "Content-Type: application/json" \
  -d '{"status": "started"}'

# Complete the ride
curl -X PATCH http://localhost:5000/api/ride-requests/1001/status \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'
```

**Expected:** Subscriber receives 2 more messages for "started" and "completed" statuses.

---

## Test Scenario 2: Driver & Passenger Simulators

**Goal:** Use automated scripts to simulate complete driver-passenger flow

### Terminal 1: Start Passenger Subscriber

```bash
cd backend
python mqtt_subscriber.py
```

### Terminal 2: Run Driver Simulator (Interactive)

```bash
cd backend
python mqtt_publisher.py
```

**Expected output:**

```
======================================================================
RIDE STATUS UPDATE - MQTT Contract Demonstration
======================================================================
Driver:      John Mwinyi (ID: 89)
Passenger:   Customer #1
Ride ID:     1701234567
Topic:       ride/status/1701234567
----------------------------------------------------------------------

[John Mwinyi] ✓ Connected to MQTT broker
[Waiting for input...]

Press ENTER to publish 'accepted' (Driver accepted the ride request)...
```

**Steps:**

1. Press Enter for each prompt
2. Subscriber displays updates in real-time

### Alternative: Auto Mode

```bash
# Terminal 2: Auto-advances through statuses without prompting
cd backend
python mqtt_publisher.py --auto
```

**Expected:** Statuses published with 2-second delays; subscriber displays all three updates.

---

## Test Scenario 3: Multiple Rides Simultaneously

**Goal:** Verify system handles multiple concurrent ride updates

### Terminal 1: Subscriber

```bash
cd backend
python mqtt_subscriber.py
```

### Terminal 2: Create multiple rides and update them

```bash
#!/bin/bash

# Create 3 rides
for i in {1..3}; do
  RESPONSE=$(curl -s -X POST http://localhost:5000/api/request-ride \
    -H "Content-Type: application/json" \
    -d '{
      "pickup": "Location 'A'",
      "destination": "Location 'B'",
      "rider_id": '$((i % 2 + 1))'
    }')

  RIDE_ID=$(echo $RESPONSE | jq -r '.id')
  echo "Created ride: $RIDE_ID"

  # Update status
  curl -s -X PATCH http://localhost:5000/api/ride-requests/$RIDE_ID/status \
    -H "Content-Type: application/json" \
    -d '{"status": "accepted"}' > /dev/null

  sleep 1
done
```

**Expected:** Subscriber displays 3 separate messages for each ride.

---

## Test Scenario 4: MQTT Traffic Monitoring

**Goal:** Observe raw MQTT messages on the broker

### Terminal 1: Subscribe to all MQTT topics

```bash
docker compose exec mqtt mosquitto_sub -h localhost -t 'ride/status/#' -v
```

### Terminal 2: Publish updates (using one of the above methods)

```bash
# Example: driver simulator
cd backend
python mqtt_publisher.py --auto
```

### Verify: Monitor MQTT Traffic

In Terminal 1, you'll see raw messages:

```
ride/status/1701234567 {"driver_id":89,"passenger_id":1,"ride_id":1701234567,"status":"accepted","timestamp":"2025-06-15T14:35:22+00:00"}
ride/status/1701234567 {"driver_id":89,"passenger_id":1,"ride_id":1701234567,"status":"started","timestamp":"2025-06-15T14:35:24+00:00"}
ride/status/1701234567 {"driver_id":89,"passenger_id":1,"ride_id":1701234567,"status":"completed","timestamp":"2025-06-15T14:35:26+00:00"}
```

---

## Test Scenario 5: Filtered Subscription

**Goal:** Verify passenger can subscribe to specific ride

### Terminal 1: Subscribe to specific ride only

```bash
cd backend

# Replace 1001 with your ride ID
python mqtt_subscriber.py --ride-id 1001
```

### Terminal 2: Publish updates to multiple rides

```bash
# Update ride 1001
curl -X PATCH http://localhost:5000/api/ride-requests/1001/status \
  -H "Content-Type: application/json" \
  -d '{"status": "accepted"}'

# Update different ride (e.g., 1002)
curl -X PATCH http://localhost:5000/api/ride-requests/1002/status \
  -H "Content-Type: application/json" \
  -d '{"status": "accepted"}'
```

**Expected:** Subscriber only shows messages for ride #1001, ignores #1002.

---

## Test Scenario 6: CI/CD Pipeline Validation

**Goal:** Verify MQTT works in the automated test environment

### Run CI/CD Tests Locally

```bash
# Install CI/CD dependencies
pip install -r backend/requirements.txt
pip install pytest

# Set test environment variables
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/bodaboda
export MQTT_HOST=localhost
export MQTT_PORT=1883

# Run tests
cd backend
pytest -v
```

**Expected:** All tests pass with MQTT broker available.

### Verify GitHub Actions Pipeline

Check `.github/workflows/ci-cd.yml`:

```yaml
services:
  mqtt:
    image: eclipse-mosquitto:latest
    ports:
      - 1883:1883
      - 9001:9001
```

This ensures MQTT is available during GitHub Actions test runs.

---

## Troubleshooting Commands

### Check MQTT Broker Health

```bash
# Container logs
docker compose logs mqtt

# Health status
docker compose ps mqtt

# Direct connection test
mosquitto_pub -h localhost -t test/topic -m "hello"
```

### Check Backend Connection to MQTT

```bash
# Inside backend container
docker compose exec backend python -c "
import os
import paho.mqtt.publish as mqtt
print(f'MQTT_HOST: {os.getenv(\"MQTT_HOST\", \"localhost\")}')
print(f'MQTT_PORT: {os.getenv(\"MQTT_PORT\", 1883)}')

# Try to publish
mqtt.single('test/topic', 'test message', hostname='mqtt', port=1883)
print('✓ Successfully published to MQTT')
"
```

### Verify Python Dependencies

```bash
python -m pip show paho-mqtt

# Output should show:
# Name: paho-mqtt
# Version: 1.6.1 (or newer)
# Location: /path/to/site-packages
```

### Check MQTT Topic Subscriptions

```bash
# Monitor active subscriptions
docker compose exec mqtt mosquitto_sub -h localhost -t '$SYS/broker/clients/+' -v
```

### Clear MQTT Data (if needed)

```bash
# Stop MQTT broker
docker compose stop mqtt

# Remove volume data
docker volume rm boda-connect_mosquitto-data

# Restart
docker compose up -d mqtt
```

---

## Expected Test Results

| Test Scenario  | Expected Result                                              | Status |
| -------------- | ------------------------------------------------------------ | ------ |
| **Scenario 1** | REST API publishes, subscriber receives 1-3 messages         | ✓      |
| **Scenario 2** | Driver simulator publishes statuses, subscriber displays all | ✓      |
| **Scenario 3** | Multiple rides update independently                          | ✓      |
| **Scenario 4** | Raw MQTT messages visible on broker                          | ✓      |
| **Scenario 5** | Filtered subscription receives only target ride              | ✓      |
| **Scenario 6** | CI/CD tests pass with MQTT available                         | ✓      |

---

## Performance Benchmarks

Typical latency (local network):

- **API call to MQTT publish:** ~10-50ms
- **MQTT publish to subscriber receive:** ~5-20ms
- **Total end-to-end:** ~15-70ms

You should see messages appear on the subscriber almost instantly (< 100ms).

---

## Common Issues & Solutions

### "Connection refused" on Port 1883

```bash
# Restart MQTT service
docker compose restart mqtt

# Check if port is bound
netstat -tln | grep 1883
# or on macOS
lsof -i :1883
```

### Subscriber doesn't receive messages

```bash
# Verify topic name (case-sensitive)
# Correct: ride/status/1001
# Wrong:  Ride/Status/1001

# Check subscriber is subscribed before publish
# Ensure both use same QoS level (default: 1)
```

### Messages appear in monitor but not subscriber

```bash
# Check Python version compatibility
python --version  # Should be 3.8+

# Reinstall paho-mqtt
pip uninstall paho-mqtt
pip install paho-mqtt==1.6.1
```

### Docker networking issues

```bash
# For local development, use 'localhost' not 'mqtt'
export MQTT_HOST=localhost

# For Docker containers, use 'mqtt' (service name)
export MQTT_HOST=mqtt

# Check docker-compose networking
docker compose exec backend ping mqtt
```

---

## Next Steps

Once all tests pass:

1. ✓ MQTT integration is working end-to-end
2. ✓ Real-time ride updates are functional
3. ✓ CI/CD pipeline can validate MQTT
4. Consider:
   - Add WebSocket support for browser clients
   - Implement message persistence
   - Add monitoring/logging
   - Secure with authentication (production)

---

## Additional Resources

- Full documentation: `MQTT_INTEGRATION.md`
- Quick reference: `MQTT_RIDE_STATUS.md`
- Driver simulator code: `mqtt_publisher.py`
- Passenger simulator code: `mqtt_subscriber.py`
- Backend integration: `mqtt_client.py`
