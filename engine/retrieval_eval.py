from typing import List, Dict

class RetrievalEvaluator:
    def calculate_ap(self, relevant_ids: List[str], retrieved_ids: List[str]) -> float:
        if not relevant_ids: return 0.0
        rel_set = set(relevant_ids)
        hits, score = 0, 0.0
        for k, doc_id in enumerate(retrieved_ids, 1):
            if doc_id in rel_set:
                hits += 1
                score += hits / k
        return score / len(relevant_ids)

    def calculate_mrr(self, relevant_ids: List[str], retrieved_ids: List[str]) -> float:
        rel_set = set(relevant_ids)
        for rank, doc_id in enumerate(retrieved_ids, 1):
            if doc_id in rel_set: return 1.0 / rank
        return 0.0

    def calculate_hit_rate(self, relevant_ids: List[str], retrieved_ids: List[str], top_k=3) -> float:
        return 1.0 if any(doc in set(relevant_ids) for doc in retrieved_ids[:top_k]) else 0.0

    def evaluate_batch(self, results: List[Dict]) -> Dict:
        per_case = []
        for r in results:
            rel, ret = r["relevant_passage_ids"], r["retrieved_ids"]
            ap, mrr, hr = self.calculate_ap(rel, ret), self.calculate_mrr(rel, ret), self.calculate_hit_rate(rel, ret)
            per_case.append({"id": r.get("id", ""), "ap": round(ap, 4), "mrr": round(mrr, 4), "hit_rate": round(hr, 4)})
            
        n = len(per_case) or 1
        return {
            "avg_map": round(sum(x["ap"] for x in per_case) / n, 4),
            "avg_mrr": round(sum(x["mrr"] for x in per_case) / n, 4),
            "avg_hit_rate": round(sum(x["hit_rate"] for x in per_case) / n, 4),
            "per_case": per_case,
        }
