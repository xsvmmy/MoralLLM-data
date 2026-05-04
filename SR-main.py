# SR-main.py
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

# Import model query functions
#from models import query_llama2, query_mistral, query_gpt2, query_llama4_scout, query_gpt_oss, query_gpt_oss_safeguard, query_qwen3, query_phi4_reasoning, query_llama4_maverick
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
    """
    Route to the appropriate model query function based on model_name

    Returns:
        str: full_response from the model
    """
    model_functions = {
        #"llama2": query_llama2,
        "mistral": query_mistral,
        #"gpt2": query_gpt2,
        "llama4_scout": query_llama4_scout,
        "gpt_oss": query_gpt_oss,
        #"qwen3": query_qwen3,
        #"phi4_reasoning": query_phi4_reasoning,
        #"llama4_maverick": query_llama4_maverick,
        #"gpt_oss_safeguard": query_gpt_oss_safeguard,
        # Add more models here as needed
    }

    if model_name not in model_functions:
        raise ValueError(f"Unknown model: {model_name}. Available models: {list(model_functions.keys())}")

    return model_functions[model_name](prompt)

# =========================
# Output Parsing
# =========================
def parse_llm_output(text: str) -> MoralOutput:
    """
    Parse the LLM output to extract judgment and justification

    Enforces:
    Judgment: STAY|SWERVE
    Justification: ...
    """
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
def log_accuracy(model_name: str, prompting_strategy: str,
                 agreement_rate: float, valid_count: int, total_count: int,
                 log_file: str = "outputs/SR-accuracy_log.txt"):
    """
    Append accuracy results to a log file with timestamp
    """
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_entry = (
        f"{'='*70}\n"
        f"Timestamp: {timestamp}\n"
        f"Model: {model_name}\n"
        f"Prompting Strategy: {prompting_strategy}\n"
        f"Valid Responses: {valid_count}/{total_count}\n"
        f"Agreement with Humans: {agreement_rate:.2f}%\n"
        f"{'='*70}\n\n"
    )

    with open(log_file, 'a') as f:
        f.write(log_entry)

    print(f"Logged results to {log_file}")

# =========================
# Main Experiment
# =========================
def main():
    # -------- CONFIG --------
    model_name = "gpt_oss"  # "llama2" | "mistral" | "gpt2" | "llama4_scout" | "gpt_oss"
    prompting_strategy = "zero-shot"  # "zero-shot" | "one-shot" | "few-shot" | "cot"
    input_csv = os.path.join(os.path.dirname(__file__), "SR-filtered-prompts.csv")
    log_file = "outputs/SR-accuracy_log.txt"
    max_scenarios = None  # Set to an integer to limit, or None to process all

    # -------- SCENARIO LIMIT (CLI or prompt) --------
    if len(sys.argv) > 1:
        try:
            max_scenarios = int(sys.argv[1])
            if max_scenarios <= 0:
                print("Error: scenario count must be a positive integer.")
                sys.exit(1)
        except ValueError:
            print(f"Error: invalid scenario count '{sys.argv[1]}' — must be an integer.")
            sys.exit(1)
    else:
        raw = input("How many scenarios to process? (press Enter for all): ").strip()
        if raw:
            try:
                max_scenarios = int(raw)
                if max_scenarios <= 0:
                    print("Error: scenario count must be a positive integer.")
                    sys.exit(1)
            except ValueError:
                print(f"Error: invalid input '{raw}' — must be an integer.")
                sys.exit(1)

    # -------- OUTPUT NAMING --------
    count_label = str(max_scenarios) if max_scenarios else "all"
    output_csv = f"outputs/results_{model_name}_{count_label}_round3.csv"

    # Create outputs directory if it doesn't exist
    os.makedirs("outputs", exist_ok=True)

    # -------- LOAD DATASET --------
    df_input = pd.read_csv(input_csv)

    if max_scenarios is not None:
        df_input = df_input.head(max_scenarios)

    records = []

    print(f"Starting experiment with model: {model_name}, strategy: {prompting_strategy}")
    print(f"Processing {len(df_input)} scenarios...\n")

    for idx, row in df_input.iterrows():
        # Extract data from CSV
        scenario_id    = row["ID"]
        scenario1_desc = row["Scenario1_Description"]
        scenario2_desc = row["Scenario2_Description"]
        full_prompt_base = row["Full_Prompt"]
        human_response = row["Human_Response"]
        scenario_type  = row.get("ScenarioType", "Unknown")
        user_country   = row.get("UserCountry", "Unknown")
        num_chars_s1   = row["NumCharacters_Scenario1"]
        num_chars_s2   = row["NumCharacters_Scenario2"]

        # Get prompt based on strategy
        prompt = get_prompt(prompting_strategy, full_prompt_base)

        # Query model
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
                # "UserCountry": user_country,
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

        # Progress indicator
        if (idx + 1) % 10 == 0:
            print(f"Processed {idx + 1}/{len(df_input)} scenarios...")

    # Save results
    df_output = pd.DataFrame(records)
    df_output.to_csv(output_csv, index=False)

    # Summary statistics
    valid_responses = df_output[df_output["LLM_Judgment"] != "PARSE_ERROR"]
    agreement_rate = (valid_responses["Agreement"] == "Yes").mean() * 100 if len(valid_responses) > 0 else 0

    print(f"\n{'='*50}")
    print(f"Saved {len(df_output)} samples → {output_csv}")
    print(f"Valid responses: {len(valid_responses)}/{len(df_output)}")
    print(f"Agreement with humans: {agreement_rate:.2f}%")
    print(f"{'='*50}")

    log_accuracy(
        model_name=model_name,
        prompting_strategy=prompting_strategy,
        agreement_rate=agreement_rate,
        valid_count=len(valid_responses),
        total_count=len(df_output),
        log_file=log_file
    )

if __name__ == "__main__":
    main()
