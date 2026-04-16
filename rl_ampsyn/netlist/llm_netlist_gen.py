import json
import os
import re
import tempfile
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# ---- Backend Selection ----
# Priority: OLLAMA (local, fast) > OpenRouter (cloud, fallback)
BACKEND = os.getenv("LLM_BACKEND", "ollama")  # "ollama" or "openrouter"
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct")

# Lazy-init client only when needed
_openai_client = None
def _get_openrouter_client():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY", "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")
        )
    return _openai_client


def _call_llm(system_prompt: str, user_prompt: str, model_override: str = None) -> str:
    """Unified LLM caller — routes to Ollama or OpenRouter."""
    if BACKEND == "ollama":
        import requests
        model = model_override or OLLAMA_MODEL
        try:
            resp = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": model,
                    "prompt": f"{system_prompt}\n\n{user_prompt}",
                    "stream": False,
                    "options": {"temperature": 0.2, "num_predict": 200}
                },
                timeout=120
            )
            return resp.json().get("response", "")
        except Exception as e:
            print(f"[Ollama Error] {e}")
            return ".PARAM ibias=10u w_in=2u l_in=500n (ollama-fallback)"
    else:
        client = _get_openrouter_client()
        model = model_override or OPENROUTER_MODEL
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=200,
                temperature=0.2
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"[OpenRouter Error] {e}")
            return ".PARAM ibias=10u w_in=2u l_in=500n (openrouter-fallback)"


def spec_to_vec(s):
    return [s["vdd"], s["gain_db"], s["gbw_hz"], s["cl_f"], s["pmax_w"], s["swing_pct"]]


def parse_spice_val(val_str):
    """Convert SPICE value strings like '2u', '500n', '1.5m' to float."""
    match = re.match(r"([0-9\.\-]+)([a-zA-Z]*)", val_str.strip())
    if not match:
        return None
    num_str = match.group(1).rstrip('.')
    try:
        num_part = float(num_str)
    except ValueError:
        return None
    suffix = match.group(2).lower()
    mult = 1.0
    if suffix.startswith('u'): mult = 1e-6
    elif suffix.startswith('n'): mult = 1e-9
    elif suffix.startswith('p'): mult = 1e-12
    elif suffix.startswith('m'): mult = 1e-3
    elif suffix.startswith('k'): mult = 1e3
    elif suffix.startswith('meg'): mult = 1e6
    return num_part * mult


def clamp_spice_value(key, val_str):
    """Physical constraint layer — clamp values to 180nm PDK bounds."""
    val = parse_spice_val(val_str)
    if val is None:
        return val_str

    key_lower = key.lower()
    # Width/Length: enforce 180nm minimum feature size
    if any(key_lower.startswith(p) for p in ['w_', 'l_', 'w', 'l']):
        if val < 180e-9:
            val = 180e-9
        if val > 100e-6:  # max 100um
            val = 100e-6
    # Bias current: 1nA to 10mA
    elif 'bias' in key_lower:
        val = max(1e-9, min(10e-3, val))
    # Capacitors: 10fF to 100pF
    elif key_lower.startswith('c'):
        val = max(10e-15, min(100e-12, val))

    return f"{val:.4e}"


DB_PATH = os.path.join(os.path.dirname(__file__), "../specset/specset_opamp.json")


class LLMNetlistGen:
    def __init__(self, db_path=DB_PATH, model=None):
        self.model = model
        try:
            with open(db_path, "r") as f:
                self.dataset = json.load(f)
        except Exception as e:
            print(f"[Warning] LLMNetlistGen failed to load {db_path}: {e}")
            self.dataset = []

    def set_model(self, model: str):
        self.model = model

    def generate(self, spec: dict, topology: str) -> str:
        # RAG: find closest reference designs
        matches = [d for d in self.dataset if d["topology"] == topology]

        if not matches:
            few_shot = "No reference examples available."
        else:
            target_vec = np.array(spec_to_vec(spec)).reshape(1, -1)
            match_vecs = np.array([spec_to_vec(m["spec"]) for m in matches])
            sim = cosine_similarity(target_vec, match_vecs)[0]
            top_idx = sim.argsort()[-3:][::-1]

            few_shot = ""
            for idx in top_idx:
                m = matches[idx]
                few_shot += f"Spec: {m['spec']} -> Params: {m['sizing_hints']}\n"

        # Load skeleton template
        skeleton_path = os.path.join(os.path.dirname(__file__), f"../specset/templates/{topology.lower()}.sp")
        try:
            with open(skeleton_path, "r") as f:
                skeleton_content = f.read()
        except Exception as e:
            skeleton_content = f"* {topology} Template\n*.PARAM placeholder\n* Missing {skeleton_path}"

        # Extract existing .PARAM key names from skeleton so LLM knows what to override
        skeleton_param_keys = []
        for line in skeleton_content.split('\n'):
            if line.strip().upper().startswith('.PARAM'):
                for km in re.finditer(r'([A-Za-z_][A-Za-z0-9_]*)\s*=', line):
                    skeleton_param_keys.append(km.group(1))

        allowed_keys_str = ', '.join(skeleton_param_keys) if skeleton_param_keys else 'ibias, w_in, l_in, w_load, l_load, w_tail, l_tail'

        sys_prompt = (
            "You are an analog circuit sizing expert. "
            "Output ONLY a single .PARAM line with key=value pairs. "
            "Use SPICE suffixes: u=micro, n=nano, p=pico. "
            f"You MUST use ONLY these parameter names: {allowed_keys_str}. "
            "Do not invent new parameter names. "
            "Example: .PARAM ibias=15u w_in=4u l_in=500n w_load=8u l_load=500n"
        )
        user_prompt = (
            f"Topology: {topology}\n"
            f"Target spec: gain={spec['gain_db']}dB gbw={spec['gbw_hz']:.0e}Hz "
            f"power<{spec['pmax_w']:.0e}W vdd={spec['vdd']}V\n"
            f"Available parameters: {allowed_keys_str}\n"
            f"Reference designs:\n{few_shot}\n"
            f"Output .PARAM line:"
        )

        llm_out = _call_llm(sys_prompt, user_prompt, model_override=self.model)

        # Parse key=value pairs from LLM output
        param_matches = re.finditer(
            r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([0-9eE\.\-]+[a-zA-Z]*)",
            llm_out
        )
        params_dict = {}
        for m in param_matches:
            key = m.group(1)
            # Only accept keys that exist in the skeleton template
            if skeleton_param_keys and key not in skeleton_param_keys:
                continue
            val = m.group(2).strip()
            val = re.sub(r"[,;.]+$", "", val)
            clamped_val = clamp_spice_value(key, val)
            params_dict[key] = clamped_val

        # Fallback: use skeleton defaults if LLM produced nothing usable
        if not params_dict:
            params_dict = {
                "ibias": "1.0000e-05", "w_in": "2.0000e-06", "l_in": "5.0000e-07",
                "w_load": "4.0000e-06", "l_load": "5.0000e-07",
                "w_tail": "4.0000e-06", "l_tail": "5.0000e-07"
            }

        param_str = ".PARAM " + " ".join([f"{k}={v}" for k, v in params_dict.items()]) + "\n"

        # Remove original .PARAM line from skeleton, keep title line FIRST
        lines = skeleton_content.split('\n')
        new_lines = [l for l in lines if not l.strip().upper().startswith(".PARAM")]

        # SPICE requires title as first line. Insert .PARAM after it.
        if new_lines:
            final_netlist = new_lines[0] + '\n' + param_str + '\n'.join(new_lines[1:])
        else:
            final_netlist = f"* {topology}\n" + param_str

        fd, path = tempfile.mkstemp(suffix=".sp", prefix=f"llm_{topology}_")
        with os.fdopen(fd, 'w') as f:
            f.write(final_netlist)

        backend_label = BACKEND.upper()
        model_label = (self.model or (OLLAMA_MODEL if BACKEND == "ollama" else OPENROUTER_MODEL)).split("/")[-1]
        print(f"[{backend_label}_{model_label}] {len(params_dict)} params -> {path}")
        return path


# Module-level singleton
_gen_singleton = None

def generate(spec: dict, topology: str) -> str:
    global _gen_singleton
    if _gen_singleton is None:
        _gen_singleton = LLMNetlistGen()
    return _gen_singleton.generate(spec, topology)

def set_model(model: str):
    global _gen_singleton
    if _gen_singleton is None:
        _gen_singleton = LLMNetlistGen(model=model)
    else:
        _gen_singleton.set_model(model)
