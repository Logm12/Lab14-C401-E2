import asyncio, json, os, time
from engine.runner import BenchmarkRunner
from engine.retrieval_eval import RetrievalEvaluator
from engine.llm_judge import LLMJudge
from agent.main_agent import MainAgent


def compute_summary(results: list, version: str) -> dict:
    n = len(results) or 1
    avg_score  = sum(r["judge"]["final_score"]          for r in results) / n
    avg_map    = sum(r["retrieval"]["ap"]               for r in results) / n
    avg_mrr    = sum(r["retrieval"]["mrr"]              for r in results) / n
    hit_rate   = sum(r["retrieval"]["hit_rate"]         for r in results) / n
    avg_faith  = sum(r["faithfulness"]["score"]         for r in results) / n
    avg_rel    = sum(r["answer_relevance"]              for r in results) / n
    agreement  = sum(r["judge"]["agreement_rate"]       for r in results) / n
    avg_lat    = sum(r["latency_s"]                     for r in results) / n
    total_cost = sum(r["cost_usd"]                      for r in results)
    pass_count = sum(1 for r in results if r["status"] == "pass")

    return {
        "metadata": {
            "version":     version,
            "total":       len(results),
            "timestamp":   time.strftime("%Y-%m-%dT%H:%M:%S"),
            "pass_count":  pass_count,
            "fail_count":  len(results) - pass_count,
        },
        "metrics": {
            "avg_score":      round(avg_score, 4),
            "hit_rate":       round(hit_rate, 4),
            "agreement_rate": round(agreement, 4),
            "avg_map":              round(avg_map, 4),
            "avg_mrr":              round(avg_mrr, 4),
            "avg_faithfulness":     round(avg_faith, 4),
            "avg_answer_relevance": round(avg_rel, 4),
            "avg_latency_s":        round(avg_lat, 3),
            "total_cost_usd":       round(total_cost, 4),
            "cost_per_eval_usd":    round(total_cost / n, 6),
        },
    }


def regression_gate(v1: dict, v2: dict) -> tuple[str, dict]:
    m1, m2 = v1["metrics"], v2["metrics"]
    checks = {
        "faithfulness_ok": m2["avg_faithfulness"]     >= m1["avg_faithfulness"]     - 0.02,
        "relevance_ok":    m2["avg_answer_relevance"] >= m1["avg_answer_relevance"] - 0.02,
        "map_ok":          m2["avg_map"]              >= m1["avg_map"]              - 0.05,
        "cost_ok":         m2["cost_per_eval_usd"]    <= m1["cost_per_eval_usd"]    * 1.20,
    }
    return ("RELEASE" if all(checks.values()) else "ROLLBACK"), checks


async def run_benchmark(version: str) -> tuple[list, dict]:
    print(f"\n{'='*50}\nRunning benchmark: {version}\n{'='*50}")

    if not os.path.exists("data/golden_dataset.json"):
        print("❌ Thiếu data/golden_dataset.json")
        return [], {}

    with open("data/golden_dataset.json", encoding="utf-8") as f:
        dataset = json.load(f)

    v = "v1" if "V1" in version else "v2"
    agent    = MainAgent(version=v)
    ret_eval = RetrievalEvaluator()
    judge    = LLMJudge()
    runner   = BenchmarkRunner(agent, ret_eval, judge)

    results = await runner.run_all(dataset, batch_size=5)
    summary = compute_summary(results, version)
    summary["metrics"]["judge_total_cost_usd"] = round(judge.total_cost(), 4)
    return results, summary


async def main():
    v1_results, v1_summary = await run_benchmark("Agent_V1_Base")
    v2_results, v2_summary = await run_benchmark("Agent_V2_Optimized")

    if not v1_summary or not v2_summary:
        print("❌ Benchmark thất bại."); return

    decision, checks = regression_gate(v1_summary, v2_summary)

    print("\n📊 REGRESSION ANALYSIS")
    rows = [
        ("avg_faithfulness",     "faithfulness_ok"),
        ("avg_answer_relevance", "relevance_ok"),
        ("avg_map",              "map_ok"),
        ("cost_per_eval_usd",    "cost_ok"),
    ]
    print(f"{'Metric':<30} {'V1':>8} {'V2':>8} {'OK':>4}")
    print("-" * 54)
    for metric, check in rows:
        v1v, v2v = v1_summary["metrics"][metric], v2_summary["metrics"][metric]
        icon = "✅" if checks[check] else "❌"
        print(f"  {metric:<28} {v1v:>8.4f} {v2v:>8.4f} {icon}")
    print(f"\n{'='*50}\nDECISION: {decision}\n{'='*50}")

    v2_summary["regression"] = {
        "v1_avg_score": v1_summary["metrics"]["avg_score"],
        "v2_avg_score": v2_summary["metrics"]["avg_score"],
        "delta":        round(v2_summary["metrics"]["avg_score"]
                              - v1_summary["metrics"]["avg_score"], 4),
        "decision":     decision,
        "checks":       checks,
    }

    os.makedirs("reports", exist_ok=True)
    with open("reports/summary.json", "w", encoding="utf-8") as f:
        json.dump(v2_summary, f, ensure_ascii=False, indent=2)
    with open("reports/benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(v2_results, f, ensure_ascii=False, indent=2)

    print(f"\n✅ reports/summary.json saved")
    print(f"✅ reports/benchmark_results.json saved")

    m = v2_summary["metrics"]
    print(f"\n📈 V2 Final Metrics:")
    for k, v in [("MAP", m["avg_map"]), ("Faithfulness", m["avg_faithfulness"]),
                 ("Answer Relevance", m["avg_answer_relevance"]),
                 ("Hit Rate@3", m["hit_rate"]), ("Agreement Rate", m["agreement_rate"]),
                 ("Avg Latency (s)", m["avg_latency_s"]),
                 ("Cost/eval ($)", m["cost_per_eval_usd"])]:
        print(f"  {k:<22} {v:.4f}")


if __name__ == "__main__":
    asyncio.run(main())
