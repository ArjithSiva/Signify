/*
  Signify - ESP32 Wired Glove Firmware (USB Serial Version)
  ---------------------------------------------------------
  Reads 5 flex sensors (thumb, index, middle, ring, pinky) and sends
  calibrated/smoothed 12-bit ADC values (0-4095) over the USB data cable.
  
  Wiring (30-pin ESP32 with 3.3V voltage dividers):
    - Thumb  : GPIO 32
    - Index  : GPIO 33
    - Middle : GPIO 34
    - Ring   : GPIO 35
    - Pinky  : GPIO 36 (VP / SVP)
    
  Power:
    - 3.3V from ESP32 to one leg of each flex sensor
    - 10k fixed resistor from other leg to GND
    - Middle junction to the designated ESP32 GPIO pin

  No WiFi or MQTT needed. Works directly with USB serial at 115200 baud.
*/

// Pin definitions (All ADC1 pins - safe and stable)
const int PIN_THUMB  = 32;
const int PIN_INDEX  = 33;
const int PIN_MIDDLE = 34;
const int PIN_RING   = 35;
const int PIN_PINKY  = 36; // Labeled VP or SVP on 30-pin boards

// Number of ADC readings averaged per sample to filter electrical noise
const int NUM_SAMPLES = 8;

int readSmoothed(int pin) {
  long sum = 0;
  for (int i = 0; i < NUM_SAMPLES; i++) {
    sum += analogRead(pin);
    delayMicroseconds(250);
  }
  return sum / NUM_SAMPLES;
}

void setup() {
  Serial.begin(115200);
  
  // Set ADC resolution to 12-bit (range 0 - 4095)
  analogReadResolution(12);
  
  // Optional: set attenuation to 11dB to read the full 0 - 3.3V range
  analogSetAttenuation(ADC_11db);
  
  // Small delay for serial to stabilize
  delay(1000);
  Serial.println("\n{\"status\":\"ready\",\"device\":\"Signify-ESP32-Wired\"}");
}

void loop() {
  int thumb  = readSmoothed(PIN_THUMB);
  int index_ = readSmoothed(PIN_INDEX);
  int middle = readSmoothed(PIN_MIDDLE);
  int ring   = readSmoothed(PIN_RING);
  int pinky  = readSmoothed(PIN_PINKY);

  // Send formatted JSON over USB Serial
  Serial.print("{\"thumb\":");
  Serial.print(thumb);
  Serial.print(",\"index\":");
  Serial.print(index_);
  Serial.print(",\"middle\":");
  Serial.print(middle);
  Serial.print(",\"ring\":");
  Serial.print(ring);
  Serial.print(",\"pinky\":");
  Serial.print(pinky);
  Serial.println("}");

  // Send updates ~15 times per second (smooth and responsive)
  delay(65);
}
