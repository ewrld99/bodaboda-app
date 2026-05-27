import paho.mqtt.client as mqtt

BROKER = "mqtt"
PORT = 1883
TOPIC = "ride/status"

def on_connect(client, userdata, flags, rc):
    print("Passenger connected")
    client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    print("Ride Update:", msg.payload.decode())

client = mqtt.Client()

client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER, PORT)

client.loop_forever()