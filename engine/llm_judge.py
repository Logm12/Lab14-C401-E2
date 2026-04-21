import asyncio, json, os
from typing import Dict, List, Tuple
import openai
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv

load_dotenv()

_GPT_IN, _GPT_OUT       = 0.15/1e6, 0.60/1e6
_CLAUDE_IN, _CLAUDE_OUT = 0.25/1e6, 1.25/1e6

_CANNOT_FIND_PHRASES = [
    "cannot find", "can't find", "not find", "no information",
    "not enough information", "insufficient information",
    "i don't have", "not in the context",
]

FAITHFULNESS_SYSTEM = """You are an expert NLI (Natural Language Inference) judge evaluating factual consistency.

Your task: determine whether a given claim is ENTAILED by the source text.

Definitions:
- ENTAILED: the source text explicitly states, directly implies, or logically necessitates the claim
- NOT ENTAILED: the claim is absent, contradicted, or requires external knowledge not present in the source

Strict rules:
- Base your verdict ONLY on the source text — not on world knowledge or common sense
- Partial support is NOT entailment; the claim must be fully covered
- Synonymous phrasing counts as entailment; do not penalise paraphrasing
- Reply with a single word: YES or NO — no explanation, no punctuation"""

FAITHFULNESS_USER = """SOURCE TEXT (the AI-generated answer):
\"\"\"
{agent_answer}
\"\"\"

CLAIM TO VERIFY:
\"{point}\"

Is this claim fully entailed by the source text above?"""

TIEBREAK_SYSTEM = """You are a senior NLI arbitrator resolving inter-judge disagreements on Faithfulness scoring.

Faithfulness measures what fraction of the expected claims are fully entailed by the agent answer.

Scoring rubric:
- 1.0  all claims explicitly stated or directly implied
- 0.75 most claims supported; one minor omission or weak implication
- 0.5  roughly half the claims supported; noticeable gaps
- 0.25 few claims supported; answer is mostly off or hallucinated
- 0.0  no claims supported or answer directly contradicts the claims

Entailment rules (same as primary judges):
- Base verdict ONLY on the agent answer — not on world knowledge
- Synonymous phrasing counts as entailment
- Partial support does NOT count as full entailment for that claim
- A claim is binary: supported (1) or not (0); average across all claims gives the score

Your output MUST be valid JSON with no extra text:
{"score": 0.XX, "supported_claims": N, "total_claims": N, "reasoning": "one sentence"}"""

TIEBREAK_USER = """JUDGE SCORES IN CONFLICT
  GPT score   : {score_gpt:.2f}
  Claude score: {score_claude:.2f}
  Delta       : {delta:.2f}  (threshold 0.70)

AGENT ANSWER:
\"\"\"
{agent_answer}
\"\"\"

EXPECTED CLAIMS ({n_claims} total):
{points_text}

Carefully verify each claim against the agent answer, then return your arbitrated score."""

REVERSE_Q_SYSTEM = """You are an expert question generation specialist trained in semantic textual similarity evaluation.

Your task: given an answer, reverse-engineer the questions that answer most precisely addresses.

Requirements for each generated question:
- Must be fully answerable by the answer text alone — no external knowledge needed
- Must target a distinct aspect of the answer (no semantic overlap between questions)
- Must be a natural, fluent question a human would realistically ask
- Must NOT be a trivial rephrasing of each other
- Vary question types: factual ("what"), causal ("why"), procedural ("how"), conditional ("when/under what conditions")

Output format: exactly 3 questions, one per line, no numbering, no bullet points, no preamble."""

REVERSE_Q_USER = """ANSWER:
\"\"\"
{agent_answer}
\"\"\"

Generate exactly 3 distinct questions that this answer directly addresses:"""

class LLMJudge:

    def __init__(self):
        self._openai = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self._openrouter = openai.AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
        self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
        self._usage = {"gpt_in": 0, "gpt_out": 0, "claude_in": 0, "claude_out": 0}

    # ── low-level callers ──────────────────────────────────────────────────

    async def _gpt(self, system: str, user: str,
                   max_tokens: int = 512) -> Tuple[str, int, int]:
        resp = await self._openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system},
                      {"role": "user",   "content": user}],
            temperature=0.0, max_tokens=max_tokens,
        )
        pt, ct = resp.usage.prompt_tokens, resp.usage.completion_tokens
        self._usage["gpt_in"] += pt; self._usage["gpt_out"] += ct
        return resp.choices[0].message.content.strip(), pt, ct

    async def _claude(self, system: str, user: str,
                      max_tokens: int = 512) -> Tuple[str, int, int]:
        resp = await self._openrouter.chat.completions.create(
            model="anthropic/claude-haiku-4.5",
            messages=[{"role": "system", "content": system},
                      {"role": "user",   "content": user}],
            temperature=0.0, max_tokens=max_tokens,
        )
        pt = resp.usage.prompt_tokens if resp.usage else 0
        ct = resp.usage.completion_tokens if resp.usage else 0
        self._usage["claude_in"] += pt; self._usage["claude_out"] += ct
        return resp.choices[0].message.content.strip(), pt, ct

    # ── Faithfulness ──────────────────────────────────────────────────────

    async def _verify_gpt(self, question: str, agent_answer: str, point: str) -> bool:
        system = FAITHFULNESS_SYSTEM
        user = FAITHFULNESS_USER.format(
            agent_answer=agent_answer.strip(),
            point=point.strip(),
        )
        raw, _, _ = await self._gpt(system, user, max_tokens=10)
        return raw.strip().upper() == "YES"

    async def _verify_claude(self, question: str, agent_answer: str, point: str) -> bool:
        system = FAITHFULNESS_SYSTEM
        user = FAITHFULNESS_USER.format(
            agent_answer=agent_answer.strip(),
            point=point.strip(),
        )
        raw, _, _ = await self._claude(system, user, max_tokens=10)
        return raw.strip().upper() == "YES"

    async def compute_faithfulness(
        self,
        question: str,
        agent_answer: str,
        answer_points: List[str],
    ) -> Dict:
        if not answer_points:
            return {"score": 0.0, "score_gpt": 0.0, "score_claude": 0.0,
                    "agreement": 1.0, "conflict_resolved": False,
                    "claims_total": 0, "claims_supported_gpt": 0,
                    "claims_supported_claude": 0}

        gpt_tasks    = [self._verify_gpt(question, agent_answer, p)    for p in answer_points]
        claude_tasks = [self._verify_claude(question, agent_answer, p) for p in answer_points]

        gpt_results, claude_results = await asyncio.gather(
            asyncio.gather(*gpt_tasks),
            asyncio.gather(*claude_tasks),
        )

        sup_gpt    = sum(gpt_results)
        sup_claude = sum(claude_results)
        total      = len(answer_points)

        score_gpt    = sup_gpt    / total
        score_claude = sup_claude / total
        agreement    = 1.0 - abs(score_gpt - score_claude)
        final        = (score_gpt + score_claude) / 2
        conflict     = False

        if agreement < 0.6:
            points_text = "\n".join(f"{i+1}. {p}" for i, p in enumerate(answer_points))

            system = TIEBREAK_SYSTEM
            user = TIEBREAK_USER.format(
                score_gpt=score_gpt,
                score_claude=score_claude,
                delta=abs(score_gpt - score_claude),
                agent_answer=agent_answer.strip(),
                n_claims=len(answer_points),
                points_text=points_text,
            )

            raw, _, _ = await self._gpt(system, user, max_tokens=80)

            try:
                parsed = json.loads(raw)
                tiebreak_score = float(parsed["score"])
                if not (0.0 <= tiebreak_score <= 1.0):
                    raise ValueError(f"Score out of range: {tiebreak_score}")
                final    = tiebreak_score
                conflict = True
            except Exception:
                pass  # keep avg, conflict stays False

        return {
            "score":                   round(final, 4),
            "score_gpt":               round(score_gpt, 4),
            "score_claude":            round(score_claude, 4),
            "agreement":               round(agreement, 4),
            "conflict_resolved":       conflict,
            "claims_total":            total,
            "claims_supported_gpt":    sup_gpt,
            "claims_supported_claude": sup_claude,
        }

    # ── Answer Relevance ──────────────────────────────────────────────────

    async def compute_answer_relevance(self, question: str, agent_answer: str) -> float:
        if any(p in agent_answer.lower() for p in _CANNOT_FIND_PHRASES):
            return 0.0

        system = REVERSE_Q_SYSTEM
        user = REVERSE_Q_USER.format(agent_answer=agent_answer.strip())

        raw, _, _ = await self._gpt(system, user, max_tokens=150)

        hyp_qs = [line.strip() for line in raw.strip().split("\n") if line.strip()]
        if not hyp_qs:
            return 0.0

        all_texts = [question] + hyp_qs
        embs = self._embedder.encode(all_texts, convert_to_numpy=True)
        sims = cosine_similarity(embs[0:1], embs[1:])[0]
        return float(np.mean(sims))

    # ── Combined (used from runner) ───────────────────────────────────────

    async def evaluate(
        self,
        question: str,
        agent_answer: str,
        answer_points: List[str],
    ) -> Dict:
        faith_task = self.compute_faithfulness(question, agent_answer, answer_points)
        rel_task   = self.compute_answer_relevance(question, agent_answer)
        faith, rel = await asyncio.gather(faith_task, rel_task)

        return {
            "faithfulness":     faith,
            "answer_relevance": round(rel, 4),
            "individual_scores": {
                "gpt-4o-mini":  faith["score_gpt"],
                "claude-haiku": faith["score_claude"],
            },
            "agreement_rate": faith["agreement"],
        }

    def total_cost(self) -> float:
        return (self._usage["gpt_in"]    * _GPT_IN
              + self._usage["gpt_out"]   * _GPT_OUT
              + self._usage["claude_in"] * _CLAUDE_IN
              + self._usage["claude_out"]* _CLAUDE_OUT)
