"""Minimal tests for the honesty gate and gold-table contract.
Model calls are mocked — the point is plumbing correctness, not LLM quality.
"""

from pathlib import Path

import pandas as pd
import pytest

from rag.gold_tables import REQUIRED_COLUMNS, load_gold_tables
from rag.retrieval import Evidence
from rag.verify import verify_answer


@pytest.fixture(scope="module")
def mock_gold_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("mock_gold")
    df = pd.DataFrame(
        [
            dict(
                doc_id="MOCK-1",
                table_name="petrol_price_pk",
                row_ids="raw.pk.2026-09-01",
                citation_tag="PBS-SPI",
                period_begin="2026-09-01",
                period_end="2026-09-15",
                entity="petrol_price",
                value=271.90,
                unit="PKR/L",
            ),
            dict(
                doc_id="MOCK-2",
                table_name="brent_daily",
                row_ids="raw.brent.2026-10-01..2026-10-18",
                citation_tag="EIA-Brent",
                period_begin="2026-10-01",
                period_end="2026-10-18",
                entity="avg_brent",
                value=68.4,
                unit="USD/bbl",
            ),
        ]
    )
    df.to_parquet(d / "mock_facts.parquet", index=False)
    return d


def test_contract_missing_column_raises(mock_gold_dir):
    df = pd.read_parquet(next(mock_gold_dir.glob("*.parquet")))
    bad = df.drop(columns=["row_ids"])
    bad_path = mock_gold_dir / "bad.parquet"
    bad.to_parquet(bad_path, index=False)
    with pytest.raises(ValueError, match="row_ids"):
        load_gold_tables(mock_gold_dir)
    bad_path.unlink()


def test_load_contract_happy_path(mock_gold_dir):
    docs = load_gold_tables(mock_gold_dir)
    assert len(docs) == 2
    d = docs[0]
    assert d.row_ids == "raw.pk.2026-09-01"
    assert d.citation_tag == "PBS-SPI"
    assert "271.9" in d.text


def test_verify_passes_cited_answer():
    evidence = [
        "Fact: petrol_price was 271.9 PKR/L for period 2026-09-01 to 2026-09-15 "
        "(citation: PBS-SPI)."
    ]
    answer = "Petrol is PKR 271.9/L [PBS-SPI]."
    ver = verify_answer(answer, evidence, valid_tags={"PBS-SPI"}, refusal=False)
    assert ver.ok, ver


def test_verify_allows_correctly_rounded_number():
    evidence = [
        "Fact: model MAE improvement was 7.269 % and diesel was 402.5 PKR/L "
        "(citation: MODEL-CARD)."
    ]
    answer = "Improvement is 7.27 % [MODEL-CARD]; diesel is 402.50 PKR/L [MODEL-CARD]."
    ver = verify_answer(answer, evidence, valid_tags={"MODEL-CARD"}, refusal=False)
    assert ver.ok, ver


def test_verify_catches_hallucinated_number():
    evidence = [
        "Fact: petrol_price was 271.9 PKR/L for period 2026-09-01 to 2026-09-15 "
        "(citation: PBS-SPI)."
    ]
    answer = "Petrol is PKR 273.55/L [PBS-SPI]."
    ver = verify_answer(answer, evidence, valid_tags={"PBS-SPI"}, refusal=False)
    assert not ver.ok and "273.55" in ver.unverified_numbers


def test_verify_catches_unknown_citation():
    evidence = [
        "Fact: petrol_price was 271.9 PKL/L (citation: PBS-SPI)."
    ]
    answer = "Petrol is PKR 271.9/L [MADE-UP-TAG]."
    ver = verify_answer(answer, evidence, valid_tags={"PBS-SPI"}, refusal=False)
    assert not ver.ok and ver.unknown_citations == ["MADE-UP-TAG"]


def test_refusal_message_is_structural():
    # refusal=True path short-circuits verification, still ok
    ver = verify_answer("", evidence_texts=[], valid_tags=set(), refusal=True)
    assert ver.ok


def _ev(meta: dict, text: str, score: float) -> Evidence:
    from rag.gold_tables import EvidenceDoc

    doc = EvidenceDoc(
        doc_id=meta.get("doc_id", "D"),
        table_name=meta.get("table_name", "t"),
        row_ids=meta.get("row_ids", "r"),
        citation_tag=meta.get("citation_tag", "c"),
        period_begin=meta.get("period_begin", "p"),
        period_end=meta.get("period_end", "p"),
        entity=meta.get("entity", "e"),
        value=meta.get("value", "0"),
        unit=meta.get("unit", "u"),
        text=text,
        meta=meta,
    )
    return Evidence(
        fact_id="F1",
        doc_id=doc.doc_id,
        row_ids=doc.row_ids,
        citation_tag=doc.citation_tag,
        text=text,
        score=score,
        meta=doc.meta,
    )
