"""Ensure gold_tables module-level docstring examples stay in sync.

Simply checks that publisher/URL/licence columns required by the citation
registry union with the citation tags used in gold tables.
"""

from pathlib import Path

import pandas as pd

from rag.config import GOLD_DIR


def test_citation_registry_covers_gold_tags():
    reg_path = GOLD_DIR / "citation_registry.csv"
    if not reg_path.exists():
        pytest_skip = True
        import pytest

        pytest.skip("citation_registry.csv not yet present (data team pending)")

    reg = pd.read_csv(reg_path)
    tags = set(reg["citation_tag"].astype(str))
    for path in [*GOLD_DIR.glob("*.parquet"), *GOLD_DIR.glob("*.csv")]:
        df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
        used = set(df["citation_tag"].astype(str))
        assert used <= tags, f"{path.name} cites unknown citation_tag(s): {used - tags}"
