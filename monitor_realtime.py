"""
monitor_realtime.py
--------------------
Simulates the deployed use case: a responder places sensors on a crashed
EV pack after suppression, and this streams a running risk score.
"""

import numpy as np
import tensorflow as tf
from collections import deque

WINDOW_SIZE = 60


def load_artifacts():
    model = tf.keras.models.load_model("reignition_lstm.keras")
    mean = np.load("norm_mean.npy")
    std = np.load("norm_std.npy")
    return model, mean, std


def simulate_stream(risky=True):
    from generate_data import reignition_risk_sequence, stabilizing_sequence
    return reignition_risk_sequence() if risky else stabilizing_sequence()


def run_monitor(model, mean, std, stream):
    window = deque(maxlen=WINDOW_SIZE)
    alert_raised = False

    for t, reading in enumerate(stream):
        window.append(reading)
        if len(window) < WINDOW_SIZE:
            continue

        arr = (np.array(window) - mean) / std
        arr = arr[np.newaxis, :, :]
        risk_score = float(model.predict(arr, verbose=0)[0, 0])

        temp1, temp2, voltage, gas = reading
        bar = "#" * int(risk_score * 30)
        print(f"t={t:3d} | temp1={temp1:6.1f}C  gas={gas:6.1f}ppm | "
              f"risk={risk_score:.2f} [{bar:<30s}]")

        if risk_score >= 0.5 and not alert_raised:
            print(f"\n*** REIGNITION RISK ALERT at t={t}. "
                  f"Extend containment / re-inspect pack. ***\n")
            alert_raised = True

    if not alert_raised:
        print("\nNo reignition risk detected -- consider standard release "
              "criteria (still confirm with physical inspection).")


if __name__ == "__main__":
    model, mean, std = load_artifacts()
    stream = simulate_stream(risky=True)
    run_monitor(model, mean, std, stream)