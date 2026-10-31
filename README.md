# Signify — ESP32 + MQTT rewrite

This is a rewrite of the original Signify project: the Arduino-over-cable
setup is replaced with an ESP32 talking over WiFi/MQTT, and the website
now displays predictions live instead of only simulating them.

## Architecture

```
[ESP32 + glove]  --MQTT publish-->  [Mosquitto broker]
                                       |            \
                          MQTT subscribe          MQTT-over-WebSockets
                                       |                    \
                          [predictor_service.py]      [Website in browser]
                          loads signify_model.pkl      subscribes directly,
                          publishes result back  -->    no polling needed
                          to the broker
```

The ESP32 never talks to the website directly. Everything goes through
the MQTT broker, which is what lets the ESP32, the Python model, and the
browser all update independently over WiFi.

## What changed from the original project

- **Arduino cable -> ESP32 + WiFi + MQTT.** `firmware/signify_esp32.ino`
  replaces both the old `sketch_nov10a.ino` (unrelated moisture-sensor
  sketch that had ended up in the project) and the half-finished
  `ESP32.cpp` (HTTP version). It also **moves the pinky sensor off
  GPIO25 onto GPIO36** — GPIO25 is an ADC2 pin, and ESP32's WiFi radio
  uses ADC2 internally, so `analogRead()` on ADC2 pins is unreliable
  once WiFi is connected. All 5 sensors are now on ADC1 pins (32-36),
  which stay reliable with WiFi on.
- **Serial-based `connection.py` -> `predictor_service.py`.** Same
  stability-buffer idea (wait for 5 consistent readings before
  predicting), but subscribes over MQTT instead of reading a COM port,
  and publishes the result back to MQTT instead of calling an HTTP
  route that didn't exist.
- **`CollectData.py` -> `collect_data.py`.** Same purpose, but pulls
  readings from MQTT and captures a few seconds of samples per label
  in one go, rather than one row per Enter-press.
- **Website wiring fixed.** Every template pointed at `chat.js`, which
  never existed (the real file was `script.js`). The site now loads
  `static/app.js`, which connects to the broker over MQTT-over-
  WebSockets and reacts to real predictions. The old "Simulate Gesture"
  button is kept as a fallback for demoing without hardware.
- **Duplicate website folders merged.** The project had two nearly-
  identical website folders (`website/` and `SignifyWebsite/`). This
  rewrite keeps one (`website/`), based on `SignifyWebsite/`'s proper
  Flask structure. If you were relying on something specific from the
  other `website/` folder, flag it and I'll fold it in.
- **Old dataset kept but not reused.** `gesture_data_legacy_arduino_10bit.csv`
  is your original 3-class dataset (labels `1`, `2`, `3`), collected on
  an Arduino's 10-bit ADC (0-1023). The ESP32 uses a 12-bit ADC
  (0-4095), so those old values are on the wrong scale for the new
  hardware — **don't append new ESP32 data to it.** `gesture_data.csv`
  starts empty; you'll recollect a small labeled dataset with the new
  `collect_data.py` (steps below).

## Realistic starting scope: ISL numerals, not "the entire ISL system"

You asked me to recommend a realistic starting scope, so here's the
reasoning: a single glove reading 5 static flex values (no motion
sensing, one hand only) can only ever distinguish **static, one-handed
hand-shapes**. Indian Sign Language is, per the literature, fundamentally
a two-handed language for most vocabulary, with meaning also carried by
hand orientation, movement, and facial expression — none of which this
hardware captures. So "the entire ISL system" isn't reachable on this
hardware; that would need at minimum a second glove, motion sensors
(IMU) per hand, and likely a camera-based approach for anything beyond
isolated static signs. That's worth stating plainly in your paper as
future work rather than promising it as delivered.

What **is** a good, honest fit for this hardware: **ISL numerals 0–9**,
which are widely documented as static, one-handed signs (unlike most of
the ISL alphabet, which is two-handed). This keeps the same "counting
gesture" theme as your existing 3-class data and gives you a complete,
demoable set of 10 classes.

### Hand signs and outcomes (first working version)

| Label | Hand shape (verify against your reference/ISLRTC dictionary before the demo) | Displayed & spoken outcome (default; editable on /customize) |
|---|---|---|
| 0 | Closed fist, no fingers extended | "0" |
| 1 | Index finger extended | "1" |
| 2 | Index + middle extended | "2" |
| 3 | Index + middle + ring extended | "3" |
| 4 | Index + middle + ring + pinky extended, thumb tucked | "4" |
| 5 | All 5 fingers extended | "5" |
| 6 | Regional/dictionary-specific — confirm shape | "6" |
| 7 | Regional/dictionary-specific — confirm shape | "7" |
| 8 | Regional/dictionary-specific — confirm shape | "8" |
| 9 | Regional/dictionary-specific — confirm shape | "9" |

I've deliberately not invented precise finger configurations for 6-9 —
ISL has documented regional variation here, and getting it wrong in a
paper is worse than leaving it for you to confirm against whatever
source you cite (ISLRTC's dictionary, or your own institution's
reference). Whatever shapes you pick, the classifier just needs them to
be *consistent and distinct* — use the Customize page to map each label
to whatever word/number you want displayed and spoken.

## Expanding beyond numerals: a real one-handed dataset exists (ASL, not ISL)

You asked whether another dataset could be included, one-handed, and if
not, whether to look at other sign languages. Short answer: I couldn't
find a public **flex-sensor** dataset for one-handed ISL signs (public
ISL datasets are image/video-based, for the two-handed alphabet). I did
find a genuinely relevant one for ASL:

**DU-ASL-DATA-GLOVE-DB** (Faisal et al., *"Exploiting domain
transformation and deep learning for hand gesture recognition using a
low-cost dataglove,"* Scientific Reports, 2022. DOI:
10.1038/s41598-022-25108-2. Dataset: https://figshare.com/articles/dataset/ASL-Sensor-Dataglove-Dataset_zip/20031017)

What makes it worth mentioning: the hardware they built it on is
**almost the same as yours** — 5 flex sensors (SEN-10264) in a voltage
divider, read by an ESP32's 12-bit ADC (they additionally have an IMU,
which you don't). They recorded 40 ASL signs: **24 static, one-handed
letters** (the standard ASL alphabet minus J and Z, which require
motion) **and 16 dynamic signs** (J, Z, and 14 common words like
"hello," "yes," "thank you") that need hand motion and are out of
scope for your flex-only, static setup — the same reasoning that ruled
out most of ISL applies to those 16.

**Important caveat before you use it:** raw flex-sensor ADC values are
specific to the exact sensor unit, resistor tolerances, hand size, and
glove tension of the rig that recorded them. Even with near-identical
hardware, you should not expect this dataset's numbers to classify
correctly on your own glove without collecting your own validation
data. Treat it as: (a) a validated list of *which* one-handed static
signs are worth targeting, and (b) an optional benchmark to sanity
check your pipeline (train/test split on their data, confirm your
`train_model.py` produces sane accuracy on a known-good dataset), not
as a drop-in replacement for collecting your own samples with
`collect_data.py`.

### Recommended expanded scope: ISL numerals + ASL fingerspelling

Since a real one-handed ISL alphabet dataset doesn't exist publicly,
and ASL's alphabet is one-handed (unlike ISL's), a realistic bigger
vocabulary for this hardware is:

- ISL numerals 0-9 (10 classes, as before)
- ASL static alphabet: A, B, C, D, E, F, G, H, I, K, L, M, N, O, P, Q,
  R, S, T, U, V, W, X, Y (24 classes — J and Z excluded, they need
  motion)

That's up to 34 one-handed, static classes total, all realistically
capturable by your 5-flex-sensor glove.

**Worth flagging honestly:** this makes the alphabet portion an ASL
fingerspelling recognizer, not an ISL one — mixing "Indian Sign
Language" and "American Sign Language" signs in one system is a
real design choice, not a technical detail. For a paper/demo, say so
plainly (e.g. "ISL numerals + ASL fingerspelling alphabet" or reframe
the project as a general assistive gesture-to-speech system with an
ISL module and an ASL module) rather than presenting the alphabet
half as ISL.

Use the standard ASL fingerspelling chart (widely available, e.g. via
a quick image search) as your reference when performing and labeling
each letter with `collect_data.py` — I won't reproduce a copyrighted
chart image here, but the shapes are consistent across any standard
ASL reference.

## One-time setup

1. **Install a broker.** Install [Mosquitto](https://mosquitto.org/download/)
   on the PC that will run the Python backend. Start it with the
   provided config so both plain MQTT and WebSockets are enabled:
   ```
   mosquitto -c mosquitto/mosquitto.conf
   ```
2. **Arduino IDE:** install the **PubSubClient** library (Library
   Manager -> search "PubSubClient" by Nick O'Leary), plus the ESP32
   board package if you don't already have it.
3. **Edit `firmware/signify_esp32.ino`:** set `WIFI_SSID`,
   `WIFI_PASSWORD`, and `MQTT_BROKER` (the PC's LAN IP running
   Mosquitto). Flash it to the ESP32.
4. **Edit `website/templates/index.html`:** set `BROKER_WS_URL` to
   `ws://<broker-PC-IP>:9001`.
5. **Python backend:**
   ```
   cd backend
   pip install -r requirements.txt
   ```

## Steps to demo it

1. Start Mosquitto (`mosquitto -c mosquitto/mosquitto.conf`).
2. Power on the ESP32 glove; check the Arduino Serial Monitor for
   "WiFi connected" and a stream of JSON sensor readings.
3. Collect training data (first time only, or whenever you add a
   class): `cd backend && python collect_data.py`, and record several
   rounds for each label. Start with `0`-`9`; add ASL letters
   (`A`-`Y`, skipping `J` and `Z`) the same way once numerals work
   reliably, one at a time.
4. Train the model: `python train_model.py`. Check the printed
   classification report — low accuracy on a class usually means that
   sign needs more/varied samples.
5. Start the predictor: `python predictor_service.py`. It will print
   each prediction as you sign.
6. Start the website: `cd ../website && python app.py`, then open
   `http://localhost:5000` in a browser on the same network.
7. (Optional) Visit `/customize` first to map labels to whatever
   words you want spoken (e.g. `0` -> "zero", or a name/phrase).
8. Perform each sign on the glove and hold it steady for a second —
   the word should appear in the chat box and can be read aloud with
   "Speak Last". Use "Simulate Gesture" to demo the UI if the hardware
   isn't available.

## Known limitations / flagged for you

- No authentication on the MQTT broker — fine for a local demo, not
  for anything beyond your LAN.
- The stability threshold and buffer size in `predictor_service.py`
  (`STABILITY_THRESHOLD = 15`, `BUFFER_SIZE = 5`) were carried over
  from the original `connection.py` design; you'll likely want to
  retune them once you see real ESP32 ADC noise levels, which can
  differ from the Arduino's.
- Only one glove is modeled. If you want two-handed signs later,
  you'd need a second ESP32 (or a second sensor set on the same board)
  publishing to a distinct topic, and a model trained on the combined
  feature vector.
