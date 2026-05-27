import paho.mqtt.client as mqtt

BROKER = "mqtt"
PORT = 1883

client = mqtt.Client()


def connect_mqtt():
    client.connect(BROKER, PORT)
    print("Connected to MQTT Broker")
    return client
