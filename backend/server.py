"""
server.py
---------
Backend API for the Reignition Watch dashboard. Loads the trained LSTM
and serves it over HTTP so the browser frontend can get REAL predictions
instead of the in-browser heuristic.

Two endpoints:
  POST /api/predict  - send a window of readings, get back a risk score
  GET  /api/stream    - Server-Sent Events stream: simulates (or later,
                         reads real hardware) readings tick by tick and
                         pushes {reading, risk} to the browser live

Run:
    pip install flask flask-cors tensorflow numpy
    python server.py
    (keep this running, then open dashboard.html in your browser)
"""

import json
import time
import sys
import os
import queue
import threading

import numpy as np
from flask import Flask, request, jsonify, Response, send_from_directory
from flask_cors import CORS
import tensorflow as tf

# generate_data.py lives one folder up (the main project folder) -- make it importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

app = Flask(__name__)
CORS(app)   # allows dashboard.html (opened as a local file) to call this API

WINDOW_SIZE = 60

# ---- load trained artifacts once at startup ----
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
model = tf.keras.models.load_model(os.path.join(PROJECT_ROOT, "reignition_lstm.keras"))
mean = np.load(os.path.join(PROJECT_ROOT, "norm_mean.npy"))
std = np.load(os.path.join(PROJECT_ROOT, "norm_std.npy"))

# ---- Live Hardware Ingestion State ----
hardware_buffer = []
hardware_buffer_lock = threading.Lock()
subscribers = set()
subscribers_lock = threading.Lock()
telemetry_stats = {
    "total_packets": 0,
    "last_device_id": None,
    "last_seen": 0,
    "latest_risk": 0.0,
    "latest_reading": None
}


def predict_risk(window):
    """window: list of [temp1, temp2, voltage, gas] readings, any length."""
    arr = np.array(window, dtype=np.float32)

    # pad or trim to WINDOW_SIZE so the model always gets a consistent shape
    if len(arr) < WINDOW_SIZE:
        pad = np.repeat(arr[-1:, :], WINDOW_SIZE - len(arr), axis=0)
        arr = np.concatenate([arr, pad], axis=0)
    elif len(arr) > WINDOW_SIZE:
        arr = arr[-WINDOW_SIZE:]

    arr_norm = (arr - mean) / std
    arr_norm = arr_norm[np.newaxis, :, :]
    pred = model(arr_norm, training=False)
    score = float(pred.numpy()[0, 0])
    return score


def broadcast_payload(payload):
    """Broadcast an SSE payload dictionary to all connected live listeners."""
    msg = f"data: {json.dumps(payload)}\n\n"
    with subscribers_lock:
        stale = []
        for q in subscribers:
            try:
                q.put_nowait(msg)
            except queue.Full:
                stale.append(q)
        for q in stale:
            subscribers.discard(q)


@app.route("/", methods=["GET"])
def serve_dashboard():
    """Serve the web dashboard frontend."""
    return send_from_directory(PROJECT_ROOT, "dashboard.html")


@app.route("/<path:filename>", methods=["GET"])
def serve_static(filename):
    """Serve static assets (manifest.json, sw.js, sample images, etc.)."""
    file_path = os.path.join(PROJECT_ROOT, filename)
    if os.path.isfile(file_path):
        return send_from_directory(PROJECT_ROOT, filename)
    return jsonify({"error": "Not found"}), 404


@app.route("/api/health", methods=["GET"])
def api_health():
    """Health & hardware status check endpoint."""
    with hardware_buffer_lock:
        buf_len = len(hardware_buffer)
    return jsonify({
        "status": "online",
        "buffer_length": buf_len,
        "subscribers_connected": len(subscribers),
        "stats": telemetry_stats
    })


@app.route("/api/telemetry", methods=["POST"])
def api_telemetry():
    """
    Hardware Ingestion Endpoint:
    Body: {
      "temp1": float,
      "temp2": float,
      "voltage": float,
      "gas": float,
      "device_id": str (optional),
      "timestep": int (optional),
      "label": str (optional)
    }
    Appends reading to rolling 60-step buffer, computes real-time LSTM risk,
    and fans out live telemetry to all connected dashboard SSE streams.
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid or missing JSON payload"}), 400

    try:
        temp1 = float(data.get("temp1", 25.0))
        temp2 = float(data.get("temp2", 25.0))
        voltage = float(data.get("voltage", 3.0))
        gas = float(data.get("gas", 0.0))
    except (ValueError, TypeError) as err:
        return jsonify({"error": f"Invalid numeric sensor value: {err}"}), 400

    device_id = str(data.get("device_id", "VIRTUAL-BMS-01"))
    timestep = data.get("timestep", None)
    label = data.get("label", None)
    relay_state = str(data.get("relay_state", "CLOSED"))
    shock_g = float(data.get("shock_g", 0.1))

    reading = {
        "temp1": temp1,
        "temp2": temp2,
        "voltage": voltage,
        "gas": gas
    }

    with hardware_buffer_lock:
        hardware_buffer.append([temp1, temp2, voltage, gas])
        if len(hardware_buffer) > WINDOW_SIZE:
            hardware_buffer.pop(0)
        current_window = list(hardware_buffer)

    risk = predict_risk(current_window) if len(current_window) >= 5 else 0.0

    # Update metadata
    telemetry_stats["total_packets"] += 1
    telemetry_stats["last_device_id"] = device_id
    telemetry_stats["last_seen"] = time.time()
    telemetry_stats["latest_risk"] = risk
    telemetry_stats["latest_reading"] = reading

    payload = {
        "t": timestep if timestep is not None else telemetry_stats["total_packets"],
        "reading": reading,
        "risk": risk,
        "device_id": device_id,
        "source": "hardware",
        "label": label,
        "relay_state": relay_state,
        "shock_g": shock_g
    }

    broadcast_payload(payload)
    return jsonify({"status": "received", "risk": risk, "t": payload["t"]}), 200


@app.route("/api/predict", methods=["POST"])
def api_predict():
    """
    Body: { "window": [[temp1, temp2, voltage, gas], ...] }
    Returns: { "risk": 0.83 }
    """
    data = request.get_json()
    window = data.get("window", [])
    if not window:
        return jsonify({"error": "empty window"}), 400
    risk = predict_risk(window)
    return jsonify({"risk": risk})


@app.route("/api/stream")
def api_stream():
    """
    Server-Sent Events stream.
    Query params:
      ?scenario=live             -> Real-time stream from virtual/physical hardware via POST /api/telemetry
      ?scenario=safe|risk|random -> Standalone simulated sequence playback (fallback)
    """
    scenario = request.args.get("scenario", "live")
    mode = request.args.get("mode", scenario)

    if mode == "live" or scenario == "live":
        # Live Hardware Subscriber Mode
        client_queue = queue.Queue(maxsize=100)
        with subscribers_lock:
            subscribers.add(client_queue)

        def event_stream():
            # Send initial keep-alive / connection ACK
            yield f"data: {json.dumps({'type': 'connected', 'message': 'Subscribed to Live Hardware Telemetry'})}\n\n"
            
            # If recent hardware telemetry exists, send it immediately to populate dashboard UI
            if telemetry_stats["latest_reading"] is not None:
                init_payload = {
                    "t": telemetry_stats["total_packets"],
                    "reading": telemetry_stats["latest_reading"],
                    "risk": telemetry_stats["latest_risk"],
                    "device_id": telemetry_stats["last_device_id"] or "INITIAL-STATE",
                    "source": "hardware",
                    "label": "initial"
                }
                yield f"data: {json.dumps(init_payload)}\n\n"

            try:
                while True:
                    try:
                        # Wait for new reading pushed by hardware node
                        msg = client_queue.get(timeout=25.0)
                        yield msg
                    except queue.Empty:
                        # Heartbeat comment to prevent proxy timeouts
                        yield ": heartbeat\n\n"
            finally:
                with subscribers_lock:
                    subscribers.discard(client_queue)

        return Response(event_stream(), mimetype="text/event-stream")

    # Fallback to simulated offline scenarios
    def generate():
        from generate_data import stabilizing_sequence, reignition_risk_sequence
        import random

        if scenario == "safe":
            seq = stabilizing_sequence()
        elif scenario == "risk":
            seq = reignition_risk_sequence()
        else:
            seq = reignition_risk_sequence() if random.random() < 0.5 else stabilizing_sequence()

        history = []
        for t, row in enumerate(seq):
            reading = {
                "temp1": float(row[0]), "temp2": float(row[1]),
                "voltage": float(row[2]), "gas": float(row[3]),
            }
            history.append([reading["temp1"], reading["temp2"],
                             reading["voltage"], reading["gas"]])

            risk = predict_risk(history) if len(history) >= 5 else 0.0

            payload = {"t": t, "reading": reading, "risk": risk, "source": "simulated"}
            yield f"data: {json.dumps(payload)}\n\n"
            time.sleep(0.18)   # mimics live pacing

    return Response(generate(), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
