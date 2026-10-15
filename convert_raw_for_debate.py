"""convert_raw_for_debate.py

model-debate.py's input reader (see main() in model-debate.py) expects a CSV
with already-parsed columns — Agreement, LLM_Judgment, LLM_Justification,
Full_LLM_Response, etc. — and selects debate candidates via
`row.get("Agreement", "").strip() == "No"`. RAW_nh_*.csv files only have a
Raw_LLM_Response blob and no Agreement column, so pointing model-debate.py
at one directly finds zero disagreements and exits immediately.

This script converts RAW files into that expected structured schema (the
same column layout used by nh_alph_1v1_ALL_n25_results_*.csv elsewhere in
this project), reusing the Judgment/Justification/EthicalFramework parsing
from raw_accuracy_log.py so the two stay in sync. Point model-debate.py's
-i flag at the converted output and it will find real disagreements to
debate.

To reuse on a new batch of files, edit INPUT_FILES below or pass paths as
command-line arguments (which override the list).
"""

import csv
import os
import sys

from raw_accuracy_log import parse_judgment, parse_framework, parse_justification

INPUT_FILES = [
    "RAW_nh_0729_1v1_ALL_200_results_glm4_200_round1.csv",
    "RAW_nh_0729_1v1_ALL_200_results_glm4_200_round2.csv",
    "RAW_nh_0729_1v1_ALL_200_results_glm4_200_round3.csv",
]

OUTPUT_FIELDS = [
    "ID", "Scenario1_Description", "Scenario2_Description", "Full_Prompt",
    "Human_Response", "ScenarioType", "UserCountry",
    "NumCharacters_Scenario1", "NumCharacters_Scenario2",
    "LLM_Judgment", "LLM_Justification", "EthicalFramework",
    "Full_LLM_Response", "Model", "Prompting_Strategy", "Agreement",
]


def convert_row(row):
    raw_response = row.get("Raw_LLM_Response", "")
    judgment = parse_judgment(raw_response)
    human_response = (row.get("Human_Response") or "").strip().upper()

    if judgment is None:
        llm_judgment = "PARSE_ERROR"
        ethical_framework = "N/A"
        agreement = "N/A"
    else:
        llm_judgment = judgment
        ethical_framework = parse_framework(raw_response)
        agreement = "Yes" if judgment == human_response else "No"

    return {
        "ID": row.get("ID", ""),
        "Scenario1_Description": row.get("Scenario1_Description", ""),
        "Scenario2_Description": row.get("Scenario2_Description", ""),
        "Full_Prompt": row.get("Full_Prompt", ""),
        "Human_Response": row.get("Human_Response", ""),
        "ScenarioType": row.get("ScenarioType", ""),
        "UserCountry": row.get("UserCountry", ""),
        "NumCharacters_Scenario1": row.get("NumCharacters_Scenario1", ""),
        "NumCharacters_Scenario2": row.get("NumCharacters_Scenario2", ""),
        "LLM_Judgment": llm_judgment,
        "LLM_Justification": parse_justification(raw_response),
        "EthicalFramework": ethical_framework,
        "Full_LLM_Response": raw_response,
        "Model": row.get("Model", ""),
        "Prompting_Strategy": row.get("Prompting_Strategy", ""),
        "Agreement": agreement,
    }


def convert_file(csv_path, output_path):
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    converted = [convert_row(row) for row in rows]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(converted)

    valid = sum(1 for r in converted if r["LLM_Judgment"] != "PARSE_ERROR")
    disagreements = sum(1 for r in converted if r["Agreement"] == "No")
    return len(converted), valid, disagreements


def output_path_for(csv_path):
    directory, filename = os.path.split(csv_path)
    if filename.startswith("RAW_"):
        filename = filename[len("RAW_"):]
    else:
        filename = f"parsed_{filename}"
    return os.path.join(directory, filename)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    input_files = sys.argv[1:] if len(sys.argv) > 1 else INPUT_FILES

    for raw_path in input_files:
        csv_path = raw_path if os.path.isabs(raw_path) else os.path.join(script_dir, raw_path)
        if not os.path.exists(csv_path):
            print(f"Skipping (file not found): {os.path.basename(csv_path)}")
            continue

        output_path = output_path_for(csv_path)
        total, valid, disagreements = convert_file(csv_path, output_path)
        print(
            f"{os.path.basename(csv_path)} -> {os.path.basename(output_path)}: "
            f"{total} rows, {valid} valid, {disagreements} disagreements "
            f"(these are what model-debate.py -i {os.path.basename(output_path)} will debate)"
        )


if __name__ == "__main__":
    main()
