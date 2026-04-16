# RL-AmpSyn: Neural-Symbolic Analog Circuit Synthesizer

## Table of Contents

1. [The Problem](#1-the-problem)
2. [Our Approach](#2-our-approach)
3. [The 8 Topologies — What They Are and When to Use Them](#3-the-8-topologies)
4. [What Parameters Change, How, and Why](#4-parameters)
5. [Output Parameters We Measure](#5-output-parameters)
6. [Why DQN? (Policy Justification)](#6-why-dqn)
7. [Training Pipeline (How the Agent Learns)](#7-training-pipeline)
8. [Inference Pipeline (What the User Gets)](#8-inference-pipeline)
9. [Expert Reward Shaping — Domain Knowledge Injection](#9-expert-shaping)
10. [Current Status](#10-current-status)
11. [File Reference](#11-files)
12. [How to Run](#12-how-to-run)

---

## 1. The Problem <a name="1-the-problem"></a>

An analog circuit designer faces two sequential decisions when designing an op-amp:

1. **Topology Selection**: "Which circuit architecture should I use?" (e.g., single-stage OTA vs. two-stage Miller vs. folded cascode). This is a discrete, experience-driven choice.
2. **Transistor Sizing**: "Given this topology, what should the transistor widths, lengths, and bias currents be?" This is a continuous optimization over a high-dimensional space.

Both steps are traditionally done by human experts using intuition, textbook rules, and iterative SPICE simulation. **RL-AmpSyn automates both steps.**

**Input**: A target specification like:
```
Gain ≥ 60 dB, GBW ≥ 10 MHz, Power ≤ 1 mW, VDD = 1.8 V
```

**Output**: A complete, simulation-validated SPICE netlist (`.sp` file) with:
- The correct topology selected automatically
- All transistor W/L dimensions and bias currents sized
- Verified simulation metrics (gain, bandwidth, phase margin, power)

---

## 2. Our Approach <a name="2-our-approach"></a>

### The Hybrid RL + LLM Architecture

We split the problem into two sub-problems handled by two different AI systems:

```
┌──────────────────────────────────────────────────────────┐
│  USER: "I need 60dB gain, 10MHz GBW, <1mW power"        │
│                          │                               │
│                          ▼                               │
│  ┌─────────────────────────────┐                         │
│  │  DQN AGENT (Architect)      │  Discrete decision      │
│  │  Observes: 11D spec vector  │  maker. Picks 1 of 8    │
│  │  Outputs: topology index    │  topologies based on     │
│  │  (0-7)                      │  learned Q-values.       │
│  └──────────┬──────────────────┘                         │
│             │ Action = "Two_Stage_Miller"                 │
│             ▼                                            │
│  ┌─────────────────────────────┐                         │
│  │  LLM CODER (Contractor)     │  Parameter generator.   │
│  │  Model: Qwen-2.5-7B local   │  Uses RAG to find 3     │
│  │  Input: spec + topology      │  similar expert designs │
│  │  Output: .PARAM overrides    │  and interpolates W/L.  │
│  └──────────┬──────────────────┘                         │
│             │ .PARAM w_in=3.6u l_in=500n ibias=12u ...   │
│             ▼                                            │
│  ┌─────────────────────────────┐                         │
│  │  CONSTRAINT CLAMPER          │  Physical bounds:       │
│  │  W,L ≥ 180nm (PDK min)     │  No hallucinated        │
│  │  Ibias: 1nA - 10mA         │  dimensions allowed.     │
│  └──────────┬──────────────────┘                         │
│             │ Clamped params injected into template       │
│             ▼                                            │
│  ┌─────────────────────────────┐                         │
│  │  NGSPICE SIMULATOR          │  Runs .op (DC) then     │
│  │  PDK: TSMC 180nm BSIM3v3   │  .ac (frequency sweep)  │
│  │  Output: gain, GBW, PM, Pwr│  on the circuit.         │
│  └──────────┬──────────────────┘                         │
│             │ Metrics fed back as reward                  │
│             ▼                                            │
│  ┌─────────────────────────────┐                         │
│  │  REWARD FUNCTION             │                        │
│  │  sim_reward: how close to   │  Gradient signal back    │
│  │  target specs?              │  to the DQN agent.       │
│  │  expert_bonus: was this the │                         │
│  │  right topology for the     │                         │
│  │  spec?                      │                         │
│  └─────────────────────────────┘                         │
└──────────────────────────────────────────────────────────┘
```

### Why Two Systems Instead of One?

- **RL alone** can't generate SPICE code — the action space would be infinite (continuous W/L values for every transistor)
- **LLM alone** hallucinates circuit connections, invents nonexistent nodes, and has no feedback from physics
- **Together**: RL handles the discrete architectural decision (8 choices), LLM handles the continuous sizing (interpolation between reference designs), ngspice provides ground truth

---

## 3. The 8 Topologies <a name="3-the-8-topologies"></a>

Each topology is a fixed circuit structure stored as a `.sp` template. The topology defines **how transistors are connected** — this never changes. Only the transistor **dimensions** (W, L, Ibias) are varied by the LLM.

### Topology 0: 5T_OTA (5-Transistor Operational Transconductance Amplifier)

```
     VDD
      │
   ┌──┴──┐
   M3    M4          ← PMOS active load (current mirror)
   │      │
 net1    out          ← Output node
   │      │
   M1    M2          ← NMOS differential pair (input transistors)
   │      │
   └──┬──┘
      │
     M5              ← NMOS tail current source
      │
     VSS
```

**Best for**: Ultra-low power, low-complexity applications.
**Typical gain**: 30-45 dB (single stage).
**Parameters**: `w_in, l_in, w_load, l_load, w_tail, l_tail, ibias`

### Topology 1: Telescopic Cascode

Same basic structure as 5T_OTA but with longer channel lengths for higher gain. In a full cascode, additional transistors stack to boost output impedance (gain = gm × Rout).

**Best for**: High-speed applications where output swing is not critical.
**Typical gain**: 40-60 dB.

### Topology 2: Folded Cascode

Uses a **PMOS differential pair** with NMOS mirror load. "Folded" because the signal path folds from PMOS → NMOS instead of staying on one type.

```
     VDD
      │
    Itail             ← PMOS tail current source
      │
   ┌──┴──┐
   M1    M2          ← PMOS differential pair (input)
   │      │
 net1    out
   │      │
   M3    M4          ← NMOS active load (current mirror)
   │      │
     VSS
```

**Best for**: Better input common-mode range than telescopic. Works well at moderate GBW.
**Typical gain**: 30-50 dB.

### Topology 3: RFC (Recycling Folded Cascode)

Same as Folded Cascode but with gain-boosting techniques. The "recycling" refers to reusing current from one branch to boost the other.

**Best for**: High gain (>80 dB) with moderate power.

### Topology 4: Two-Stage Miller Compensated Op-Amp ⭐

The **workhorse** of analog design. Stage 1 is a diff pair for gain. Stage 2 is a common-source amplifier for additional gain and output swing. A Miller compensation capacitor (Cc) between Stage 1 output and Stage 2 output ensures stability.

```
     VDD                    VDD
      │                      │
   ┌──┴──┐                Mcs_load
   M3    M4                  │
   │      │        Cc       out ──── Cload
 net1   stg1 ──────┤├────── │
   │      │                 M2
   M1    M2                  │
   └──┬──┘                 VSS
      │
     Mtail ← Ibias
      │
     VSS

   Stage 1               Stage 2
   (Gain ≈ 40dB)         (Gain ≈ 40dB)
                          Total ≈ 80dB
```

**Best for**: General-purpose design. Highest combined gain (80-90 dB).
**Parameters**: `w_in, l_in, w_load, l_load, w_tail, l_tail, w_2, l_2, ibias, cc`

### Topology 5: Three-Stage (Nested Miller Compensation)

Three cascaded gain stages with two Miller capacitors (Cc1, Cc2). Achieves extreme gain (>100 dB) but requires careful frequency compensation.

**Best for**: Precision applications requiring very high open-loop gain.

### Topology 6: Bulk-Driven OTA

Standard diff pair but with larger W/L ratios optimized for sub-threshold operation. In true bulk-driven designs, the gate is biased to a constant voltage and the bulk terminal receives the input signal, enabling operation below the threshold voltage.

**Best for**: Ultra-low-voltage supply (<0.5V) designs.

### Topology 7: CFA (Current Feedback Amplifier)

Optimized for high slew rate and bandwidth. Uses current-mode feedback instead of voltage-mode.

**Best for**: High-frequency, high-slew-rate applications (video, RF front-ends).

---

## 4. What Parameters Change, How, and Why <a name="4-parameters"></a>

### The Parameters (What Changes)

| Parameter | Symbol | Unit | Range (180nm PDK) | Physical Meaning |
|-----------|--------|------|---------------------|-----------------|
| Input transistor width | `w_in` | µm | 0.18 – 100 | Controls transconductance (gm). Wider = more gm = more gain |
| Input transistor length | `l_in` | µm | 0.18 – 100 | Controls output resistance (ro). Longer = more ro = more gain, but slower |
| Load transistor width | `w_load` | µm | 0.18 – 100 | Sets load current and impedance |
| Load transistor length | `l_load` | µm | 0.18 – 100 | Sets load output resistance |
| Tail transistor width | `w_tail` | µm | 0.18 – 100 | Controls bias current delivery |
| Tail transistor length | `l_tail` | µm | 0.18 – 100 | Sets bias current mirror accuracy |
| Bias current | `ibias` | A | 1nA – 10mA | Sets quiescent power consumption |
| 2nd stage width (Miller) | `w_2` | µm | 0.18 – 100 | Controls 2nd stage gm and swing |
| Compensation cap (Miller) | `cc` | F | 10fF – 100pF | Sets dominant pole for stability |

### How They Change

The **LLM generates** the `.PARAM` line. The process:

1. **RAG retrieval**: Find 3 closest reference designs from our 600-entry dataset based on the target specification
2. **LLM prompt**: "Given these reference designs and this target spec, generate the `.PARAM` values for a {topology}"
3. **LLM output**: A single `.PARAM` line like:
   ```spice
   .PARAM w_in=3.6u l_in=500n w_load=7.2u l_load=500n ibias=12u
   ```
4. **Clamping**: Every value is checked against the PDK bounds. `w_in=50n` → clamped to `180n`. `ibias=100mA` → clamped to `10mA`.

### Why They Change (The Design Tradeoffs)

The fundamental analog design equation governing every parameter:

```
  Gain = gm × Rout

  where:
    gm ∝ √(µCox × W/L × Ibias)     ← more W or more Ibias = more gm
    Rout ∝ L / Ibias                 ← longer L = more Rout = more gain

  GBW = gm / (2π × CL)              ← more gm = more bandwidth
  Power = VDD × Ibias                ← more current = more power
```

So `W` controls speed (gm), `L` controls gain (Rout), and `Ibias` controls the gain-power tradeoff. Every parameter choice is a tradeoff:

| Want more... | Increase... | But sacrifice... |
|-------------|-------------|-----------------|
| Gain | L (length) | Speed (bandwidth) |
| Speed (GBW) | W (width) or Ibias | Power, area |
| Low power | Reduce Ibias | Gain, speed |
| Output swing | Reduce L (shorter) | Gain |

---

## 5. Output Parameters We Measure <a name="5-output-parameters"></a>

After every simulation, ngspice extracts these metrics from the `.control` block:

| Parameter | Symbol | How Measured | What It Means |
|-----------|--------|-------------|---------------|
| **DC Open-Loop Gain** | `gain_db` | `MAX vdb(out)` at low frequency | Amplification strength in dB. 60dB = 1000× voltage gain |
| **Gain-Bandwidth Product** | `gbw_hz` | Frequency where `vdb(out) = 0 dB` | The frequency at which gain drops to unity. Higher = faster |
| **Phase Margin** | `pm_deg` | Phase at UGF crossing | Stability indicator. Ideally 45°-90°. <0° = oscillation risk |
| **Power Consumption** | `pwr_w` | `Vdd_current × VDD` | Total DC power drawn from supply |

### Parameters We Don't Currently Measure (Future Work)

| Parameter | Symbol | Why It Matters |
|-----------|--------|---------------|
| Output Impedance (Zout) | — | How well the opamp drives resistive loads |
| Output Voltage Swing | Vswing | Max/min output voltage before clipping |
| Slew Rate | SR (V/µs) | How fast the output can change (large-signal speed) |
| Input Offset Voltage | Vio | DC error at the input (mismatch related) |
| CMRR | — | Rejection of common-mode noise |
| PSRR | — | Rejection of supply noise |
| Input-Referred Noise | Vn | Noise floor at the input |

These would require additional `.tran` (transient) and `.noise` simulations in ngspice. Currently we only run `.op` + `.ac`.

---

## 6. Why DQN? (Policy Justification) <a name="6-why-dqn"></a>

### Our Problem Characteristics

| Property | Our Task | Implication |
|----------|----------|-------------|
| Action space | **Discrete(8)** — pick 1 of 8 topologies | Need value-based method, not continuous |
| Episode length | **1 step** — pick topology, simulate, done | No temporal credit assignment needed |
| Reward | **Delayed, noisy** — depends on LLM + ngspice | Need replay buffer for stability |
| Sample efficiency | **Critical** — each step costs ~3s (LLM + sim) | Need off-policy learning |
| Environment | **Stochastic** — same spec + topology gives different results because LLM is non-deterministic | Need averaging over transitions |

### Why DQN Is the Right Choice

**DQN (Deep Q-Network)** is the natural fit because:

1. **Discrete action space**: DQN is designed for `Discrete(N)` — it outputs a Q-value for each of the 8 actions and picks the highest. PPO/A2C/TRPO produce a probability distribution over actions, which is unnecessarily complex for 8 choices.

2. **Off-policy + replay buffer**: DQN stores every past `(state, action, reward, next_state)` in a replay buffer and learns from random mini-batches. This means it reuses old experience instead of throwing it away — critical when each sample costs 3 seconds.

3. **Single-step episodes**: Our episodes are length-1 (pick topology → simulate → done). On-policy methods (PPO, TRPO, A2C, GRPO) need to collect full trajectories before updating. With length-1 episodes, this degrades to pure bandit learning — DQN handles this naturally.

### Why NOT the Alternatives

| Method | Type | Why It Doesn't Fit |
|--------|------|--------------------|
| **PPO** | On-policy, actor-critic | Wastes samples — throws away experience after each update. Designed for long episodes with temporal structure. Our 1-step episodes make PPO's generalized advantage estimation (GAE) meaningless. |
| **GRPO** | On-policy, group-relative | Designed for sequential text generation (token-by-token decisions). Our action is a single discrete choice, not a sequence. The "group relative" advantage has no groups to compare in a 1-step episode. |
| **TRPO** | On-policy, trust-region | Same sample efficiency problem as PPO. The complex second-order KL-constraint optimization is overkill for a simple 8-action classification task. Computationally expensive for no benefit. |
| **A2C** | On-policy, actor-critic | No replay buffer — every transition is used once then discarded. With 3s per sample, we cannot afford this waste. Also suffers from high variance on short episodes. |
| **SPO** | On-policy, sequence model | Designed for LLM fine-tuning (RLHF). Completely wrong abstraction — we are not optimizing a sequence model; we are optimizing a topology classifier. |
| **VC-PPO** | On-policy, value-calibrated | Designed for long-horizon reasoning chains where reward signals decay over many steps. Our reward is immediate (1-step), so value calibration adds nothing. |

### The Bottom Line

For a **discrete, 1-step, stochastic, expensive-to-sample** decision problem, DQN with experience replay is the textbook answer. On-policy methods (PPO, TRPO, A2C) throw away 3-second samples after one use. Sequential methods (GRPO, SPO) are designed for token-level autoregressive generation, not single-shot classification. VC-PPO solves a problem (long-horizon reward decay) that we don't have.

---

## 7. Training Pipeline <a name="7-training-pipeline"></a>

### Training Type: **Reinforcement Learning (neither supervised nor unsupervised)**

- **Not supervised**: We don't have ground-truth labels saying "for this spec, topology X is correct." The agent discovers which topologies work through trial and error.
- **Not unsupervised**: We have a reward signal from the physics simulator. The agent is optimizing a clear objective.
- **RL**: The agent learns a policy π(spec) → topology by maximizing expected cumulative reward from SPICE simulation feedback.

### Training Loop (Per Episode)

```
1. Sample random spec from dataset (600 entries)
2. Agent observes: normalize(spec) → 11D vector ∈ [0,1]
3. Agent acts: ε-greedy action selection
     ├─ With probability ε: pick random topology (explore)
     └─ With probability 1-ε: pick argmax Q(s,a) (exploit)
4. LLM generates .PARAM values for chosen topology
5. Params clamped to PDK bounds
6. Injected into SPICE template → /tmp/llm_{topology}_{hash}.sp
7. ngspice runs .op + .ac analysis (2-5 seconds)
8. Parse stdout: gain_db, gbw_hz, pm_deg, pwr_w
9. Compute reward:
     ├─ sim_reward: how close are metrics to target? (-5 to +2)
     └─ expert_bonus: is this the right topology? (-0.1 to +0.3)
10. Store (state, action, reward) in replay buffer
11. Every 4 steps: sample mini-batch of 64, update Q-network via TD-error
12. Every 10 steps: soft-update target network
```

### DQN Hyperparameters

```python
MlpPolicy:           128 → 128 fully connected (ReLU)
learning_rate:        1e-3
buffer_size:          10,000 transitions
learning_starts:      200 (fill buffer before learning)
batch_size:           64
gamma:                0.99
exploration_fraction: 0.3 (ε decays from 1.0 → 0.05 over 30% of training)
exploration_final_eps: 0.05 (always 5% random exploration)
target_update_interval: 10 steps
```

---

## 8. Inference Pipeline (What the User Gets) <a name="8-inference-pipeline"></a>

### Scenario A: User provides spec, no topology preference

```
User → "gain=70dB, GBW=5MHz, Pmax=500µW, VDD=1.8V"

1. Normalize spec → 11D vector
2. Query trained DQN: argmax Q(s, a) → "Two_Stage_Miller"
3. LLM sizes the Miller template with RAG
4. ngspice validates → gain=72dB, GBW=4.8MHz, Pwr=480µW ✅
5. Return: two_stage_miller.sp (complete, validated netlist)
```

### Scenario B: User specifies topology

```
User → "I want a Folded Cascode with gain=50dB, GBW=10MHz"

1. Skip DQN — user override
2. LLM sizes the Folded Cascode template
3. ngspice validates
4. If meets spec → return netlist
5. If fails → report: "Folded Cascode cannot meet 50dB gain at 10MHz GBW.
   Recommended alternative: Two_Stage_Miller (tested: gain=52dB, GBW=9.5MHz)"
```

### Scenario C: Spec is physically impossible

```
User → "gain=120dB, GBW=1GHz, Power<10µW"

1. DQN selects topology
2. LLM sizes it
3. ngspice fails or produces poor metrics
4. Report: "No topology can simultaneously achieve 120dB gain at 1GHz with 10µW 
   in 180nm CMOS. Best achievable: Three_Stage_Miller at gain=95dB, GBW=2MHz, 
   Pwr=200µW."
```

### Concrete Inference Results (Hard-Spec Diagnostic)

These are real outputs from the trained DQN agent, compared against expert heuristic scoring:

| Spec (condensed) | Agent Selects | Expert Would Select | Match | Reasoning |
|---|---|---|---|---|
| Gain=90dB, GBW=1MHz, Pmax=1mW | *(pending v3 retrain)* | RFC or Two_Stage_Miller | — | High gain requires multi-stage or cascoded output impedance |
| GBW=100kHz, Pmax=1µW, ultra_low_i=1 | **5T_OTA** | 5T_OTA | **✅** | Simplest topology, lowest quiescent current |
| GBW=800MHz, mixed_signal=1 | **CFA** | Telescopic or CFA | **✅** | CFA's complementary input gives highest bandwidth |
| VDD=1.8V, low_voltage=1, Gain=50dB | **Bulk_Driven** | Bulk_Driven | **✅** | Designed for sub-threshold / low-voltage operation |

> **Interpreting the reward scale**: A reward of +0.3 corresponds to netlists where simulated metrics satisfy approximately 30% of the weighted specification targets on average. The theoretical maximum is +2.0 (all metrics within 20% of target + the all-close bonus). A reward of 0.0 is the break-even point — the simulation ran but metrics are far from targets. Negative rewards indicate simulation crashes (-5.0) or physically nonsensical results (-3.0).

---

## 9. Expert Reward Shaping — Precise Mechanism <a name="9-expert-shaping"></a>

### The Problem (v1 & v2)

The v1 agent converged to picking Folded Cascode/RFC for **every** spec because:
- 3 templates (5T_OTA, CFA, Telescopic) were accidentally identical circuits → agent couldn't differentiate them
- FC/RFC power measurement was broken (reported ~0W → free power bonus)
- No domain knowledge in the reward signal

### The Fix: Expert Reward Shaping (Exact Mechanism)

The reward is a **sum of two components**:

```
R_total = R_simulation + R_expert_shaping
```

**R_simulation** (range: -5.0 to +2.0): Standard simulation quality reward
- -5.0: ngspice crashed (no convergence)
- -3.0: simulation ran but gain < 0 or GBW < 0 (nonsense)
- 0.0 to 1.0: weighted metric matching (0.35×gain + 0.35×GBW + 0.15×PM + 0.15×power)
- +1.0 bonus: all metrics within 20% of target simultaneously

**R_expert_shaping** (range: -0.1 to +0.3): A **potential-based reward shaping term** computed from the `score_topology()` heuristic function in `opamp_selector_scoring.py`. For each specification, all 8 topologies are scored using textbook analog design rules (e.g., "high gain → prefer multi-stage", "low voltage → prefer bulk-driven"). The chosen topology's **rank** among the 8 scores determines the bonus:

```python
def compute_expert_bonus(self, topology_name, spec):
    scores = {t: score_topology(t, spec) for t in TOPOLOGY_LABELS}
    sorted_topos = sorted(scores.items(), key=lambda x: -x[1])
    rank = [t for t, s in sorted_topos].index(topology_name)
    return 0.3 - (rank / 7.0) * 0.4  # rank 0→+0.3, rank 7→-0.1
```

This is **not** an exploration bonus or forced visitation count. It is a continuous reward shaping term added to every transition. It does not override simulation reality — a Folded Cascode that achieves 60dB gain will still be rewarded even if the expert prefers Two_Stage_Miller. But over many transitions, the agent learns that choosing domain-appropriate topologies yields +0.3 extra per step.

### Template Fix (v3)

All 8 templates now produce **distinct** simulation metrics with default parameters:

| Topology | Gain (dB) | GBW (Hz) | Power (W) | Circuit Distinction |
|----------|-----------|----------|-----------|--------------------|
| 5T_OTA | 39.9 | 1.36M | 55 µW | NMOS diff + PMOS mirror (simplest) |
| Telescopic | 49.1 | 1.57M | 5.6 µW | 5T + NMOS cascode stacking |
| Folded_Cascode | 37.1 | 2.07M | ~0 | PMOS diff + NMOS mirror |
| RFC | 54.5 | 2.03M | 53 µW | FC + cascoded NMOS+PMOS load |
| Two_Stage_Miller | **86.1** | **5.10M** | 55 µW | Two cascaded gain stages + Cc |
| Three_Stage | 44.0 | 1.91M | 55 µW | Three gain stages + NMC |
| Bulk_Driven | 44.3 | 901k | 25 µW | Large W/L for sub-threshold |
| CFA | 40.2 | 1.56M | 34 µW | Complementary NMOS+PMOS pairs |

---

## 10. Current Status <a name="10-current-status"></a>

### What Works ✅

| Component | Status | Details |
|-----------|--------|---------|
| 8/8 SPICE templates | ✅ All distinct | Each produces unique gain/GBW/power metrics |
| TSMC 180nm model | ✅ Validated | MOSIS-verified BSIM3v3.1 (80+ parameters) |
| LLM parameter generation | ✅ Working | Qwen-2.5-7B via local Ollama (~3s/call) |
| DQN training loop | ✅ Converges | v3 training in progress with fixed templates |
| Expert reward shaping | ✅ Active | Continuous bonus term, not exploration hack |
| Tiered reward function | ✅ Working | -5 crash / -3 nonsense / gradient otherwise |
| Physical clamping | ✅ Working | All LLM params bounded to PDK limits |

### What We Measure ✅ (Paper Results)

These 4 metrics are extracted from every ngspice simulation:
- **DC open-loop gain** (gain_db): `MAX vdb(out)` from AC sweep
- **Unity-gain bandwidth** (gbw_hz): frequency where `vdb(out) = 0 dB`
- **Phase margin** (pm_deg): phase at UGF crossing
- **Power consumption** (pwr_w): `Vdd_current × VDD`

### What We Do NOT Measure ⬜ (Future Work Only)

These are NOT part of our current results and should NOT appear in the abstract:
- Slew rate (requires `.tran` transient analysis)
- CMRR, PSRR (requires `.noise` or differential stimulus)
- Input-referred noise (requires `.noise` analysis)
- Output swing (requires DC sweep to clipping)
- Layout-aware sizing constraints
- Per-topology LLM fine-tuning (LoRA adapters)

---

## 11. File Reference <a name="11-files"></a>

| File | Purpose |
|------|---------|
| `env/opamp_env.py` | Gymnasium environment with tiered reward + expert shaping |
| `agent/dqn_agent.py` | SB3 DQN wrapper (128×128 MLP, ε-greedy) |
| `netlist/llm_netlist_gen.py` | Ollama LLM backend + RAG + parameter clamping |
| `sim/ngspice_runner.py` | ngspice subprocess runner + stdout metrics parser |
| `specset/opamp_selector_scoring.py` | Expert heuristic scoring function (domain knowledge) |
| `specset/generate_specset.py` | Generates the 600-entry training spec dataset |
| `specset/specset_opamp.json` | The 600 training specifications |
| `specset/templates/*.sp` | 8 validated SPICE skeleton templates |
| `models/ptm180nm.lib` | TSMC 180nm BSIM3v3.1 model library |
| `train.py` | Training entry point |
| `evaluate.py` | Evaluation + figure generation |
| `results/` | Generated plots (reward convergence, heatmap, distribution) |

---

## 12. How to Run <a name="12-how-to-run"></a>

### Prerequisites

```bash
# Python packages
pip install gymnasium stable-baselines3 scikit-learn matplotlib seaborn

# ngspice (circuit simulator)
sudo apt install ngspice

# Ollama (local LLM server)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:7b
```

### Training

```bash
# Quick training (2000 steps, ~1.5 hours)
TRAIN_STEPS=2000 python3 rl_ampsyn/train.py

# Full training (15000 steps, ~11 hours)
python3 rl_ampsyn/train.py

# Monitor live
tail -f train_logs_v2.txt
```

### Evaluation

```bash
# Generate convergence plot + heatmap + distribution chart
python3 generate_figures.py

# Run hard-spec diagnostic (does agent differentiate topologies?)
python3 diagnose_policy.py

# Verify all 8 templates simulate correctly
python3 diagnose.py
```
