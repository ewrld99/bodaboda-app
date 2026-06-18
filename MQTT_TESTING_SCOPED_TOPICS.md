# MQTT Scoped Topics - Testing Guide

## Quick Start: Verify Message Isolation

All commands assume you're in the project root directory (`/path/to/boda-connect`).

---

## Setup (One-Time)

```bash
# Start all services
docker compose up -d

# Verify MQTT broker is healthy
docker compose ps mqtt

# Verify services
docker compose ps
```

---

## Test 1: Basic Message Isolation - Driver Requests

### **Objective**

Verify that when a ride is requested from Driver 1, only Driver 1 receives it (Driver 2 doesn't).

### **Terminal 1: Driver 1 Listening**

```bash
cd backend
python mqtt_driver_subscriber.py 1
```

**Expected Output:**

```
MQTT DRIVER SUBSCRIBER - MESSAGE ISOLATION DEMO
Driver:         Driver #1
Driver ID:      1
Broker:         localhost:1883
Private Topic:  driver/1/ride_request
[Driver #1] ✓ Connected to MQTT broker
[Driver #1] ✓ Subscribed to: driver/1/ride_request
[Driver #1] Waiting for ride requests...
```

### **Terminal 2: Driver 2 Listening**

```bash
cd backend
python mqtt_driver_subscriber.py 2
```

**Expected Output:**

```
MQTT DRIVER SUBSCRIBER - MESSAGE ISOLATION DEMO
Driver:         Driver #2
Driver ID:      2
Broker:         localhost:1883
Private Topic:  driver/2/ride_request
[Driver #2] ✓ Connected to MQTT broker
[Driver #2] ✓ Subscribed to: driver/2/ride_request
[Driver #2] Waiting for ride requests...
```

### **Terminal 3: Passenger Requesting from Driver 1**

```bash
cd backend
python mqtt_passenger_request.py
```

**Interactive Prompts:**

```
Enter pickup location: Downtown Nairobi
Enter destination: Jomo Kenyatta Airport
Enter driver ID: 1
```

### **Verify Isolation**

**Terminal 1 (Driver 1):** ✅ SHOULD SEE NEW MESSAGE

```
┌────────────────────────────────────────────────────┐
│         NEW RIDE REQUEST RECEIVED                 │
├────────────────────────────────────────────────────┤
│ Ride ID:        1001                              │
│ Passenger ID:   42                                │
│ Pickup:         Downtown Nairobi                  │
│ Destination:    Jomo Kenyatta Airport             │
│ Time:           14:35:22                          │
│ Topic:          driver/1/ride_request             │
├────────────────────────────────────────────────────┤
│ Message #1                                        │
└────────────────────────────────────────────────────┘
```

**Terminal 2 (Driver 2):** ❌ SHOULD NOT SEE ANY MESSAGE

- Remains idle waiting for requests on `driver/2/ride_request`

**Why Isolation Works:**

- Terminal 3 published to: `driver/1/ride_request`
- Terminal 1 subscribed to: `driver/1/ride_request` → RECEIVES
- Terminal 2 subscribed to: `driver/2/ride_request` → IGNORES (different topic)

---

## Test 2: Request from Different Driver

### **Verify Cross-Driver Isolation**

With all three terminals still running, repeat passenger request but for **Driver 2**:

### **Terminal 3: Passenger Requesting from Driver 2**

```bash
# In Terminal 3, run again
python mqtt_passenger_request.py

# Provide input:
# Enter pickup location: Westlands
# Enter destination: Nairobi Central
# Enter driver ID: 2
```

### **Verify Isolation Again**

**Terminal 1 (Driver 1):** ❌ NO NEW MESSAGE

- Still only shows the previous message for Driver 1

**Terminal 2 (Driver 2):** ✅ SHOULD SEE NEW MESSAGE

```
┌────────────────────────────────────────────────────┐
│         NEW RIDE REQUEST RECEIVED                 │
├────────────────────────────────────────────────────┤
│ Ride ID:        1002                              │
│ Passenger ID:   <new>                             │
│ Pickup:         Westlands                         │
│ Destination:    Nairobi Central                   │
│ Time:           14:36:15                          │
│ Topic:          driver/2/ride_request             │
├────────────────────────────────────────────────────┤
│ Message #1                                        │
└────────────────────────────────────────────────────┘
```

**Result:** ✅ ISOLATION VERIFIED

- Driver 1 request only seen by Driver 1
- Driver 2 request only seen by Driver 2

---

## Test 3: Passenger Status Update Isolation

### **Objective**

Verify that when a status is updated for Passenger A's Ride, only Passenger A receives it.

### **Terminal 4: Passenger 42 Listening to Ride 1001**

```bash
cd backend
python mqtt_passenger_subscriber.py 42 1001
```

**Expected Output:**

```
MQTT PASSENGER SUBSCRIBER - MESSAGE ISOLATION DEMO
Passenger:           Passenger #42
Passenger ID:        42
Ride ID (Specific):  1001
Broker:              localhost:1883
[Passenger #42] ✓ Connected to MQTT broker
[Passenger #42] ✓ Subscribed to: passenger/42/ride/1001/status
[Passenger #42] Waiting for ride status updates...
```

### **Terminal 5: Passenger 99 Listening to All Rides**

```bash
cd backend
python mqtt_passenger_subscriber.py 99
```

**Expected Output:**

```
MQTT PASSENGER SUBSCRIBER - MESSAGE ISOLATION DEMO
Passenger:           Passenger #99
Passenger ID:        99
Ride ID (Filter):    All own rides (+)
Broker:              localhost:1883
[Passenger #99] ✓ Connected to MQTT broker
[Passenger #99] ✓ Subscribed to: passenger/99/ride/+/status
[Passenger #99] Waiting for ride status updates...
```

### **Terminal 6: Driver Updating Ride 1001 Status**

```bash
cd backend
python mqtt_driver_status_publisher.py
```

**Interactive Prompts:**

```
Enter ride ID: 1001
Enter new status: accepted
```

### **Verify Isolation**

**Terminal 4 (Passenger 42, Ride 1001):** ✅ SHOULD SEE MESSAGE

```
┌────────────────────────────────────────────────────┐
│         RIDE STATUS UPDATE RECEIVED               │
├────────────────────────────────────────────────────┤
│ Ride ID:        1001                              │
│ Status:         ✓ ACCEPTED                        │
│ Driver ID:      89                                │
│ Time:           14:35:30                          │
│ Topic:          passenger/42/ride/1001/status     │
├────────────────────────────────────────────────────┤
│ Message #1                                        │
└────────────────────────────────────────────────────┘
```

**Terminal 5 (Passenger 99):** ❌ NO MESSAGE

- Remains idle (no ride 1001 for this passenger)

**Why Isolation Works:**

- Terminal 6 published to: `passenger/42/ride/1001/status`
- Terminal 4 subscribed to: `passenger/42/ride/1001/status` → RECEIVES
- Terminal 5 subscribed to: `passenger/99/ride/+/status` → IGNORES (different passenger)

---

## Test 4: Complete Ride Flow with Isolation

### **Simulate Complete Ride Journey**

This test runs the entire flow: request → accept → started → completed

### **Setup Terminals (keep running)**

**Terminal 1: Driver 1**

```bash
cd backend
python mqtt_driver_subscriber.py 1
```

**Terminal 2: Passenger 42** (listen to all their rides with wildcard)

```bash
cd backend
python mqtt_passenger_subscriber.py 42
# No ride ID specified - listens to: passenger/42/ride/+/status
```

### **Terminal 3: Create Ride Request**

```bash
cd backend
python mqtt_passenger_request.py

# Input:
# Pickup: Downtown Nairobi
# Destination: Airport
# Driver ID: 1
```

**What happens:**

- ✓ Driver 1 (Terminal 1) RECEIVES the request
- ✓ Message published to: `driver/1/ride_request`

### **Terminal 4: Driver Updates Status (Accepted)**

```bash
cd backend
python mqtt_driver_status_publisher.py

# Input:
# Ride ID: 1001  (from previous output)
# Status: accepted
```

**What happens:**

- ✓ Passenger 42 (Terminal 2) RECEIVES the update
- ✓ Message published to: `passenger/42/ride/1001/status`

### **Terminal 4: Driver Updates Status (Started)**

```bash
# Run again in same terminal
python mqtt_driver_status_publisher.py

# Input:
# Ride ID: 1001
# Status: started
```

**What happens:**

- ✓ Passenger 42 (Terminal 2) RECEIVES another update

### **Terminal 4: Driver Updates Status (Completed)**

```bash
# Run again in same terminal
python mqtt_driver_status_publisher.py

# Input:
# Ride ID: 1001
# Status: completed
```

**What happens:**

- ✓ Passenger 42 (Terminal 2) RECEIVES the final update

### **Verify Complete Flow**

**Terminal 1 (Driver 1):** 1 message (ride request)
**Terminal 2 (Passenger 42):** 3 messages (accepted, started, completed)

**Result:** ✅ COMPLETE ISOLATION MAINTAINED THROUGHOUT

---

## Test 5: Automated Demonstration

### **Run Pre-Built Demos**

```bash
# Demo 1: Passenger requesting ride (shows isolation)
python backend/mqtt_passenger_request.py --demo

# Demo 2: Driver updating status (shows isolation)
python backend/mqtt_driver_status_publisher.py --demo
```

---

## Test 6: Monitor Raw MQTT Traffic

### **Watch All Messages on Broker**

```bash
# In new terminal:
docker compose exec mqtt mosquitto_sub -t 'driver/+/ride_request' -v

# In another terminal:
docker compose exec mqtt mosquitto_sub -t 'passenger/+/ride/+/status' -v
```

### **Publish Test Message**

```bash
# Manually publish to driver/1/ride_request
docker compose exec mqtt mosquitto_pub -t 'driver/1/ride_request' -m '{"test": "message"}'
```

---

## Troubleshooting Tests

### **"Connection refused" when running scripts**

```bash
# Check MQTT is running
docker compose ps mqtt

# Restart if needed
docker compose restart mqtt

# Check logs
docker compose logs mqtt
```

### **Backend not found when running passenger request**

```bash
# Start the backend (new terminal)
cd backend
python app.py

# Or in Docker:
docker compose up -d backend
```

### **"Invalid JSON in message" in subscriber**

- Check that passenger/driver scripts are running correctly
- Verify MQTT broker health

### **Scripts not showing any output**

- Verify MQTT broker is healthy: `docker compose ps mqtt`
- Check environment variables: `echo $MQTT_HOST` (should be localhost)
- Try running with debug: `python script.py --debug` (if supported)

---

## Validation Checklist

- [ ] **Test 1: Driver Request Isolation**
  - [ ] Driver 1 receives request sent to driver/1/ride_request
  - [ ] Driver 2 does NOT receive driver/1/ride_request
  - [ ] Each driver only receives their own requests

- [ ] **Test 2: Cross-Driver Isolation**
  - [ ] Request to Driver 2 NOT shown to Driver 1
  - [ ] Each request routed to correct driver

- [ ] **Test 3: Passenger Status Isolation**
  - [ ] Passenger 42 receives updates for ride 1001
  - [ ] Passenger 99 does NOT receive Passenger 42's updates
  - [ ] Each passenger only receives their own rides

- [ ] **Test 4: Complete Ride Flow**
  - [ ] Request delivered to correct driver
  - [ ] Status updates delivered to correct passenger
  - [ ] Isolation maintained throughout entire flow

- [ ] **Test 5: Automated Demos**
  - [ ] Passenger demo runs without errors
  - [ ] Driver demo runs without errors
  - [ ] Clear output explaining isolation

- [ ] **Test 6: Raw MQTT Traffic**
  - [ ] Can monitor messages on broker
  - [ ] Topic names correct
  - [ ] Payload formats valid JSON

---

## Performance Validation

```bash
# Time the request flow
time python backend/mqtt_passenger_request.py

# Time the status update flow
time python backend/mqtt_driver_status_publisher.py

# Expected: < 100ms total end-to-end
```

---

## Expected Test Results

| Scenario                | Expected                                    | Result  |
| ----------------------- | ------------------------------------------- | ------- |
| Request to Driver 1     | Driver 1 RECEIVES, Driver 2 IGNORES         | ✅ PASS |
| Request to Driver 2     | Driver 2 RECEIVES, Driver 1 IGNORES         | ✅ PASS |
| Status for Passenger 42 | Passenger 42 RECEIVES, Passenger 99 IGNORES | ✅ PASS |
| Status for Passenger 99 | Passenger 99 RECEIVES, Passenger 42 IGNORES | ✅ PASS |
| Complete ride flow      | All messages reach correct recipient        | ✅ PASS |
| Isolation at all stages | Zero cross-delivery observed                | ✅ PASS |

---

## Advanced: Unit Testing

### **Run Automated Tests**

```bash
cd backend
pytest -v

# Run specific test
pytest -v test_mqtt.py
```

---

## Cleanup

```bash
# Stop all services
docker compose down

# Remove volumes (reset all data)
docker compose down -v

# View logs
docker compose logs mqtt --tail=50
```

---

## Next Steps After Validation

1. ✅ Isolation verified → Deploy to staging
2. ✅ Integration with frontend → Add WebSocket layer
3. ✅ Add authentication → Implement user-based access
4. ✅ Monitor performance → Set up metrics collection
5. ✅ Production deployment → Implement TLS/SSL
