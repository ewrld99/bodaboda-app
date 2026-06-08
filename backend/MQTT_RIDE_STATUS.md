# Ride Status MQTT Contract

Drivers update ride status through the Flask API after accepting, starting, or
completing a ride. The Flask backend publishes the new status to the MQTT
broker, and the customer dashboard subscribes to that topic.

```text
Driver/Rider
     |
 Flask API
     | publish
 MQTT Broker
     | subscribe
 Customer Dashboard
```

## Topic

`ride/status`

The Flask backend publishes to the broker over MQTT TCP port `1883`. The
customer dashboard subscribes from the browser over MQTT WebSocket port `9001`.

## JSON message format

```json
{
  "ride_id": 15,
  "status": "started"
}
```

Allowed published statuses are:

- `accepted`
- `started`
- `completed`

The backend publishes this message when
`PATCH /api/ride-requests/<ride_id>/status` receives one of those statuses.
