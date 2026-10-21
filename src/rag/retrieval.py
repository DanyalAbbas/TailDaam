"""Retrieval: Chroma vector store over gold-table facts.

Embeddings
----------
- If MISTRAL_API_KEY is set: Mistral `mistral-embed` (multilingual, needs network).
- Otherwise: a local TF-IDF embedder fitted on the gold corpus and persisted next
  to the Chroma index. This keeps the submission runnable offline (important for
  reproducible judging) at the cost of lexical rather than semantic matching.
  The mode is reported in /health so no one mistakes it for the hosted model.

Each indexed chunk is one gold-table fact with full metadata (row_ids,
citation_tag) so whatever the agent quotes is traceable by construction.
"""

from __future__ import annotations

import os
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
from langchain_chroma import Chroma
from langchain_core.documents import Document

from sklearn.feature_extraction.text import TfidfVectorizer

from rag.config import (
    CHROMA_DIR,
    MISTRAL_API_KEY,
    MISTRAL_EMBED_MODEL,
    TOP_K,
)
from rag.gold_tables import load_gold_tables

COLLECTION = "insight_agent_facts"
TFIDF_PATH = CHROMA_DIR / "tfidf.joblib"

# On FastAPI Cloud the 109 MB Chroma directory is deliberately excluded from
# the upload. The service can still answer: fit the same TF-IDF vectorizer over
# the 2,129 gold facts in memory on first use. This keeps startup fast (the
# container health check must pass) and avoids a 100 MB upload. Locally, when
# data/chroma exists, the persistent Chroma path is used unchanged.
_MEMORY_LOCK = threading.Lock()
_MEMORY_INDEX: tuple[list, object, object] | None = None


class LocalTfidfEmbeddings:
    """Minimal sklearn TF-IDF embedding function with Chroma's interface."""

    def __init__(self, vectorizer):
        self.vectorizer = vectorizer

    def embed_documents(self, texts):
        return self.vectorizer.transform(texts).toarray().astype(float).tolist()

    def embed_query(self, text):
        return self.vectorizer.transform([text]).toarray()[0].astype(float).tolist()


def embedding_mode() -> str:
    return "mistral-embed" if MISTRAL_API_KEY else "local-tfidf"


def get_embedding_fn():
    if MISTRAL_API_KEY:
        from langchain_mistralai import MistralAIEmbeddings

        return MistralAIEmbeddings(model=MISTRAL_EMBED_MODEL, api_key=MISTRAL_API_KEY)
    if not TFIDF_PATH.exists():
        raise RuntimeError(
            "No MISTRAL_API_KEY and no fitted TF-IDF index. Run "
            "`python -m rag build-index` first."
        )
    return LocalTfidfEmbeddings(joblib.load(TFIDF_PATH))


def get_vectorstore():
    return Chroma(
        collection_name=COLLECTION,
        embedding_function=get_embedding_fn(),
        persist_directory=str(CHROMA_DIR),
        collection_metadata={"hnsw:space": "cosine"},
    )


def _fit_vectorizer(texts: list[str]):
    vec = TfidfVectorizer(
        lowercase=True, ngram_range=(1, 2), min_df=1,
        sublinear_tf=True, max_features=20000,
    )
    return vec.fit(texts)


def _memory_index():
    """Lazy in-memory TF-IDF index used when Chroma is not shipped."""
    global _MEMORY_INDEX
    if _MEMORY_INDEX is not None:
        return _MEMORY_INDEX
    with _MEMORY_LOCK:
        if _MEMORY_INDEX is not None:
            return _MEMORY_INDEX
        docs = load_gold_tables()
        texts = [d.text for d in docs]
        vectorizer = joblib.load(TFIDF_PATH) if TFIDF_PATH.exists() else _fit_vectorizer(texts)
        matrix = vectorizer.transform(texts)
        _MEMORY_INDEX = (docs, vectorizer, matrix)
        return _MEMORY_INDEX


def _memory_retrieve(question: str, k: int) -> list[Evidence]:
    docs, vectorizer, matrix = _memory_index()
    query = vectorizer.transform([question])
    scores = np.asarray((matrix @ query.T).todense()).ravel()
    top = np.argsort(-scores)[:k]
    evidence: list[Evidence] = []
    for idx in top:
        d = docs[int(idx)]
        evidence.append(Evidence(
            fact_id=d.meta.get("fact_id", ""),
            doc_id=d.doc_id,
            row_ids=d.row_ids,
            citation_tag=d.citation_tag,
            text=d.text,
            score=max(0.0, min(1.0, float(scores[int(idx)]))),
            meta={**d.meta, "doc_id": d.doc_id},
        ))
    return evidence


def indexed_fact_count() -> int:
    """Number of facts available, without forcing a Chroma rebuild."""
    if (CHROMA_DIR / "chroma.sqlite3").exists():
        try:
            return get_vectorstore()._collection.count()
        except Exception:
            pass
    try:
        return len(load_gold_tables())
    except Exception:
        return 0


def build_index(dry_run: bool = False, gold_dir=None) -> int:
    """Rebuild the vector index from data/gold (or a supplied dir)."""
    docs = load_gold_tables(gold_dir)
    if dry_run:
        return len(docs)

    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    if not MISTRAL_API_KEY:
        vec = _fit_vectorizer([d.text for d in docs])
        joblib.dump(vec, TFIDF_PATH)

    vs = get_vectorstore()
    documents = [
        Document(
            page_content=d.text,
            metadata={**d.meta, "doc_id": d.doc_id, "fact_id": f"F{i:05d}"},
        )
        for i, d in enumerate(docs)
    ]
    vs.add_documents(documents)
    return len(documents)


@dataclass
class Evidence:
    fact_id: str
    doc_id: str
    row_ids: str
    citation_tag: str
    text: str
    score: float
    meta: dict


def retrieve(question: str, k: int | None = None) -> list[Evidence]:
    """Top-k facts for a question, with cosine similarity in [0, 1]."""
    k = k or TOP_K
    if not (CHROMA_DIR / "chroma.sqlite3").exists() and not MISTRAL_API_KEY:
        return _memory_retrieve(question, k)
    try:
        vs = get_vectorstore()
        results = vs.similarity_search_with_score(question, k=k)
    except Exception:
        if MISTRAL_API_KEY:
            raise
        return _memory_retrieve(question, k)
    evidence: list[Evidence] = []
    for doc, distance in results:
        score = max(0.0, min(1.0, 1.0 - float(distance)))
        evidence.append(Evidence(
            fact_id=doc.metadata.get("fact_id", ""),
            doc_id=doc.metadata.get("doc_id", ""),
            row_ids=doc.metadata.get("row_ids", ""),
            citation_tag=doc.metadata.get("citation_tag", ""),
            text=doc.page_content,
            score=score,
            meta=dict(doc.metadata),
        ))
    return evidence


def best_score(evidence: list[Evidence]) -> float:
    return max((e.score for e in evidence), default=0.0)
