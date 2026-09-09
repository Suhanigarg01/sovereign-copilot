"""
Local, offline RAG search over the FAISS index built by ingest.py.
Exposed to the agent as the `doc_search` tool.
"""
import pickle
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

INDEX_DIR = Path(__file__).parent.parent / "kb_index"
EMBED_MODEL_NAME = "all-MiniLM-L6-v2"

_model = None
_index = None
_meta = None


def _load():
    global _model, _index, _meta
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL_NAME)
    if _index is None:
        index_path = INDEX_DIR / "kb.index"
        if not index_path.exists():
            raise FileNotFoundError("No KB index found. Run `python -m knowledge_base.ingest` first.")
        _index = faiss.read_index(str(index_path))
        with open(INDEX_DIR / "kb_meta.pkl", "rb") as f:
            _meta = pickle.load(f)


def doc_search(query: str, top_k: int = 4) -> list:
    _load()
    q_emb = _model.encode([query], normalize_embeddings=True)
    scores, idxs = _index.search(np.array(q_emb, dtype="float32"), top_k)
    results = []
    for score, idx in zip(scores[0], idxs[0]):
        if idx == -1:
            continue
        results.append({
            "text": _meta["chunks"][idx],
            "source": _meta["metadata"][idx]["source"],
            "score": float(score),
        })
    return results
