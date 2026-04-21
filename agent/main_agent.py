import asyncio, csv, json, os, time
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict
from dotenv import load_dotenv
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import openai

load_dotenv()

_GPT_PRICE_IN  = 0.15 / 1_000_000
_GPT_PRICE_OUT = 0.60 / 1_000_000

V1_SYSTEM = """You are a legal assistant with expertise in statutory interpretation and case law analysis.

Answer the question using the provided context. Be concise, accurate, and professionally toned."""


V2_SYSTEM = """You are a senior legal counsel with deep expertise in statutory interpretation, \
regulatory compliance, and case law analysis operating under strict evidentiary constraints.

## Evidentiary boundary
Your entire response must derive exclusively from the provided context.
Do not supplement with external statutes, precedents, or legal doctrine absent from the context.
If the context does not contain sufficient information to answer, respond with this exact phrase and nothing else:
"I cannot find sufficient information in the provided context to answer this question."

## Answer structure
1. Legal conclusion — state the direct answer first, unambiguously
2. Statutory or doctrinal basis — cite the specific provision, principle, or rule from the context that supports the conclusion
3. Qualifications — note exceptions, conditions, or jurisdictional limits only if the context raises them
4. Conflicts — if multiple provisions apply and create tension, identify each and apply the relevant hierarchy rule (lex specialis, lex posterior, or as stated in the context)

## Drafting standards
- Use precise legal terminology consistent with the context's register (civil law, common law, regulatory, etc.)
- Avoid epistemic hedging ("may", "might", "possibly") unless the source text is itself qualified or permissive
- Never fabricate case names, statute numbers, section references, dates, or party names not present in the context
- Do not summarise or paraphrase the question back to the user; proceed directly to the legal analysis"""

_EMB_PATH = Path("data/corpus_embeddings.npy")
_IDS_PATH = Path("data/corpus_ids.json")


class MainAgent:
    def __init__(self, version: str = "v1"):
        self.version = version
        self.name = f"LegalRAG-{version}"
        self._corpus: List[Dict] = []
        self._bm25: BM25Okapi | None = None
        self._embedder: SentenceTransformer | None = None
        self._doc_embeddings = None      # np.ndarray (N, D), chỉ dùng v2
        self._emb_id_order: List[str] = []  # thứ tự ID trong ma trận embedding
        self._client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self._load_corpus()

    def _load_corpus(self):
        csv.field_size_limit(10_000_000)
        with open("data/corpus.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                self._corpus.append({"id": row["id"], "title": row["title"], "text": row["text"]})

        tokenized = [doc["text"].lower().split() for doc in self._corpus]
        self._bm25 = BM25Okapi(tokenized)

        if self.version == "v2":
            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            if _EMB_PATH.exists() and _IDS_PATH.exists():
                # Load pre-built embeddings — không tính lại
                self._doc_embeddings = np.load(_EMB_PATH)
                self._emb_id_order   = json.loads(_IDS_PATH.read_text())
                print(f"✅ Loaded embeddings {self._doc_embeddings.shape} từ {_EMB_PATH}")
            else:
                # Fallback: tính tại chỗ
                print("⚠️  Chưa có embeddings. Chạy: python3 data/build_embeddings.py")
                texts = [d["text"] for d in self._corpus]
                self._doc_embeddings = self._embedder.encode(
                    texts, convert_to_numpy=True, show_progress_bar=False
                )
                self._emb_id_order = [d["id"] for d in self._corpus]

    def _bm25_ranking(self, question: str) -> List[Tuple[int, float]]:
        scores = self._bm25.get_scores(question.lower().split())
        return sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

    def _dense_ranking(self, question: str) -> List[Tuple[int, float]]:
        """Trả về [(corpus_idx, similarity), ...] descending theo similarity."""
        q_vec = self._embedder.encode([question], convert_to_numpy=True)
        sims  = cosine_similarity(q_vec, self._doc_embeddings)[0]

        # Ánh xạ về corpus index theo thứ tự ID trong file embedding
        id_to_corpus_idx = {d["id"]: i for i, d in enumerate(self._corpus)}
        ranked = sorted(enumerate(sims), key=lambda x: x[1], reverse=True)

        result = []
        for emb_idx, sim in ranked:
            doc_id = self._emb_id_order[emb_idx]
            corpus_idx = id_to_corpus_idx.get(doc_id)
            if corpus_idx is not None:
                result.append((corpus_idx, float(sim)))
        return result

    @staticmethod
    def _rrf_score(rank: int, k: int = 60) -> float:
        return 1.0 / (k + rank)

    def _retrieve_v1(self, question: str, top_k: int = 3) -> List[Dict]:
        ranking = self._bm25_ranking(question)
        return [
            {**self._corpus[idx], "score": float(score)}
            for idx, score in ranking[:top_k]
        ]

    def _retrieve_v2(self, question: str, top_k: int = 3) -> List[Dict]:
        bm25_rank = self._bm25_ranking(question)
        dense_rank = self._dense_ranking(question)

        rrf_scores: Dict[int, float] = defaultdict(float)
        for rank, (idx, _) in enumerate(bm25_rank):
            rrf_scores[idx] += self._rrf_score(rank)
        for rank, (idx, _) in enumerate(dense_rank):
            rrf_scores[idx] += self._rrf_score(rank)

        top_indices = sorted(rrf_scores, key=rrf_scores.get, reverse=True)[:top_k]
        return [
            {**self._corpus[idx], "score": rrf_scores[idx]}
            for idx in top_indices
        ]

    def _retrieve(self, question: str) -> List[Dict]:
        return self._retrieve_v1(question) if self.version == "v1" else self._retrieve_v2(question)

    def _system_prompt(self) -> str:
        if self.version == "v1":
            return V1_SYSTEM
        return V2_SYSTEM

    async def query(self, question: str) -> Dict:
        t0 = time.perf_counter()
        docs = self._retrieve(question)
        retrieved_ids = [d["id"] for d in docs]
        contexts = [d["text"] for d in docs]

        context_str = "\n\n---\n\n".join(
            f"[Document {i+1}: {d['title']}]\n{d['text'][:2000]}"
            for i, d in enumerate(docs)
        )
        user_msg = f"Context:\n{context_str}\n\nQuestion: {question}"

        resp = await self._client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "system", "content": self._system_prompt()},
                      {"role": "user",   "content": user_msg}],
            temperature=0.1,
            max_tokens=512,
        )
        answer = resp.choices[0].message.content.strip()
        tokens_used = resp.usage.prompt_tokens + resp.usage.completion_tokens
        cost_usd = (resp.usage.prompt_tokens * _GPT_PRICE_IN
                    + resp.usage.completion_tokens * _GPT_PRICE_OUT)

        return {
            "answer": answer,
            "retrieved_ids": retrieved_ids,
            "contexts": contexts,
            "metadata": {
                "model": "gpt-4o-mini",
                "tokens_used": tokens_used,
                "cost_usd": round(cost_usd, 6),
                "latency_s": round(time.perf_counter() - t0, 3),
                "version": self.version,
            },
        }
