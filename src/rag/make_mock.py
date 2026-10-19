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
    # Pakistani notified petrol price (PKR/L) — fortnightly, OGRA-notified.
    # Real anchor points from PBS weekly SPI (Jan 2026: 254.87, Oct 2026: 264.74).
    # Intermediate fortnights are realistic OGRA-notified values.
    prices = [
        ("2024-01-01", "2024-01-15", 267.34),
        ("2024-01-16", "2024-01-31", 272.86),
        ("2024-02-01", "2024-02-15", 272.86),
        ("2024-02-16", "2024-02-29", 279.75),
        ("2024-03-01", "2024-03-15", 279.75),
        ("2024-03-16", "2024-03-31", 279.75),
        ("2024-04-01", "2024-04-15", 293.94),
        ("2024-04-16", "2024-04-30", 293.94),
        ("2024-05-01", "2024-05-15", 288.49),
        ("2024-05-16", "2024-05-31", 288.49),
        ("2024-06-01", "2024-06-15", 268.36),
        ("2024-06-16", "2024-06-30", 268.36),
        ("2024-07-01", "2024-07-15", 265.61),
        ("2024-07-16", "2024-07-31", 265.61),
        ("2024-08-01", "2024-08-15", 269.43),
        ("2024-08-16", "2024-08-31", 269.43),
        ("2024-09-01", "2024-09-15", 255.00),
        ("2024-09-16", "2024-09-30", 255.00),
        ("2024-10-01", "2024-10-15", 247.03),
        ("2024-10-16", "2024-10-31", 247.03),
        ("2024-11-01", "2024-11-15", 248.38),
        ("2024-11-16", "2024-11-30", 248.38),
        ("2024-12-01", "2024-12-15", 252.10),
        ("2024-12-16", "2024-12-31", 252.10),
        ("2025-01-01", "2025-01-15", 256.13),
        ("2025-01-16", "2025-01-31", 256.13),
        ("2025-02-01", "2025-02-15", 257.13),
        ("2025-02-16", "2025-02-28", 257.13),
        ("2025-03-01", "2025-03-15", 255.63),
        ("2025-03-16", "2025-03-31", 255.63),
        ("2025-04-01", "2025-04-15", 254.63),
        ("2025-04-16", "2025-04-30", 254.63),
        ("2025-05-01", "2025-05-15", 252.63),
        ("2025-05-16", "2025-05-31", 252.63),
        ("2025-06-01", "2025-06-15", 254.63),
        ("2025-06-16", "2025-06-30", 254.63),
        ("2025-07-01", "2025-07-15", 258.43),
        ("2025-07-16", "2025-07-31", 265.10),
        ("2025-08-01", "2025-08-15", 262.77),
        ("2025-08-16", "2025-08-31", 268.43),
        ("2025-09-01", "2025-09-15", 271.90),
        ("2025-09-16", "2025-09-30", 269.15),
        ("2025-10-01", "2025-10-15", 273.55),
        ("2025-10-16", "2025-10-31", 263.45),
        ("2025-11-01", "2025-11-15", 265.45),
        ("2025-11-16", "2025-11-30", 263.45),
        ("2025-12-01", "2025-12-15", 253.17),
        ("2025-12-16", "2025-12-31", 253.17),
        ("2026-01-01", "2026-01-15", 254.87),   # PBS SPI Jan 2026
        ("2026-01-16", "2026-01-31", 254.87),
        ("2026-02-01", "2026-02-15", 255.87),
        ("2026-02-16", "2026-02-28", 255.87),
        ("2026-03-01", "2026-03-15", 258.87),
        ("2026-03-16", "2026-03-31", 258.87),
        ("2026-04-01", "2026-04-15", 266.87),
        ("2026-04-16", "2026-04-30", 266.87),
        ("2026-05-01", "2026-05-15", 266.87),
        ("2026-05-16", "2026-05-31", 266.87),
        ("2026-06-01", "2026-06-15", 264.87),
        ("2026-06-16", "2026-06-30", 264.87),
        ("2026-07-01", "2026-07-15", 264.87),
        ("2026-07-16", "2026-07-31", 264.87),
        ("2026-08-01", "2026-08-15", 264.87),
        ("2026-08-16", "2026-08-31", 264.87),
        ("2026-09-01", "2026-09-15", 264.87),
        ("2026-09-16", "2026-09-30", 264.87),
        ("2026-10-01", "2026-10-15", 264.74),   # PBS SPI Oct 2026
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
                entity="petrol_price_pk",
                value=v,
                unit="PKR/L",
            )
            for i, (b, e, v) in enumerate(prices)
        ]
    )


def mock_brent() -> pd.DataFrame:
    brent = [
        ("2026-01-01", "2026-01-31", "avg_brent", 74.5),
        ("2026-02-01", "2026-02-28", "avg_brent", 72.1),
        ("2026-03-01", "2026-03-31", "avg_brent", 70.8),
        ("2026-04-01", "2026-04-30", "avg_brent", 68.2),
        ("2026-05-01", "2026-05-31", "avg_brent", 64.5),
        ("2026-06-01", "2026-06-30", "avg_brent", 67.3),
        ("2026-07-01", "2026-07-31", "avg_brent", 69.1),
        ("2026-08-01", "2026-08-31", "avg_brent", 70.5),
        ("2026-09-01", "2026-09-30", "avg_brent", 68.9),
        ("2026-10-01", "2026-10-18", "avg_brent", 66.4),
    ]
    return pd.DataFrame(
        [
            dict(
                doc_id=f"MOCK-BR-{i:03d}",
                table_name="brent_daily",
                row_ids=f"raw.avg_brent.{b}..{e}",
                citation_tag="EIA-Brent",
                period_begin=b,
                period_end=e,
                entity="avg_brent",
                value=v,
                unit="USD/bbl",
            )
            for i, (b, e, _entity, v) in enumerate(brent)
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
