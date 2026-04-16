## RL-AmpSyn — Implementation Pointers for Claude Code / Cursor
##
## Hand this file to Claude Code or paste into Cursor's composer.
## Each section is a concrete coding task with enough context
## for an LLM coding agent to execute without ambiguity.
## =============================================================

# ── PROJECT LAYOUT ────────────────────────────────────────────
#
# rl_ampsyn/
# ├── specset/
# │   ├── generate_specset.py       [TASK A]
# │   ├── templates/                [TASK B]
# │   │   ├── ota_5t.sp
# │   │   ├── telescopic.sp
# │   │   ├── folded_cascode.sp
# │   │   ├── rfc.sp
# │   │   ├── two_stage_miller.sp
# │   │   ├── three_stage.sp
# │   │   ├── bulk_driven.sp
# │   │   └── cfa.sp
# │   └── specset_opamp.json        [output of TASK A]
# ├── env/
# │   └── opamp_env.py              [TASK C]
# ├── sim/
# │   └── ngspice_runner.py         [TASK D]
# ├── netlist/
# │   └── llm_netlist_gen.py        [TASK E]
# ├── agent/
# │   └── dqn_agent.py              [TASK F]
# ├── train.py                      [TASK G]
# ├── evaluate.py                   [TASK H]
# └── requirements.txt


# =============================================================
# TASK A — specset/generate_specset.py
# "Build the SpecSet-OpAmp dataset by grid-sampling the spec space
#  and labelling each point with the expert scoring model."
# =============================================================
#
# INPUTS
#   N_SAMPLES   = 600  (int)
#   SPEC_BOUNDS = {
#       "vdd":    (0.3, 5.0),   # volts
#       "gain_db":(40,  120),   # dB
#       "gbw_hz": (1e5, 1e9),   # Hz  — sample log-uniform
#       "cl_f":   (1e-12, 100e-12),   # F
#       "pmax_w": (10e-9, 10e-3),     # W  — sample log-uniform
#       "swing_pct": (0.5, 1.0),      # fraction of VDD
#       "noise_priority": (1, 5),     # integer 1-5
#       # Binary flags (Bernoulli 0.5)
#       "mixed_signal": [0, 1],
#       "low_voltage":  [0, 1],
#       "diff_input":   [0, 1],
#       "ultra_low_i":  [0, 1],
#   }
#   TOPOLOGY_LABELS = [
#       "5T_OTA", "Telescopic", "Folded_Cascode", "RFC",
#       "Two_Stage_Miller", "Three_Stage", "Bulk_Driven", "CFA"
#   ]
#
# SCORING MODEL (port from the existing opamp_selector.html JS):
#   Each topology has a score matrix: score(topology, spec_vector).
#   Port the JavaScript scoring logic into a Python function
#   `score_topology(topology_id: str, spec: dict) -> float`.
#   Ground-truth label = argmax over 8 topology scores.
#
# OUTPUT FORMAT (specset_opamp.json):
#   [
#     {
#       "id": "spec_0001",
#       "spec": {"vdd": 1.8, "gain_db": 70, ...},
#       "topology": "Folded_Cascode",
#       "netlist_path": "templates/folded_cascode.sp",
#       "sizing_hints": {"ibias_ua": 10, "wl_ratio_input": 20}
#     }, ...
#   ]
#
# CLAUDE CODE PROMPT:
#   "Read rl_ampsyn/specset/generate_specset.py and
#    rl_ampsyn/specset/opamp_selector_scoring.py (ported from
#    opamp_selector.html). Generate 600 spec samples using the
#    bounds in SPEC_BOUNDS, run score_topology() for each of the
#    8 topologies, assign the argmax label, and write the result
#    to specset_opamp.json."


# =============================================================
# TASK B — specset/templates/*.sp
# "Write minimal parameterised SPICE skeleton netlists for each
#  of the 8 op-amp topologies."
# =============================================================
#
# REQUIREMENTS per template:
#   - Uses ngspice-compatible syntax (no Cadence-only extensions)
#   - Parameterised with .PARAM for W, L, IBIAS, CC (where applicable)
#   - Includes a standard test bench: VDD supply, differential input
#     sources Vp/Vm, AC analysis .ac dec 100 1 1G, DC op .op
#   - Technology: use PTM 180nm BSIM3v3 models (public, no NDA)
#     Model file path: models/ptm180nm.lib
#
# SIZING_HINTS seeded from SpecSet entry are injected by
# llm_netlist_gen.py as .PARAM overrides before simulation.
#
# CLAUDE CODE PROMPT:
#   "Write SPICE netlist templates for the following 8 op-amp
#    topologies using ngspice-compatible syntax and PTM 180nm
#    models. Each file must have .PARAM placeholders for key
#    sizing variables. Topologies: 5T_OTA, Telescopic,
#    Folded_Cascode, RFC, Two_Stage_Miller, Three_Stage,
#    Bulk_Driven, CFA."


# =============================================================
# TASK C — env/opamp_env.py
# "OpenAI Gym environment wrapping the RL-AmpSyn loop."
# =============================================================
#
# CLASS: OpAmpEnv(gym.Env)
#
# observation_space: gym.spaces.Box(low=0, high=1, shape=(11,), dtype=np.float32)
#   — normalised spec vector (apply min-max per SPEC_BOUNDS)
#
# action_space: gym.spaces.Discrete(8)
#   — topology index 0..7
#
# reset() -> obs
#   — sample a new spec vector from specset_opamp.json (or uniform random)
#   — return normalised spec as observation
#
# step(action: int) -> (obs, reward, done, info)
#   1. topology_name = TOPOLOGY_LABELS[action]
#   2. netlist_path  = llm_netlist_gen.generate(spec, topology_name)
#   3. metrics       = ngspice_runner.run(netlist_path)
#   4. reward        = compute_reward(metrics, spec_targets)  [see eq:reward]
#   5. done          = True (single-step episode — one topology per spec)
#   6. info          = {"metrics": metrics, "netlist": netlist_path}
#
# compute_reward(metrics, targets) -> float
#   weights = {"gain_db": 0.3, "gbw_hz": 0.3, "pm_deg": 0.2, "pwr_w": 0.2}
#   penalty = 5.0 if sim_failed else 0.0
#   r = sum(w * (1 - abs(m-t)/t) for (m,t,w)) - penalty
#   return np.clip(r, -5.0, 1.0)
#
# CLAUDE CODE PROMPT:
#   "Implement OpAmpEnv in env/opamp_env.py following the spec
#    above. Import NgspiceRunner from sim/ngspice_runner.py and
#    LLMNetlistGen from netlist/llm_netlist_gen.py. Add unit tests
#    in env/test_opamp_env.py that mock the simulator and verify
#    reward computation."


# =============================================================
# TASK D — sim/ngspice_runner.py
# "Python wrapper that calls ngspice, parses output, returns metrics."
# =============================================================
#
# FUNCTION: run(netlist_path: str) -> dict | None
#   1. subprocess.run(["ngspice", "-b", netlist_path, "-o", tmp_lis])
#   2. Parse tmp_lis for:
#        - DC gain  : search "vout/vin = " or use .MEASURE result
#        - GBW      : from .measure GBW WHEN vm(out)=0 FIND vdb(out)
#        - Phase margin: from .measure PM  (set up in netlist template)
#        - Power    : from .measure PWR AVG POWER
#   3. Return {"gain_db": float, "gbw_hz": float, "pm_deg": float, "pwr_w": float}
#      or None if ngspice exit-code != 0 or parse fails.
#
# TIMEOUT: 30s per simulation. Kill process on timeout, return None.
#
# CLAUDE CODE PROMPT:
#   "Implement NgspiceRunner in sim/ngspice_runner.py. Use
#    subprocess.run with timeout=30. Write a regex-based parser
#    for ngspice .lis output files extracting gain_db, gbw_hz,
#    pm_deg, pwr_w. Return None on failure. Add tests in
#    sim/test_ngspice_runner.py using a fixture .lis file."


# =============================================================
# TASK E — netlist/llm_netlist_gen.py
# "RAG-based LLM module: retrieves closest SpecSet template and
#  calls Claude API to adapt sizing parameters."
# =============================================================
#
# FUNCTION: generate(spec: dict, topology: str) -> str (path to .sp file)
#   1. Load specset_opamp.json, filter rows where topology matches.
#   2. Compute cosine similarity between query spec vector and
#      all matching SpecSet entries (sklearn cosine_similarity).
#   3. Retrieve top-3 nearest neighbours → use as few-shot examples.
#   4. Construct prompt:
#        system: "You are an analog circuit sizing expert. Given a
#                 SPICE skeleton netlist and a target specification,
#                 output ONLY the .PARAM overrides as key=value pairs."
#        user:   f"Topology: {topology}\n"
#                f"Target spec: {spec}\n"
#                f"Skeleton netlist:\n{skeleton}\n"
#                f"Reference designs:\n{few_shot_examples}\n"
#                f"Output .PARAM overrides:"
#   5. Call Anthropic API (claude-sonnet-4-6, max_tokens=256).
#   6. Parse response for .PARAM KEY=VALUE lines.
#   7. Write skeleton netlist with overrides injected to tmp dir.
#   8. Return path to modified netlist.
#
# RETRY: on LLM parse failure, retry once with simplified prompt.
#
# CLAUDE CODE PROMPT:
#   "Implement LLMNetlistGen in netlist/llm_netlist_gen.py following
#    the spec above. Use anthropic SDK (pip install anthropic). Use
#    cosine similarity from sklearn for nearest-neighbour retrieval.
#    Mock the API call in tests. Add diagnostic logging of the
#    .PARAM overrides applied."


# =============================================================
# TASK F — agent/dqn_agent.py
# "DQN agent using stable-baselines3 — thin wrapper."
# =============================================================
#
# USE: stable_baselines3.DQN
#
# CONFIG:
#   policy          = "MlpPolicy"
#   learning_rate   = 1e-3
#   buffer_size     = 10_000
#   learning_starts = 200
#   batch_size      = 64
#   gamma           = 0.99          # single-step episode → gamma matters less
#   exploration_fraction = 0.3
#   exploration_final_eps = 0.05
#   policy_kwargs   = dict(net_arch=[128, 128])
#
# LOGGING: TensorBoard callback writing to runs/dqn_opamp/
#
# CLAUDE CODE PROMPT:
#   "Implement a thin DQNAgent wrapper in agent/dqn_agent.py that
#    instantiates stable-baselines3 DQN with the config above,
#    exposes train(total_timesteps) and predict(obs) methods,
#    and saves/loads checkpoints to agent/checkpoints/."


# =============================================================
# TASK G — train.py
# "Main training script."
# =============================================================
#
# FLOW:
#   1. env   = OpAmpEnv(specset_path="specset/specset_opamp.json")
#   2. agent = DQNAgent(env)
#   3. agent.train(total_timesteps=50_000)
#   4. agent.save("agent/checkpoints/dqn_final")
#   5. Log: topology selection histogram per 1000 steps
#            valid-netlist rate per 1000 steps
#
# CLAUDE CODE PROMPT:
#   "Write train.py that instantiates OpAmpEnv and DQNAgent,
#    trains for 50_000 timesteps with a TensorBoard callback,
#    logs topology selection histogram and valid-netlist rate to
#    runs/dqn_opamp/, and saves the final checkpoint."


# =============================================================
# TASK H — evaluate.py  (produces Fig. 2 data)
# "Evaluation script that generates the two result panels."
# =============================================================
#
# PANEL 1 — Topology heatmap:
#   Grid 20×20 over (log GBW, log P_max); all other spec dims fixed
#   at median values. Run agent.predict() at each grid point.
#   Plot with seaborn.heatmap, 8 discrete colors (one per topology).
#   Save: results/topology_heatmap.pdf
#
# PANEL 2 — Reward convergence:
#   Load TensorBoard event file from runs/dqn_opamp/.
#   Plot: x=episode, y1=mean_reward (left axis), y2=valid_netlist_rate
#         (right axis, %). Twin-axis matplotlib figure.
#   Save: results/reward_convergence.pdf
#
# CLAUDE CODE PROMPT:
#   "Write evaluate.py that: (1) loads the trained DQN checkpoint,
#    (2) generates a 20×20 topology selection heatmap over the
#    GBW–Pmax subspace and saves it to results/topology_heatmap.pdf,
#    (3) loads TensorBoard logs and plots reward + valid-netlist-rate
#    convergence curves to results/reward_convergence.pdf."


# =============================================================
# requirements.txt
# =============================================================
# anthropic>=0.30
# gymnasium>=0.29
# stable-baselines3>=2.2
# numpy>=1.26
# scikit-learn>=1.4
# matplotlib>=3.8
# seaborn>=0.13
# tensorboard>=2.16
# scipy>=1.12
# tqdm>=4.66


# =============================================================
# FIGURE INTEGRATION (Overleaf / LaTeX)
# =============================================================
#
# After TASK H completes:
#   1. Copy results/topology_heatmap.pdf and
#              results/reward_convergence.pdf
#      into the Overleaf project root (or figures/ subdirectory).
#
#   2. In RL_AmpSyn_MADCAP.tex, replace the \figplaceholder block
#      for Fig. 2 with:
#
#        \includegraphics[width=\columnwidth]{figures/topology_heatmap}
#        \hfill
#        \includegraphics[width=\columnwidth]{figures/reward_convergence}
#
#      (adjust width/layout as needed to fit the single column)
#
#   3. For Fig. 1 (pipeline):
#      Export the SVG pipeline diagram to PDF using Inkscape:
#        inkscape RL_AmpSyn_pipeline.svg --export-pdf=figures/framework.pdf
#      Then replace the \figplaceholder block with:
#        \includegraphics[width=\columnwidth]{figures/framework}
#
# NOTE: IEEEtran at one-column conference format = \columnwidth ≈ 8.5 cm.
#       Keep both figures within \columnwidth to avoid overfull hbox.


# =============================================================
# NGSPICE INSTALL NOTE
# =============================================================
# macOS:  brew install ngspice
# Linux:  sudo apt install ngspice
# Verify: ngspice --version   (need >=40)
# PTM 180nm models: http://ptm.asu.edu/modelcard/LP/180nm_LP.pm
#   Download and save to rl_ampsyn/models/ptm180nm.lib
#   Each .sp template must include: .include "../models/ptm180nm.lib"
