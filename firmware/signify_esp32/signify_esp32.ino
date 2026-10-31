/*
  Signify - ESP32 glove firmware (MQTT version)
  ------------------------------------------------
  Reads 5 flex sensors (thumb, index, middle, ring, pinky) and publishes
  their raw ADC readings as JSON to an MQTT broker over WiFi.

  Replaces the old serial-over-cable (Arduino) and HTTP-POST (ESP32.cpp)
  versions in the original project.

  Library required (install via Arduino IDE Library Manager):
    - "PubSubClient" by Nick O'Leary

  IMPORTANT - ESP32 ADC pin choice:
  The ESP32 has two ADC units. ADC2 (GPIO 0,2,4,12-15,25-27) is shared
  internally with the WiFi radio, so analogRead() on those pins is
  unreliable/garbage whenever WiFi is active. This firmware only uses
  ADC1 pins (GPIO 32-39), which stay reliable while connected to WiFi.
  If you rewire the glove, keep all 5 sensors on ADC1 pins.
*/

#include <WiFi.h>
#include <PubSubClient.h>

// ------------------- EDIT THESE FOR YOUR SETUP -------------------
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
const char* MQTT_BROKER   = "192.168.1.100";   // IP of the PC running the MQTT broker
const int   MQTT_PORT     = 1883;
// -------------------------------------------------------------------

const char* MQTT_TOPIC_SENSORS = "signify/sensors";
const char* DEVICE_ID           = "signify-glove-01";

// Flex sensor pins - ADC1 ONLY (see note above). Do not move these to
// GPIO 0, 2, 4, 12-15, 25, 26 or 27.
const int PIN_THUMB  = 32;
const int PIN_INDEX  = 33;
const int PIN_MIDDLE = 34;
const int PIN_RING   = 35;
const int PIN_PINKY  = 36; // labeled "VP" on many dev boards

WiFiClient espClient;
PubSubClient mqtt(espClient);

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("WiFi connected, IP: ");
  Serial.println(WiFi.localIP());
}

void connectMQTT() {
  while (!mqtt.connected()) {
    Serial.print("Connecting to MQTT broker at ");
    Serial.print(MQTT_BROKER);
    Serial.print(" ... ");
    if (mqtt.connect(DEVICE_ID)) {
      Serial.println("connected");
    } else {
      Serial.print("failed, rc=");
      Serial.print(mqtt.state());
      Serial.println(" - retrying in 2s");
      delay(2000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(300);
  analogReadResolution(12); // 0-4095, ESP32's native ADC width
  connectWiFi();
  mqtt.setServer(MQTT_BROKER, MQTT_PORT);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }
  if (!mqtt.connected()) {
    connectMQTT();
  }
  mqtt.loop();

  int thumb  = analogRead(PIN_THUMB);
  int index_ = analogRead(PIN_INDEX);
  int middle = analogRead(PIN_MIDDLE);
  int ring   = analogRead(PIN_RING);
  int pinky  = analogRead(PIN_PINKY);

  char payload[128];
  snprintf(payload, sizeof(payload),
    "{\"thumb\":%d,\"index\":%d,\"middle\":%d,\"ring\":%d,\"pinky\":%d}",
    thumb, index_, middle, ring, pinky);

  mqtt.publish(MQTT_TOPIC_SENSORS, payload);
  Serial.println(payload);

  delay(150); // ~6-7 readings/sec - stability filtering happens on the Python side
}
