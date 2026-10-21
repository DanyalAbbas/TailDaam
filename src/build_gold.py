"""Build gold tables: the only layer the Insight Agent may quote.

Every gold row carries:
  - doc_id       stable id
  - table_name   gold table it belongs to
  - row_ids      ids of the clean/raw rows it was derived from
  - citation_tag key into data/gold/citation_registry.csv
  - period_begin / period_end
  - entity, value, unit

The RAG loader refuses to index a table that breaks this contract.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd

from common import ARTIFACTS, CLEAN, GOLD, ROOT, utc_now

ACCESSED = datetime.now(timezone.utc).date().isoformat()


def petro_weekly(pbs: pd.DataFrame) -> pd.DataFrame:
    rows = []
    label = {"petrol_super": "Petrol Super price in Pakistan",
             "hsd": "High-speed diesel price in Pakistan"}
    for _, r in pbs.iterrows():
        flag = bool(r.get("flagged_range", False))
        jump = bool(r.get("flagged_jump", False))
        rows.append({
            "doc_id": f"PKW-{r['product']}-{r['week_end']}",
            "table_name": "pk_petrol_weekly",
            "row_ids": r["row_id"],
            "citation_tag": "PBS-SPI",
            "period_begin": r["week_end"],
            "period_end": r["week_end"],
            "entity": label[r["product"]],
            "value": round(float(r["price_pkr_l"]), 2),
            "unit": "PKR/L",
            "notes": f"Weekly SPI report for the week ended {r['week_end']}."
                     + (" Quality flag: value outside expected range." if flag else "")
                     + (" Quality flag: unusually large week-on-week move." if jump else ""),
        })
    return pd.DataFrame(rows)


def city_monthly(city: pd.DataFrame) -> pd.DataFrame:
    if city.empty:
        return pd.DataFrame()
    pretty = lambda s: s.replace("-", "").strip()
    rows = []
    label = {"petrol_super": "Petrol Super price", "hsd": "High-speed diesel price"}
    for _, r in city.iterrows():
        place = pretty(r["city"])
        rows.append({
            "doc_id": f"PKC-{r['product']}-{place}-{r['month']}",
            "table_name": "pk_city_prices_monthly",
            "row_ids": r["row_id"],
            "citation_tag": "PBS-SPI",
            "period_begin": f"{r['month']}-01",
            "period_end": f"{r['month']}-01",
            "entity": f"{label[r['product']]} in {place}",
            "value": round(float(r["price_pkr_l"]), 2),
            "unit": "PKR/L",
            "notes": f"Monthly average price, {r['month']}, city={place}",
        })
    return pd.DataFrame(rows)


def eia_monthly(eia: pd.DataFrame, start: str = "2018-01-01") -> pd.DataFrame:
    df = eia.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df[df.date >= start]
    df["month"] = df.date.dt.to_period("M").astype(str)
    rows = []
    for (series, month), g in df.groupby(["series_name", "month"]):
        rows.append({
            "doc_id": f"EIA-{series}-{month}",
            "table_name": "global_petroleum_monthly",
            "row_ids": ";".join(g.row_id.tolist()),
            "citation_tag": "EIA-PETRO",
            "period_begin": f"{month}-01",
            "period_end": g.date.max().date().isoformat(),
            "entity": series,
            "value": round(float(g.value.mean()), 4),
            "unit": g.unit.iloc[0],
            "notes": f"Monthly mean of {len(g)} daily observations for {series}",
        })
    return pd.DataFrame(rows)


def wb_monthly(wb: pd.DataFrame, start: str = "2018-01") -> pd.DataFrame:
    df = wb[wb.month >= start].copy()
    rows = []
    for _, r in df.iterrows():
        rows.append({
            "doc_id": f"WB-{r['row_id'].split(':', 2)[-1]}-{r['month']}",
            "table_name": "worldbank_energy_monthly",
            "row_ids": r["row_id"],
            "citation_tag": "WB-PINK",
            "period_begin": f"{r['month']}-01",
            "period_end": f"{r['month']}-01",
            "entity": r["commodity"],
            "value": round(float(r["value"]), 4),
            "unit": r["unit"],
            "notes": "World Bank Pink Sheet monthly price",
        })
    return pd.DataFrame(rows)


def model_facts() -> pd.DataFrame:
    path = ARTIFACTS / "model_metrics.json"
    pt_path = ARTIFACTS / "pakistan_passthrough.json"
    if not path.exists():
        return pd.DataFrame()
    m = json.loads(path.read_text())
    rows = [
        ("model-baseline-mae", "Baseline persistence MAE (annualised volatility points)", m["baseline"]["mae"],
         "annualised vol points",
         "Declared baseline (persistence) mean absolute error for next-month "
         "Brent realised volatility on the held-out test set"),
        ("model-challenger-mae", "Challenger HAR ridge MAE (annualised volatility points)",
         m["challenger"]["mae"], "annualised vol points",
         "HAR-style ridge challenger mean absolute error on the held-out test set"),
        ("model-improvement", "Model MAE improvement over baseline",
         m["improvement_vs_baseline_pct"], "%",
         "Relative MAE improvement of the challenger over the declared baseline "
         "for next-month Brent volatility"),
        ("model-coverage", "Empirical coverage of the 90% prediction interval",
         m["uncertainty"]["empirical_coverage"] * 100, "%",
         "Empirical coverage of the nominal 90% prediction interval"),
    ]
    if pt_path.exists():
        pt = json.loads(pt_path.read_text())
        if pt.get("available"):
            rows.append(("model-passthrough-corr", "Correlation of weekly Pakistani petrol change with Brent change",
                         pt["correlation_d_petrol_d_brent"], "corr",
                         "Correlation between weekly Pakistani petrol price "
                         "changes and weekly Brent changes"))
    out = []
    for doc_id, entity, value, unit, note in rows:
        out.append({
            "doc_id": doc_id,
            "table_name": "model_evaluation",
            "row_ids": "artifacts/model_metrics.json",
            "citation_tag": "MODEL-CARD",
            "period_begin": m["split"].get("test_start", "2020-01-01"),
            "period_end": m["split"].get("test_end", utc_now()[:10]),
            "entity": entity,
            "value": value,
            "unit": unit,
            "notes": note,
        })
    return pd.DataFrame(out)


def citation_registry() -> pd.DataFrame:
    return pd.DataFrame([
        dict(citation_tag="PBS-SPI",
             publisher="Pakistan Bureau of Statistics",
             url="https://www.pbs.gov.pk/price-statistics/",
             licence="Government of Pakistan open publication",
             accessed_at=ACCESSED),
        dict(citation_tag="EIA-PETRO",
             publisher="U.S. Energy Information Administration",
             url="https://www.eia.gov/dnav/pet/pet_pri_spt_s1_d.htm",
             licence="public-domain (US Government work)",
             accessed_at=ACCESSED),
        dict(citation_tag="WB-PINK",
             publisher="World Bank",
             url="https://www.worldbank.org/en/research/commodity-markets",
             licence="CC BY 4.0",
             accessed_at=ACCESSED),
        dict(citation_tag="MODEL-CARD",
             publisher="HACK INSIGHT submission (own model artifact)",
             url="artifacts/model_card.md",
             licence="internal artifact, generated by this repository",
             accessed_at=ACCESSED),
    ])


def main() -> int:
    GOLD.mkdir(parents=True, exist_ok=True)
    pbs = pd.read_parquet(CLEAN / "pbs_weekly_pk.parquet")
    eia = pd.read_parquet(CLEAN / "eia_daily.parquet")
    wb = pd.read_parquet(CLEAN / "wb_monthly_energy.parquet")
    city = pd.read_parquet(CLEAN / "pbs_monthly_city.parquet")

    tables = {
        "pk_petrol_weekly": petro_weekly(pbs),
        "pk_city_prices_monthly": city_monthly(city),
        "global_petroleum_monthly": eia_monthly(eia),
        "worldbank_energy_monthly": wb_monthly(wb),
        "model_evaluation": model_facts(),
    }
    total = 0
    for name, df in tables.items():
        if df.empty:
            print(f"WARN: gold table {name} empty")
            continue
        df.to_csv(GOLD / f"{name}.csv", index=False)
        total += len(df)
        print(f"gold/{name}.csv: {len(df):,} rows")
    citation_registry().to_csv(GOLD / "citation_registry.csv", index=False)
    print(f"total gold facts: {total:,}")
    if total < 100:
        raise SystemExit("gold layer too small - refusing to build RAG index")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
