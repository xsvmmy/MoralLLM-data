"""downsample_to_200.py

Downsample the 500-scenario nh (no human response) result CSVs to 200
scenarios per round, keeping validity and agreement rates proportional to
the original 500-scenario run.

For each CSV in SOURCE_DIR, rows are split into three pools based on the
`Agreement` column:
    agree    -> Agreement == 'Yes'
    disagree -> Agreement == 'No'
    invalid  -> Agreement == 'N/A'  (LLM_Judgment == PARSE_ERROR)

Target counts for each pool at TARGET_N are computed with largest-remainder
apportionment on (pool_size * TARGET_N / total_rows), which keeps the valid
count and agreement % within rounding distance of their 500-scenario values
(e.g. 214/500 agree -> 86/200, 340/500 valid -> 136/200). Rows are then
randomly sampled from each pool (seeded for reproducibility) and written to
a new CSV, and a matching accuracy log is produced with per-round stats
recomputed from the actual sample (valid responses, agreement %, ethical
framework breakdown), reusing the original entry's timestamp, prompting
strategy, and condition text.
"""

import csv
import math
import os
import random
import re
from collections import Counter

SOURCE_DIR = "0818-1v1-nh-500-LLM-results"
TARGET_DIR = "0824-1v1-nh-200-LLM-results"
TARGET_N = 200
SEED = 42

# Each family is a separate group of 500-scenario CSVs + its own accuracy
# log, using its own filename pattern. Every family gets a fresh rng seeded
# with SEED so adding a new family never changes the sampling of files
# already produced for an earlier family.
FAMILIES = [
    {
        "log_filename": "nh-alph-1v1-ALL-n25-accuracy-log.txt",
        "filename_re": re.compile(
            r"^nh_alph_1v1_ALL_n25_results_(?P<model>.+)_500_round(?P<round>\d+)\.csv$"
        ),
    },
    {
        "log_filename": "nh-gemini-1v1-ALL-n25-accuracy-log.txt",
        "filename_re": re.compile(
            r"^nh_gemini_1v1_ALL_n25_results_500_round(?P<round>\d+)\.csv$"
        ),
        "fixed_model": "gemini",
    },
]

LOG_ENTRY_RE = re.compile(
    r"Timestamp:\s*(?P<timestamp>.+)\n"
    r"Model:\s*(?P<model>.+)\n"
    r"Prompting Strategy:\s*(?P<prompting_strategy>.+)\n"
    r"Condition:\s*(?P<condition>.+)\n"
    r"Round:\s*(?P<round>\d+)\n"
    r"Valid Responses:\s*(?P<valid>\d+)/(?P<total>\d+)\n"
    r"Agreement with Humans:\s*(?P<agreement>[\d.]+)%"
)


def parse_log(log_path):
    """Return {(model, round): {timestamp, prompting_strategy, condition}}."""
    with open(log_path, encoding="utf-8") as f:
        text = f.read()

    entries = {}
    for match in LOG_ENTRY_RE.finditer(text):
        model = match.group("model").strip()
        round_num = int(match.group("round"))
        entries[(model, round_num)] = {
            "timestamp": match.group("timestamp").strip(),
            "prompting_strategy": match.group("prompting_strategy").strip(),
            "condition": match.group("condition").strip(),
        }
    return entries


def apportion(pool_sizes, target_n):
    """Largest-remainder apportionment of target_n across pools, capped at
    each pool's size. pool_sizes: dict[name] -> size. Returns dict[name] -> target count."""
    total = sum(pool_sizes.values())
    scale = target_n / total if total else 0
    fractions = {k: v * scale for k, v in pool_sizes.items()}
    targets = {k: math.floor(v) for k, v in fractions.items()}
    remainder = target_n - sum(targets.values())

    order = sorted(pool_sizes.keys(), key=lambda k: fractions[k] - targets[k], reverse=True)
    i = 0
    while remainder > 0 and any(targets[k] < pool_sizes[k] for k in order):
        k = order[i % len(order)]
        if targets[k] < pool_sizes[k]:
            targets[k] += 1
            remainder -= 1
        i += 1

    return targets


def downsample_file(csv_path, rng, target_n=TARGET_N):
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    pools = {
        "agree": [r for r in rows if r["Agreement"] == "Yes"],
        "disagree": [r for r in rows if r["Agreement"] == "No"],
        "invalid": [r for r in rows if r["Agreement"] not in ("Yes", "No")],
    }
    pool_sizes = {k: len(v) for k, v in pools.items()}
    targets = apportion(pool_sizes, target_n)

    sampled = []
    for name, pool in pools.items():
        sampled.extend(rng.sample(pool, targets[name]))
    rng.shuffle(sampled)

    valid_count = targets["agree"] + targets["disagree"]
    agreement_pct = (targets["agree"] / valid_count * 100) if valid_count else 0.0
    framework_counts = Counter(
        r["EthicalFramework"] for r in sampled if r["Agreement"] in ("Yes", "No")
    )

    stats = {
        "valid": valid_count,
        "total": len(sampled),
        "agree_count": targets["agree"],
        "agreement_pct": agreement_pct,
        "frameworks": framework_counts,
    }
    return fieldnames, sampled, stats


def format_log_entry(model, round_num, log_meta, stats):
    lines = [
        "=" * 70,
        f"Timestamp: {log_meta['timestamp']}",
        f"Model: {model}",
        f"Prompting Strategy: {log_meta['prompting_strategy']}",
        f"Condition: {log_meta['condition']}",
        f"Round: {round_num}",
        f"Valid Responses: {stats['valid']}/{stats['total']}",
        f"Agreement with Humans: {stats['agree_count']}/{stats['valid']} ({stats['agreement_pct']:.2f}%)",
        "Ethical Framework Selection (valid responses only):",
    ]
    for framework, count in stats["frameworks"].most_common():
        lines.append(f"    {framework}: {count}")
    lines.append("=" * 70)
    lines.append("")
    return "\n".join(lines)


def process_family(family, source_dir, target_dir):
    log_path = os.path.join(source_dir, family["log_filename"])
    log_entries = parse_log(log_path)

    rng = random.Random(SEED)
    log_output_chunks = []

    csv_files = sorted(f for f in os.listdir(source_dir) if f.endswith(".csv"))

    processed = set()
    for filename in csv_files:
        match = family["filename_re"].match(filename)
        if not match:
            continue

        model = match.groupdict().get("model") or family.get("fixed_model")
        round_num = int(match.group("round"))
        key = (model, round_num)

        log_meta = log_entries.get(key)
        if log_meta is None:
            print(f"Warning: no log entry found for model={model} round={round_num}, skipping {filename}")
            continue

        csv_path = os.path.join(source_dir, filename)
        fieldnames, sampled_rows, stats = downsample_file(csv_path, rng)

        out_filename = filename.replace("_500_", "_200_")
        out_path = os.path.join(target_dir, out_filename)
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(sampled_rows)

        log_output_chunks.append((key, format_log_entry(model, round_num, log_meta, stats)))
        processed.add(key)
        print(
            f"{filename} -> {out_filename}: "
            f"valid {stats['valid']}/{stats['total']}, "
            f"agreement {stats['agreement_pct']:.2f}%"
        )

    if not processed:
        print(f"No files matched for {family['log_filename']}, skipping log output.")
        return 0

    # Preserve the original log's ordering for entries we processed.
    ordered_keys = [k for k in log_entries.keys() if k in processed]
    chunk_by_key = dict(log_output_chunks)
    log_text = "\n".join(chunk_by_key[k] for k in ordered_keys) + "\n"

    out_log_path = os.path.join(target_dir, family["log_filename"])
    with open(out_log_path, "w", encoding="utf-8") as f:
        f.write(log_text)

    return len(processed)


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    source_dir = os.path.join(script_dir, SOURCE_DIR)
    target_dir = os.path.join(script_dir, TARGET_DIR)
    os.makedirs(target_dir, exist_ok=True)

    total_processed = 0
    for family in FAMILIES:
        total_processed += process_family(family, source_dir, target_dir)

    print(f"\nWrote {total_processed} CSVs and log(s) to: {target_dir}")


if __name__ == "__main__":
    main()
