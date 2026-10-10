"""
visualize_dataset.py
---------------------
Generates a comparison plot of a "stabilizing" vs "reignition risk"
example sequence across all sensors -- your headline demo/report image.
"""

import numpy as np
import matplotlib.pyplot as plt

from generate_data import stabilizing_sequence, reignition_risk_sequence, TIMESTEPS


def plot_example_curves(path="sample_curves.png"):
    safe = stabilizing_sequence()
    risk = reignition_risk_sequence()
    t = np.arange(TIMESTEPS)

    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    fig.suptitle("Post-Crash Battery Monitoring: Stabilizing vs Reignition Risk",
                 fontsize=13, fontweight="bold")

    panels = [
        (axes[0, 0], 0, "Temperature - Probe 1", "°C"),
        (axes[0, 1], 1, "Temperature - Probe 2", "°C"),
        (axes[1, 0], 2, "Voltage", "V"),
        (axes[1, 1], 3, "Gas / VOC level", "ppm"),
    ]
    for ax, feat_idx, title, ylabel in panels:
        ax.plot(t, safe[:, feat_idx], label="stabilizing", color="#2a9d8f")
        ax.plot(t, risk[:, feat_idx], label="reignition risk", color="#e76f51")
        ax.set_title(title)
        ax.set_xlabel("timestep")
        ax.set_ylabel(ylabel)
        ax.legend()

    plt.tight_layout()
    plt.savefig(path, dpi=150)
    print(f"Saved {path}")


if __name__ == "__main__":
    plot_example_curves()