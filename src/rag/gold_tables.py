"""Gold table contract and loader.

GOLD TABLE CONTRACT
===================
Every file `data/gold/*.parquet` must be a table the Insight Agent can quote
from. Required columns:

    doc_id        str   unique id for one quoted row, e.g. "PB-2011-42"
    table_name    str   name of the gold table the row belongs to
    row_ids       list[str] / str  raw-layer row ids this fact is derived from
    citation_tag  str   short cite key used in answers, e.g. "PBS-SPI" or
                          "EIA-Brent" (grouped with tag_registry.csv entries:
                          citation_tag, publisher, url, licence, accessed_at)
    period_begin  datetime-ish  inclusive start of the period the fact covers
    period_end    datetime-ish  inclusive end (may equal begin for point facts)
    entity        str   what the fact is about, e.g. "petrol_price", "brent"
    value         float the number itself
    unit          str   e.g. "PKR/L", "USD/bbl", "%"

Optional metadata columns (series_name, region, notes, ...) are preserved as
Chroma metadata so the retriever can filter on them.

The loader refuses to index a file missing required columns, so a broken
`make data` can never silently produce a RAG that quotes untraceable numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterator

import pandas as pd

from rag.config import GOLD_DIR, MOCK_GOLD_DIR

REQUIRED_COLUMNS = [
    "doc_id",
    "table_name",
    "row_ids",
    "citation_tag",
    "period_begin",
    "period_end",
    "entity",
    "value",
    "unit",
]


@dataclass
class EvidenceDoc:
    """One quoted fact ready for the vector store."""

    doc_id: str
    table_name: str
    row_ids: str
    citation_tag: str
    period_begin: str
    period_end: str
    entity: str
    value: str
    unit: str
    text: str
    meta: dict = field(default_factory=dict)


def _load_one(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"{path.name}: gold table missing required columns {missing}. "
            "Fix the gold builder or check the contract in gold_tables.py."
        )
    df = df.copy()
    df["row_ids"] = df["row_ids"].apply(_canonical_row_ids)
    df["period_begin"] = df["period_begin"].apply(_iso_date)
    df["period_end"] = df["period_end"].apply(_iso_date)
    if df["doc_id"].duplicated().any():
        raise ValueError(f"{path.name}: doc_id must be unique")
    return df


def _canonical_row_ids(v) -> str:
    if isinstance(v, str):
        if v.startswith("["):
            import json

            return ",".join(json.loads(v))
        return v
    if isinstance(v, (list, tuple)):
        return ",".join(map(str, v))
    return str(v)


def _iso_date(v) -> str:
    if isinstance(v, (date, datetime)):
        return v.date().isoformat() if isinstance(v, datetime) else v.isoformat()
    return str(pd.Timestamp(v).date())


def _row_to_doc(row: pd.Series) -> EvidenceDoc:
    entity = str(row["entity"])
    period = (
        row["period_begin"]
        if row["period_begin"] == row["period_end"]
        else f"{row['period_begin']} to {row['period_end']}"
    )
    text = (
        f"Fact: {entity} was {row['value']:g} {row['unit']} for period {period} "
        f"(citation: {row['citation_tag']})."
    )
    extra = {k: str(v) for k, v in row.items() if k not in REQUIRED_COLUMNS}
    return EvidenceDoc(
        doc_id=str(row["doc_id"]),
        table_name=str(row["table_name"]),
        row_ids=str(row["row_ids"]),
        citation_tag=str(row["citation_tag"]),
        period_begin=str(row["period_begin"]),
        period_end=str(row["period_end"]),
        entity=entity,
        value=f"{row['value']:g}",
        unit=str(row["unit"]),
        text=text,
        meta={
            "table_name": str(row["table_name"]),
            "row_ids": str(row["row_ids"]),
            "citation_tag": str(row["citation_tag"]),
            "entity": entity,
            "period_begin": str(row["period_begin"]),
            "period_end": str(row["period_end"]),
            "value": f"{row['value']:g}",
            "unit": str(row["unit"]),
            **extra,
        },
    )


def load_gold_tables(gold_dir: Path | None = None) -> list[EvidenceDoc]:
    """Load every gold table in the directory. Raises on contract violations."""
    gold_dir = gold_dir or GOLD_DIR
    docs: list[EvidenceDoc] = []
    paths = sorted(
        p for p in [*gold_dir.glob("*.parquet"), *gold_dir.glob("*.csv")]
        if p.name != "citation_registry.csv" and not p.name.startswith("manifest")
    )
    if not paths:
        raise FileNotFoundError(
            f"No gold tables in {gold_dir}. Run `make data` (data team) or use "
            "the mock fixture for plumbing tests."
        )
    for path in paths:
        df = _load_one(path)
        docs.extend(_row_to_doc(row) for _, row in df.iterrows())
    return docs


def load_mock_gold_tables() -> list[EvidenceDoc]:
    """Mock fixture, clearly labelled MOCK — only for plumbing tests."""
    return load_gold_tables(MOCK_GOLD_DIR)


def iter_table_names(gold_dir: Path | None = None) -> Iterator[str]:
    gold_dir = gold_dir or GOLD_DIR
    for path in sorted([*gold_dir.glob("*.parquet"), *gold_dir.glob("*.csv")]):
        yield path.name
