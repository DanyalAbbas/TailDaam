"""Retrieval: Chroma vector store over gold-table facts.

Each indexed chunk is one gold-table fact with full metadata (row_ids,
citation_tag) so whatever the LLM quotes is traceable by construction.
"""

from __future__ import annotations

from dataclasses import dataclass

from chromadb import PersistentClient
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_mistralai import MistralAIEmbeddings

from rag.config import (
    CHROMA_DIR,
    MISTRAL_API_KEY,
    MISTRAL_EMBED_MODEL,
    TOP_K,
)
from rag.gold_tables import EvidenceDoc, load_gold_tables

COLLECTION = "insight_agent_facts"


import os

def get_embedding_fn():
    if MISTRAL_API_KEY:
        return MistralAIEmbeddings(model=MISTRAL_EMBED_MODEL, api_key=MISTRAL_API_KEY)
    # Offline plumbing fallback (clearly labelled, NOT for eval).
    if os.getenv("RAG_ALLOW_MOCK_EMBEDDINGS") == "1":
        import hashlib

        class _MockEmbeddings:
            size = 64

            def embed_documents(self, texts):
                return [self.embed_query(t) for t in texts]

            def embed_query(self, text):
                h = hashlib.sha256(text.encode("utf-8")).digest()
                # Repeat hash to reach desired dimension; clearly a placeholder.
                vec = [ (h[i % len(h)] / 255.0) for i in range(self.size) ]
                return vec

        return _MockEmbeddings()
    raise RuntimeError("MISTRAL_API_KEY not set (needed for mistral-embed)")


def get_vectorstore():
    embeddings = get_embedding_fn()
    return Chroma(
        collection_name=COLLECTION,
        embedding_function=embeddings,
        persist_directory=str(CHROMA_DIR),
    )


def build_index(dry_run: bool = False, gold_dir=None) -> int:
    """Rebuild the vector index from data/gold (or a supplied dir). Idempotent."""
    docs = load_gold_tables(gold_dir)
    if dry_run:
        return len(docs)

    import shutil

    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    vs = get_vectorstore()
    documents = [
        Document(
            page_content=d.text,
            metadata={
                **d.meta,
                "doc_id": d.doc_id,
                "fact_id": f"F{i:05d}",
            },
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
    """Top-k facts for a question with similarity scores (0-1, higher = closer)."""
    vs = get_vectorstore()
    k = k or TOP_K
    results = vs.similarity_search_with_score(question, k=k)
    evidence: list[Evidence] = []
    for doc, distance in results:
        # Chroma default metric is l2 (lower = closer). Convert to a 0-1
        # closeness score so the refusal gate is intuitive and tunable.
        score = max(0.0, 1.0 / (1.0 + distance)) if distance >= 0 else 1.0
        evidence.append(
            Evidence(
                fact_id=doc.metadata.get("fact_id", ""),
                doc_id=doc.metadata.get("doc_id", ""),
                row_ids=doc.metadata.get("row_ids", ""),
                citation_tag=doc.metadata.get("citation_tag", ""),
                text=doc.page_content,
                score=score,
                meta=dict(doc.metadata),
            )
        )
    return evidence


def best_score(evidence: list[Evidence]) -> float:
    return max((e.score for e in evidence), default=0.0)
