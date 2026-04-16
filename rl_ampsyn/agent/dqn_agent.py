import os
from stable_baselines3 import DQN

class DQNAgent:
    def __init__(self, env):
        self.env = env
        
        policy_kwargs = dict(net_arch=[128, 128])
        
        self.model = DQN(
            "MlpPolicy",
            env,
            learning_rate=1e-3,
            buffer_size=10000,
            learning_starts=200,
            batch_size=64,
            gamma=0.99,
            exploration_fraction=0.3,
            exploration_final_eps=0.05,
            policy_kwargs=policy_kwargs,
            tensorboard_log="rl_ampsyn/runs/dqn_opamp/",
            verbose=1
        )
        
    def train(self, total_timesteps=50000):
        self.model.learn(total_timesteps=total_timesteps, tb_log_name="dqn")
        
    def predict(self, obs):
        action, _states = self.model.predict(obs, deterministic=True)
        return action
        
    def save(self, path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.model.save(path)
        
    def load(self, path):
        self.model = DQN.load(path, env=self.env)
