TOPOLOGY_LABELS = [
    "5T_OTA", "Telescopic", "Folded_Cascode", "RFC",
    "Two_Stage_Miller", "Three_Stage", "Bulk_Driven", "CFA"
]

def score_topology(topology: str, spec: dict) -> float:
    # Heuristic scoring based on analog design tradeoffs
    score = 10.0 # base score
    
    # 5T_OTA: good for ultra low I, low power, but low gain/gbw
    if topology == "5T_OTA":
        if spec["ultra_low_i"]: score += 5
        if spec["gain_db"] > 50: score -= 5
        if spec["gbw_hz"] > 1e7: score -= 5
        
    # Telescopic: highest speed, highest gain for single stage, but terrible swing
    elif topology == "Telescopic":
        if spec["gbw_hz"] > 1e8: score += 5
        if spec["gain_db"] > 60: score += 2
        if spec["swing_pct"] > 0.6: score -= 10
        if spec["low_voltage"]: score -= 5
        
    # Folded_Cascode: good speed, improved swing over telescopic
    elif topology == "Folded_Cascode":
        score += 3 # solid default
        if spec["gbw_hz"] > 1e7: score += 3
        if spec["swing_pct"] > 0.7: score -= 5
        if spec["low_voltage"]: score -= 3
        
    # RFC (Regulated Folded Cascode / Gain Boosted): extremely high gain
    elif topology == "RFC":
        if spec["gain_db"] > 80: score += 10
        if spec["pmax_w"] < 1e-4: score -= 5 # needs more power
        
    # Two_Stage_Miller: high gain, high swing, moderate speed
    elif topology == "Two_Stage_Miller":
        score += 2 # classic versatile default
        if spec["gain_db"] > 70: score += 4
        if spec["swing_pct"] > 0.8: score += 4
        if spec["gbw_hz"] > 5e7: score -= 5
        
    # Three_Stage: extreme gain, very high swing, very low bandwidth
    elif topology == "Three_Stage":
        if spec["gain_db"] > 90: score += 10
        if spec["swing_pct"] > 0.9: score += 4
        if spec["gbw_hz"] > 1e7: score -= 10
        if spec["pmax_w"] > 1e-3: score += 2

    # Bulk_Driven: excellent for low voltage / rail-to-rail, poor bandwidth
    elif topology == "Bulk_Driven":
        if spec["low_voltage"]: score += 10
        if spec["gbw_hz"] > 1e6: score -= 10
        
    # CFA (Current Feedback): high slew rate, high bandwidth, noisy
    elif topology == "CFA":
        if spec["gbw_hz"] > 5e8: score += 10
        if spec["noise_priority"] > 3: score -= 8

    return score
