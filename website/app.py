"""
Signify Website Backend (Flask)
--------------------------------
Serves the modern Signify dashboard pages and provides both MQTT-over-WebSockets
support and a local REST API bridge for real-time sign language translation
and text-to-speech.
"""

from flask import Flask, render_template, request, jsonify
import time

app = Flask(__name__)

# In-memory buffer of latest predictions for REST-based clients
latest_prediction = {
    "label": "Ready",
    "word": "System Ready",
    "confidence": 100,
    "timestamp": time.time(),
    "sensors": [0, 0, 0, 0, 0]
}


@app.route('/')
def chat():
    return render_template('index.html')


@app.route('/customize')
def customize():
    return render_template('customize.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/api/predict', methods=['POST'])
def receive_prediction():
    """Endpoint for Python collector/predictor scripts to push predictions directly."""
    global latest_prediction
    data = request.get_json(force=True, silent=True) or {}
    label = str(data.get('label', '')).strip()
    if label:
        latest_prediction = {
            "label": label,
            "word": data.get('word', label),
            "confidence": data.get('confidence', 95),
            "timestamp": time.time(),
            "sensors": data.get('sensors', [0, 0, 0, 0, 0])
        }
        return jsonify({"status": "success", "received": latest_prediction})
    return jsonify({"status": "error", "message": "No label provided"}), 400


@app.route('/api/latest', methods=['GET'])
def get_latest_prediction():
    """Poll endpoint for browsers when WebSocket/MQTT is not active."""
    return jsonify(latest_prediction)


if __name__ == '__main__':
    # Host on all interfaces so mobile phones or laptops on same WiFi can connect
    app.run(host='0.0.0.0', port=5000, debug=True)
