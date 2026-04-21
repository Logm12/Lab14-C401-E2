import asyncio, time
from typing import Dict, List
from tqdm.asyncio import tqdm_asyncio


class BenchmarkRunner:

    def __init__(self, agent, retrieval_evaluator, judge):
        self.agent    = agent
        self.ret_eval = retrieval_evaluator
        self.judge    = judge

    async def run_single_test(self, case: Dict) -> Dict:
        t0 = time.perf_counter()

        agent_resp = await self.agent.query(case["question"])

        rel_ids = case["relevant_passage_ids"]
        ret_ids = agent_resp["retrieved_ids"]

        ap  = self.ret_eval.calculate_ap(rel_ids, ret_ids)
        mrr = self.ret_eval.calculate_mrr(rel_ids, ret_ids)
        hr  = self.ret_eval.calculate_hit_rate(rel_ids, ret_ids, top_k=3)

        judge_result = await self.judge.evaluate(
            question     = case["question"],
            agent_answer = agent_resp["answer"],
            answer_points= case["answer_points"],
        )

        faith_score = judge_result["faithfulness"]["score"]
        rel_score   = judge_result["answer_relevance"]
        final_score = round(faith_score * 0.6 + rel_score * 0.4, 4)

        return {
            "id":                  case["id"],
            "question":            case["question"],
            "expected_answer":     case["expected_answer"],
            "agent_answer":        agent_resp["answer"],
            "relevant_passage_ids": rel_ids,
            "retrieved_ids":       ret_ids,
            "retrieval": {
                "ap":       round(ap, 4),
                "mrr":      round(mrr, 4),
                "hit_rate": round(hr, 4),
            },
            "faithfulness":    judge_result["faithfulness"],
            "answer_relevance": judge_result["answer_relevance"],
            "judge": {
                "final_score":       final_score,
                "individual_scores": judge_result["individual_scores"],
                "agreement_rate":    judge_result["agreement_rate"],
            },
            "latency_s":   round(time.perf_counter() - t0, 3),
            "tokens_used": agent_resp["metadata"]["tokens_used"],
            "cost_usd":    round(agent_resp["metadata"]["cost_usd"], 6),
            "status":      "pass" if final_score >= 0.5 else "fail",
            "metadata":    case.get("metadata", {}),
        }

    async def run_all(self, dataset: List[Dict], batch_size: int = 5) -> List[Dict]:
        sem = asyncio.Semaphore(batch_size)

        async def _run(case):
            async with sem:
                return await self.run_single_test(case)

        tasks = [_run(c) for c in dataset]
        return await tqdm_asyncio.gather(*tasks, desc="Benchmarking")
