"""
model-debate.py
-----------------
Multi-agent debate pipeline for autonomous-vehicle scenarios
where a human and an LLM originally disagreed.

Three Ollama models each play a distinct role:
  - gpt-oss:20b   → Affirmative debater  (argues its own STAY/SWERVE position)
  - mistral        → Negative debater     (argues the opposing position)
  - llama4:scout   → Moderator / Judge   (drives consensus, makes final call)

Each model reasons independently, then debates over up to MAX_ROUNDS rounds.
The moderator decides when consensus is reached and outputs the final verdict.

Input:  outputs/SR-stat-comparisons.csv  (or path via -i)
        Required columns: ID, Scenario1_Description, Scenario2_Description,
        Full_Prompt, Human_Response, ScenarioType, NumCharacters_Scenario1,
        NumCharacters_Scenario2, LLM_Judgment, LLM_Justification,
        Full_LLM_Response, Model, Prompting_Strategy, Agreement

Output: outputs/SR-debate-decisions.csv
        Columns: (all input columns except Full_LLM_Response) +
        GPT_OSS_Judgment, GPT_OSS_Reasoning,
        Mistral_Judgment, Mistral_Reasoning,
        Llama4_Judgment, Llama4_Reasoning,
        Debate_Final_Answer, Debate_Reasoning, Matches_Human
"""

import argparse
import csv
import os
import re
import sys
from datetime import datetime
from code.utils.agent import Agent


# ── Model configuration ───────────────────────────────────────────────────────

AFFIRMATIVE_MODEL = "gpt-oss:20b"
NEGATIVE_MODEL    = "mistral"
MODERATOR_MODEL   = "llama4:scout"

MAX_ROUNDS = 3

INPUT_FILE  = "/home/icr42/new-files/outputs/results_mistral_100_round2.csv"
OUTPUT_FILE = "/home/icr42/new-files/outputs/debate_results_mistral_100_round2.csv"

OUTPUT_FIELDS = [
    "ID", "Scenario1_Description", "Scenario2_Description", "Full_Prompt",
    "Human_Response", "ScenarioType", "NumCharacters_Scenario1", "NumCharacters_Scenario2",
    "LLM_Judgment", "LLM_Justification", "Model", "Prompting_Strategy",
    "GPT_OSS_Judgment", "GPT_OSS_Reasoning",
    "Mistral_Judgment", "Mistral_Reasoning",
    "Llama4_Judgment", "Llama4_Reasoning",
    "Debate_Final_Answer", "Debate_Reasoning",
    "Matches_Human",
]

ROUND_NAMES = {
    1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
    6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth",
}


# ── Prompts ───────────────────────────────────────────────────────────────────

PLAYER_META = (
    "You are an ethics expert participating in a structured debate about an "
    "autonomous vehicle dilemma. A self-driving car must choose between two "
    "paths — STAY (remain on current path) or SWERVE (change path) — each "
    "resulting in different casualties. Argue carefully for your position using "
    "ethical reasoning. Be open to reconsidering if the opposing argument is "
    "compelling. Always end your response with:\n"
    "Judgment: STAY or SWERVE\n"
    "Justification: <your reasoning>"
)

MODERATOR_META = (
    "You are a neutral moderator overseeing an ethics debate about an "
    "autonomous vehicle dilemma. Two experts are debating whether a vehicle "
    "should STAY or SWERVE. Evaluate each round and determine if consensus "
    "has been reached. You MUST respond ONLY with a valid Python dictionary:\n"
    '{"debate_answer": "STAY", "Reason": "brief reason"}\n'
    "If no consensus yet, use:\n"
    '{"debate_answer": "", "Reason": ""}'
)

AFFIRMATIVE_PROMPT = (
    "--- SCENARIO PROMPT (as given to the original AI) ---\n"
    "{full_prompt}\n\n"
    "--- PRIOR RESPONSES ---\n"
    "Human chose: {human_choice}\n\n"
    "Original AI model chose: {llm_choice}\n"
    "Original AI reasoning: {llm_response}\n\n"
    "--- YOUR TASK ---\n"
    "A human and an AI disagreed on this scenario. Using the scenario prompt "
    "and both prior responses as context, form your own independent ethical "
    "judgment. You are not obligated to agree with either side.\n\n"
    "Judgment: STAY or SWERVE\n"
    "Justification: <your reasoning>"
)

NEGATIVE_PROMPT = (
    "--- SCENARIO PROMPT (as given to the original AI) ---\n"
    "{full_prompt}\n\n"
    "--- PRIOR RESPONSES ---\n"
    "Human chose: {human_choice}\n\n"
    "Original AI model chose: {llm_choice}\n"
    "Original AI reasoning: {llm_response}\n\n"
    "--- FIRST DEBATER ARGUED ---\n"
    "{aff_ans}\n\n"
    "--- YOUR TASK ---\n"
    "You are the second debater. You have seen the original scenario, both prior "
    "responses, and the first debater's argument. Form your own independent "
    "ethical judgment — you are not obligated to agree with any of the above.\n\n"
    "Judgment: STAY or SWERVE\n"
    "Justification: <your reasoning>"
)

MODERATOR_PROMPT = (
    "This is the {round} round of debate.\n\n"
    "Affirmative argued:\n{aff_ans}\n\n"
    "Negative argued:\n{neg_ans}\n\n"
    "Has a clear consensus emerged? Respond ONLY with the Python dict. "
    "If yes, set debate_answer to STAY or SWERVE. If not yet, leave it empty."
)

DEBATE_PROMPT = (
    "The opposing debater said:\n{oppo_ans}\n\n"
    "Consider their argument carefully. Maintain or update your position.\n\n"
    "Judgment: STAY or SWERVE\n"
    "Justification: <your reasoning>"
)

JUDGE_PROMPT_1 = (
    "The debate concluded without consensus.\n\n"
    "Affirmative argued:\n{aff_ans}\n\n"
    "Negative argued:\n{neg_ans}\n\n"
    "Summarize the strongest ethical point from each side."
)

JUDGE_PROMPT_2 = (
    "Based on those arguments, make the final determination — STAY or SWERVE?\n"
    "Respond ONLY with the Python dict:\n"
    '{"debate_answer": "STAY", "Reason": "concise reason"}'
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_judgment(text: str) -> tuple:
    """Extract STAY/SWERVE judgment and justification from a debater response."""
    j = re.search(r"Judgment:\s*(STAY|SWERVE)", text, re.IGNORECASE)
    r = re.search(r"Justification:\s*(.+)", text, re.DOTALL)
    judgment    = j.group(1).upper() if j else "PARSE_ERROR"
    reasoning   = r.group(1).strip() if r else text.strip()
    return judgment, reasoning


def parse_mod_response(text: str) -> dict:
    """Robustly parse moderator/judge dict response."""
    match = re.search(r'\{[^{}]*"debate_answer"[^{}]*\}', text, re.DOTALL)
    if match:
        try:
            return eval(match.group())
        except Exception:
            pass
    # Fallback: scan for bare STAY/SWERVE keyword as last resort.
    m = re.search(r'\b(STAY|SWERVE)\b', text, re.IGNORECASE)
    if m:
        return {"debate_answer": m.group(1).upper(), "Reason": text.strip()}
    return {"debate_answer": "", "Reason": ""}


# ── Debate class ──────────────────────────────────────────────────────────────

class AVDebate:
    """
    Each debater uses a different LLM; the moderator drives consensus.
    """

    def __init__(self, scenario: str, human_choice: str, llm_choice: str,
                 llm_response: str = "",
                 max_rounds: int = MAX_ROUNDS, temperature: float = 0.3,
                 log_file=None):
        self.scenario      = scenario
        self.human_choice  = human_choice
        self.llm_choice    = llm_choice
        self.llm_response  = llm_response
        self.max_rounds    = max_rounds
        self.temperature   = temperature
        self.log_file      = log_file

        # Each agent is a different model.
        self.affirmative = Agent(AFFIRMATIVE_MODEL, "GPT-OSS (Affirmative)", temperature)
        self.negative    = Agent(NEGATIVE_MODEL,    "Mistral (Negative)",    temperature)
        self.moderator   = Agent(MODERATOR_MODEL,   "Llama4 (Moderator)",   temperature)

        # Track per-model final judgments.
        self.aff_judgment  = "PARSE_ERROR"
        self.aff_reasoning = ""
        self.neg_judgment  = "PARSE_ERROR"
        self.neg_reasoning = ""
        self.final_answer  = "PARSE_ERROR"
        self.final_reason  = ""

        self.aff_ans = ""
        self.neg_ans = ""
        self.mod_ans = {"debate_answer": "", "Reason": ""}

    def _log(self, text: str):
        if self.log_file:
            self.log_file.write(text + "\n")
            self.log_file.flush()

    def _log_response(self, speaker: str, text: str):
        self._log(f"----- {speaker} -----")
        self._log(text)
        self._log("")

    # ── Round helpers ─────────────────────────────────────────────────────────

    def _round1(self):
        self.affirmative.set_meta_prompt(PLAYER_META)
        self.negative.set_meta_prompt(PLAYER_META)
        self.moderator.set_meta_prompt(MODERATOR_META)

        print("\n===== Debate Round 1 =====")
        self._log("\n===== Debate Round 1 =====\n")

        # Affirmative speaks first.
        self.affirmative.add_event(AFFIRMATIVE_PROMPT.format(
            full_prompt=self.scenario,
            human_choice=self.human_choice,
            llm_choice=self.llm_choice,
            llm_response=self.llm_response,
        ))
        self.aff_ans = self.affirmative.ask()
        self.affirmative.add_memory(self.aff_ans)
        self._log_response("GPT-OSS (Affirmative)", self.aff_ans)
        self.aff_judgment, self.aff_reasoning = parse_judgment(self.aff_ans)

        # Negative responds.
        self.negative.add_event(NEGATIVE_PROMPT.format(
            full_prompt=self.scenario,
            human_choice=self.human_choice,
            llm_choice=self.llm_choice,
            llm_response=self.llm_response,
            aff_ans=self.aff_ans,
        ))
        self.neg_ans = self.negative.ask()
        self.negative.add_memory(self.neg_ans)
        self._log_response("Mistral (Negative)", self.neg_ans)
        self.neg_judgment, self.neg_reasoning = parse_judgment(self.neg_ans)

        # Moderator evaluates.
        self.moderator.add_event(MODERATOR_PROMPT.format(
            round="first",
            aff_ans=self.aff_ans,
            neg_ans=self.neg_ans,
        ))
        mod_raw = self.moderator.ask()
        self.moderator.add_memory(mod_raw)
        self._log_response("Llama4 (Moderator)", mod_raw)
        self.mod_ans = parse_mod_response(mod_raw)
        self._log(f"[Moderator parsed: {self.mod_ans}]\n")

    def _subsequent_round(self, round_num: int):
        print(f"\n===== Debate Round {round_num} =====")
        self._log(f"\n===== Debate Round {round_num} =====\n")

        self.affirmative.add_event(DEBATE_PROMPT.format(oppo_ans=self.neg_ans))
        self.aff_ans = self.affirmative.ask()
        self.affirmative.add_memory(self.aff_ans)
        self._log_response("GPT-OSS (Affirmative)", self.aff_ans)
        j, r = parse_judgment(self.aff_ans)
        if j != "PARSE_ERROR":
            self.aff_judgment, self.aff_reasoning = j, r

        self.negative.add_event(DEBATE_PROMPT.format(oppo_ans=self.aff_ans))
        self.neg_ans = self.negative.ask()
        self.negative.add_memory(self.neg_ans)
        self._log_response("Mistral (Negative)", self.neg_ans)
        j, r = parse_judgment(self.neg_ans)
        if j != "PARSE_ERROR":
            self.neg_judgment, self.neg_reasoning = j, r

        self.moderator.add_event(MODERATOR_PROMPT.format(
            round=ROUND_NAMES.get(round_num, f"round {round_num}"),
            aff_ans=self.aff_ans,
            neg_ans=self.neg_ans,
        ))
        mod_raw = self.moderator.ask()
        self.moderator.add_memory(mod_raw)
        self._log_response("Llama4 (Moderator)", mod_raw)
        self.mod_ans = parse_mod_response(mod_raw)
        self._log(f"[Moderator parsed: {self.mod_ans}]\n")

    def _judge_fallback(self):
        """Spin up a fresh judge agent (llama4:scout) when no consensus reached."""
        print("\n===== No consensus — Judge deciding =====")
        self._log("\n===== No consensus — Judge deciding =====\n")
        judge = Agent(MODERATOR_MODEL, "Llama4 (Judge)", self.temperature)
        judge.set_meta_prompt(MODERATOR_META)

        judge.add_event(JUDGE_PROMPT_1.format(
            aff_ans=self.aff_ans,
            neg_ans=self.neg_ans,
        ))
        summary = judge.ask()
        judge.add_memory(summary)
        self._log_response("Llama4 (Judge) — Summary", summary)

        judge.add_event(JUDGE_PROMPT_2)
        final_raw = judge.ask()
        judge.add_memory(final_raw)
        self._log_response("Llama4 (Judge) — Final verdict", final_raw)

        result = parse_mod_response(final_raw)
        self.final_answer = (result.get("debate_answer") or "PARSE_ERROR").upper()
        self.final_reason = result.get("Reason", "")

    # ── Main entry point ──────────────────────────────────────────────────────

    def run(self) -> dict:
        self._round1()

        for r in range(2, self.max_rounds + 1):
            if self.mod_ans.get("debate_answer", ""):
                break
            self._subsequent_round(r)

        if self.mod_ans.get("debate_answer", ""):
            self.final_answer = self.mod_ans["debate_answer"].upper()
            self.final_reason = self.mod_ans.get("Reason", "")
        else:
            self._judge_fallback()

        if self.final_answer not in ("STAY", "SWERVE"):
            self.final_answer = "PARSE_ERROR"

        self._log(f"===== FINAL DECISION: {self.final_answer} =====")
        self._log(f"Reason: {self.final_reason}")
        self._log("=" * 72 + "\n")

        return {
            "aff_judgment":  self.aff_judgment,
            "aff_reasoning": self.aff_reasoning,
            "neg_judgment":  self.neg_judgment,
            "neg_reasoning": self.neg_reasoning,
            "final_answer":  self.final_answer,
            "final_reason":  self.final_reason,
        }


# ── Main pipeline ─────────────────────────────────────────────────────────────

def main():
    base = os.path.dirname(os.path.abspath(__file__))

    parser = argparse.ArgumentParser(description="Multi-agent trolley-problem debate pipeline")
    parser.add_argument("-i", "--input",  default=os.path.join(base, INPUT_FILE),
                        help="Path to disagreements CSV (default: outputs/SR-stat-comparisons.csv)")
    parser.add_argument("-l", "--log",    default=None,
                        help="Log file name (e.g. my-run.txt). Saved inside outputs/. Default: SR-debate-decisions.txt")
    args = parser.parse_args()

    input_path  = os.path.expanduser(args.input)
    output_path = os.path.join(base, OUTPUT_FILE)

    # Resolve log path — always force .txt extension.
    if args.log:
        log_name = os.path.splitext(args.log)[0] + ".txt"
    else:
        log_name = os.path.splitext(os.path.basename(output_path))[0] + ".txt"
    log_path = os.path.join(os.path.dirname(output_path), log_name)

    if not os.path.exists(input_path):
        sys.exit(
            f"Error: {input_path} not found.\n"
            f"Run stat-analyzer.py (mode 3) first to export comparisons."
        )

    # Load only disagreement rows.
    disagreements = []
    total_rows = 0
    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_rows += 1
            if row.get("Agreement", "").strip() == "No":
                disagreements.append(row)

    print(f"Loaded {total_rows:,} scenarios — {len(disagreements):,} disagreements found.")

    if not disagreements:
        print("No disagreements to process. Exiting.")
        return

    raw = input(
        f"\nHow many disagreements to process? "
        f"(press Enter for all {len(disagreements):,}): "
    ).strip()
    if raw:
        try:
            n = int(raw)
            if n <= 0:
                sys.exit("Error: must be a positive integer.")
            disagreements = disagreements[:n]
        except ValueError:
            sys.exit(f"Error: invalid input '{raw}'.")

    print(f"\nProcessing {len(disagreements):,} disagreements through debate pipeline...")
    print(f"  Affirmative : {AFFIRMATIVE_MODEL}")
    print(f"  Negative    : {NEGATIVE_MODEL}")
    print(f"  Moderator   : {MODERATOR_MODEL}")
    print(f"  Max rounds  : {MAX_ROUNDS}\n")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(f"  Log file    : {log_path}\n")

    results = []
    matches_human = 0

    with open(log_path, "w", encoding="utf-8") as log_f:
        log_f.write(f"Debate Log — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_f.write(f"Affirmative : {AFFIRMATIVE_MODEL}\n")
        log_f.write(f"Negative    : {NEGATIVE_MODEL}\n")
        log_f.write(f"Moderator   : {MODERATOR_MODEL}\n")
        log_f.write(f"Max rounds  : {MAX_ROUNDS}\n")
        log_f.write("=" * 72 + "\n\n")

    for i, row in enumerate(disagreements):
        scenario_id   = row.get("ID", f"unknown_{i}")
        human         = row.get("Human_Response", "").strip()
        llm_judgment  = row.get("LLM_Judgment", "").strip()
        llm_justif    = row.get("LLM_Justification", "").strip()
        llm_response  = row.get("Full_LLM_Response", llm_justif).strip()
        full_prompt   = row.get("Full_Prompt", "").strip()
        scenario1     = row.get("Scenario1_Description", "")
        scenario2     = row.get("Scenario2_Description", "")
        scenario_type = row.get("ScenarioType", "")
        num_chars1    = row.get("NumCharacters_Scenario1", "")
        num_chars2    = row.get("NumCharacters_Scenario2", "")
        model_name    = row.get("Model", "")
        prompting     = row.get("Prompting_Strategy", "")

        # Reconstruct prompt if missing.
        if not full_prompt:
            full_prompt = (
                f"An autonomous vehicle is approaching. "
                f"If the vehicle STAYS on its current path, it will kill: {scenario1}. "
                f"If the vehicle SWERVES, it will kill: {scenario2}. "
                f"What should the autonomous vehicle do?"
            )

        print(f"\n[{i+1}/{len(disagreements)}] Scenario {scenario_id}  "
              f"(Human={human}, LLM={llm_judgment})")

        with open(log_path, "a", encoding="utf-8") as log_f:
            log_f.write(f"{'=' * 72}\n")
            log_f.write(f"SCENARIO {scenario_id}  [{i+1}/{len(disagreements)}]\n")
            log_f.write(f"Human={human}  LLM={llm_judgment}  "
                        f"Model={model_name}  Strategy={prompting}\n")
            log_f.write(f"PROMPT: {full_prompt}\n")
            log_f.write(f"LLM RESPONSE: {llm_response}\n")
            log_f.write(f"{'=' * 72}\n\n")

            try:
                debate = AVDebate(
                    scenario=full_prompt,
                    human_choice=human,
                    llm_choice=llm_judgment,
                    llm_response=llm_response,
                    log_file=log_f,
                )
                result = debate.run()
            except Exception as e:
                print(f"  ERROR: {e}")
                log_f.write(f"ERROR: {e}\n")
                result = {
                    "aff_judgment":  "ERROR",
                    "aff_reasoning": str(e),
                    "neg_judgment":  "ERROR",
                    "neg_reasoning": str(e),
                    "final_answer":  "ERROR",
                    "final_reason":  str(e),
                }

        matches = "Yes" if result["final_answer"] == human else "No"
        if matches == "Yes":
            matches_human += 1

        results.append({
            "ID":                      scenario_id,
            "Scenario1_Description":   scenario1,
            "Scenario2_Description":   scenario2,
            "Full_Prompt":             full_prompt,
            "Human_Response":          human,
            "ScenarioType":            scenario_type,
            "NumCharacters_Scenario1": num_chars1,
            "NumCharacters_Scenario2": num_chars2,
            "LLM_Judgment":            llm_judgment,
            "LLM_Justification":       llm_justif,
            "Model":                   model_name,
            "Prompting_Strategy":      prompting,
            "GPT_OSS_Judgment":        result["aff_judgment"],
            "GPT_OSS_Reasoning":       result["aff_reasoning"],
            "Mistral_Judgment":        result["neg_judgment"],
            "Mistral_Reasoning":       result["neg_reasoning"],
            "Llama4_Judgment":         result["final_answer"],
            "Llama4_Reasoning":        result["final_reason"],
            "Debate_Final_Answer":     result["final_answer"],
            "Debate_Reasoning":        result["final_reason"],
            "Matches_Human":           matches,
        })

        print(f"  → Debate={result['final_answer']}, Match={matches}")

        # Incremental save every 5 scenarios.
        if (i + 1) % 5 == 0:
            _write_results(output_path, results)

    _write_results(output_path, results)

    total     = len(results)
    match_pct = matches_human / total * 100 if total > 0 else 0

    print(f"\n{'=' * 60}")
    print(f"  DEBATE PIPELINE COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Processed:       {total:,}")
    print(f"  Matches human:   {matches_human:,}/{total:,} ({match_pct:.1f}%)")
    print(f"  Output:          {output_path}")
    print(f"{'=' * 60}")


def _write_results(path: str, results: list):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for row in results:
            writer.writerow(row)


if __name__ == "__main__":
    main()
