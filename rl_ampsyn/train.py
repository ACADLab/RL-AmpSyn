import os
import sys
sys.path.append(os.path.dirname(__file__))

from env.opamp_env import OpAmpEnv
from agent.dqn_agent import DQNAgent

def main():
    print("Starting RL-AmpSyn Training...")
    env = OpAmpEnv(specset_path="rl_ampsyn/specset/specset_opamp.json")
    agent = DQNAgent(env)
    
    # Default 15k steps guarantees the DQN stabilizes beyond the initial replay warming
    steps = int(os.getenv("TRAIN_STEPS", "15000"))
    agent.train(total_timesteps=steps)
    
    agent.save("rl_ampsyn/agent/checkpoints/dqn_final")
    print("Training Complete. Model saved to rl_ampsyn/agent/checkpoints/dqn_final")

if __name__ == "__main__":
    main()
