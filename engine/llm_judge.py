import asyncio, json, os
import openai
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv

load_dotenv()

# Keep original prompts to maintain evaluation quality
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

FAITHFULNESS_USER = "SOURCE TEXT (the AI-generated answer):\n\"\"\"\n{agent_answer}\n\"\"\"\n\nCLAIM TO VERIFY:\n\"{point}\"\n\nIs this claim fully entailed by the source text above?"

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

REVERSE_Q_USER = "ANSWER:\n\"\"\"\n{agent_answer}\n\"\"\"\n\nGenerate exactly 3 distinct questions that this answer directly addresses:"

# Costs per 1M tokens
COSTS = {"gpt_in": 0.15, "gpt_out": 0.60, "claude_in": 0.25, "claude_out": 1.25}
_CANNOT_FIND_PHRASES = ["cannot find", "can't find", "not find", "no information", "not enough information", "insufficient information", "i don't have", "not in the context"]

class LLMJudge:
    def __init__(self):
        self._openai = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self._openrouter = openai.AsyncOpenAI(base_url="https://openrouter.ai/api/v1", api_key=os.getenv("OPENROUTER_API_KEY"))
        self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
        self._usage = {k: 0 for k in COSTS}

    async def _call(self, client, model, sys_msg, user_msg, max_tok, in_key, out_key):
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
            temperature=0.0, max_tokens=max_tok
        )
        u = resp.usage
        self._usage[in_key] += getattr(u, 'prompt_tokens', 0)
        self._usage[out_key] += getattr(u, 'completion_tokens', 0)
        return resp.choices[0].message.content.strip()

    async def _verify(self, is_gpt, answer, point):
        client, model, ik, ok = (self._openai, "gpt-4o-mini", "gpt_in", "gpt_out") if is_gpt else \
                                (self._openrouter, "anthropic/claude-haiku-4.5", "claude_in", "claude_out")
        msg = FAITHFULNESS_USER.format(agent_answer=answer, point=point)
        res = await self._call(client, model, FAITHFULNESS_SYSTEM, msg, 10, ik, ok)
        return res.upper() == "YES"

    async def compute_faithfulness(self, question: str, agent_answer: str, points: list) -> dict:
        if not points: 
            return {"score": 0.0, "score_gpt": 0.0, "score_claude": 0.0, "agreement": 1.0, 
                    "conflict_resolved": False, "claims_total": 0, "claims_supported_gpt": 0, "claims_supported_claude": 0}
        
        gpt_tasks = [self._verify(True, agent_answer, p) for p in points]
        claude_tasks = [self._verify(False, agent_answer, p) for p in points]
        gpt_res, claude_res = await asyncio.gather(asyncio.gather(*gpt_tasks), asyncio.gather(*claude_tasks))
        
        sup_gpt, sup_claude = sum(gpt_res), sum(claude_res)
        sg, sc = sup_gpt / len(points), sup_claude / len(points)
        final, conflict, agreement = (sg + sc) / 2, False, 1.0 - abs(sg - sc)

        if agreement < 0.6:
            pts_txt = "\n".join(f"{i+1}. {p}" for i, p in enumerate(points))
            msg = TIEBREAK_USER.format(score_gpt=sg, score_claude=sc, delta=abs(sg-sc), 
                                       agent_answer=agent_answer, n_claims=len(points), points_text=pts_txt)
            res = await self._call(self._openai, "gpt-4o-mini", TIEBREAK_SYSTEM, msg, 80, "gpt_in", "gpt_out")
            try:
                final = float(json.loads(res).get("score", final))
                conflict = True
            except: pass
            
        return {
            "score": round(final, 4), "score_gpt": round(sg, 4), "score_claude": round(sc, 4), 
            "agreement": round(agreement, 4), "conflict_resolved": conflict,
            "claims_total": len(points), "claims_supported_gpt": sup_gpt, "claims_supported_claude": sup_claude
        }

    async def compute_answer_relevance(self, question: str, answer: str) -> float:
        if any(p in answer.lower() for p in _CANNOT_FIND_PHRASES): return 0.0
        
        msg = REVERSE_Q_USER.format(agent_answer=answer)
        res = await self._call(self._openai, "gpt-4o-mini", REVERSE_Q_SYSTEM, msg, 150, "gpt_in", "gpt_out")
        hyp_qs = [q.strip() for q in res.split("\n") if q.strip()]
        
        if not hyp_qs: return 0.0
        embs = self._embedder.encode([question] + hyp_qs, convert_to_numpy=True)
        return float(np.mean(cosine_similarity(embs[0:1], embs[1:])[0]))

    async def evaluate(self, question: str, answer: str, points: list) -> dict:
        f, r = await asyncio.gather(self.compute_faithfulness(question, answer, points), 
                                    self.compute_answer_relevance(question, answer))
        return {
            "faithfulness": f, "answer_relevance": round(r, 4), 
            "individual_scores": {"gpt-4o-mini": f["score_gpt"], "claude-haiku": f["score_claude"]}, 
            "agreement_rate": f["agreement"]
        }

    def total_cost(self) -> float:
        return sum(self._usage[k] * COSTS[k] for k in COSTS) / 1e6
