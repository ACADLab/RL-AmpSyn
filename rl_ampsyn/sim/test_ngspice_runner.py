import os
import tempfile
import sys
import unittest

sys.path.append(os.path.dirname(__file__))
from ngspice_runner import run

class TestNgspiceRunner(unittest.TestCase):
    def test_parse_success(self):
        # Create a mock netlist and lis file directly for parsing logic
        with tempfile.NamedTemporaryFile(suffix='.sp', delete=False) as tf:
            netlist_path = tf.name
            
        lis_path = f"{netlist_path}.lis"
        with open(lis_path, 'w') as f:
            f.write("""
Some ngspice debug info here...
gain_db             =  4.250000e+01
gbw_hz              =  1.200000e+08
pm_deg              =  6.500000e+01
pwr                 =  5.000000e-03
More spam...
            """)
            
        # Instead of running `run()` which triggers the subprocess, we just wrap around the parsing logic
        # OR better yet, we override subprocess.run just for tests, but since we just want to test parsing,
        # we can put a mock subprocess.run. To keep it simple, let's just make the run function accept a mock flag,
        # but the standard `run` uses subprocess. So here we mock subprocess
        
        import subprocess
        original_run = subprocess.run
        
        def mock_run(*args, **kwargs):
            return subprocess.CompletedProcess(args, 0)
            
        subprocess.run = mock_run
        
        try:
            metrics = run(netlist_path)
            self.assertIsNotNone(metrics)
            self.assertEqual(metrics["gain_db"], 42.5)
            self.assertEqual(metrics["gbw_hz"], 120e6)
            self.assertEqual(metrics["pm_deg"], 65.0)
            self.assertEqual(metrics["pwr_w"], 0.005)
        finally:
            subprocess.run = original_run
            os.remove(netlist_path)
            os.remove(lis_path)

if __name__ == '__main__':
    unittest.main()
