"""
prob-creation.py
----------------
Add human-credence columns to SR-filtered.csv (in-place).

New columns added:
  Saved       — pulled from SharedResponses.csv if not already present
  StayCred    — proportion of humans who chose STAY for this scenario fingerprint
  SwerveCred  — proportion of humans who chose SWERVE
  MajChoice   — "STAY", "SWERVE", or "TIE"

A scenario fingerprint is the combination of character counts on the
stay-side (Intervention=0) and swerve-side (Intervention=1), plus
structural columns (PedPed, Barrier, CrossingSignal).

Human choice per row is derived from the Saved column on the
Intervention=0 row:
  Saved=0 → stay-side characters died → human chose STAY
  Saved=1 → stay-side characters survived → human chose SWERVE
"""

import csv
import os
import sys

INPUT_FILE = "SR-filtered.csv"
SHARED_RESPONSES = "../data/SharedResponses.csv"

CHAR_COLS = [
    "Man", "Woman", "OldMan", "OldWoman", "Boy", "Girl",
    "Pregnant", "Stroller", "Homeless", "LargeWoman", "LargeMan",
    "Criminal", "MaleExecutive", "FemaleExecutive",
    "FemaleAthlete", "MaleAthlete", "FemaleDoctor", "MaleDoctor",
    "Dog", "Cat",
]

STRUCTURAL_COLS = ["PedPed", "Barrier", "CrossingSignal"]

NEW_COLS = ["Saved", "StayCred", "SwerveCred", "MajChoice"]


def _safe_int(val):
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return 0


def _make_fingerprint(stay_row, swerve_row, active_chars):
    """
    Build a hashable fingerprint from the character counts on each side
    plus the structural context columns.
    """
    stay_chars = tuple(_safe_int(stay_row.get(c, 0)) for c in active_chars)
    swerve_chars = tuple(_safe_int(swerve_row.get(c, 0)) for c in active_chars)
    structure = tuple(stay_row.get(c, "").strip() for c in STRUCTURAL_COLS)
    return (stay_chars, swerve_chars, structure)


def _get_choice(saved_val):
    """Derive human choice from the Saved value on the Intervention=0 row."""
    return "STAY" if _safe_int(saved_val) == 0 else "SWERVE"


def main():
    base = os.path.dirname(__file__)
    input_path = os.path.join(base, INPUT_FILE)
    shared_path = os.path.join(base, SHARED_RESPONSES)

    if not os.path.exists(input_path):
        sys.exit(f"Error: {input_path} not found.")

    # ── Step 0: Read headers and check if Saved is already present ───────
    with open(input_path, newline="", encoding="utf-8") as f:
        headers = csv.DictReader(f).fieldnames or []

    has_saved = "Saved" in headers
    active_chars = [c for c in CHAR_COLS if c in headers]

    if not active_chars:
        sys.exit("Error: no character columns found in SR-filtered.csv.")

    print(f"Character columns: {', '.join(active_chars)}")
    print(f"Saved column present: {has_saved}")

    # ── Step 1: If Saved is missing, build a lookup from SharedResponses ─
    saved_lookup = {}  # (ResponseID, Intervention) → Saved

    if not has_saved:
        if not os.path.exists(shared_path):
            sys.exit(
                f"Error: Saved column not in SR-filtered.csv and "
                f"SharedResponses.csv not found at {shared_path}.\n"
                f"Re-run sr-filter.py with the Saved column included, or "
                f"place SharedResponses.csv in the data/ directory."
            )

        print(f"\nReading Saved values from {shared_path} ...")

        # First collect all ResponseIDs we need.
        needed_rids = set()
        with open(input_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rid = row.get("ResponseID", "").strip()
                if rid:
                    needed_rids.add(rid)

        print(f"  Looking up Saved for {len(needed_rids):,} ResponseIDs ...")

        found = 0
        with open(shared_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rid = row.get("ResponseID", "").strip()
                if rid in needed_rids:
                    intervention = row.get("Intervention", "").strip()
                    saved_lookup[(rid, intervention)] = row.get("Saved", "").strip()
                    found += 1

        print(f"  Found {found:,} matching rows in SharedResponses.csv.")

    # ── Step 2: Read all rows, pair by ResponseID, build fingerprints ────
    print(f"\nProcessing {input_path} ...")

    all_rows = []
    pending = {}  # ResponseID → index of first row in all_rows
    pairs = []    # list of (idx_stay, idx_swerve) into all_rows

    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            idx = len(all_rows)
            all_rows.append(row)

            rid = row.get("ResponseID", "").strip()
            if not rid:
                continue

            # Inject Saved from lookup if missing.
            if not has_saved:
                intervention = row.get("Intervention", "").strip()
                row["Saved"] = saved_lookup.get((rid, intervention), "")

            if rid not in pending:
                pending[rid] = idx
            else:
                first_idx = pending.pop(rid)
                first_row = all_rows[first_idx]

                if _safe_int(first_row.get("Intervention", 0)) == 0:
                    pairs.append((first_idx, idx))
                else:
                    pairs.append((idx, first_idx))

    print(f"  Total rows: {len(all_rows):,}")
    print(f"  Complete pairs: {len(pairs):,}")

    # ── Step 3: Fingerprint each pair and count STAY/SWERVE ──────────────
    fp_counts = {}  # fingerprint → {"stay": int, "swerve": int}
    pair_fps = []   # parallel to pairs: fingerprint for each pair

    for stay_idx, swerve_idx in pairs:
        stay_row = all_rows[stay_idx]
        swerve_row = all_rows[swerve_idx]

        fp = _make_fingerprint(stay_row, swerve_row, active_chars)
        pair_fps.append(fp)

        saved_val = stay_row.get("Saved", "0")
        choice = _get_choice(saved_val)

        if fp not in fp_counts:
            fp_counts[fp] = {"stay": 0, "swerve": 0}
        fp_counts[fp][choice.lower()] += 1

    print(f"  Unique fingerprints: {len(fp_counts):,}")

    # ── Step 4: Compute credences and assign to rows ─────────────────────
    # Build fingerprint → (StayCred, SwerveCred, MajChoice)
    fp_creds = {}
    for fp, counts in fp_counts.items():
        total = counts["stay"] + counts["swerve"]
        if total > 0:
            stay_cred = round(counts["stay"] / total, 4)
            swerve_cred = round(counts["swerve"] / total, 4)
        else:
            stay_cred = 0.0
            swerve_cred = 0.0

        if stay_cred > swerve_cred:
            maj = "STAY"
        elif swerve_cred > stay_cred:
            maj = "SWERVE"
        else:
            maj = "TIE"

        fp_creds[fp] = (stay_cred, swerve_cred, maj)

    # Assign credences to both rows of each pair.
    for i, (stay_idx, swerve_idx) in enumerate(pairs):
        fp = pair_fps[i]
        stay_cred, swerve_cred, maj = fp_creds[fp]

        for row_idx in (stay_idx, swerve_idx):
            all_rows[row_idx]["StayCred"] = stay_cred
            all_rows[row_idx]["SwerveCred"] = swerve_cred
            all_rows[row_idx]["MajChoice"] = maj

    # Rows without a matched pair get empty values.
    for row in all_rows:
        row.setdefault("StayCred", "")
        row.setdefault("SwerveCred", "")
        row.setdefault("MajChoice", "")
        row.setdefault("Saved", "")

    # ── Step 5: Write back to SR-filtered.csv ────────────────────────────
    # Preserve original column order, append new columns that aren't already there.
    out_fields = list(headers)
    for col in NEW_COLS:
        if col not in out_fields:
            out_fields.append(col)

    with open(input_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        writer.writeheader()
        for row in all_rows:
            writer.writerow(row)

    print(f"\nDone! :)")
    print(f"  Columns added: {[c for c in NEW_COLS if c not in headers]}")
    print(f"  Updated: {input_path}")


if __name__ == "__main__":
    main()
