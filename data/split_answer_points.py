"""
split_answer_points.py
======================
Reads a dataset file (JSONL or JSON array), calls OpenAI GPT-4.1-mini to
decompose each record's `expected_answer` into a list of atomic answer
points, and saves the result as a new JSON file with an added
`answer_points` column.

Supported input formats
-----------------------
  JSON array  →  [ {...}, {...}, ... ]          (file starts with "[")
  JSONL       →  one JSON object per line       (any other format)

The format is detected automatically.

Usage
-----
    pip install openai
    export OPENAI_API_KEY="sk-..."

    # Basic
    python split_answer_points.py --input dataset.jsonl --output out.json

    # With explicit API key and slower rate
    python split_answer_points.py \\
        --input  dataset.jsonl \\
        --output out.json \\
        --api-key sk-... \\
        --delay 1.0

    # Resume an interrupted run (skips records that already have answer_points)
    python split_answer_points.py \\
        --input  dataset.jsonl \\
        --output out.json \\
        --resume
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI

# ── Prompts ────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are an expert in educational assessment and NLP dataset construction.
Your task is to decompose a model answer into a list of independent, atomic answer points \
where each point captures exactly one distinct fact, claim, or reasoning step that addresses \
part of the question.

## Core principles

1. ATOMIC: Each point must be self-contained and meaningful on its own, without requiring \
other points to be understood.

2. NON-REDUNDANT: No two points should express the same idea, even in different words. \
Overlap is a defect.

3. FAITHFUL: Do not invent, infer, or embellish. Every point must be directly grounded in \
the provided answer text. Do not add external knowledge.

4. QUESTION-RELEVANT: Each point must answer something the question actually asks. Discard \
background context or asides that are not responsive to the question.

5. GRANULAR: Split compound sentences. If one sentence contains two separable claims \
(e.g. a conclusion AND the legal test applied), produce two points.

6. NEUTRAL PHRASING: Write each point as a clear declarative statement. Strip markdown \
formatting (*italics*, **bold**) from the output text. Preserve technical and legal \
terminology exactly.

## Output format

Return ONLY a valid JSON object in this exact structure — no preamble, no explanation, \
no markdown fences:

{
  "answer_points": [
    "Point 1.",
    "Point 2.",
    "Point 3."
  ]
}

## Quality checks before outputting

- Does each point make sense when read in isolation? If not, rewrite or merge.
- Is every point traceable to a specific sentence in the source answer? If not, remove it.
- Do any two points say essentially the same thing? If so, merge them.
- Does every point answer something the question asks? If not, remove it.\
"""

USER_PROMPT_TEMPLATE = """\
## Question
{question}

## Model answer
{expected_answer}

---

Decompose the model answer above into atomic answer points following the system instructions. \
Each point must directly address something the question asks.\
"""


# ── File I/O ───────────────────────────────────────────────────────────────────

def detect_format(text: str) -> str:
    """Return 'json_array' or 'jsonl'."""
    return "json_array" if text.lstrip().startswith("[") else "jsonl"


def load_dataset(path: str) -> list:
    """
    Load a dataset from a JSON array file or a JSONL file.
    Returns a list of dicts.
    """
    text = Path(path).read_text(encoding="utf-8")
    fmt = detect_format(text)

    if fmt == "json_array":
        records = json.loads(text)
        if not isinstance(records, list):
            raise ValueError("JSON file does not contain a top-level array.")
        return records

    # JSONL: parse line by line, skip blanks
    records = []
    errors  = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            errors.append(f"  Line {lineno}: {exc}")

    if errors:
        print(f"WARNING: {len(errors)} line(s) could not be parsed:")
        print("\n".join(errors))

    return records


def save_dataset(records: list, path: str) -> None:
    """Save records to a JSON array file (pretty-printed, UTF-8)."""
    Path(path).write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── OpenAI call ────────────────────────────────────────────────────────────────

def call_openai(client: OpenAI, question: str, expected_answer: str,
                retries: int = 3) -> list:
    """
    Call GPT-4.1-mini with the system + user prompt and return answer_points.
    Retries up to `retries` times with exponential back-off on failure.
    """
    user_msg = USER_PROMPT_TEMPLATE.format(
        question=question,
        expected_answer=expected_answer,
    )

    for attempt in range(1, retries + 1):
        try:
            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                temperature=0,
                max_tokens=1024,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": user_msg},
                ],
            )
            raw    = response.choices[0].message.content
            parsed = json.loads(raw)
            points = parsed.get("answer_points", [])

            if not isinstance(points, list):
                raise ValueError(f"'answer_points' is not a list — got: {type(points)}")
            if len(points) == 0:
                raise ValueError("'answer_points' is an empty list.")

            return points

        except Exception as exc:
            wait = 2 ** attempt
            print(f"  [attempt {attempt}/{retries}] {exc}")
            if attempt < retries:
                print(f"  Retrying in {wait}s ...")
                time.sleep(wait)
            else:
                raise


# ── Main ───────────────────────────────────────────────────────────────────────

# ── Cấu hình trực tiếp tại đây ──────────────────────────────────────────────
INPUT_FILE  = "/Users/dat/Documents/Ai-in-action/Lab14-AI-Evaluation-Benchmarking-main/data/golden_set.jsonl"          # File đầu vào
OUTPUT_FILE = "/Users/dat/Documents/Ai-in-action/Lab14-AI-Evaluation-Benchmarking-main/data/golden_dataset.json"         # File đầu ra
API_KEY     = os.getenv("API_KEY")                 # Nếu để None, code sẽ tự lấy từ biến môi trường OPENAI_API_KEY
DELAY       = 0.1                   # Giây chờ giữa các lần gọi API
RESUME      = True                  # Bật/tắt chế độ chạy tiếp (skip bản ghi đã có)

def main() -> None:
    # ── API key ──────────────────────────────────────────────────────────────
    api_key = API_KEY or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit(
            "ERROR: OpenAI API key not found.\n"
            "Vui lòng điền API_KEY trong code hoặc thiết lập biến môi trường OPENAI_API_KEY."
        )
    client = OpenAI(api_key=api_key)

    # ── Load input ────────────────────────────────────────────────────────────
    if not Path(INPUT_FILE).exists():
        sys.exit(f"ERROR: Input file not found: {INPUT_FILE}")

    print(f"\nInput  : {INPUT_FILE}")
    records = load_dataset(INPUT_FILE)
    
    # Giả định detect_format và load_dataset đã được định nghĩa ở trên
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        fmt = detect_format(f.read())
        
    print(f"Format : {fmt}")
    print(f"Records: {len(records)}\n")

    # ── Resume mode ───────────────────────────────────────────────────────────
    done_ids = set()
    if RESUME and Path(OUTPUT_FILE).exists():
        try:
            existing     = load_dataset(OUTPUT_FILE)
            existing_map = {r["id"]: r for r in existing if "id" in r}
            done_ids     = {
                rid for rid, r in existing_map.items()
                if r.get("answer_points") is not None
            }
            # Gộp các điểm đã tính vào danh sách hiện tại
            for rec in records:
                rid = rec.get("id")
                if rid in existing_map:
                    rec["answer_points"] = existing_map[rid].get("answer_points")
            print(f"Resume : {len(done_ids)} record(s) already processed — skipping.\n")
        except Exception as exc:
            print(f"WARNING: Could not load existing output for resume: {exc}\n")

    # ── Process ───────────────────────────────────────────────────────────────
    total, success, skipped, errors = len(records), 0, 0, 0

    for idx, rec in enumerate(records, start=1):
        rec_id  = rec.get("id", f"index-{idx}")
        q       = (rec.get("question")        or "").strip()
        ans     = (rec.get("expected_answer") or "").strip()

        # Bỏ qua nếu đã xong (Resume)
        if rec_id in done_ids:
            print(f"[{idx:>4}/{total}] SKIP     {rec_id}")
            skipped += 1
            continue

        # Bỏ qua nếu thiếu dữ liệu
        if not q or not ans:
            missing = []
            if not q:   missing.append("question")
            if not ans: missing.append("expected_answer")
            print(f"[{idx:>4}/{total}] SKIP     {rec_id}  (missing: {', '.join(missing)})")
            rec["answer_points"] = None
            skipped += 1
            continue

        # Gọi API
        print(f"[{idx:>4}/{total}] Process  {rec_id} ...", end=" ", flush=True)
        try:
            points = call_openai(client, q, ans)
            rec["answer_points"] = points
            print(f"→ {len(points)} points")
            success += 1
        except Exception as exc:
            print(f"→ FAILED ({exc})")
            rec["answer_points"] = None
            errors += 1

        # Lưu checkpoint ngay lập tức (an toàn khi crash)
        save_dataset(records, OUTPUT_FILE)

        if idx < total:
            time.sleep(DELAY)

    # ── Summary ───────────────────────────────────────────────────────────────
    print()
    print("=" * 56)
    print(f"  Total    : {total}")
    print(f"  Success  : {success}")
    print(f"  Skipped  : {skipped}")
    print(f"  Failed   : {errors}")
    print(f"  Output   : {OUTPUT_FILE}")
    print("=" * 56)

if __name__ == "__main__":
    main()