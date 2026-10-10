"""
generate_data.py
-----------------
Simulates POST-INCIDENT battery sensor readings after a crash/fire has
already been suppressed. Unlike a pre-crash fire detector (which watches
for a rising trend), this watches a COOLING trend and asks: does it keep
cooling safely, or does "stranded energy" in heat-damaged cells cause it
to re-spike toward a second thermal runaway (reignition)?

Sensors simulated (4 features):
  1. Temperature - probe 1 (near suspected damage zone), C
  2. Temperature - probe 2 (elsewhere on pack), C
  3. Voltage (V) - residual pack voltage
  4. Gas/VOC level (ppm) - residual off-gassing from damaged cells

Labels: 0 = stabilizing safely, 1 = reignition risk (re-spike coming)
"""

import numpy as np

RNG = np.random.default_rng(7)

TIMESTEPS = 60           # e.g. one reading every 5 min over 5 hours
FEATURES = 4              # temp1, temp2, voltage, gas
N_SEQUENCES_PER_CLASS = 1000


def stabilizing_sequence():
    """Pack cools down steadily and safely after suppression."""
    t = np.linspace(0, 1, TIMESTEPS)
    start_temp = RNG.uniform(60, 90)
    temp1 = 25 + (start_temp - 25) * np.exp(-3.5 * t) + RNG.normal(0, 1.0, TIMESTEPS)
    temp2 = 25 + (start_temp - 30) * np.exp(-3.8 * t) + RNG.normal(0, 1.0, TIMESTEPS)

    voltage = np.clip(3.0 - 0.3 * t + RNG.normal(0, 0.05, TIMESTEPS), 0, None)
    gas_start = RNG.uniform(150, 300)
    gas = gas_start * np.exp(-3.0 * t) + RNG.normal(0, 5, TIMESTEPS)
    gas = np.clip(gas, 0, None)

    return np.stack([temp1, temp2, voltage, gas], axis=1)


def reignition_risk_sequence():
    """Cools normally at first, then re-spikes from stranded energy."""
    t = np.linspace(0, 1, TIMESTEPS)
    respike_start = RNG.integers(20, 45)

    start_temp = RNG.uniform(60, 90)
    temp1 = np.zeros(TIMESTEPS)
    temp2 = np.zeros(TIMESTEPS)
    voltage = np.zeros(TIMESTEPS)
    gas = np.zeros(TIMESTEPS)

    gas_start = RNG.uniform(150, 300)

    for i in range(TIMESTEPS):
        frac = i / TIMESTEPS
        if i < respike_start:
            temp1[i] = 25 + (start_temp - 25) * np.exp(-3.5 * frac) + RNG.normal(0, 1.0)
            temp2[i] = 25 + (start_temp - 30) * np.exp(-3.8 * frac) + RNG.normal(0, 1.0)
            voltage[i] = max(0, 3.0 - 0.3 * frac + RNG.normal(0, 0.05))
            gas[i] = max(0, gas_start * np.exp(-3.0 * frac) + RNG.normal(0, 5))
        else:
            k = i - respike_start
            temp1[i] = temp1[respike_start - 1] + 4 * np.exp(0.12 * k) + RNG.normal(0, 1.5)
            temp2[i] = temp2[respike_start - 1] + 1.5 * np.exp(0.08 * k) + RNG.normal(0, 1.0)
            voltage[i] = max(0.2, voltage[respike_start - 1] - 0.05 * k + RNG.normal(0, 0.08))
            gas[i] = gas[respike_start - 1] + 20 * np.exp(0.15 * k) + RNG.normal(0, 10)

    temp1 = np.clip(temp1, 20, 300)
    temp2 = np.clip(temp2, 20, 300)
    gas = np.clip(gas, 0, 2000)

    return np.stack([temp1, temp2, voltage, gas], axis=1)


def build_dataset():
    X, y = [], []
    for _ in range(N_SEQUENCES_PER_CLASS):
        X.append(stabilizing_sequence())
        y.append(0)
    for _ in range(N_SEQUENCES_PER_CLASS):
        X.append(reignition_risk_sequence())
        y.append(1)

    X = np.array(X, dtype=np.float32)
    y = np.array(y, dtype=np.int64)

    idx = RNG.permutation(len(X))
    return X[idx], y[idx]


if __name__ == "__main__":
    X, y = build_dataset()
    print("X shape:", X.shape)
    print("y shape:", y.shape)
    print("Class counts (0=stabilizing, 1=reignition risk):", np.bincount(y))

    np.save("sequences.npy", X)
    np.save("labels.npy", y)
    print("Saved sequences.npy and labels.npy")