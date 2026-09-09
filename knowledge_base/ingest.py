"""
Ingests SOPs/manuals/correspondence from kb_docs/ into a local FAISS index.
Fully offline: embeddings model is downloaded once ahead of time and then
loaded from local cache (set HF_HUB_OFFLINE=1 at demo time to prove it).

Run: python -m knowledge_base.ingest
"""
import os
import pickle
from pathlib import Path

import faiss
import numpy as np
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

DOCS_DIR = Path(__file__).parent.parent / "kb_docs"
INDEX_DIR = Path(__file__).parent.parent / "kb_index"
INDEX_DIR.mkdir(exist_ok=True)

EMBED_MODEL_NAME = "all-MiniLM-L6-v2"   # small, good enough offline, ~80MB
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


def load_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    return path.read_text(errors="ignore")


def chunk_text(text: str, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return [c.strip() for c in chunks if c.strip()]


def build_index():
    model = SentenceTransformer(EMBED_MODEL_NAME)   # loads from local HF cache once downloaded
    all_chunks, metadata = [], []

    for path in DOCS_DIR.rglob("*"):
        if path.suffix.lower() not in (".txt", ".md", ".pdf"):
            continue
        text = load_text(path)
        for i, chunk in enumerate(chunk_text(text)):
            all_chunks.append(chunk)
            metadata.append({"source": str(path.relative_to(DOCS_DIR)), "chunk_id": i})

    if not all_chunks:
        print(f"No documents found in {DOCS_DIR}. Add .txt/.md/.pdf files there and re-run.")
        return

    embeddings = model.encode(all_chunks, show_progress_bar=True, normalize_embeddings=True)
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)   # cosine similarity via normalized inner product
    index.add(np.array(embeddings, dtype="float32"))

    faiss.write_index(index, str(INDEX_DIR / "kb.index"))
    with open(INDEX_DIR / "kb_meta.pkl", "wb") as f:
        pickle.dump({"chunks": all_chunks, "metadata": metadata}, f)

    print(f"Indexed {len(all_chunks)} chunks from {DOCS_DIR} -> {INDEX_DIR}")


if __name__ == "__main__":
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    build_index()
