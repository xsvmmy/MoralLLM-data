"""
LLM Debate Results CSV Loader

Parses per-scenario LLM debate result CSVs — one row per ResponseID, each
carrying several debaters' individual judgments plus the debate's final
verdict (e.g. NH_LS_DEBATE_RES_nh_alph_1v1_200_results_glm4_200_round1_all.csv).

Distinct from llm_results_loader.py, which parses single-model (no debate)
LLM result CSVs.
"""

import csv
from pathlib import Path
from typing import Dict, List


def _normalize_choice(raw: str) -> str:
    """
    Map a judgment/verdict cell to 'stay', 'swerve', or 'parse_error'.

    The debate pipeline can fail to produce a clean verdict (logged as
    PARSE_ERROR in Debate_Final_Answer) when the judge's output couldn't be
    parsed — that's a distinct, meaningful outcome, not a default to hide.
    """
    low = (raw or "").strip().lower()
    if "parse_error" in low or "parse error" in low:
        return "parse_error"
    if "swerve" in low:
        return "swerve"
    if "stay" in low:
        return "stay"
    return "parse_error"


def load_debate_results(csv_path: str, max_rows: int = 50_000) -> List[Dict]:
    """
    Load and parse an LLM debate results CSV into a list of result dicts.

    Each row becomes:
        {
          "response_id":       str,   # matches a Moral Machine ResponseID
          "pedestrians_desc":  str,    # Scenario1_Description (STAY victims)
          "swerve_desc":       str,    # Scenario2_Description (SWERVE victims)
          "debate_judgment":   "stay"|"swerve"|"parse_error",
          "debate_reasoning":  str,
          "model":             str,
          "human_response":    "stay"|"swerve",
          "matches_human":     str,    # "Yes"/"No" as recorded in the CSV
        }

    Args:
        csv_path: Absolute or relative path to the CSV file
        max_rows: Stop after this many rows (default 50 000)

    Returns:
        List of result dicts
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    results: List[Dict] = []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if len(results) >= max_rows:
                break

            rid = (row.get("ID") or "").strip()
            if not rid:
                continue

            results.append({
                "response_id":       rid,
                "pedestrians_desc":  (row.get("Scenario1_Description") or "").strip(),
                "swerve_desc":       (row.get("Scenario2_Description") or "").strip(),
                "debate_judgment":   _normalize_choice(row.get("Debate_Final_Answer", "")),
                "debate_reasoning":  (row.get("Debate_Reasoning") or "").strip(),
                "model":             (row.get("Model") or "").strip(),
                "human_response":    _normalize_choice(row.get("Human_Response", "")),
                "matches_human":     (row.get("Matches_Human") or "").strip(),
            })

    return results
