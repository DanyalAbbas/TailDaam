"""Generate the clearly-labelled MOCK gold fixture for plumbing tests.

    python -m rag.make_mock

Only for local testing of RAG plumbing while the data team finishes
`make data`. Never used in model training or evaluation (hackathon rule 3).
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from rag.config import MOCK_GOLD_DIR


def mock_domestic() -> pd.DataFrame:
    # OGRA-style fortnightly notified petrol price (PKR/L), mocked.
    prices = [
        ("2026-07-01", "2026-07-15", 258.43),
        ("2026-07-16", "2026-07-31", 265.10),
        ("2026-08-01", "2026-08-15", 262.77),
        ("2026-08-16", "2026-08-31", 268.43),
        ("2026-09-01", "2026-09-15", 271.90),
        ("2026-09-16", "2026-09-30", 269.15),
        ("2026-10-01", "2026-10-15", 273.55),
    ]
    return pd.DataFrame(
        [
            dict(
                doc_id=f"MOCK-PK-{i:03d}",
                table_name="petrol_price_pk",
                row_ids=f"raw.pk.{b}..{e}",
                citation_tag="PBS-SPI",
                period_begin=b,
                period_end=e,
                entity="petrol_price",
                value=v,
                unit="PKR/L",
            )
            for i, (b, e, v) in enumerate(prices)
        ]
    )


def mock_brent() -> pd.DataFrame:
    brent = [
        ("2026-07-01", "2026-09-30", "avg_brent", 71.2),
        ("2026-10-01", "2026-10-18", "avg_brent", 68.4),
        ("2026-10-01", "2026-10-18", "avg_usd_pkr", 278.0),
    ]
    tags = ["EIA-Brent", "EIA-Brent", "SBP-FX"]
    return pd.DataFrame(
        [
            dict(
                doc_id=f"MOCK-BR-{i:03d}",
                table_name="brent_daily",
                row_ids=f"raw.{entity}.{b}..{e}",
                citation_tag=tags[i],
                period_begin=b,
                period_end=e,
                entity=entity,
                value=v,
                unit="USD/bbl" if entity == "avg_brent" else "PKR/USD",
            )
            for i, (b, e, entity, v) in enumerate(brent)
        ]
    )


def main() -> None:
    MOCK_GOLD_DIR.mkdir(parents=True, exist_ok=True)
    df1, df2 = mock_domestic(), mock_brent()
    try:
        df1.to_parquet(MOCK_GOLD_DIR / "mock_petrol_price_pk.parquet", index=False)
        df2.to_parquet(MOCK_GOLD_DIR / "mock_brent_daily.parquet", index=False)
    except ImportError:
        df1.to_csv(MOCK_GOLD_DIR / "mock_petrol_price_pk.csv", index=False)
        df2.to_csv(MOCK_GOLD_DIR / "mock_brent_daily.csv", index=False)

    reg = pd.DataFrame(
        [
            dict(
                citation_tag="PBS-SPI",
                publisher="Pakistan Bureau of Statistics [MOCK]",
                url="https://www.pbs.gov.pk/mock",
                licence="mock licence",
                accessed_at=date.today().isoformat(),
            ),
            dict(
                citation_tag="EIA-Brent",
                publisher="US Energy Information Administration [MOCK]",
                url="https://www.eia.gov/dnav/pet/hist/mock",
                licence="mock licence",
                accessed_at=date.today().isoformat(),
            ),
            dict(
                citation_tag="SBP-FX",
                publisher="State Bank of Pakistan [MOCK]",
                url="https://www.sbp.org.pk/ecodata/mock",
                licence="mock licence",
                accessed_at=date.today().isoformat(),
            ),
        ]
    )
    reg.to_csv(MOCK_GOLD_DIR / "citation_registry.csv", index=False)
    print("mock fixture written:",
          sorted(p.name for p in MOCK_GOLD_DIR.iterdir()))


if __name__ == "__main__":
    main()
