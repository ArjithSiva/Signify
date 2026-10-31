"""
Signify - data collection (MQTT version)
-----------------------------------------
Replaces the old CollectData.py, which read straight from a serial port
(COM3). The ESP32 now talks over WiFi/MQTT instead of a cable, so this
script subscribes to the sensor topic instead of opening a serial port.

Usage:
    python collect_data.py

For each gesture you want to record, hold the sign steady on the glove,
then press Enter to capture ~3 seconds of samples under that label.
Repeat for every class (e.g. "0" through "9"), doing several capture
rounds per class from slightly different hand positions for a more
robust dataset. Type 'q' at the label prompt to stop.
"""

import json
import csv
import time
import threading

import paho.mqtt.client as mqtt

from mqtt_config import MQTT_BROKER, MQTT_PORT, TOPIC_SENSORS

CSV_PATH = "gesture_data.csv"
FIELDS = ["thumb", "index", "middle", "ring", "pinky"]
CAPTURE_SECONDS = 3.0

latest_reading = None
lock = threading.Lock()


def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker (rc={rc}); subscribing to {TOPIC_SENSORS}")
    client.subscribe(TOPIC_SENSORS)


def on_message(client, userdata, msg):
    global latest_reading
    try:
        data = json.loads(msg.payload.decode())
        with lock:
            latest_reading = [data[f] for f in FIELDS]
    except (json.JSONDecodeError, KeyError):
        pass  # ignore malformed packets


def main():
    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    client.loop_start()

    print("Waiting for the ESP32 glove to come online...")
    while latest_reading is None:
        time.sleep(0.2)
    print("Receiving live sensor data.\n")

    with open(CSV_PATH, "a", newline="") as f:
        writer = csv.writer(f)
        while True:
            label = input("Enter the label for the next gesture (or 'q' to quit): ").strip()
            if label.lower() == "q":
                break

            input(f"  Hold the '{label}' sign steady, then press Enter to capture {CAPTURE_SECONDS:.0f}s of samples...")
            samples = []
            start = time.time()
            while time.time() - start < CAPTURE_SECONDS:
                with lock:
                    if latest_reading is not None:
                        samples.append(list(latest_reading))
                time.sleep(0.05)

            for row in samples:
                writer.writerow(row + [label])
            f.flush()
            print(f"  Captured {len(samples)} samples for '{label}'.\n")

    client.loop_stop()
    print("Done. Data saved to", CSV_PATH)


if __name__ == "__main__":
    main()
