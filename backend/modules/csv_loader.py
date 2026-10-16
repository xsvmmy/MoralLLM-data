"""
CSV Loader Module

Parses filtered_responses.csv and returns structured scenario dicts
suitable for RL agent simulation. Each unique ResponseID produces one
scenario by pairing its two rows (Intervention=0 and Intervention=1).
"""

import csv
from pathlib import Path
from typing import List, Dict, Optional

# Character columns present in the CSV (in order)
CHARACTER_COLUMNS = [
    "Man", "Woman", "Pregnant", "Stroller", "OldMan", "OldWoman",
    "Boy", "Girl", "Homeless", "LargeWoman", "LargeMan", "Criminal",
    "MaleExecutive", "FemaleExecutive", "FemaleAthlete", "MaleAthlete",
    "FemaleDoctor", "MaleDoctor", "Dog", "Cat"
]


def _counts_to_list(row: dict, cap: int = 5) -> List[str]:
    """
    Convert character count columns in a CSV row to a flat list of names.

    E.g. if row["Man"]==2 and row["Woman"]==1, returns ["Man","Man","Woman"].
    Caps total list length at `cap` (default 5) to match existing validation.

    Args:
        row: Dict of column→value for one CSV row
        cap: Maximum characters to return

    Returns:
        List of character name strings
    """
    result = []
    for col in CHARACTER_COLUMNS:
        raw = row.get(col, 0)
        try:
            count = int(float(raw))
        except (ValueError, TypeError):
            count = 0
        for _ in range(count):
            if len(result) >= cap:
                break
            result.append(col)
        if len(result) >= cap:
            break
    return result


def load_csv_scenarios(csv_path: str, max_scenarios: int = 50_000) -> List[Dict]:
    """
    Load and parse filtered_responses.csv into a list of scenario dicts.

    Each unique ResponseID with both Intervention=0 and Intervention=1 rows
    produces one scenario dict with the structure:

        {
          "response_id": str,
          "passengers":  List[str],   # harmed if AV swerves (Intervention=1 row)
          "pedestrians": List[str],   # harmed if AV stays   (Intervention=0 row)
          "traffic_light": "Green"|"Red",
          "barrier": bool,            # True if swerve target is a barricade
          "credences": {
              "deontological": float, # stay_prob  (non-interference belief)
              "utilitarian":   float, # swerve_prob (intervention belief)
          },
          "human_choice": "stay"|"swerve",
        }

    Pairs where either intervention row is missing are silently skipped.
    Reading stops once max_scenarios complete pairs have been collected, so
    large CSV files (20M+ rows) load quickly.

    Args:
        csv_path:      Absolute or relative path to filtered_responses.csv
        max_scenarios: Stop after collecting this many complete pairs (default 50 000)

    Returns:
        List of scenario dicts
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    # Group rows by ResponseID
    groups: Dict[str, Dict[str, dict]] = {}  # {response_id: {0: row, 1: row}}
    complete_count = 0

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Early exit once we have enough complete pairs
            if complete_count >= max_scenarios:
                break

            rid = row.get("ResponseID", "").strip()
            if not rid:
                continue
            try:
                intervention = int(float(row.get("Intervention", "-1")))
            except (ValueError, TypeError):
                continue
            if intervention not in (0, 1):
                continue

            if rid not in groups:
                groups[rid] = {}
            # Keep first occurrence for each intervention value per ResponseID
            if intervention not in groups[rid]:
                groups[rid][intervention] = row
                # Count complete pairs as they form
                if len(groups[rid]) == 2:
                    complete_count += 1

    scenarios = []
    for rid, pair in groups.items():
        if 0 not in pair or 1 not in pair:
            continue  # Skip incomplete pairs

        row_stay   = pair[0]  # Intervention=0: these characters die if AV stays
        row_swerve = pair[1]  # Intervention=1: these characters die if AV swerves

        # Per the README: Barrier column identifies character type in each row.
        #   Barrier=1 → characters in that row are AV *passengers* (inside the vehicle).
        #   Barrier=0 → characters in that row are *pedestrians* (on the road).
        try:
            barrier_stay   = int(float(row_stay.get("Barrier",   0))) == 1
            barrier_swerve = int(float(row_swerve.get("Barrier", 0))) == 1
        except (ValueError, TypeError):
            barrier_stay, barrier_swerve = False, False

        # AV passengers: from whichever row is marked Barrier=1.
        # PedPed=1 scenarios have Barrier=0 on both rows → no passengers.
        if barrier_stay:
            passengers_in_av = _counts_to_list(row_stay)
        elif barrier_swerve:
            passengers_in_av = _counts_to_list(row_swerve)
        else:
            passengers_in_av = []

        # Lane character groups (only from pedestrian rows, i.e. Barrier=0).
        lane1_chars = [] if barrier_stay   else _counts_to_list(row_stay)
        lane2_chars = [] if barrier_swerve else _counts_to_list(row_swerve)

        if not lane1_chars and not barrier_stay:
            lane1_chars = ["Man"]
        if not lane2_chars and not barrier_swerve:
            lane2_chars = ["Man"]

        # Legacy fields used by simulation engine (harmed counts must be correct).
        #   pedestrians = characters harmed if AV stays
        #   passengers  = characters harmed if AV swerves
        pedestrians = passengers_in_av if barrier_stay   else lane1_chars
        passengers  = passengers_in_av if barrier_swerve else lane2_chars
        if not pedestrians:
            pedestrians = ["Man"]
        if not passengers:
            passengers = ["Man"]

        # ── Scenario metadata ───────────────────────────────────────────────
        # PedPed first — needed to decide how to parse crossing signals below.
        try:
            ped_ped = int(float(row_stay.get("PedPed", 0))) == 1
        except (ValueError, TypeError):
            ped_ped = False

        # Prefer ScenarioTypeStrict (more accurate); fall back to ScenarioType
        scenario_type = (
            row_stay.get("ScenarioTypeStrict", "").strip()
            or row_stay.get("ScenarioType",       "").strip()
            or "Random"
        )

        # AttributeLevel: what ethical dimension is being contrasted
        # (e.g. "Fit" vs "Fat" for a Fitness scenario)
        attribute_level = (
            row_stay.get("AttributeLevel",   "").strip()
            or row_swerve.get("AttributeLevel", "").strip()
            or ""
        )

        # ── Traffic light / legality ────────────────────────────────────────
        # CrossingSignal: 0=no legality, 1=legal/green, 2=illegal/red
        #
        # In ped_ped scenarios both rows are pedestrian rows with *independent*
        # signals (one lane is legal, the other illegal).  In standard scenarios
        # only the pedestrian row carries a signal; the passenger row does not.
        _sig_map = {0: "None", 1: "Green", 2: "Red"}
        try:
            sig_stay   = int(float(row_stay.get("CrossingSignal",   0)))
            sig_swerve = int(float(row_swerve.get("CrossingSignal", 0)))
        except (ValueError, TypeError):
            sig_stay, sig_swerve = 0, 0

        if ped_ped:
            # Each lane has its own independent crossing signal.
            lane1_traffic_light = _sig_map.get(sig_stay,   "None")
            lane2_traffic_light = _sig_map.get(sig_swerve, "None")
            # Primary traffic_light / legal_status uses lane1 for RL state.
            signal        = sig_stay
            traffic_light = lane1_traffic_light
        else:
            # Only the pedestrian row carries a signal.
            ped_row = row_swerve if barrier_stay else row_stay
            try:
                signal = int(float(ped_row.get("CrossingSignal", 0)))
            except (ValueError, TypeError):
                signal = 0
            traffic_light       = _sig_map.get(signal, "None")
            lane1_traffic_light = traffic_light
            lane2_traffic_light = "None"   # passenger lane has no crossing signal

        legal_status = signal   # 0/1/2

        # Absolute difference in character count between the two outcomes
        try:
            diff_n_chars = abs(int(float(row_stay.get("DiffNumberOFCharacters", 0))))
        except (ValueError, TypeError):
            diff_n_chars = 0

        # ── Crowd credences ─────────────────────────────────────────────────
        # Two known schemas:
        #   filtered_responses.csv  → stay_prob / swerve_prob (pre-aggregated)
        #   1v1-200-scenarios.csv   → StayCred / SwerveCred
        try:
            if "stay_prob" in row_stay or "swerve_prob" in row_stay:
                stay_prob   = float(row_stay.get("stay_prob",   0.5))
                swerve_prob = float(row_stay.get("swerve_prob", 0.5))
            elif "StayCred" in row_stay or "SwerveCred" in row_stay:
                stay_prob   = float(row_stay.get("StayCred",   0.5))
                swerve_prob = float(row_stay.get("SwerveCred", 0.5))
            else:
                stay_prob, swerve_prob = 0.5, 0.5
        except (ValueError, TypeError):
            stay_prob, swerve_prob = 0.5, 0.5

        total = stay_prob + swerve_prob
        if total > 0:
            stay_prob   /= total
            swerve_prob /= total
        else:
            stay_prob, swerve_prob = 0.5, 0.5

        # ── Human majority choice ───────────────────────────────────────────
        # Two known schemas:
        #   filtered_responses.csv  → n_stay / n_swerve (raw vote counts)
        #   1v1-200-scenarios.csv   → MajChoice ("STAY" / "SWERVE")
        if "n_stay" in row_stay or "n_swerve" in row_stay:
            try:
                n_stay   = float(row_stay.get("n_stay",   0))
                n_swerve = float(row_stay.get("n_swerve", 0))
            except (ValueError, TypeError):
                n_stay, n_swerve = 0.0, 0.0
            human_choice = "stay" if n_stay >= n_swerve else "swerve"
        elif "MajChoice" in row_stay:
            human_choice = "stay" if row_stay.get("MajChoice", "").strip().upper() == "STAY" else "swerve"
        else:
            human_choice = "stay" if stay_prob >= swerve_prob else "swerve"

        scenarios.append({
            "response_id":      rid,
            # Simulation fields (harmed group depends on action)
            "pedestrians":      pedestrians,
            "passengers":       passengers,
            # Road visualization fields
            "passengers_in_av": passengers_in_av,
            "lane1_chars":      lane1_chars,
            "lane2_chars":      lane2_chars,
            "lane1_is_barrier": barrier_stay,
            "lane2_is_barrier": barrier_swerve,
            "barrier":          barrier_swerve,   # legacy
            # Traffic / legality
            "traffic_light":      traffic_light,        # "None" | "Green" | "Red"  (lane1 / ped row)
            "lane1_traffic_light": lane1_traffic_light, # per-lane signals (ped_ped only differs)
            "lane2_traffic_light": lane2_traffic_light,
            "legal_status":       legal_status,         # 0=none | 1=green | 2=red
            # Scenario metadata (from Moral Machine dataset)
            "scenario_type":    scenario_type,    # Utilitarian | Gender | Fitness | Age | Social Status | Species | Random
            "attribute_level":  attribute_level,  # More | Less | Fit | Fat | Young | Old | Male | Female | High | Low | Hoomans | Pets | Rand
            "ped_ped":          ped_ped,          # True = ped vs ped; False = ped vs passenger
            "diff_n_chars":     diff_n_chars,     # |n_lane1 − n_lane2|
            "credences": {
                "deontological": round(stay_prob,   6),
                "utilitarian":   round(swerve_prob, 6),
            },
            "human_choice":     human_choice,
        })

    return scenarios
