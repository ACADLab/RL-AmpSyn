import subprocess
import os
import re


def run(netlist_path: str) -> dict | None:
    """Run ngspice simulation and extract metrics from output.
    
    Uses interactive mode (not -b batch) since templates use .control blocks.
    The .control block runs the simulation, prints results, and calls quit.
    """
    try:
        result = subprocess.run(
            ["ngspice", netlist_path],
            capture_output=True,
            text=True,
            timeout=30
        )

        # Combine stdout and stderr for parsing
        content = result.stdout + "\n" + result.stderr

        # Parse ngspice measure outputs from .control block print statements
        metrics = {}
        patterns = {
            "gain_db": r"gain_db\s*=\s*([+\-0-9\.eE]+)",
            "gbw_hz": r"gbw_hz\s*=\s*([+\-0-9\.eE]+)",
            "pm_deg": r"pm_deg\s*=\s*([+\-0-9\.eE]+)",
            "pwr_w": r"pwr_w\s*=\s*([+\-0-9\.eE]+)"
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    metrics[key] = float(match.group(1))
                except ValueError:
                    metrics[key] = None
            else:
                metrics[key] = None

        # If gain or GBW fails to parse, something went fundamentally wrong
        if metrics["gain_db"] is None or metrics["gbw_hz"] is None:
            return None

        # Default PM to 0 if phase measurement fails
        if metrics["pm_deg"] is None:
            metrics["pm_deg"] = 0.0

        # Default power if measurement fails
        if metrics["pwr_w"] is None:
            metrics["pwr_w"] = 1.0  # Assign high power penalty

        # Make power positive (ngspice reports supply current as negative)
        metrics["pwr_w"] = abs(metrics["pwr_w"])

        return metrics

    except subprocess.TimeoutExpired:
        print(f"[Timeout] Ngspice hung on {netlist_path}")
        return None
    except Exception as e:
        print(f"[Error] Ngspice failed: {e}")
        return None
