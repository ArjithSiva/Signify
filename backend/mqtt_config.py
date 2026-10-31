# Shared MQTT settings used by collect_data.py and predictor_service.py.
# Edit MQTT_BROKER if the broker isn't running on the same machine as these scripts.

MQTT_BROKER = "localhost"   # e.g. "192.168.1.100" if the broker runs elsewhere
MQTT_PORT = 1883

TOPIC_SENSORS = "signify/sensors"       # ESP32 -> backend (raw flex sensor readings)
TOPIC_PREDICTION = "signify/prediction"  # backend -> website (recognized sign)
