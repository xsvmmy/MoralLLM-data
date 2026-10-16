"""
LLM Results CSV Loader

Parses per-scenario LLM result CSVs — one row per ResponseID, already
carrying the LLM's stay/swerve judgment (e.g.
nh_alph_1v1_200_results_gemini_200_round1.csv).

Distinct from csv_loader.py, which parses raw Moral Machine survey CSVs
(two rows per ResponseID, one per Intervention value, no LLM judgment).
"""

import csv
from pathlib import Path
from typing import Dict, List


def _normalize_choice(raw: str) -> str:
    """Map a judgment/response cell to 'stay' or 'swerve' (default 'stay')."""
    low = (raw or "").strip().lower()
    if "swerve" in low:
        return "swerve"
    return "stay"


def load_llm_results(csv_path: str, max_rows: int = 50_000) -> List[Dict]:
    """
    Load and parse an LLM results CSV into a list of result dicts.

    Each row becomes:
        {
          "response_id":        str,   # matches a Moral Machine ResponseID
          "pedestrians_desc":   str,    # Scenario1_Description (STAY victims)
          "swerve_desc":        str,    # Scenario2_Description (SWERVE victims)
          "llm_judgment":       "stay"|"swerve",
          "llm_justification":  str,
          "ethical_framework":  str,
          "model":              str,
          "prompting_strategy": str,
          "human_response":     "stay"|"swerve",
          "agreement":          str,    # "Yes"/"No" as recorded in the CSV
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
                "response_id":        rid,
                "pedestrians_desc":   (row.get("Scenario1_Description") or "").strip(),
                "swerve_desc":        (row.get("Scenario2_Description") or "").strip(),
                "llm_judgment":       _normalize_choice(row.get("LLM_Judgment", "")),
                "llm_justification":  (row.get("LLM_Justification") or "").strip(),
                "ethical_framework":  (row.get("EthicalFramework") or "").strip(),
                "model":              (row.get("Model") or "").strip(),
                "prompting_strategy": (row.get("Prompting_Strategy") or "").strip(),
                "human_response":     _normalize_choice(row.get("Human_Response", "")),
                "agreement":          (row.get("Agreement") or "").strip(),
            })

    return results
