# Quick Commands Reference - MQTT Testing

**Copy and paste these commands directly into your terminal for quick testing.**

---

## Setup (One-Time)

```bash
# Navigate to project
cd /path/to/boda-connect

# Start all services
docker compose up -d

# Verify MQTT is running
docker compose ps mqtt
```

---

## Test 1: REST API → Subscriber Flow

**Terminal 1: Start Subscriber**

```bash
cd backend && python mqtt_subscriber.py
```

**Terminal 2: Create & Update Ride**

```bash
# Create a ride request
RIDE_RESPONSE=$(curl -s -X POST http://localhost:5000/api/request-ride \
  -H "Content-Type: application/json" \
  -d '{
    "pickup": "Downtown Nairobi",
    "destination": "Airport",
    "rider_id": 1
  }')

# Extract ride ID (save for next commands)
RIDE_ID=$(echo $RIDE_RESPONSE | jq -r '.id')
echo "Created ride: $RIDE_ID"

# Accept the ride
curl -X PATCH http://localhost:5000/api/ride-requests/$RIDE_ID/status \
  -H "Content-Type: application/json" \
  -d '{"status": "accepted"}'

# Start the ride
curl -X PATCH http://localhost:5000/api/ride-requests/$RIDE_ID/status \
  -H "Content-Type: application/json" \
  -d '{"status": "started"}'

# Complete the ride
curl -X PATCH http://localhost:5000/api/ride-requests/$RIDE_ID/status \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'
```

---

## Test 2: Driver & Passenger Simulators

**Terminal 1: Passenger Subscriber**

```bash
cd backend && python mqtt_subscriber.py
```

**Terminal 2: Driver Simulator (Auto Mode)**

```bash
cd backend && python mqtt_publisher.py --auto
```

---

## Test 3: Interactive Driver Simulator

**Terminal 1: Passenger Subscriber**

```bash
cd backend && python mqtt_subscriber.py
```

**Terminal 2: Driver Simulator (Interactive)**

```bash
cd backend && python mqtt_publisher.py
# Press Enter at each prompt to advance
```

---

## Test 4: Filtered Subscription (Specific Ride)

**Terminal 1: Passenger Subscribes to Specific Ride**

```bash
# Replace RIDE_ID with actual ride ID
cd backend && python mqtt_subscriber.py --ride-id 1001
```

**Terminal 2: Publish to Multiple Rides**

```bash
# Updates to ride 1001 will be received
curl -X PATCH http://localhost:5000/api/ride-requests/1001/status \
  -H "Content-Type: application/json" \
  -d '{"status": "accepted"}'

# Updates to ride 1002 will be IGNORED (different ride)
curl -X PATCH http://localhost:5000/api/ride-requests/1002/status \
  -H "Content-Type: application/json" \
  -d '{"status": "accepted"}'
```

---

## Test 5: Monitor Raw MQTT Messages

**Terminal 1: Monitor All MQTT Traffic**

```bash
docker compose exec mqtt mosquitto_sub -h localhost -t 'ride/status/#' -v
```

**Terminal 2: Publish Updates**

```bash
# Use any method from above tests (API, simulators, etc.)
cd backend && python mqtt_publisher.py --auto
```

---

## Test 6: Check MQTT Broker Health

```bash
# View broker logs
docker compose logs mqtt | tail -20

# Check health status
docker compose ps mqtt

# Test broker connectivity
docker compose exec mqtt mosquitto_pub -h localhost -t healthcheck -m "ping"
```

---

## Test 7: Verify Python Dependencies

```bash
# Check paho-mqtt installation
python -m pip show paho-mqtt

# Quick import test
python -c "import paho.mqtt; print('✓ paho-mqtt is installed')"
```

---

## Cleanup Commands

```bash
# Stop all services
docker compose down

# View MQTT logs
docker compose logs mqtt

# Restart MQTT only
docker compose restart mqtt

# Remove MQTT data volume (reset)
docker volume rm boda-connect_mosquitto-data

# Full cleanup (warning: deletes all volumes)
docker compose down -v
```

---

## Expected Output Examples

### Subscriber Receiving Message

```
┌─────────────────────────────────────────────────┐
│         RIDE STATUS UPDATE RECEIVED             │
├─────────────────────────────────────────────────┤
│ Ride ID:       1001                             │
│ Status:        ACCEPTED                         │
│ Driver ID:     89                               │
│ Passenger ID:  42                               │
│ Time:          14:35:22                         │
│ Topic:         ride/status/1001                 │
├─────────────────────────────────────────────────┤
│ Message #1                                      │
└─────────────────────────────────────────────────┘
```

### Raw MQTT Message

```
ride/status/1001 {"driver_id":89,"passenger_id":42,"ride_id":1001,"status":"accepted","timestamp":"2025-06-15T14:35:22+00:00"}
```

### Driver Simulator Output

```
[John Mwinyi] ✓ Published 'accepted' for ride #1701234567
  └─ Topic: ride/status/1701234567
  └─ Payload: {"driver_id": 89, "passenger_id": 1, "ride_id": 1701234567, "status": "accepted", "timestamp": "2025-06-15T14:35:22+00:00"}
```

---

## Troubleshooting Quick Fixes

### Connection Refused

```bash
docker compose restart mqtt
sleep 2
# Try again
```

### Port Already in Use

```bash
# Find process using port 1883
lsof -i :1883

# Kill it (replace PID)
kill -9 PID
```

### MQTT Not Connecting

```bash
# Check environment variables
echo $MQTT_HOST
echo $MQTT_PORT

# Set defaults for local testing
export MQTT_HOST=localhost
export MQTT_PORT=1883
```

### Python Module Not Found

```bash
# Reinstall dependencies
pip install --upgrade paho-mqtt
```

---

## One-Command Test Suite

Run all tests in sequence (from project root):

```bash
#!/bin/bash
set -e

echo "🚀 Starting MQTT Integration Tests..."
echo ""

# Start services
echo "1️⃣  Starting Docker services..."
docker compose up -d mqtt db
sleep 3

# Verify broker
echo "2️⃣  Verifying MQTT broker..."
docker compose exec mqtt mosquitto_pub -h localhost -t test -m test && echo "✓ Broker healthy"

# Install dependencies
echo "3️⃣  Installing dependencies..."
cd backend && pip install -q -r requirements.txt

# Run simulator test
echo "4️⃣  Running simulator test..."
cd backend && timeout 10 python mqtt_subscriber.py &
SUB_PID=$!
sleep 2
python mqtt_publisher.py --auto
wait $SUB_PID 2>/dev/null || true

echo ""
echo "✅ All tests completed!"
echo ""
echo "📚 Documentation:"
echo "  - Full Guide: MQTT_INTEGRATION.md"
echo "  - Testing Guide: MQTT_TESTING_GUIDE.md"
echo "  - Quick Ref: MQTT_RIDE_STATUS.md"
```

---

## Docker Compose Helpful Commands

```bash
# View all services status
docker compose ps

# View specific service logs
docker compose logs mqtt -f        # follow mode
docker compose logs mqtt --tail=50 # last 50 lines

# Enter MQTT container shell
docker compose exec mqtt sh

# Run MQTT command in container
docker compose exec mqtt mosquitto_pub -h localhost -t ride/status/test -m '{"test":true}'
```

---

## More Info

- **Full Documentation:** `MQTT_INTEGRATION.md`
- **Detailed Testing:** `MQTT_TESTING_GUIDE.md`
- **Implementation Summary:** `MQTT_IMPLEMENTATION_SUMMARY.md`
- **Code Reference:** `backend/mqtt_client.py`
