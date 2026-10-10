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

import numpy as np
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import tensorflow as tf

# generate_data.py lives one folder up (the main project folder) -- make it importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

app = Flask(__name__)
CORS(app)   # allows dashboard.html (opened as a local file) to call this API

WINDOW_SIZE = 60

# ---- load trained artifacts once at startup ----
model = tf.keras.models.load_model("../reignition_lstm.keras")
mean = np.load("../norm_mean.npy")
std = np.load("../norm_std.npy")


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
    score = float(model.predict(arr_norm, verbose=0)[0, 0])
    return score


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
    Server-Sent Events stream. Simulates a scenario server-side (swap this
    for real sensor reads later) and pushes {reading, risk, t} every tick.
    Query param: ?scenario=safe|risk|random
    """
    scenario = request.args.get("scenario", "random")

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

            payload = {"t": t, "reading": reading, "risk": risk}
            yield f"data: {json.dumps(payload)}\n\n"
            time.sleep(0.18)   # mimics live pacing; remove for real hardware feed

    return Response(generate(), mimetype="text/event-stream")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True ,threaded=True )
