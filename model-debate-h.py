import argparse
import ast
import csv
import os
import re
import sys
from datetime import datetime
from code.utils.agent import Agent


# ── Model configuration ───────────────────────────────────────────────────────

DEBATER1_MODEL  = "gpt-oss:20b"
DEBATER2_MODEL  = "mistral:latest"
DEBATER3_MODEL  = "glm4:latest"   # update as needed
DEBATER4_MODEL  = "gemma4:latest"
DEBATER5_MODEL  = "gemini-3.5-flash-lite"
MODERATOR_MODEL = "llama4:scout"

MAX_ROUNDS = 3

INPUT_FILE  = "/home/icr42/0824-LLM-nh-outputs/nh_alph_1v1_nh_200_results_glm4_200_round3.csv"
OUTPUT_FILE = "/home/icr42/0824-new-debate-output/LS_DEBATE_RES_nh_alph_1v1_results_glm4_200_round3.csv"

OUTPUT_FIELDS = [
    "ID", "Scenario1_Description", "Scenario2_Description", "Full_Prompt",
    "Human_Response", "ScenarioType", "NumCharacters_Scenario1", "NumCharacters_Scenario2",
    "LLM_Judgment", "LLM_Justification", "Model", "Prompting_Strategy",
    "Debater1_Judgment", "Debater1_Reasoning", "Debater1_EthicalFramework",
    "Debater2_Judgment", "Debater2_Reasoning", "Debater2_EthicalFramework",
    "Debater3_Judgment", "Debater3_Reasoning", "Debater3_EthicalFramework",
    "Debater4_Judgment", "Debater4_Reasoning", "Debater4_EthicalFramework",
    "Debater5_Judgment", "Debater5_Reasoning", "Debater5_EthicalFramework",
    "Debate_Final_Answer", "Debate_Reasoning",
    "Matches_Human",
]

ROUND_NAMES = {
    1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
    6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth",
}

VALID_FRAMEWORKS = {
    "utilitarianism", "deontology", "common sense morality",
    "justice", "virtue ethics",
}


# ── Prompts ───────────────────────────────────────────────────────────────────

PLAYER_META = (
    "You are an ethics expert participating in a structured debate about an "
    "autonomous vehicle dilemma. A self-driving car must choose between two "
    "paths — STAY (remain on current path) or SWERVE (change path) — each "
    "resulting in different casualties. Choose the ethical framework you find "
    "most applicable to this scenario and use it to guide your reasoning. "
    "Be open to reconsidering if opposing arguments are compelling. "
    "Always end your response with:\n"
    "Judgment: STAY or SWERVE\n"
    "Justification: <your reasoning>\n"
    "Ethical Framework: <Utilitarianism | Deontology | Common Sense Morality | Justice | Virtue Ethics>"
)

MODERATOR_META = (
    "You are a neutral moderator overseeing an ethics debate about an "
    "autonomous vehicle dilemma. Five experts are debating whether a vehicle "
    "should STAY or SWERVE. Evaluate each round and determine if consensus "
    "has been reached. You MUST respond ONLY with a valid Python dictionary:\n"
    '{"debate_answer": "STAY", "Reason": "brief reason"}\n'
    "If no consensus yet, use:\n"
    '{"debate_answer": "", "Reason": ""}'
)

DEBATER1_PROMPT = (
    "--- SCENARIO PROMPT (as given to the original AI) ---\n"
    "{full_prompt}\n\n"
    "--- PRIOR RESPONSES ---\n"
    "Human chose: {human_choice}\n\n"
    "Original AI model chose: {llm_choice}\n"
    "Original AI reasoning: {llm_response}\n\n"
    "--- YOUR TASK ---\n"
    "You are Debater 1. Using the scenario and prior responses as context, "
    "form your own independent ethical judgment. Select the ethical framework "
    "you find most applicable and use it to guide your reasoning.\n\n"
    "Judgment: STAY or SWERVE\n"
    "Justification: <your reasoning>\n"
    "Ethical Framework: <framework name>"
)

DEBATER2_PROMPT = (
    "--- SCENARIO PROMPT (as given to the original AI) ---\n"
    "{full_prompt}\n\n"
    "--- PRIOR RESPONSES ---\n"
    "Human chose: {human_choice}\n\n"
    "Original AI model chose: {llm_choice}\n"
    "Original AI reasoning: {llm_response}\n\n"
    "--- DEBATER 1 ARGUED ---\n"
    "{d1_ans}\n\n"
    "--- YOUR TASK ---\n"
    "You are Debater 2. You have seen the scenario, prior responses, and "
    "Debater 1's argument. Form your own independent ethical judgment.\n\n"
    "Judgment: STAY or SWERVE\n"
    "Justification: <your reasoning>\n"
    "Ethical Framework: <framework name>"
)

DEBATER3_PROMPT = (
    "--- SCENARIO PROMPT (as given to the original AI) ---\n"
    "{full_prompt}\n\n"
    "--- PRIOR RESPONSES ---\n"
    "Human chose: {human_choice}\n\n"
    "Original AI model chose: {llm_choice}\n"
    "Original AI reasoning: {llm_response}\n\n"
    "--- DEBATER 1 ARGUED ---\n"
    "{d1_ans}\n\n"
    "--- DEBATER 2 ARGUED ---\n"
    "{d2_ans}\n\n"
    "--- YOUR TASK ---\n"
    "You are Debater 3. You have seen all prior arguments above. "
    "Form your own independent ethical judgment.\n\n"
    "Judgment: STAY or SWERVE\n"
    "Justification: <your reasoning>\n"
    "Ethical Framework: <framework name>"
)

DEBATER4_PROMPT = (
    "--- SCENARIO PROMPT (as given to the original AI) ---\n"
    "{full_prompt}\n\n"
    "--- PRIOR RESPONSES ---\n"
    "Human chose: {human_choice}\n\n"
    "Original AI model chose: {llm_choice}\n"
    "Original AI reasoning: {llm_response}\n\n"
    "--- DEBATER 1 ARGUED ---\n"
    "{d1_ans}\n\n"
    "--- DEBATER 2 ARGUED ---\n"
    "{d2_ans}\n\n"
    "--- DEBATER 3 ARGUED ---\n"
    "{d3_ans}\n\n"
    "--- YOUR TASK ---\n"
    "You are Debater 4. You have seen all prior arguments above. "
    "Form your own independent ethical judgment.\n\n"
    "Judgment: STAY or SWERVE\n"
    "Justification: <your reasoning>\n"
    "Ethical Framework: <framework name>"
)

DEBATER5_PROMPT = (
    "--- SCENARIO PROMPT (as given to the original AI) ---\n"
    "{full_prompt}\n\n"
    "--- PRIOR RESPONSES ---\n"
    "Human chose: {human_choice}\n\n"
    "Original AI model chose: {llm_choice}\n"
    "Original AI reasoning: {llm_response}\n\n"
    "--- DEBATER 1 ARGUED ---\n"
    "{d1_ans}\n\n"
    "--- DEBATER 2 ARGUED ---\n"
    "{d2_ans}\n\n"
    "--- DEBATER 3 ARGUED ---\n"
    "{d3_ans}\n\n"
    "--- DEBATER 4 ARGUED ---\n"
    "{d4_ans}\n\n"
    "--- YOUR TASK ---\n"
    "You are Debater 5. You have seen all prior arguments above. "
    "Form your own independent ethical judgment.\n\n"
    "Judgment: STAY or SWERVE\n"
    "Justification: <your reasoning>\n"
    "Ethical Framework: <framework name>"
)

MODERATOR_PROMPT = (
    "This is the {round} round of debate.\n\n"
    "Debater 1 argued:\n{d1_ans}\n\n"
    "Debater 2 argued:\n{d2_ans}\n\n"
    "Debater 3 argued:\n{d3_ans}\n\n"
    "Debater 4 argued:\n{d4_ans}\n\n"
    "Debater 5 argued:\n{d5_ans}\n\n"
    "Has a clear consensus emerged? Respond ONLY with the Python dict. "
    "If yes, set debate_answer to STAY or SWERVE. If not yet, leave it empty."
)

# Each debater in subsequent rounds sees all other debaters' most recent arguments.
DEBATE_PROMPT_MULTI = (
    "The other debaters most recently argued:\n{other_ans}\n\n"
    "Consider their arguments carefully. Maintain or update your position.\n\n"
    "Judgment: STAY or SWERVE\n"
    "Justification: <your reasoning>\n"
    "Ethical Framework: <framework name>"
)

JUDGE_PROMPT_1 = (
    "The debate concluded without consensus.\n\n"
    "Debater 1 argued:\n{d1_ans}\n\n"
    "Debater 2 argued:\n{d2_ans}\n\n"
    "Debater 3 argued:\n{d3_ans}\n\n"
    "Debater 4 argued:\n{d4_ans}\n\n"
    "Debater 5 argued:\n{d5_ans}\n\n"
    "Summarize the strongest ethical point from each debater."
)

JUDGE_PROMPT_2 = (
    "Based on those arguments, make the final determination — STAY or SWERVE?\n"
    "Respond ONLY with the Python dict:\n"
    '{"debate_answer": "STAY", "Reason": "concise reason"}'
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_judgment(text: str) -> tuple:
    """Extract STAY/SWERVE judgment, justification, and ethical framework."""
    j  = re.search(r"Judgment:\s*(STAY|SWERVE)", text, re.IGNORECASE)
    r  = re.search(r"Justification:\s*(.+?)(?=\nEthical Framework:|$)", text, re.DOTALL | re.IGNORECASE)
    ef = re.search(r"Ethical Framework:\s*([^\n]+)", text, re.IGNORECASE)

    judgment   = j.group(1).upper()  if j  else "PARSE_ERROR"
    reasoning  = r.group(1).strip()  if r  else text.strip()

    raw_fw  = ef.group(1).strip().lower() if ef else ""
    framework = "UNRECOGNIZED"
    for valid in VALID_FRAMEWORKS:
        if valid in raw_fw:
            framework = valid.title()
            break

    return judgment, reasoning, framework


def parse_mod_response(text: str) -> dict:
    """Robustly parse moderator/judge dict response."""
    import ast as _ast

    # Strip markdown code fences if present
    cleaned = re.sub(r"```(?:python|json)?\s*", "", text).replace("```", "").strip()

    # Try increasingly loose extraction strategies
    for pattern in [
        r'\{[^{}]*"debate_answer"[^{}]*\}',   # strict: no nested braces
        r'\{.*?"debate_answer".*?\}',           # loose: allows nested content
    ]:
        match = re.search(pattern, cleaned, re.DOTALL)
        if match:
            candidate = match.group()
            for loader in (_ast.literal_eval, eval):
                try:
                    result = loader(candidate)
                    if isinstance(result, dict) and "debate_answer" in result:
                        return result
                except Exception:
                    pass

    # Last resort: scan for a bare STAY/SWERVE keyword
    m = re.search(r'\b(STAY|SWERVE)\b', cleaned, re.IGNORECASE)
    if m:
        return {"debate_answer": m.group(1).upper(), "Reason": cleaned}
    return {"debate_answer": "", "Reason": ""}


# ── Debate class ──────────────────────────────────────────────────────────────

class AVDebate:
    """
    Five-debater multi-agent debate. Each debater uses a different LLM and
    selects its own ethical framework to guide its reasoning. The moderator
    drives consensus; a judge resolves deadlocks without imposing a framework.
    """

    def __init__(self, scenario: str, human_choice: str, llm_choice: str,
                 llm_response: str = "",
                 max_rounds: int = MAX_ROUNDS, temperature: float = 0.3,
                 log_file=None):
        self.scenario     = scenario
        self.human_choice = human_choice
        self.llm_choice   = llm_choice
        self.llm_response = llm_response
        self.max_rounds   = max_rounds
        self.temperature  = temperature
        self.log_file     = log_file

        self.debaters = [
            Agent(DEBATER1_MODEL,  "Debater 1", temperature),
            Agent(DEBATER2_MODEL,  "Debater 2", temperature),
            Agent(DEBATER3_MODEL,  "Debater 3", temperature),
            Agent(DEBATER4_MODEL,  "Debater 4", temperature),
            Agent(DEBATER5_MODEL,  "Debater 5", temperature),
        ]
        self.moderator = Agent(MODERATOR_MODEL, "Moderator", temperature)

        self.judgments    = ["PARSE_ERROR"] * 5
        self.reasonings   = [""] * 5
        self.frameworks   = ["UNRECOGNIZED"] * 5
        self.last_answers = [""] * 5

        self.final_answer = "PARSE_ERROR"
        self.final_reason = ""
        self.mod_ans      = {"debate_answer": "", "Reason": ""}
        self.used_judge   = False

    def _log(self, text: str):
        if self.log_file:
            self.log_file.write(text + "\n")
            self.log_file.flush()

    def _log_response(self, speaker: str, text: str):
        self._log(f"----- {speaker} -----")
        self._log(text)
        self._log("")

    def _run_moderator(self, round_num: int):
        self.moderator.add_event(MODERATOR_PROMPT.format(
            round=ROUND_NAMES.get(round_num, f"round {round_num}"),
            d1_ans=self.last_answers[0],
            d2_ans=self.last_answers[1],
            d3_ans=self.last_answers[2],
            d4_ans=self.last_answers[3],
            d5_ans=self.last_answers[4],
        ))
        mod_raw = self.moderator.ask()
        self.moderator.add_memory(mod_raw)
        self._log_response("Moderator", mod_raw)
        self.mod_ans = parse_mod_response(mod_raw)
        self._log(f"[Moderator parsed: {self.mod_ans}]\n")

        # Retry once if the response could not be parsed
        if not self.mod_ans.get("debate_answer", ""):
            self._log("[Moderator parse failed — retrying with simplified prompt]\n")
            self.moderator.add_event(
                'Your previous response could not be parsed. '
                'Reply ONLY with one of these two dicts and nothing else:\n'
                '{"debate_answer": "STAY", "Reason": "<brief reason>"}\n'
                '{"debate_answer": "", "Reason": ""}'
            )
            retry_raw = self.moderator.ask()
            self.moderator.add_memory(retry_raw)
            self._log_response("Moderator (retry)", retry_raw)
            self.mod_ans = parse_mod_response(retry_raw)
            self._log(f"[Moderator retry parsed: {self.mod_ans}]\n")

    # ── Round helpers ─────────────────────────────────────────────────────────

    def _round1(self):
        for d in self.debaters:
            d.set_meta_prompt(PLAYER_META)
        self.moderator.set_meta_prompt(MODERATOR_META)

        print("\n===== Debate Round 1 =====")
        self._log("\n===== Debate Round 1 =====\n")

        ctx = dict(
            full_prompt=self.scenario,
            human_choice=self.human_choice,
            llm_choice=self.llm_choice,
            llm_response=self.llm_response,
        )

        prompts_r1 = [
            DEBATER1_PROMPT.format(**ctx),
            DEBATER2_PROMPT.format(**ctx, d1_ans="{d1_ans}"),
            DEBATER3_PROMPT.format(**ctx, d1_ans="{d1_ans}", d2_ans="{d2_ans}"),
            DEBATER4_PROMPT.format(**ctx, d1_ans="{d1_ans}", d2_ans="{d2_ans}", d3_ans="{d3_ans}"),
            DEBATER5_PROMPT.format(**ctx, d1_ans="{d1_ans}", d2_ans="{d2_ans}", d3_ans="{d3_ans}", d4_ans="{d4_ans}"),
        ]

        for i, debater in enumerate(self.debaters):
            filled = prompts_r1[i].format(
                d1_ans=self.last_answers[0],
                d2_ans=self.last_answers[1],
                d3_ans=self.last_answers[2],
                d4_ans=self.last_answers[3],
            )
            debater.add_event(filled)
            ans = debater.ask()
            debater.add_memory(ans)
            self.last_answers[i] = ans
            self._log_response(f"Debater {i+1}", ans)
            j, r, f = parse_judgment(ans)
            self.judgments[i], self.reasonings[i], self.frameworks[i] = j, r, f

        self._run_moderator(1)

    def _subsequent_round(self, round_num: int):
        print(f"\n===== Debate Round {round_num} =====")
        self._log(f"\n===== Debate Round {round_num} =====\n")

        new_answers = []
        for i, debater in enumerate(self.debaters):
            others = "\n\n".join(
                f"Debater {j+1} argued:\n{self.last_answers[j]}"
                for j in range(5) if j != i
            )
            debater.add_event(DEBATE_PROMPT_MULTI.format(other_ans=others))
            ans = debater.ask()
            debater.add_memory(ans)
            new_answers.append(ans)
            self._log_response(f"Debater {i+1}", ans)
            j, r, f = parse_judgment(ans)
            if j != "PARSE_ERROR":
                self.judgments[i], self.reasonings[i], self.frameworks[i] = j, r, f

        self.last_answers = new_answers
        self._run_moderator(round_num)

    def _judge_fallback(self):
        """Fresh judge agent resolves deadlock — does not select an ethical framework."""
        self.used_judge = True
        print("\n===== No consensus — Judge deciding =====")
        self._log("\n===== No consensus — Judge deciding =====\n")
        judge = Agent(MODERATOR_MODEL, "Judge", self.temperature)
        judge.set_meta_prompt(MODERATOR_META)

        judge.add_event(JUDGE_PROMPT_1.format(
            d1_ans=self.last_answers[0],
            d2_ans=self.last_answers[1],
            d3_ans=self.last_answers[2],
            d4_ans=self.last_answers[3],
            d5_ans=self.last_answers[4],
        ))
        summary = judge.ask()
        judge.add_memory(summary)
        self._log_response("Judge — Summary", summary)

        judge.add_event(JUDGE_PROMPT_2)
        final_raw = judge.ask()
        judge.add_memory(final_raw)
        self._log_response("Judge — Final verdict", final_raw)

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
            "d1_judgment":  self.judgments[0],  "d1_reasoning":  self.reasonings[0],  "d1_framework":  self.frameworks[0],
            "d2_judgment":  self.judgments[1],  "d2_reasoning":  self.reasonings[1],  "d2_framework":  self.frameworks[1],
            "d3_judgment":  self.judgments[2],  "d3_reasoning":  self.reasonings[2],  "d3_framework":  self.frameworks[2],
            "d4_judgment":  self.judgments[3],  "d4_reasoning":  self.reasonings[3],  "d4_framework":  self.frameworks[3],
            "d5_judgment":  self.judgments[4],  "d5_reasoning":  self.reasonings[4],  "d5_framework":  self.frameworks[4],
            "final_answer": self.final_answer,
            "final_reason": self.final_reason,
            "used_judge":   self.used_judge,
        }


# ── Main pipeline ─────────────────────────────────────────────────────────────

def main():
    base = os.path.dirname(os.path.abspath(__file__))

    parser = argparse.ArgumentParser(description="5-debater ethical-framework debate pipeline")
    parser.add_argument("-i", "--input",     default=os.path.join(base, INPUT_FILE))
    parser.add_argument("-l", "--log",       default=None)
    parser.add_argument("-n", "--scenarios", type=int, default=None,
                        help="Number of disagreements to process (default: all)")
    parser.add_argument("-r", "--range", dest="scenario_range", default=None,
                        help="Inclusive range to process, e.g. 1-15 or 16-30 (1-indexed)")
    args = parser.parse_args()

    input_path = os.path.expanduser(args.input)

    if not os.path.exists(input_path):
        sys.exit(f"Error: {input_path} not found.")

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

    range_label = "all"
    if args.scenario_range is not None:
        try:
            start_str, end_str = args.scenario_range.split("-")
            start, end = int(start_str), int(end_str)
            if start < 1 or end < start:
                sys.exit("Error: range must be in the form START-END where START >= 1 and END >= START.")
            disagreements = disagreements[start - 1:end]
            range_label = f"{start}-{end}"
            print(f"Processing range {start}–{end} ({len(disagreements):,} scenarios).")
        except ValueError:
            sys.exit("Error: --range must be in the form START-END, e.g. 16-30.")
    elif args.scenarios is not None:
        if args.scenarios <= 0:
            sys.exit("Error: -n must be a positive integer.")
        disagreements = disagreements[:args.scenarios]
        range_label = f"1-{args.scenarios}"

    # Build output and log paths now that range_label is known
    base_output = os.path.join(base, OUTPUT_FILE)
    stem, ext = os.path.splitext(base_output)
    output_path = f"{stem}_{range_label}{ext}"

    if args.log:
        log_name = os.path.splitext(args.log)[0] + ".txt"
    else:
        log_name = os.path.splitext(os.path.basename(output_path))[0] + ".txt"
    log_path = os.path.join(os.path.dirname(output_path), log_name)

    print(f"\nProcessing {len(disagreements):,} disagreements through debate pipeline...")
    print(f"  Debater 1   : {DEBATER1_MODEL}")
    print(f"  Debater 2   : {DEBATER2_MODEL}")
    print(f"  Debater 3   : {DEBATER3_MODEL}")
    print(f"  Debater 4   : {DEBATER4_MODEL}")
    print(f"  Debater 5   : {DEBATER5_MODEL}")
    print(f"  Moderator   : {MODERATOR_MODEL}")
    print(f"  Max rounds  : {MAX_ROUNDS}\n")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    print(f"  Log file    : {log_path}\n")

    results            = []
    matches_human      = 0
    judge_invoked      = 0
    judge_parse_errors = 0

    with open(log_path, "w", encoding="utf-8") as log_f:
        log_f.write(f"Debate Log — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_f.write(f"Debater 1   : {DEBATER1_MODEL}\n")
        log_f.write(f"Debater 2   : {DEBATER2_MODEL}\n")
        log_f.write(f"Debater 3   : {DEBATER3_MODEL}\n")
        log_f.write(f"Debater 4   : {DEBATER4_MODEL}\n")
        log_f.write(f"Debater 5   : {DEBATER5_MODEL}\n")
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
                    "d1_judgment": "ERROR", "d1_reasoning": str(e), "d1_framework": "N/A",
                    "d2_judgment": "ERROR", "d2_reasoning": str(e), "d2_framework": "N/A",
                    "d3_judgment": "ERROR", "d3_reasoning": str(e), "d3_framework": "N/A",
                    "d4_judgment": "ERROR", "d4_reasoning": str(e), "d4_framework": "N/A",
                    "d5_judgment": "ERROR", "d5_reasoning": str(e), "d5_framework": "N/A",
                    "final_answer": "ERROR", "final_reason": str(e),
                }

        matches = "Yes" if result["final_answer"] == human else "No"
        if matches == "Yes":
            matches_human += 1
        if result.get("used_judge"):
            judge_invoked += 1
            if result["final_answer"] not in ("STAY", "SWERVE"):
                judge_parse_errors += 1

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
            "Debater1_Judgment":           result["d1_judgment"],
            "Debater1_Reasoning":          result["d1_reasoning"],
            "Debater1_EthicalFramework":   result["d1_framework"],
            "Debater2_Judgment":           result["d2_judgment"],
            "Debater2_Reasoning":          result["d2_reasoning"],
            "Debater2_EthicalFramework":   result["d2_framework"],
            "Debater3_Judgment":           result["d3_judgment"],
            "Debater3_Reasoning":          result["d3_reasoning"],
            "Debater3_EthicalFramework":   result["d3_framework"],
            "Debater4_Judgment":           result["d4_judgment"],
            "Debater4_Reasoning":          result["d4_reasoning"],
            "Debater4_EthicalFramework":   result["d4_framework"],
            "Debater5_Judgment":           result["d5_judgment"],
            "Debater5_Reasoning":          result["d5_reasoning"],
            "Debater5_EthicalFramework":   result["d5_framework"],
            "Debate_Final_Answer":     result["final_answer"],
            "Debate_Reasoning":        result["final_reason"],
            "Matches_Human":           matches,
        })

        print(f"  → Debate={result['final_answer']}, Match={matches}")
        print(f"    Frameworks: D1={result['d1_framework']}, D2={result['d2_framework']}, "
              f"D3={result['d3_framework']}, D4={result['d4_framework']}, D5={result['d5_framework']}")

        if (i + 1) % 5 == 0:
            _write_results(output_path, results)

    _write_results(output_path, results)

    total     = len(results)
    match_pct = matches_human / total * 100 if total > 0 else 0

    judge_fail_pct = judge_parse_errors / judge_invoked * 100 if judge_invoked > 0 else 0

    print(f"\n{'=' * 60}")
    print(f"  DEBATE PIPELINE COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Processed:           {total:,}")
    print(f"  Matches human:       {matches_human:,}/{total:,} ({match_pct:.1f}%)")
    print(f"  Judge invoked:       {judge_invoked:,}/{total:,}")
    print(f"  Judge parse errors:  {judge_parse_errors:,}/{judge_invoked:,} ({judge_fail_pct:.1f}%)")
    print(f"  Output:              {output_path}")
    print(f"{'=' * 60}")


def _write_results(path: str, results: list):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        for row in results:
            writer.writerow(row)


if __name__ == "__main__":
    main()
