"""Citation registry: tag -> publisher, URL, licence.

The data team (or manifest tooling) writes `data/gold/citation_registry.csv`
with columns: citation_tag, publisher, url, licence, accessed_at.

If it is missing, the agent still works but marks citations as UNVERIFIED so
we never silently pretend a citation exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from rag.config import GOLD_DIR, MOCK_GOLD_DIR

REQUIRED = ["citation_tag", "publisher", "url", "licence", "accessed_at"]


@dataclass
class Citation:
    citation_tag: str
    publisher: str
    url: str
    licence: str
    accessed_at: str
    verified: bool


def load_citation_registry(gold_dir: Path | None = None) -> dict[str, Citation]:
    gold_dir = gold_dir or GOLD_DIR
    path = gold_dir / "citation_registry.csv"
    if not path.exists() and gold_dir == GOLD_DIR:
        path = MOCK_GOLD_DIR / "citation_registry.csv"

    registry: dict[str, Citation] = {}
    if not path.exists():
        return registry

    df = pd.read_csv(path)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"citation_registry.csv missing columns {missing}")
    for _, row in df.iterrows():
        registry[str(row["citation_tag"])] = Citation(
            citation_tag=str(row["citation_tag"]),
            publisher=str(row["publisher"]),
            url=str(row["url"]),
            licence=str(row["licence"]),
            accessed_at=str(row["accessed_at"]),
            verified=True,
        )
    return registry


def resolve_citation(tag: str, registry: dict[str, Citation]) -> Citation:
    if tag in registry:
        return registry[tag]
    return Citation(
        citation_tag=tag,
        publisher="UNVERIFIED publisher",
        url="UNVERIFIED url",
        licence="UNVERIFIED licence",
        accessed_at="UNVERIFIED access date",
        verified=False,
    )
