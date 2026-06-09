# main-ind.py
# Independent condition: the LLM receives only the scenario prompt.
# Human_Response is read from the CSV solely for post-hoc Agreement computation
# and is never included in anything sent to the model.
import re
import sys
import os
import pandas as pd
from pydantic import BaseModel, Field, ValidationError
from typing import Literal
from datetime import datetime

# Resolve imports relative to the project root (one level up)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from prompts import get_prompt

from models import query_llama4_scout, query_mistral, query_gpt_oss

# =========================
# Pydantic Output Schema
# =========================
class MoralOutput(BaseModel):
    judgment: Literal["STAY", "SWERVE"] = Field(...)
    justification: str = Field(..., min_length=5)

# =========================
# Model Dispatcher
# =========================
def query_model(model_name: str, prompt: str) -> str:
    model_functions = {
        "mistral": query_mistral,
        "llama4_scout": query_llama4_scout,
        "gpt_oss": query_gpt_oss,
    }

    if model_name not in model_functions:
        raise ValueError(f"Unknown model: {model_name}. Available models: {list(model_functions.keys())}")

    return model_functions[model_name](prompt)

# =========================
# Output Parsing
# =========================
def parse_llm_output(text: str) -> MoralOutput:
    judgment_match = re.search(r"Judgment:\s*(STAY|SWERVE)", text, re.IGNORECASE)
    justification_match = re.search(r"Justification:\s*(.+)", text, re.DOTALL)

    if not judgment_match or not justification_match:
        raise ValueError("Output format invalid - missing Judgment or Justification")

    return MoralOutput(
        judgment=judgment_match.group(1).upper(),
        justification=justification_match.group(1).strip()
    )

# =========================
# Log Results to File
# =========================
def log_accuracy(model_name: str, prompting_strategy: str, round_num: int,
                 agreement_rate: float, valid_count: int, total_count: int,
                 log_file: str = "outputs/nh-accuracy-log.txt"):
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_entry = (
        f"{'='*70}\n"
        f"Timestamp: {timestamp}\n"
        f"Model: {model_name}\n"
        f"Prompting Strategy: {prompting_strategy}\n"
        f"Condition: independent (human response withheld from LLM)\n"
        f"Round: {round_num}\n"
        f"Valid Responses: {valid_count}/{total_count}\n"
        f"Agreement with Humans: {agreement_rate:.2f}%\n"
        f"{'='*70}\n\n"
    )

    with open(log_file, 'a') as f:
        f.write(log_entry)

    print(f"Logged results to {log_file}")

# =========================
# Single Round Runner
# =========================
def run_round(round_num: int, model_name: str, prompting_strategy: str,
              df_input: pd.DataFrame, log_file: str):
    count_label = str(len(df_input))
    output_csv = f"outputs/nh_results_{model_name}_{count_label}_round{round_num}.csv"

    print(f"\n{'='*50}")
    print(f"Round {round_num} — model: {model_name}, strategy: {prompting_strategy}")
    print(f"Processing {len(df_input)} scenarios...")
    print(f"{'='*50}\n")

    records = []

    for idx, row in df_input.iterrows():
        scenario_id      = row["ID"]
        scenario1_desc   = row["Scenario1_Description"]
        scenario2_desc   = row["Scenario2_Description"]
        full_prompt_base = row["Full_Prompt"]
        human_response   = row["Human_Response"]  # read for Agreement only — not sent to LLM
        scenario_type    = row.get("ScenarioType", "Unknown")
        user_country     = row.get("UserCountry", "Unknown")
        num_chars_s1     = row["NumCharacters_Scenario1"]
        num_chars_s2     = row["NumCharacters_Scenario2"]

        # Only the scenario text is sent to the model — human_response is withheld.
        prompt = get_prompt(prompting_strategy, full_prompt_base)

        try:
            full_response = query_model(model_name, prompt)
            parsed = parse_llm_output(full_response)

            records.append({
                "ID": scenario_id,
                "Scenario1_Description": scenario1_desc,
                "Scenario2_Description": scenario2_desc,
                "Full_Prompt": full_prompt_base,
                "Human_Response": human_response,
                "ScenarioType": scenario_type,
                "NumCharacters_Scenario1": num_chars_s1,
                "NumCharacters_Scenario2": num_chars_s2,
                "LLM_Judgment": parsed.judgment,
                "LLM_Justification": parsed.justification,
                "Full_LLM_Response": full_response,
                "Model": model_name,
                "Prompting_Strategy": prompting_strategy,
                "Agreement": "Yes" if parsed.judgment == human_response else "No"
            })

        except (ValidationError, ValueError, Exception) as e:
            records.append({
                "ID": scenario_id,
                "Scenario1_Description": scenario1_desc,
                "Scenario2_Description": scenario2_desc,
                "Full_Prompt": full_prompt_base,
                "Human_Response": human_response,
                "ScenarioType": scenario_type,
                "UserCountry": user_country,
                "NumCharacters_Scenario1": num_chars_s1,
                "NumCharacters_Scenario2": num_chars_s2,
                "LLM_Judgment": "PARSE_ERROR",
                "LLM_Justification": str(e),
                "Full_LLM_Response": "",
                "Model": model_name,
                "Prompting_Strategy": prompting_strategy,
                "Agreement": "N/A"
            })

        if (idx + 1) % 10 == 0:
            print(f"  Processed {idx + 1}/{len(df_input)} scenarios...")

    df_output = pd.DataFrame(records)
    df_output.to_csv(output_csv, index=False)

    valid_responses = df_output[df_output["LLM_Judgment"] != "PARSE_ERROR"]
    agreement_rate = (valid_responses["Agreement"] == "Yes").mean() * 100 if len(valid_responses) > 0 else 0

    print(f"\nSaved {len(df_output)} samples → {output_csv}")
    print(f"Valid responses: {len(valid_responses)}/{len(df_output)}")
    print(f"Agreement with humans: {agreement_rate:.2f}%")

    log_accuracy(
        model_name=model_name,
        prompting_strategy=prompting_strategy,
        round_num=round_num,
        agreement_rate=agreement_rate,
        valid_count=len(valid_responses),
        total_count=len(df_output),
        log_file=log_file,
    )

# =========================
# Main Experiment
# =========================
def main():
    # -------- CONFIG --------
    model_name          = "llama4_scout"   # "mistral" | "llama4_scout" | "gpt_oss"
    prompting_strategy  = "zero-shot"      # "zero-shot" | "one-shot" | "few-shot" | "cot"
    input_csv           = os.path.join(os.path.dirname(__file__), "SR-filtered-prompts-2v1.csv")
    log_file            = "outputs/nh-accuracy-log.txt"
    max_scenarios       = 100              # number of scenarios per round
    num_rounds          = 3               # number of times to repeat the experiment

    os.makedirs("outputs", exist_ok=True)

    # -------- LOAD & SLICE DATASET --------
    df_input = pd.read_csv(input_csv)
    if max_scenarios is not None:
        df_input = df_input.head(max_scenarios)

    print(f"Model: {model_name} | Strategy: {prompting_strategy}")
    print(f"Condition: independent (human response withheld from LLM)")
    print(f"Scenarios per round: {len(df_input)} | Rounds: {num_rounds}")

    for round_num in range(1, num_rounds + 1):
        run_round(
            round_num=round_num,
            model_name=model_name,
            prompting_strategy=prompting_strategy,
            df_input=df_input,
            log_file=log_file,
        )

    print(f"\n{'='*50}")
    print(f"All {num_rounds} round(s) complete.")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
