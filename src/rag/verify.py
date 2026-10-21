"""Honesty gate: verify that the LLM answer only quotes gold-table facts.

Hackathon rule 1: no number may come from the LLM. So after generation we:

1. Extract every number the model wrote.
2. Check each appears in the retrieved evidence facts (as text or metadata).
3. Check every citation tag it used exists in the evidence, and that facts
   the answer states are traceable.
4. If verification fails, we log the violation, the answer is discarded and a
   refusal is returned instead. The log lands in `artifacts/rag_integrity.csv`
   so the repo's honesty story is auditable.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from rag.config import BASE_DIR

ARTIFACTS_DIR = BASE_DIR / "artifacts"
INTEGRITY_LOG = ARTIFACTS_DIR / "rag_integrity.csv"

NUMBER_RE = re.compile(
    r"\d[\d,]*(?:\.\d+)?"  # 268.43 / 1,200 / 45
)

CITE_TAG_IN_ANSWER_RE = re.compile(r"\[([A-Za-z0-9_\-]+)\]")


@dataclass
class Verification:
    ok: bool
    unverified_numbers: list[str]
    unknown_citations: list[str]
    refusal: bool


def _numbers_in_evidence(evidence_texts: list[str]) -> set[str]:
    tokens: set[str] = set()
    for text in evidence_texts:
        for tok in NUMBER_RE.findall(text):
            tokens.add(tok)
            # allow the formatted variant with and without thousand separators
            tokens.add(tok.replace(",", ""))
    return tokens


def _as_float(token: str) -> float | None:
    try:
        return float(token.replace(",", ""))
    except ValueError:
        return None


def _is_supported_number(token: str, ev_tokens: set[str],
                         ev_values: list[float]) -> bool:
    """Exact match, or a correctly rounded rendering of an evidence value.

    The extractive answer formats 402.5 as 402.50 and 7.269 as 7.27. Those are
    the same number, not a new claim, so allow half a unit in the last printed
    decimal place. A number that cannot be rounded from a retrieved fact still
    fails the gate.
    """
    if token in ev_tokens or token.replace(",", "") in ev_tokens:
        return True
    value = _as_float(token)
    if value is None:
        return False
    decimals = len(token.split(".", 1)[1]) if "." in token else 0
    tolerance = 0.5 * (10 ** -decimals) + 1e-12
    return any(abs(value - ev) <= tolerance for ev in ev_values)


def verify_answer(
    answer: str,
    evidence_texts: list[str],
    valid_tags: set[str],
    refusal: bool,
) -> Verification:
    ev_numbers = _numbers_in_evidence(evidence_texts)
    ev_values = [v for v in (_as_float(t) for t in ev_numbers) if v is not None]
    answer_numbers = NUMBER_RE.findall(answer)

    unverified = [
        n for n in answer_numbers
        if not _is_supported_number(n, ev_numbers, ev_values)
    ]
    # Dates mentioned like 2026-10-19 or years are numbers too; strip common
    # non-fact numbers: pure years 19xx/20xx are allowed only with context,
    # but we stay strict — years must exist in evidence text as well.

    used_tags = set(CITE_TAG_IN_ANSWER_RE.findall(answer))
    unknown_citations = sorted(used_tags - valid_tags) if used_tags else []

    ok = refusal or (not unverified and not unknown_citations)
    return Verification(
        ok=ok,
        unverified_numbers=unverified,
        unknown_citations=unknown_citations,
        refusal=refusal,
    )


def log_verification(question: str, ver: Verification, lang: str) -> None:
    """Append one line to artifacts/rag_integrity.csv (audit trail)."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    new_file = not INTEGRITY_LOG.exists()
    with INTEGRITY_LOG.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new_file:
            w.writerow(
                ["timestamp", "lang", "passed", "refusal",
                 "unverified_numbers", "unknown_citations", "question"]
            )
        w.writerow([
            datetime.now().isoformat(timespec="seconds"),
            lang,
            ver.ok,
            ver.refusal,
            ";".join(ver.unverified_numbers),
            ";".join(ver.unknown_citations),
            question.replace("\n", " ")[:200],
        ])
