from typing import List, Dict


class RetrievalEvaluator:

    def calculate_ap(self, relevant_ids: List[str], retrieved_ids: List[str]) -> float:
        if not relevant_ids:
            return 0.0
        relevant_set = set(relevant_ids)
        hits, score = 0, 0.0
        for k, doc_id in enumerate(retrieved_ids, start=1):
            if doc_id in relevant_set:
                hits += 1
                score += hits / k
        return score / len(relevant_ids)

    def calculate_mrr(self, relevant_ids: List[str], retrieved_ids: List[str]) -> float:
        relevant_set = set(relevant_ids)
        for rank, doc_id in enumerate(retrieved_ids, start=1):
            if doc_id in relevant_set:
                return 1.0 / rank
        return 0.0

    def calculate_hit_rate(self, relevant_ids: List[str],
                           retrieved_ids: List[str], top_k: int = 3) -> float:
        relevant_set = set(relevant_ids)
        return 1.0 if any(d in relevant_set for d in retrieved_ids[:top_k]) else 0.0

    def evaluate_batch(self, results: List[Dict]) -> Dict:
        """
        Input: list of result dicts, mỗi dict có:
          "relevant_passage_ids": List[str]
          "retrieved_ids": List[str]
          "id": str

        Output:
          {
            "avg_map": float, "avg_mrr": float, "avg_hit_rate": float,
            "per_case": [{"id", "ap", "mrr", "hit_rate"}, ...]
          }
        """
        aps, mrrs, hrs = [], [], []
        per_case = []
        for r in results:
            ap  = self.calculate_ap(r["relevant_passage_ids"], r["retrieved_ids"])
            mrr = self.calculate_mrr(r["relevant_passage_ids"], r["retrieved_ids"])
            hr  = self.calculate_hit_rate(r["relevant_passage_ids"], r["retrieved_ids"])
            aps.append(ap); mrrs.append(mrr); hrs.append(hr)
            per_case.append({"id": r.get("id",""), "ap": round(ap,4),
                             "mrr": round(mrr,4), "hit_rate": round(hr,4)})
        n = len(aps) or 1
        return {
            "avg_map": round(sum(aps)/n, 4),
            "avg_mrr": round(sum(mrrs)/n, 4),
            "avg_hit_rate": round(sum(hrs)/n, 4),
            "per_case": per_case,
        }
