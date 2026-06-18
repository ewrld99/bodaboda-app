# Ride Status MQTT Contract

## Overview

Drivers update ride status through the Flask API after accepting, starting, or completing a ride. The Flask backend publishes the new status to the MQTT broker, and the customer dashboard subscribes to that topic for real-time updates.

## Communication Flow

```
Driver/Rider App
     ↓
  Flask API (PATCH /api/ride-requests/<ride_id>/status)
     ↓
Backend Database + MQTT Publish
     ↓
  MQTT Broker (Mosquitto)
     ↓
Customer Dashboard / Mobile App (Subscribed)
```

## Topic Structure

**Topic Format:** `ride/status/{ride_id}`

**Examples:**

- `ride/status/1001` - Updates for ride request #1001
- `ride/status/42` - Updates for ride request #42

## Message Format

### Payload Structure

```json
{
  "ride_id": 1001,
  "status": "accepted",
  "driver_id": 89,
  "passenger_id": 42,
  "timestamp": "2025-06-15T14:35:22.123456+00:00"
}
```

### Field Reference

| Field          | Type    | Required | Description                      |
| -------------- | ------- | -------- | -------------------------------- |
| `ride_id`      | integer | ✓        | Unique ride request identifier   |
| `status`       | string  | ✓        | Current ride state (see below)   |
| `driver_id`    | integer | ✓        | Rider ID from database           |
| `passenger_id` | integer | ✓        | Customer/User ID from database   |
| `timestamp`    | string  | ✓        | ISO 8601 UTC timestamp of update |

## Allowed Statuses

The following statuses are published to MQTT:

| Status      | Meaning                                         | Example Scenario                     |
| ----------- | ----------------------------------------------- | ------------------------------------ |
| `accepted`  | Driver has accepted the ride request            | Driver taps "Accept" in app          |
| `started`   | Driver has picked up passenger and started ride | Passenger enters vehicle             |
| `completed` | Ride has been completed                         | Passenger dropped off at destination |

**Note:** The `pending` status is NOT published to MQTT (only driver-to-passenger assignments trigger notifications).

## Implementation Details

### Backend Publishing

**File:** `backend/app.py`

```python
@app.route("/api/ride-requests/<int:ride_id>/status", methods=["PATCH"])
def update_ride_status(ride_id):
    # ... status validation ...

    ride_request.status = status
    db.session.commit()

    # Publish to MQTT if status is accepted, started, or completed
    if status in MQTT_RIDE_STATUS_VALUES:
        publish_ride_status_update(ride_status_mqtt_message(ride_request))

    return jsonify(serialize_ride_request(ride_request))
```

### MQTT Configuration

**Broker:** Eclipse Mosquitto  
**Host:** `mqtt` (Docker) or `localhost` (local dev)  
**Port:** `1883` (MQTT TCP) / `9001` (WebSocket)  
**Auth:** Anonymous connections allowed (dev mode)

## Testing

### Quick Test with curl

```bash
# Update ride status via API
curl -X PATCH http://localhost:5000/api/ride-requests/1/status \
  -H "Content-Type: application/json" \
  -d '{"status": "accepted"}'
```

### Monitor MQTT Messages

```bash
# Via docker-compose
docker compose exec mqtt mosquitto_sub -h localhost -t 'ride/status/#' -v

# Output:
# ride/status/1 {"driver_id":89,"passenger_id":42,"ride_id":1,"status":"accepted","timestamp":"2025-06-15T14:35:22+00:00"}
```

### Using Python Simulators

```bash
# Terminal 1: Start passenger subscriber
python backend/mqtt_subscriber.py --ride-id 1

# Terminal 2: Start driver simulator
python backend/mqtt_publisher.py --auto
```

## Quality of Service (QoS)

Messages are published with **QoS level 1** (exactly-once delivery):

- Message is guaranteed to arrive at least once
- Slight overhead compared to QoS 0
- Suitable for ride status updates where guaranteed delivery matters

## Troubleshooting

| Issue                               | Cause                                     | Solution                                                |
| ----------------------------------- | ----------------------------------------- | ------------------------------------------------------- |
| Messages not received               | Passenger not subscribed to correct topic | Subscribe to `ride/status/{ride_id}` or `ride/status/+` |
| "Connection refused"                | MQTT broker not running                   | `docker compose up -d mqtt`                             |
| Timestamp format error              | Timezone confusion                        | Always UTC with ISO 8601 format                         |
| Messages published but not received | QoS mismatch                              | Ensure subscriber also uses QoS 1 or higher             |

## Passenger Integration Example

### JavaScript (Browser)

```javascript
// Using mqtt.js library
const client = mqtt.connect("ws://localhost:9001");

client.on("connect", () => {
  // Subscribe to specific ride
  client.subscribe("ride/status/1001", (err) => {
    if (!err) console.log("Subscribed to ride #1001");
  });
});

client.on("message", (topic, message) => {
  const update = JSON.parse(message.toString());
  console.log("Ride status:", update.status);
  console.log("Updated at:", update.timestamp);

  // Update UI based on status
  updateRideStatusUI(update);
});
```

### Python (Mobile/Backend)

```python
import paho.mqtt.client as mqtt
import json

def on_message(client, userdata, msg):
    update = json.loads(msg.payload.decode())
    print(f"Ride {update['ride_id']} is now {update['status']}")
    # Handle update: notify user, update UI, etc.

client = mqtt.Client()
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe("ride/status/1001")
client.loop_forever()
```

## See Also

- `MQTT_INTEGRATION.md` - Comprehensive MQTT integration guide
- `MQTT_DEMO.md` - MQTT demonstration and examples
- `mqtt_client.py` - Backend MQTT client library
- `mqtt_publisher.py` - Driver simulator script
- `mqtt_subscriber.py` - Passenger simulator script
