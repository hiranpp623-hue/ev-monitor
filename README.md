# Post-Crash Battery Reignition Risk Prediction

Predicts whether a crashed/suppressed EV battery pack is stabilizing
safely or heading toward a delayed reignition ("stranded energy"),
using an LSTM over post-incident sensor readings.

## Setup

```bash
pip install tensorflow numpy scikit-learn
```

## Run order

```bash
pip install matplotlib   # needed in addition to the packages above
python generate_data.py       # creates sequences.npy, labels.npy, dataset.csv, sample_curves.png
python train.py                # trains model, prints metrics, saves reignition_lstm.keras
python monitor_realtime.py     # simulates a live post-incident monitoring session
```

## Files

| File | Purpose |
|---|---|
| `generate_data.py` | Generates synthetic post-incident sensor sequences AND exports demo-ready `dataset.csv` + `sample_curves.png` in one run |
| `train.py` | LSTM binary classifier, training, evaluation, early-warning metric |
| `monitor_realtime.py` | Simulated live monitoring session with a running risk score |

## What `generate_data.py` now produces, in one run

- `sequences.npy` / `labels.npy` — for training (`train.py` reads these)
- `dataset.csv` — flat, human-readable table (sequence_id, timestep, temp1, temp2, voltage, gas, label) — open in Excel or attach as an appendix
- `sample_curves.png` — a 4-panel plot comparing one stabilizing vs one reignition-risk example across all sensors — use this as your demo/report headline image; the two curves look identical early on and only diverge when the re-spike happens, which visually makes the case for why a time-series model is needed over a simple threshold check

## Key differences from a pre-crash fire detector (for your report)

- **Input shape**: a *cooling* trend that may or may not re-spike, not a rising trend
- **Labels**: binary (`stabilizing` / `reignition_risk`), not a 3-class normal/warning/fire
- **Headline metric**: "early-warning lead" — how many timesteps before a raw
  temperature re-spike becomes obvious does the model already flag risk?
  This directly maps to extra time given to a responder before they'd
  notice with a thermal camera alone.
- **Time horizon**: hours, not seconds — a gentler real-time constraint,
  which matters if you're also deploying this on ESP32 hardware.

## Data generation logic (document this in your report)

`generate_data.py` simulates two physically-grounded scenarios:
1. **Stabilizing**: pack temperature decays exponentially toward ambient,
   voltage drifts down slowly, gas off-gassing tapers off — normal
   post-suppression cooldown.
2. **Reignition risk**: identical-looking cooldown for a while, then an
   internal short in a heat-damaged cell causes temperature and gas to
   climb again while voltage sags irregularly — modeling "stranded
   energy" reheating the pack.

Because no public dataset of real post-crash EV sensor logs exists, this
is synthetic — state this explicitly and cite it as a limitation, same
as you would for a pre-crash detector.

## Next steps

- Convert `reignition_lstm.keras` to TensorFlow Lite for ESP32 deployment
- Run a controlled heat-source test (soldering iron/hot air gun, safe
  distance, never a real damaged cell) to validate your synthetic
  re-spike curve shape against something real
- Consider extending the risk score to a rough time-to-reignition
  estimate (regression head) if you have time — currently this is
  binary risk classification only
