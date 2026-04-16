import os
import sys
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

sys.path.append(os.path.dirname(__file__))
from env.opamp_env import OpAmpEnv
from agent.dqn_agent import DQNAgent

def plot_heatmap(agent, env):
    gbw_vals = np.logspace(5, 9, 20)
    pmax_vals = np.logspace(-8, -3, 20)
    
    action_map = np.zeros((20, 20), dtype=int)
    
    base_spec = {
        "vdd": 1.8, "gain_db": 60, "cl_f": 1e-12, 
        "swing_pct": 0.8, "noise_priority": 3,
        "mixed_signal": 0, "low_voltage": 0, "diff_input": 1, "ultra_low_i": 0
    }
    
    for i, pmax in enumerate(pmax_vals):
        for j, gbw in enumerate(gbw_vals):
            spec = base_spec.copy()
            spec["gbw_hz"] = gbw
            spec["pmax_w"] = pmax
            
            obs = env._normalize(spec)
            action = agent.predict(np.expand_dims(obs, 0))[0]
            if isinstance(action, np.ndarray):
                action = int(action[0])
            action_map[i, j] = int(action)
            
    plt.figure(figsize=(8,6))
    sns.heatmap(action_map, cmap="tab10", cbar=True, 
                xticklabels=[f"{x:.1e}" for x in gbw_vals],
                yticklabels=[f"{y:.1e}" for y in pmax_vals])
    plt.xlabel("GBW (Hz)")
    plt.ylabel("Pmax (W)")
    plt.title("Topology Selection Map")
    
    os.makedirs("rl_ampsyn/results", exist_ok=True)
    plt.savefig("rl_ampsyn/results/topology_heatmap.pdf", bbox_inches='tight')
    plt.close()

def plot_learning_curves():
    # Typically stable baselines saves to runs/dqn_opamp/dqn_1/...
    log_dir = "rl_ampsyn/runs/dqn_opamp"
    
    # find the latest dqn_* directoy
    subdirs = [os.path.join(log_dir, d) for d in os.listdir(log_dir) if os.path.isdir(os.path.join(log_dir, d))] if os.path.exists(log_dir) else []
    if not subdirs:
        print("No tf logs found.")
        return
        
    latest_dir = max(subdirs, key=os.path.getmtime)
        
    ea = EventAccumulator(latest_dir)
    ea.Reload()
    
    if "rollout/ep_rew_mean" in ea.Tags()['scalars']:
        rewards = ea.Scalars("rollout/ep_rew_mean")
        x = [s.step for s in rewards]
        y = [s.value for s in rewards]
        
        plt.figure(figsize=(6,4))
        plt.plot(x, y, label="Mean Reward", color='blue')
        plt.xlabel("Timesteps")
        plt.ylabel("Reward")
        plt.title("Reward Convergence")
        plt.grid(True)
        plt.savefig("rl_ampsyn/results/reward_convergence.pdf", bbox_inches='tight')
        plt.close()

def main():
    print("Evaluating Policy...")
    env = OpAmpEnv(specset_path="rl_ampsyn/specset/specset_opamp.json")
    agent = DQNAgent(env)
    
    try:
        agent.load("rl_ampsyn/agent/checkpoints/dqn_final")
    except Exception as e:
        print(f"Could not load agent weights (maybe train.py has not been run): {e}")
        return
        
    plot_heatmap(agent, env)
    plot_learning_curves()
    print("Evaluation Complete. Saved to rl_ampsyn/results/")

if __name__ == "__main__":
    main()
