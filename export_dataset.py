"""
export_dataset.py
------------------
Exports the generated sequences/labels into a flat, human-readable CSV
table. Run this AFTER generate_data.py.
"""

import csv
import numpy as np

LABEL_NAMES = {0: "stabilizing", 1: "reignition_risk"}


def export_csv(X, y, path="dataset.csv"):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["sequence_id", "timestep", "temp1_C", "temp2_C",
                          "voltage_V", "gas_ppm", "label"])
        for seq_id, (seq, label) in enumerate(zip(X, y)):
            label_name = LABEL_NAMES[int(label)]
            for t, row in enumerate(seq):
                writer.writerow([seq_id, t, f"{row[0]:.2f}", f"{row[1]:.2f}",
                                  f"{row[2]:.3f}", f"{row[3]:.1f}", label_name])
    print(f"Saved {path}")


if __name__ == "__main__":
    X = np.load("sequences.npy")
    y = np.load("labels.npy")
    export_csv(X, y)