import unittest
import numpy as np
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from env.opamp_env import OpAmpEnv

class TestOpAmpEnv(unittest.TestCase):
    def test_reset_and_normalize(self):
        env = OpAmpEnv()
        obs, info = env.reset()
        self.assertEqual(obs.shape, (11,))
        self.assertTrue(np.all(obs >= 0.0) and np.all(obs <= 1.0))
        
    def test_compute_reward(self):
        env = OpAmpEnv()
        targets = {
            "gain_db": 60, "gbw_hz": 1e7, "pmax_w": 1e-3
        }
        
        # Test failed sim
        r_fail = env.compute_reward(None, targets)
        self.assertEqual(r_fail, -5.0)
        
        # Test perfect match
        metrics_perfect = {
            "gain_db": 60, "gbw_hz": 1e7, "pm_deg": 60, "pwr_w": 0.5e-3
        }
        r_perfect = env.compute_reward(metrics_perfect, targets)
        self.assertAlmostEqual(r_perfect, 1.0)
        
if __name__ == '__main__':
    unittest.main()
