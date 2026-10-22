"""
virtual_hardware.py
-------------------
Virtual Hardware & IoT Edge Node for the EV Battery AI Monitor.

Simulates an embedded Battery Management System (BMS) with physical sensor probes
(2x Temperature, Pack Voltage, Gas/VOC ppm). Pushes live telemetry packets
over HTTP POST to the backend API (`/api/telemetry`), which feeds the LSTM model
and live dashboard.

Modes:
  1. dataset (default) : Replays sequence runs from `dataset.csv` tick-by-tick.
  2. physics           : Real-time dynamic thermal & electrochemical differential
                         cooling equations with optional runaway fault injection.

Usage:
  python virtual_hardware.py --mode dataset --interval 0.5
  python virtual_hardware.py --mode dataset --sequence 10    # Stream specific run
  python virtual_hardware.py --mode physics --interval 0.4
"""

import argparse
import csv
import json
import math
import os
import random
import sys
import time
import urllib.error
import urllib.request

# Ensure UTF-8 output on Windows console
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ANSI Colors for terminal output
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_BLUE = "\033[94m"
COLOR_DIM = "\033[2m"


def make_bar(val, min_v, max_v, width=20, fill_char="█", empty_char="░"):
    """Render a text progress/gauge bar."""
    ratio = max(0.0, min(1.0, (val - min_v) / (max_v - min_v + 1e-9)))
    filled = int(round(ratio * width))
    return fill_char * filled + empty_char * (width - filled)


def check_backend_alive(base_url):
    """Verify backend connectivity before streaming."""
    url = f"{base_url.rstrip('/')}/api/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Virtual-BMS/1.0"})
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return True, data
    except Exception as e:
        return False, str(e)
    return False, "Unknown status"


def send_telemetry(base_url, payload):
    """Send one JSON sensor reading to POST /api/telemetry."""
    url = f"{base_url.rstrip('/')}/api/telemetry"
    json_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=json_bytes,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Virtual-BMS-Node/1.0"
        },
        method="POST"
    )

    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            latency_ms = (time.time() - t0) * 1000.0
            if resp.status == 200:
                res = json.loads(resp.read().decode("utf-8"))
                return True, res.get("risk", 0.0), latency_ms
            return False, 0.0, latency_ms
    except Exception as e:
        latency_ms = (time.time() - t0) * 1000.0
        return False, str(e), latency_ms


def iterate_sequences_from_csv(csv_path="dataset.csv", target_seq_id=None):
    """Stream sequences on-the-fly from dataset.csv without loading entire file into RAM."""
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Dataset file '{csv_path}' not found! Run generate_data.py first.")

    current_seq_id = None
    current_label = None
    readings = []

    with open(csv_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            s_id = int(row["sequence_id"])
            if target_seq_id is not None and s_id != target_seq_id:
                if s_id > target_seq_id:
                    break
                continue

            if current_seq_id is None:
                current_seq_id = s_id
                current_label = row.get("label", "unknown")

            if s_id != current_seq_id:
                yield current_seq_id, current_label, readings
                if target_seq_id is not None:
                    return
                current_seq_id = s_id
                current_label = row.get("label", "unknown")
                readings = []

            readings.append({
                "timestep": int(row["timestep"]),
                "temp1": float(row["temp1_C"]),
                "temp2": float(row["temp2_C"]),
                "voltage": float(row["voltage_V"]),
                "gas": float(row["gas_ppm"]),
                "label": row.get("label", "unknown")
            })

        if readings:
            yield current_seq_id, current_label, readings


def run_dataset_mode(args):
    """Stream stored sequences from dataset.csv tick-by-tick."""
    print(f"{COLOR_CYAN}[i] Streaming dataset from '{args.file}'...{COLOR_RESET}", flush=True)

    pkt_count = 0
    while True:
        matched_any = False
        for s_id, label, readings in iterate_sequences_from_csv(args.file, args.sequence):
            matched_any = True
            label_color = COLOR_RED if "risk" in label else COLOR_GREEN

            print(f"\n{COLOR_BOLD}=================================================================={COLOR_RESET}", flush=True)
            print(f" {COLOR_BOLD}INCIDENT SEQUENCE #{s_id} | Ground Truth: {label_color}{label.upper()}{COLOR_RESET}", flush=True)
            print(f"{COLOR_BOLD}=================================================================={COLOR_RESET}", flush=True)

            for step_data in readings:
                pkt_count += 1
                t = step_data["timestep"]
                payload = {
                    "device_id": args.device_id,
                    "sequence_id": s_id,
                    "timestep": t,
                    "temp1": step_data["temp1"],
                    "temp2": step_data["temp2"],
                    "voltage": step_data["voltage"],
                    "gas": step_data["gas"],
                    "label": label
                }

                ok, result, latency = send_telemetry(args.url, payload)

                t1 = step_data["temp1"]
                t2 = step_data["temp2"]
                volt = step_data["voltage"]
                gas = step_data["gas"]

                if ok:
                    risk = float(result)
                    risk_pct = int(round(risk * 100))
                    if risk < 0.50:
                        risk_color = COLOR_GREEN
                        badge = "OPTIMAL "
                    elif risk < 0.75:
                        risk_color = COLOR_YELLOW
                        badge = "CAUTION "
                    else:
                        risk_color = COLOR_RED
                        badge = "DANGER! "

                    risk_bar = make_bar(risk, 0.0, 1.0, width=16)
                    status_line = (
                        f" {COLOR_CYAN}[t={t:02d}]{COLOR_RESET} "
                        f"T1:{t1:5.1f}°C  T2:{t2:5.1f}°C  V:{volt:4.2f}V  G:{gas:5.0f}ppm  │ "
                        f"{risk_color}{badge} Risk:{risk_pct:3d}% [{risk_bar}]{COLOR_RESET}  "
                        f"{COLOR_DIM}({latency:3.0f}ms){COLOR_RESET}"
                    )
                else:
                    status_line = f" {COLOR_CYAN}[t={t:02d}]{COLOR_RESET} {COLOR_RED}FAILED TO TRANSMIT: {result}{COLOR_RESET}"

                print(status_line, flush=True)
                time.sleep(args.interval)

            if not args.loop:
                print(f"\n{COLOR_GREEN}✓ Sequence #{s_id} complete. Exiting.{COLOR_RESET}\n", flush=True)
                return

            print(f"{COLOR_DIM}Pause before next sequence...{COLOR_RESET}", flush=True)
            time.sleep(1.0)

        if not matched_any:
            print(f"{COLOR_RED}Error: Sequence ID {args.sequence} not found in dataset.{COLOR_RESET}", flush=True)
            return


def run_physics_mode(args):
    """Run real-time dynamic differential cooling and thermal runaway simulation."""
    print(f"\n{COLOR_BOLD}=================================================================={COLOR_RESET}")
    print(f" {COLOR_BOLD}RUNNING INTERACTIVE PHYSICS SIMULATION{COLOR_RESET}")
    print(f" {COLOR_CYAN}Physics Engine: Newton Cooling + Stochastic Off-gassing{COLOR_RESET}")
    print(f"{COLOR_BOLD}=================================================================={COLOR_RESET}\n")

    t_step = 0
    start_temp = random.uniform(70, 85)
    gas_start = random.uniform(180, 260)
    is_runaway = False
    runaway_tick = 0

    print(f"{COLOR_YELLOW}Press Ctrl+C to stop.{COLOR_RESET}")

    while True:
        t_step += 1
        # Fraction of cooling curve
        frac = min(1.0, t_step / 60.0)

        # Auto-trigger runaway after step 25 randomly if requested
        if args.trigger_runaway and t_step >= 25 and not is_runaway:
            is_runaway = True
            runaway_tick = 0
            print(f"\n{COLOR_RED}🚨 FAULT INJECTION: Thermal runaway initiated!{COLOR_RESET}\n")

        if not is_runaway:
            # Safe exponential decay
            t1 = 25.0 + (start_temp - 25.0) * math.exp(-3.5 * frac) + random.gauss(0, 0.8)
            t2 = 25.0 + (start_temp - 30.0) * math.exp(-3.8 * frac) + random.gauss(0, 0.8)
            voltage = max(0.5, 3.0 - 0.3 * frac + random.gauss(0, 0.03))
            gas = max(5.0, gas_start * math.exp(-3.0 * frac) + random.gauss(0, 4.0))
            label = "stabilizing"
        else:
            # Active runaway re-spike
            runaway_tick += 1
            k = runaway_tick
            t1 = 35.0 + 4.0 * math.exp(0.12 * k) + random.gauss(0, 1.2)
            t2 = 30.0 + 1.5 * math.exp(0.08 * k) + random.gauss(0, 0.9)
            voltage = max(0.2, 2.7 - 0.05 * k + random.gauss(0, 0.06))
            gas = 40.0 + 20.0 * math.exp(0.15 * k) + random.gauss(0, 8.0)
            label = "reignition_risk"

        t1 = max(20.0, min(300.0, t1))
        t2 = max(20.0, min(300.0, t2))
        gas = max(0.0, min(2000.0, gas))

        payload = {
            "device_id": args.device_id,
            "timestep": t_step,
            "temp1": round(t1, 2),
            "temp2": round(t2, 2),
            "voltage": round(voltage, 3),
            "gas": round(gas, 1),
            "label": label
        }

        ok, result, latency = send_telemetry(args.url, payload)

        if ok:
            risk = float(result)
            risk_pct = int(round(risk * 100))
            risk_color = COLOR_GREEN if risk < 0.50 else (COLOR_YELLOW if risk < 0.75 else COLOR_RED)
            badge = "OPTIMAL " if risk < 0.50 else ("CAUTION " if risk < 0.75 else "DANGER! ")
            risk_bar = make_bar(risk, 0.0, 1.0, width=16)
            print(
                f" {COLOR_CYAN}[t={t_step:03d}]{COLOR_RESET} "
                f"T1:{t1:5.1f}°C  T2:{t2:5.1f}°C  V:{voltage:4.2f}V  G:{gas:5.0f}ppm  │ "
                f"{risk_color}{badge} Risk:{risk_pct:3d}% [{risk_bar}]{COLOR_RESET}  "
                f"{COLOR_DIM}({latency:3.0f}ms){COLOR_RESET}"
            )
        else:
            print(f" {COLOR_CYAN}[t={t_step:03d}]{COLOR_RESET} {COLOR_RED}FAILED: {result}{COLOR_RESET}")

        time.sleep(args.interval)


def main():
    parser = argparse.ArgumentParser(description="EV Battery AI Monitor - Virtual Hardware Node")
    parser.add_argument("--mode", choices=["dataset", "physics"], default="dataset",
                        help="Mode: 'dataset' (replay dataset.csv) or 'physics' (live equations)")
    parser.add_argument("--file", default="dataset.csv", help="Path to dataset.csv")
    parser.add_argument("--sequence", type=int, default=None,
                        help="Specific sequence_id to stream (default: sequential)")
    parser.add_argument("--interval", type=float, default=0.5,
                        help="Time between readings in seconds (default: 0.5)")
    parser.add_argument("--url", default="https://ev-monitor-backend.onrender.com",
                        help="Backend URL (default: https://ev-monitor-backend.onrender.com or http://127.0.0.1:5000)")
    parser.add_argument("--device-id", default="BMS-VIRTUAL-01",
                        help="Virtual hardware device identifier")
    parser.add_argument("--no-loop", dest="loop", action="store_false",
                        help="Do not loop sequences continuously (exit after 1 sequence)")
    parser.add_argument("--trigger-runaway", action="store_true", default=False,
                        help="Automatically inject runaway fault after t=25 in physics mode")
    parser.set_defaults(loop=True)

    args = parser.parse_args()

    print(f"\n{COLOR_BOLD}{COLOR_GREEN}╔═══════════════════════════════════════════════════════════════╗{COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_GREEN}║       EV Battery AI Monitor - Virtual Hardware Node           ║{COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_GREEN}╚═══════════════════════════════════════════════════════════════╝{COLOR_RESET}")
    print(f" Device ID : {COLOR_CYAN}{args.device_id}{COLOR_RESET}")
    print(f" Target API: {COLOR_CYAN}{args.url}{COLOR_RESET}")
    print(f" Mode      : {COLOR_BOLD}{args.mode.upper()}{COLOR_RESET}")
    print(f" Interval  : {args.interval}s per tick")

    # Health check
    print(f"\n{COLOR_DIM}Checking backend connection at {args.url}...{COLOR_RESET}")
    alive, info = check_backend_alive(args.url)
    if not alive:
        print(f"{COLOR_YELLOW}⚠️  Warning: Backend not responding at {args.url} ({info}).{COLOR_RESET}")
        print(f"{COLOR_YELLOW}   Make sure 'python backend/server.py' is running!{COLOR_RESET}\n")
    else:
        print(f"{COLOR_GREEN}✓ Backend online! Connected to LSTM inference engine.{COLOR_RESET}\n")

    try:
        if args.mode == "dataset":
            run_dataset_mode(args)
        else:
            run_physics_mode(args)
    except KeyboardInterrupt:
        print(f"\n\n{COLOR_YELLOW}[!] Virtual Hardware stopped by user.{COLOR_RESET}")


if __name__ == "__main__":
    main()
