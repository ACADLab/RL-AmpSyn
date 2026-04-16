import json
import numpy as np
import os
import sys

# Ensure import works when running from anywhere or within specset dir
sys.path.append(os.path.dirname(__file__))
from opamp_selector_scoring import score_topology, TOPOLOGY_LABELS

N_SAMPLES = 600

SPEC_BOUNDS = {
    "vdd":    (0.3, 5.0),
    "gain_db":(40,  120),
    "gbw_hz": (1e5, 1e9), # log
    "cl_f":   (1e-12, 100e-12),
    "pmax_w": (10e-9, 10e-3), # log
    "swing_pct": (0.5, 1.0),
    "noise_priority": (1, 5), # int
    "mixed_signal": [0, 1],
    "low_voltage":  [0, 1],
    "diff_input":   [0, 1],
    "ultra_low_i":  [0, 1],
}

def generate_samples():
    dataset = []
    np.random.seed(42)
    for i in range(N_SAMPLES):
        spec = {
            "vdd": float(round(np.random.uniform(*SPEC_BOUNDS["vdd"]), 2)),
            "gain_db": float(round(np.random.uniform(*SPEC_BOUNDS["gain_db"]), 1)),
            "gbw_hz": float(np.exp(np.random.uniform(np.log(SPEC_BOUNDS["gbw_hz"][0]), np.log(SPEC_BOUNDS["gbw_hz"][1])))),
            "cl_f": float(np.random.uniform(*SPEC_BOUNDS["cl_f"])),
            "pmax_w": float(np.exp(np.random.uniform(np.log(SPEC_BOUNDS["pmax_w"][0]), np.log(SPEC_BOUNDS["pmax_w"][1])))),
            "swing_pct": float(round(np.random.uniform(*SPEC_BOUNDS["swing_pct"]), 2)),
            "noise_priority": int(np.random.randint(SPEC_BOUNDS["noise_priority"][0], SPEC_BOUNDS["noise_priority"][1]+1)),
            "mixed_signal": int(np.random.choice(SPEC_BOUNDS["mixed_signal"])),
            "low_voltage":  int(np.random.choice(SPEC_BOUNDS["low_voltage"])),
            "diff_input":   int(np.random.choice(SPEC_BOUNDS["diff_input"])),
            "ultra_low_i":  int(np.random.choice(SPEC_BOUNDS["ultra_low_i"]))
        }
        
        scores = {t: score_topology(t, spec) for t in TOPOLOGY_LABELS}
        best_topology = max(scores, key=scores.get)
        
        entry = {
            "id": f"spec_{i:04d}",
            "spec": spec,
            "topology": best_topology,
            "netlist_path": f"templates/{best_topology.lower()}.sp",
            "sizing_hints": {"ibias_ua": 10, "wl_ratio_input": 20}
        }
        dataset.append(entry)
        
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "specset_opamp.json")
    with open(out_path, "w") as f:
        json.dump(dataset, f, indent=2)
    print(f"Dataset generated at {out_path}")

if __name__ == "__main__":
    generate_samples()
