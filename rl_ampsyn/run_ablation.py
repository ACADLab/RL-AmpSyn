import os
import sys

sys.path.append(os.path.dirname(__file__))

from env.opamp_env import OpAmpEnv
from agent.dqn_agent import DQNAgent
import netlist.llm_netlist_gen as llm_netlist_gen

MODELS_TO_TEST = [
    "meta-llama/llama-3.3-70b-instruct",
    "deepseek/deepseek-chat",
    "qwen/qwen-2.5-72b-instruct"
]
TRAIN_STEPS = 15000

def main():
    print(f"Starting Multi-Model Ablation Run over {TRAIN_STEPS} steps...")
    
    for model_name in MODELS_TO_TEST:
        print(f"\n======================================")
        print(f"Ablating Model: {model_name}")
        print(f"======================================")
        
        # Inject custom model dynamically
        llm_netlist_gen.set_model(model_name)
        
        env = OpAmpEnv(specset_path="rl_ampsyn/specset/specset_opamp.json")
        agent = DQNAgent(env)
        
        # Override tensorboard logging destination so we can plot them individually or concurrently
        safe_model_name = model_name.replace("/", "_")
        agent.model.tensorboard_log = f"rl_ampsyn/runs/ablation_{safe_model_name}/"
        
        agent.train(total_timesteps=TRAIN_STEPS)
        
        checkpoint_path = f"rl_ampsyn/agent/checkpoints/dqn_ablation_{safe_model_name}"
        agent.save(checkpoint_path)
        print(f"Finished {model_name}. Checkpoint saved -> {checkpoint_path}")

    print("\nAblation complete. Use evaluate.py to process the Tensorboard trajectories.")

if __name__ == "__main__":
    main()
