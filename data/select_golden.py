"""
Selects 50 questions from qa.csv + enriches with corpus.csv context.

Selection strategy (stratified):
  - Cover all 13 chapters (min 3 per chapter)
  - Two tiers per chapter:
      Tier-A (corpus-only): requires_supplemental=False  → answerable from corpus text alone
      Tier-B (supplemental): requires_supplemental=True  → needs external case law (harder)
  - Within each tier, prefer:
      1. New sections not yet covered
      2. Diverse question types (case_reading / explanatory / yes_no_application / factual)
      3. Mix of short vs long answers within tier
  - Global target: ~55 % Tier-A, ~18 % hard (supplemental+long), remainder medium-supplemental

Output: data/golden_set.jsonl
"""

import json
import re
import pandas as pd

# ── helpers ──────────────────────────────────────────────────────────────────

def parse_passages(raw: str) -> list[str]:
    inner = str(raw).strip().strip("[]")
    items = re.findall(r"'([^']+)'", inner)
    return items if items else [inner.strip()]


def question_type(q: str) -> str:
    q = q.lower()
    if q.strip().startswith("read "):
        return "case_reading"
    if any(k in q for k in ["why or why not", "explain", "how does", "how do", "how is"]):
        return "explanatory"
    if any(k in q for k in ["is this", "can ", "does ", "did ", "will ", "has "]):
        return "yes_no_application"
    return "factual"


def difficulty(row) -> str:
    """Three tiers based on supplemental requirement + answer depth."""
    if row["requires_supplemental"] and row["answer_len"] > 500:
        return "hard"
    if row["requires_supplemental"]:
        return "medium"
    if row["answer_len"] > 400:
        return "medium"
    return "easy"


# ── load & enrich ─────────────────────────────────────────────────────────────

qa = pd.read_csv("data/qa.csv")
corpus = pd.read_csv("data/corpus.csv")

corpus_by_id: dict[str, dict] = {r["id"]: r.to_dict() for _, r in corpus.iterrows()}

qa["passages_list"] = qa["relevant_passages"].apply(parse_passages)
qa["answer_len"] = qa["answer"].apply(len)
qa["chapter"] = qa["id"].apply(lambda x: int(x.split("-")[0]))
qa["section"] = qa["id"].apply(lambda x: x.split("-q")[0])
qa["q_type"] = qa["question"].apply(question_type)
qa["difficulty"] = qa.apply(difficulty, axis=1)

print("=== Full dataset difficulty distribution ===")
print(qa["difficulty"].value_counts().to_string())
print(f"\nTotal questions: {len(qa)}")

# ── per-chapter quotas ────────────────────────────────────────────────────────

TARGET = 50
chapter_counts = qa.groupby("chapter").size()

# Proportional quota, min 3, sum = TARGET
raw = (chapter_counts / chapter_counts.sum() * TARGET)
chapter_quota: dict[int, int] = {ch: max(3, round(v)) for ch, v in raw.items()}

# Fix total: add to largest chapters first, then subtract from largest
while sum(chapter_quota.values()) < TARGET:
    ch = max(chapter_quota, key=lambda c: chapter_counts[c] - chapter_quota[c])
    chapter_quota[ch] += 1
while sum(chapter_quota.values()) > TARGET:
    ch = max(chapter_quota, key=lambda c: chapter_quota[c])
    if chapter_quota[ch] > 3:
        chapter_quota[ch] -= 1

print("\n=== Chapter quotas ===")
print(chapter_quota)
print("Total:", sum(chapter_quota.values()))

# ── within each chapter: target difficulty split ──────────────────────────────
# For quota Q:  hard = min(hard_available, ceil(Q*0.33))
#               easy = min(easy_available, ceil(Q*0.33))
#               medium fills the rest

import math

selected_ids: list[str] = []
used_sections: set[str] = set()
global_seen_types: set[str] = set()

for ch in sorted(chapter_quota.keys()):
    quota = chapter_quota[ch]
    pool = qa[qa["chapter"] == ch].copy()

    hard_target = min((pool["difficulty"] == "hard").sum(), math.ceil(quota * 0.30))
    easy_target = min((pool["difficulty"] == "easy").sum(), math.ceil(quota * 0.30))
    # medium fills the rest
    medium_target = quota - hard_target - easy_target

    picked: list[str] = []
    seen_sections: set[str] = set()
    seen_types: set[str] = set()

    def pick_from(sub_pool: pd.DataFrame, n: int) -> None:
        """Greedy pick up to n rows, maximising section & type diversity."""
        # Sort: prefer new section, then new type, then shorter answer (easy) or longer (hard)
        candidates = sub_pool[~sub_pool["id"].isin(picked)].copy()
        # Score: +2 new section, +1 new type
        candidates["_score"] = (
            candidates["section"].apply(lambda s: 2 if s not in used_sections else 0)
            + candidates["q_type"].apply(lambda t: 1 if t not in global_seen_types else 0)
        )
        candidates = candidates.sort_values("_score", ascending=False)
        for _, row in candidates.iterrows():
            if len([x for x in picked if x in sub_pool["id"].values]) >= n:
                break
            if row["id"] not in picked:
                picked.append(row["id"])
                seen_sections.add(row["section"])
                seen_types.add(row["q_type"])
                used_sections.add(row["section"])
                global_seen_types.add(row["q_type"])

    pick_from(pool[pool["difficulty"] == "hard"], hard_target)
    pick_from(pool[pool["difficulty"] == "easy"], easy_target)
    pick_from(pool[pool["difficulty"] == "medium"], medium_target)

    # If still short, pull from any remaining rows in chapter
    for _, row in pool.iterrows():
        if len(picked) >= quota:
            break
        if row["id"] not in picked:
            picked.append(row["id"])
            used_sections.add(row["section"])

    selected_ids.extend(picked[:quota])

selected_ids = selected_ids[:TARGET]
print(f"\nSelected: {len(selected_ids)} questions")

# ── build golden_set.jsonl ────────────────────────────────────────────────────

selected_qa = qa[qa["id"].isin(selected_ids)].set_index("id")

records: list[dict] = []
for qid in selected_ids:
    row = selected_qa.loc[qid]
    passage_ids: list[str] = row["passages_list"]

    context_texts: list[str] = []
    found_ids: list[str] = []
    for pid in passage_ids:
        if pid in corpus_by_id:
            context_texts.append(corpus_by_id[pid]["text"])
            found_ids.append(pid)

    records.append({
        "id": qid,
        "question": row["question"],
        "expected_answer": row["expected_answer"] if "expected_answer" in row else row["answer"],
        "relevant_passage_ids": passage_ids,
        "corpus_passage_ids": found_ids,
        "context_texts": context_texts,
        "metadata": {
            "chapter": int(row["chapter"]),
            "section": row["section"],
            "difficulty": row["difficulty"],
            "question_type": row["q_type"],
            "requires_supplemental": bool(row["requires_supplemental"]),
            "num_relevant_passages": len(passage_ids),
            "answer_length": int(row["answer_len"]),
        },
    })

# Fix column name: qa.csv uses 'answer', not 'expected_answer'
for rec in records:
    if rec["expected_answer"] is None:
        qid = rec["id"]
        rec["expected_answer"] = qa.set_index("id").loc[qid, "answer"]

output_path = "data/golden_set.jsonl"
with open(output_path, "w", encoding="utf-8") as f:
    for rec in records:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

print(f"Written to {output_path}")

# ── summary ───────────────────────────────────────────────────────────────────

sel = qa[qa["id"].isin(selected_ids)]

print("\n=== SELECTION SUMMARY ===")
print(f"Total:              {len(selected_ids)}")
print(f"Unique chapters:    {sel['chapter'].nunique()} / 13")
print(f"Unique sections:    {sel['section'].nunique()} / {qa['section'].nunique()}")

print("\n--- Difficulty ---")
print(sel["difficulty"].value_counts().to_string())

print("\n--- Question type ---")
print(sel["q_type"].value_counts().to_string())

print("\n--- Requires supplemental ---")
print(sel["requires_supplemental"].value_counts().to_string())

print("\n--- Answer length (chars) ---")
print(sel["answer_len"].describe().round(0).to_string())

print("\n--- Per-chapter breakdown ---")
print(sel.groupby("chapter")["difficulty"].value_counts().unstack(fill_value=0).to_string())
