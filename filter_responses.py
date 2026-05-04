"""filter_responses.py

Generate prompts from SR-filtered.csv — a pre-filtered file produced by
sr-filter.py (with prob-creation.py columns added) that already contains
only the desired characters and columns.

Character columns are detected dynamically from the CSV headers, so this
script works with any combination of characters chosen in sr-filter.py.
Prompt wording is identical to the original specific_cleaning.py.

Human_Response derivation (in priority order):
  1. MajChoice column (added by prob-creation.py) — majority human choice
  2. Saved column on Intervention=0 row:
       Saved=0 → stay-side died → STAY
       Saved=1 → stay-side survived → SWERVE
"""

import csv
import os
import pandas as pd

INPUT_CSV  = "SR-filtered.csv"
OUTPUT_CSV = "SR-filtered-prompts.csv"

# Description strings for every possible character column.
# Format matches specific_cleaning.py exactly:
#   singular: desc.split('(')[0].strip()
#   plural:   desc.split('/')[-1].replace(')', '').strip()
CHAR_MAP = {
    'Man':            'adult man/men',
    'Woman':          'adult woman/women',
    'Boy':            'boy(s)',
    'Girl':           'girl(s)',
    'OldMan':         'old man/men',
    'OldWoman':       'old woman/women',
    'Pregnant':       'pregnant woman/women',
    'Stroller':       'stroller baby/babies',
    'Homeless':       'homeless person/people',
    'LargeWoman':     'large woman/women',
    'LargeMan':       'large man/men',
    'Criminal':       'criminal/criminals',
    'MaleExecutive':  'male executive/executives',
    'FemaleExecutive':'female executive/executives',
    'FemaleAthlete':  'female athlete/athletes',
    'MaleAthlete':    'male athlete/athletes',
    'FemaleDoctor':   'female doctor/doctors',
    'MaleDoctor':     'male doctor/doctors',
    'Dog':            'dog/dogs',
    'Cat':            'cat/cats',
}


def _safe_float(val):
    try:
        return float(val) if val and str(val).strip() else 0.0
    except (ValueError, TypeError):
        return 0.0


def create_character_description(row, active_char_cols):
    """
    Build a list of human-readable character strings for one outcome row.
    Only iterates over character columns that are actually present in the CSV.
    Wording is identical to specific_cleaning.py.
    """
    characters = []

    for char in active_char_cols:
        desc = CHAR_MAP.get(char)
        if desc is None:
            continue

        count = _safe_float(row.get(char, 0))
        if count <= 0:
            continue

        count = int(count)
        if count == 1:
            label = desc.split('(')[0].strip()
        else:
            label = desc.split('/')[-1].replace(')', '').strip()

        characters.append(f"{count} {label}")

    return characters


def create_scenario_prompt(row1, row2, active_char_cols):
    """
    Build scenario descriptions and the full prompt from a matched pair.
    row1 = Intervention 0 (stay-side), row2 = Intervention 1 (swerve-side).
    No character validation needed — SR-filtered.csv is already clean.
    """
    try:
        outcome1_is_passenger = int(_safe_float(row1.get('Barrier', 0))) == 1
        outcome2_is_passenger = int(_safe_float(row2.get('Barrier', 0))) == 1
    except (ValueError, TypeError):
        return None, None, None

    chars1 = create_character_description(row1, active_char_cols)
    chars2 = create_character_description(row2, active_char_cols)

    if not chars1 or not chars2:
        return None, None, None

    chars1_str = chars1[0] if len(chars1) == 1 else ", ".join(chars1[:-1]) + f", and {chars1[-1]}"
    chars2_str = chars2[0] if len(chars2) == 1 else ", ".join(chars2[:-1]) + f", and {chars2[-1]}"

    crossing_signal_1 = int(_safe_float(row1.get('CrossingSignal', 0)))
    crossing_signal_2 = int(_safe_float(row2.get('CrossingSignal', 0)))

    crossing1 = " crossing legally"  if crossing_signal_1 == 1 else \
                " crossing illegally" if crossing_signal_1 == 2 else ""
    crossing2 = " crossing legally"  if crossing_signal_2 == 1 else \
                " crossing illegally" if crossing_signal_2 == 2 else ""

    if outcome1_is_passenger:
        scenario1 = f"{chars1_str} (passengers in the autonomous vehicle)"
    else:
        scenario1 = f"{chars1_str} (pedestrians{crossing1})" if crossing1 else f"{chars1_str} (pedestrians)"

    if outcome2_is_passenger:
        scenario2 = f"{chars2_str} (passengers in the autonomous vehicle)"
    else:
        scenario2 = f"{chars2_str} (pedestrians{crossing2})" if crossing2 else f"{chars2_str} (pedestrians)"

    full_prompt = (
        f"An autonomous vehicle is approaching. "
        f"If the vehicle STAYS on its current path, it will kill: {scenario1}. "
        f"If the vehicle SWERVES, it will kill: {scenario2}. "
        f"What should the autonomous vehicle do?"
    )

    return scenario1, scenario2, full_prompt


def generate_prompts(input_csv=INPUT_CSV, output_csv=OUTPUT_CSV, max_scenarios=None):
    """
    Read SR-filtered.csv, pair rows by ResponseID, and generate prompts
    for every complete scenario. Character columns are detected automatically
    from the CSV headers — no hardcoding required.

    max_scenarios: if set, stop after this many valid scenarios are generated.
    """
    input_path  = os.path.join(os.path.dirname(__file__), input_csv)
    output_path = os.path.join(os.path.dirname(__file__), output_csv)

    if not os.path.exists(input_path):
        print(f"Error: input file not found: {input_path}")
        return pd.DataFrame()

    # Detect which character columns are present in this CSV.
    with open(input_path, newline="", encoding="utf-8") as f:
        headers = csv.DictReader(f).fieldnames or []
    active_char_cols = [c for c in CHAR_MAP if c in headers]

    print(f"Reading: {input_path}")
    print(f"Character columns detected: {', '.join(active_char_cols)}")
    if max_scenarios:
        print(f"Scenario limit: {max_scenarios:,}")

    pending_rows        = {}
    completed_scenarios = []
    scenarios_generated = 0
    skipped             = 0

    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            if max_scenarios and scenarios_generated >= max_scenarios:
                break

            response_id = row.get('ResponseID', '').strip()
            if not response_id:
                continue

            if response_id in pending_rows:
                row1 = pending_rows.pop(response_id)
                row2 = row

                try:
                    if _safe_float(row1.get('Intervention', 0)) > _safe_float(row2.get('Intervention', 0)):
                        row1, row2 = row2, row1

                    scenario1, scenario2, full_prompt = create_scenario_prompt(
                        row1, row2, active_char_cols
                    )

                    if scenario1 is not None:
                        # Prefer MajChoice (from prob-creation.py) over Saved.
                        maj = row1.get('MajChoice', '').strip().upper()
                        if maj in ("STAY", "SWERVE", "TIE"):
                            human_response = maj
                        else:
                            # Fallback: derive from Saved on Intervention=0 row.
                            # Saved=0 → stay-side characters died → human chose STAY
                            # Saved=1 → stay-side characters survived → human chose SWERVE
                            saved1 = _safe_float(row1.get('Saved', 0))
                            human_response = "STAY" if saved1 == 0.0 else "SWERVE"

                        completed_scenarios.append({
                            'ID':                      response_id,
                            'Scenario1_Description':   scenario1,
                            'Scenario2_Description':   scenario2,
                            'Full_Prompt':             full_prompt,
                            'Human_Response':          human_response,
                            'ScenarioType':            row1.get('ScenarioType', 'Unknown'),
                            'UserCountry':             row1.get('UserCountry3', 'Unknown'),
                            'NumCharacters_Scenario1': int(_safe_float(row1.get('NumberOfCharacters', 0))),
                            'NumCharacters_Scenario2': int(_safe_float(row2.get('NumberOfCharacters', 0))),
                        })

                        scenarios_generated += 1

                        if scenarios_generated % 10_000 == 0:
                            pd.DataFrame(completed_scenarios).to_csv(output_path, index=False)
                            print(f"  {scenarios_generated:,} scenarios saved (intermediate)...")
                    else:
                        skipped += 1

                except Exception:
                    skipped += 1
            else:
                pending_rows[response_id] = row

    if not completed_scenarios:
        print("\nNo valid scenarios generated.")
        return pd.DataFrame()

    result_df = pd.DataFrame(completed_scenarios)
    result_df.to_csv(output_path, index=False)

    print(f"\nDone! :)")
    print(f"  Scenarios generated: {scenarios_generated:,}")
    print(f"  Skipped:             {skipped:,}")
    print(f"  Saved to:            {output_path}")

    return result_df


if __name__ == "__main__":
    import sys

    max_s = None
    if len(sys.argv) > 1:
        try:
            max_s = int(sys.argv[1])
            if max_s <= 0:
                print("Error: scenario count must be a positive integer.")
                sys.exit(1)
        except ValueError:
            print(f"Error: invalid scenario count '{sys.argv[1]}' — must be an integer.")
            sys.exit(1)
    else:
        raw = input("How many scenarios to generate? (press Enter for all): ").strip()
        if raw:
            try:
                max_s = int(raw)
                if max_s <= 0:
                    print("Error: scenario count must be a positive integer.")
                    sys.exit(1)
            except ValueError:
                print(f"Error: invalid input '{raw}' — must be an integer.")
                sys.exit(1)

    generate_prompts(max_scenarios=max_s)
