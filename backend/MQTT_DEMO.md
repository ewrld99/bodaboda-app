# MQTT Ride Status Demo

Use this checklist during the presentation to show that MQTT is running, that
messages are sent and received, and that customers receive ride status updates
in real time.

## Architecture

```text
Driver/Rider
     |
 Flask API
     | publish
 MQTT Broker
     | subscribe
 Customer Dashboard
```

## 0. One-time Python setup

If this machine has not installed the backend dependencies yet:

```powershell
cd backend
python -m pip install -r requirements.txt
cd ..
```

## 1. Start the MQTT broker

From the project root:

```powershell
docker compose up -d mqtt
docker compose ps mqtt
```

Expected result: the `mqtt` service is `running` or `healthy`.
The broker exposes MQTT on `1883` for Flask and MQTT-over-WebSocket on `9001`
for the customer dashboard.

You can also prove the broker is reachable with:

```powershell
docker compose logs mqtt --tail=20
```

## 2. Start the customer subscriber

Open a second terminal:

```powershell
cd backend
python mqtt_subscriber.py
```

Expected result:

```text
Connected to MQTT broker at localhost:1883
Customer subscriber subscribed to ride/status
```

## 3. Publish sample status messages

Open a third terminal:

```powershell
cd backend
python mqtt_publisher.py
```

Press `ENTER` when prompted to publish each required ride status:

- `accepted`
- `started`
- `completed`

Expected result in the subscriber terminal: each message appears immediately
after it is published.

## 4. Show backend real-time behavior

Start the backend stack:

```powershell
docker compose up -d db mqtt backend
```

Then use the app normally:

1. Register/login as a customer.
2. Request a ride.
3. Login as the rider.
4. Click `Accept`, then `Start`, then `Complete`.

Keep the customer dashboard or subscriber terminal visible. Every rider action
publishes a JSON message to the MQTT topic `ride/status`, and the customer side
receives it immediately.

## MQTT contract to mention

Topic:

```text
ride/status
```

Message format:

```json
{
  "ride_id": 15,
  "status": "started"
}
```

## What to say during the demo

1. "This terminal shows the Mosquitto MQTT broker running."
2. "The customer dashboard subscribes to the required topic, `ride/status`."
3. "The rider updates status through Flask: `accepted`, `started`, then `completed`."
4. "Flask publishes the message, and the customer receives it instantly."
