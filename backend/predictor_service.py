"""
Signify - predictor service (MQTT version)
---------------------------------------------
Replaces the old connection.py, which read the Arduino over a serial cable
and POSTed predictions to a Flask /predict route that didn't exist yet.

This service:
  1. Subscribes to the raw sensor topic (signify/sensors) published by the ESP32.
  2. Buffers recent readings and waits for the hand to be held steady
     (same stability-check idea as the original connection.py).
  3. Runs the trained model on the stable reading.
  4. Publishes the recognized label to signify/prediction, which the
     website subscribes to directly (over MQTT-over-WebSockets) to
     display and speak it - no polling required.

Usage:
    python predictor_service.py
"""

import json
import time
from collections import deque

import joblib
import pandas as pd
import paho.mqtt.client as mqtt

from mqtt_config import MQTT_BROKER, MQTT_PORT, TOPIC_SENSORS, TOPIC_PREDICTION

MODEL_PATH = "signify_model.pkl"
FIELDS = ["thumb", "index", "middle", "ring", "pinky"]
BUFFER_SIZE = 5
STABILITY_THRESHOLD = 15  # max allowed variation per sensor across the buffer window

model = joblib.load(MODEL_PATH)
buffer = deque(maxlen=BUFFER_SIZE)
last_published = None


def is_stable(buf):
    for i in range(len(FIELDS)):
        values = [reading[i] for reading in buf]
        if max(values) - min(values) > STABILITY_THRESHOLD:
            return False
    return True


def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker (rc={rc}); subscribing to {TOPIC_SENSORS}")
    client.subscribe(TOPIC_SENSORS)


def on_message(client, userdata, msg):
    global last_published
    try:
        data = json.loads(msg.payload.decode())
        reading = [data[f] for f in FIELDS]
    except (json.JSONDecodeError, KeyError):
        return

    buffer.append(reading)
    if len(buffer) == BUFFER_SIZE and is_stable(buffer):
        X = pd.DataFrame([reading], columns=FIELDS)
        prediction = str(model.predict(X)[0])

        if prediction != last_published:
            client.publish(
                TOPIC_PREDICTION,
                json.dumps({"label": prediction, "ts": time.time()}),
            )
            print("Predicted:", prediction)
            last_published = prediction

        buffer.clear()  # avoid re-publishing the same held sign repeatedly


def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    print("Predictor service running. Waiting for gesture data...")
    client.loop_forever()


if __name__ == "__main__":
    main()
