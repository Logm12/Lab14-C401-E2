"""
Pre-compute dense embeddings cho corpus và lưu ra file.
Chạy một lần: python3 data/build_embeddings.py
Kết quả:
  data/corpus_embeddings.npy   — ma trận (N, 384)
  data/corpus_ids.json         — list ID theo thứ tự hàng
"""
import csv, json, sys, numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer

csv.field_size_limit(10_000_000)

CORPUS_PATH = Path("data/corpus.csv")
EMB_PATH    = Path("data/corpus_embeddings.npy")
IDS_PATH    = Path("data/corpus_ids.json")
MODEL_NAME  = "all-MiniLM-L6-v2"
BATCH_SIZE  = 32


def main():
    if not CORPUS_PATH.exists():
        print(f"❌ Thiếu {CORPUS_PATH}"); sys.exit(1)

    docs = []
    with open(CORPUS_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            docs.append({"id": row["id"], "text": row["text"]})
    print(f"✅ Đọc {len(docs)} documents")

    print(f"⏳ Encoding với {MODEL_NAME} ...")
    embedder   = SentenceTransformer(MODEL_NAME)
    texts      = [d["text"] for d in docs]
    embeddings = embedder.encode(texts, batch_size=BATCH_SIZE,
                                 convert_to_numpy=True, show_progress_bar=True)

    np.save(EMB_PATH, embeddings)
    IDS_PATH.write_text(json.dumps([d["id"] for d in docs], ensure_ascii=False))

    print(f"✅ Đã lưu {embeddings.shape} → {EMB_PATH}")
    print(f"✅ Đã lưu {len(docs)} IDs  → {IDS_PATH}")


if __name__ == "__main__":
    main()
