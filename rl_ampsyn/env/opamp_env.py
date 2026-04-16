import gymnasium as gym
from gymnasium import spaces
import numpy as np
import json
import os
import sys

# Ensure imports work from project root
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
import sim.ngspice_runner as ngspice_runner
import netlist.llm_netlist_gen as llm_netlist_gen
from specset.generate_specset import SPEC_BOUNDS
from specset.opamp_selector_scoring import TOPOLOGY_LABELS, score_topology

SPEC_KEYS = list(SPEC_BOUNDS.keys())

class OpAmpEnv(gym.Env):
    def __init__(self, specset_path=None):
        super(OpAmpEnv, self).__init__()
        
        self.action_space = spaces.Discrete(8)
        self.observation_space = spaces.Box(low=0, high=1, shape=(11,), dtype=np.float32)
        
        if specset_path is None:
            specset_path = os.path.join(os.path.dirname(__file__), "../specset/specset_opamp.json")
            
        try:
            with open(specset_path, "r") as f:
                self.dataset = json.load(f)
        except Exception as e:
            print(f"[Warning] Could not load specset, will use dummy spec on reset: {e}")
            self.dataset = []
            
        self.current_spec = None
        
    def _normalize(self, spec):
        vec = []
        for k in SPEC_KEYS:
            bnd = SPEC_BOUNDS[k]
            val = spec[k]
            if isinstance(bnd, tuple):
                mn, mx = bnd
                if k in ["gbw_hz", "pmax_w"]:
                    # log normalized bounds
                    mn, mx = np.log10(mn), np.log10(mx)
                    val = np.log10(max(val, 1e-15))
                v = (val - mn) / (mx - mn)
                vec.append(max(0.0, min(1.0, v)))
            elif isinstance(bnd, list):
                vec.append(float(val))
        return np.array(vec, dtype=np.float32)
        
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        
        if self.dataset:
            idx = self.np_random.integers(0, len(self.dataset))
            self.current_spec = self.dataset[idx]["spec"]
        else:
            self.current_spec = {
                "vdd": 1.8, "gain_db": 60, "gbw_hz": 1e7, "cl_f": 1e-12, 
                "pmax_w": 1e-3, "swing_pct": 0.8, "noise_priority": 3, 
                "mixed_signal": 0, "low_voltage": 0, "diff_input": 1, "ultra_low_i": 0
            }
            
        return self._normalize(self.current_spec), {}
        
    def step(self, action):
        topology_name = TOPOLOGY_LABELS[action]
        netlist_path = llm_netlist_gen.generate(self.current_spec, topology_name)
        
        metrics = ngspice_runner.run(netlist_path)
        
        # Compute simulation reward
        sim_reward = self.compute_reward(metrics, self.current_spec)
        
        # Compute expert shaping bonus (domain knowledge injection)
        expert_bonus = self.compute_expert_bonus(topology_name, self.current_spec)
        
        # Total reward = simulation quality + expert guidance
        reward = sim_reward + expert_bonus
        
        done = True
        truncated = False
        
        info = {
            "metrics": metrics, "netlist": netlist_path, "topology": topology_name,
            "sim_reward": sim_reward, "expert_bonus": expert_bonus
        }
        
        # Cleanup temp netlist to prevent disk space leaks
        try:
            if os.path.exists(netlist_path):
                os.remove(netlist_path)
            lis_path = f"{netlist_path}.lis"
            if os.path.exists(lis_path):
                os.remove(lis_path)
        except:
            pass
            
        return self._normalize(self.current_spec), reward, done, truncated, info

    def compute_expert_bonus(self, topology_name, spec):
        """Expert reward shaping: bonus if the chosen topology is domain-appropriate.
        
        This encodes analog design knowledge into the reward signal:
        - Score each topology for this spec using expert heuristics
        - Normalize to [0, 1] range
        - If the chosen topology is in the top-2 expert picks: bonus
        - If it's the worst pick: penalty
        
        Weight: 0.3 (significant but doesn't override simulation reality)
        """
        scores = {t: score_topology(t, spec) for t in TOPOLOGY_LABELS}
        sorted_topos = sorted(scores.items(), key=lambda x: -x[1])
        
        # Rank of chosen topology (0 = best, 7 = worst)
        rank = [t for t, s in sorted_topos].index(topology_name)
        
        # Continuous shaping: best gets +0.3, worst gets -0.1
        # Linear mapping: rank 0 → +0.3, rank 7 → -0.1
        bonus = 0.3 - (rank / 7.0) * 0.4
        
        return bonus

    def compute_reward(self, metrics, targets):
        if metrics is None:
            return -5.0  # Complete failure — simulation crashed or timed out

        # Check if metrics are physically plausible at all
        if metrics.get("gain_db", 0) < 0 or metrics.get("gbw_hz", 0) < 0:
            return -3.0  # Simulation ran but produced nonsense

        # Normal weighted reward with per-metric clamping
        w_gain = 0.35
        w_gbw = 0.35
        w_pm = 0.15
        w_pwr = 0.15

        r = 0.0

        tg = max(targets["gain_db"], 1e-3)
        r += w_gain * max(0.0, 1.0 - abs(metrics["gain_db"] - tg) / tg)

        tb = max(targets["gbw_hz"], 1e-3)
        r += w_gbw * max(0.0, 1.0 - abs(metrics["gbw_hz"] - tb) / tb)

        # Power: only penalize if power is physically meaningful (> 1µW)
        # Templates with ideal current sources report near-zero power — don't reward that
        tp = max(targets["pmax_w"], 1e-9)
        pwr = metrics.get("pwr_w", 1.0)
        if pwr < 1e-8:
            # Suspiciously low power — likely measurement artifact, neutral score
            r += w_pwr * 0.5
        elif pwr > tp:
            r -= w_pwr * min(1.0, (pwr - tp) / tp)
        else:
            r += w_pwr  # Full power reward if legitimately under spec

        tpm = 60.0  # Standard phase margin target
        r += w_pm * max(0.0, 1.0 - abs(metrics["pm_deg"] - tpm) / tpm)

        # Bonus for gain and GBW within 20% of target
        all_close = all(
            abs(metrics.get(k, 0) - targets.get(k, 1)) / max(targets.get(k, 1), 1e-9) < 0.2
            for k in ["gain_db", "gbw_hz"]
        )
        if all_close:
            r += 1.0

        return float(np.clip(r, -1.0, 2.0))
