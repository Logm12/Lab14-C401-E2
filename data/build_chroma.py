"""
Build ChromaDB vector store từ corpus.csv.
Chạy một lần: python3 data/build_chroma.py
Kết quả lưu tại: data/chroma_db/
"""
import csv, os, sys
from pathlib import Path

csv.field_size_limit(10_000_000)

CORPUS_PATH = Path("data/corpus.csv")
CHROMA_DIR  = Path("data/chroma_db")
COLLECTION  = "corpus"
MODEL_NAME  = "all-MiniLM-L6-v2"
BATCH_SIZE  = 32


def main():
    if not CORPUS_PATH.exists():
        print(f"❌ Thiếu {CORPUS_PATH}"); sys.exit(1)

    # Đọc corpus
    docs = []
    with open(CORPUS_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            docs.append({"id": row["id"], "title": row["title"], "text": row["text"]})
    print(f"✅ Đọc {len(docs)} documents từ corpus.csv")

    # Encode
    from sentence_transformers import SentenceTransformer
    print(f"⏳ Encoding với {MODEL_NAME} ...")
    embedder = SentenceTransformer(MODEL_NAME)
    texts = [d["text"] for d in docs]
    embeddings = embedder.encode(
        texts,
        batch_size=BATCH_SIZE,
        convert_to_numpy=True,
        show_progress_bar=True,
    )
    print(f"✅ Embedding shape: {embeddings.shape}")

    # Lưu vào ChromaDB
    import chromadb
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    # Xóa collection cũ nếu tồn tại để build lại từ đầu
    try:
        client.delete_collection(COLLECTION)
        print(f"🗑  Đã xóa collection cũ '{COLLECTION}'")
    except Exception:
        pass

    col = client.create_collection(
        name=COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )

    # Upsert theo batch
    for i in range(0, len(docs), BATCH_SIZE):
        batch = docs[i:i + BATCH_SIZE]
        col.upsert(
            ids        = [d["id"]    for d in batch],
            embeddings = embeddings[i:i + BATCH_SIZE].tolist(),
            documents  = [d["text"]  for d in batch],
            metadatas  = [{"title": d["title"]} for d in batch],
        )

    print(f"✅ Đã lưu {col.count()} vectors vào {CHROMA_DIR}/")
    print("   Dùng trong MainAgent V2 qua: chroma_db/corpus")


if __name__ == "__main__":
    main()
