"""Data Quality Agent.

Runs deterministic validation rules on the clean layer, then decides for each
issue: FIX (safe automatic repair), FILL (documented imputation) or FLAG
(keep, mark, do not silently alter). Every decision is written to
artifacts/quality_decisions.csv with a human-readable reason, so the agent's
behaviour is auditable rather than a black box.

Design note: the agent never invents values. FILL is only forward-fill of a
known price for a missing weekly publication, and every filled row is marked
`filled=true` and excluded from model evaluation.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from common import ARTIFACTS, CLEAN, write_json

DECISIONS = ARTIFACTS / "quality_decisions.csv"

RANGES = {
    "petrol_super": (50.0, 800.0),
    "hsd": (50.0, 900.0),
}


@dataclass
class Decision:
    timestamp: str
    table: str
    rule: str
    action: str
    row_ids: str
    reason: str


def _log(decisions: list[Decision], table: str, rule: str, action: str,
         row_ids, reason: str) -> None:
    if not isinstance(row_ids, str):
        row_ids = ";".join(map(str, list(row_ids)[:50]))
    decisions.append(Decision(
        datetime.now(timezone.utc).isoformat(timespec="seconds"),
        table, rule, action, row_ids, reason,
    ))


def _schema_check(table: str, df: pd.DataFrame, required: list[str],
                  decisions: list[Decision]) -> list[str]:
    missing = [c for c in required if c not in df.columns]
    if missing:
        _log(decisions, table, "schema.required_columns", "FAIL",
             "", f"missing columns: {missing}")
    else:
        _log(decisions, table, "schema.required_columns", "PASS", "",
             f"all {len(required)} required columns present")
    return missing


def check_eia(df: pd.DataFrame, decisions: list[Decision]) -> pd.DataFrame:
    req = ["row_id", "date", "series_id", "value", "unit"]
    if _schema_check("eia_daily", df, req, decisions):
        return df
    df = df.copy()
    dup = df[df.duplicated("row_id", keep=False)]
    if len(dup):
        df = df.drop_duplicates("row_id", keep="first")
        _log(decisions, "eia_daily", "duplicates.row_id", "FIX", dup.row_id,
             f"removed {len(dup)} duplicate rows, kept first occurrence")
    else:
        _log(decisions, "eia_daily", "duplicates.row_id", "PASS", "",
             "row_id is unique")

    bad = df[~np.isfinite(df["value"]) | (df["value"] <= 0)]
    if len(bad):
        df = df.drop(bad.index)
        _log(decisions, "eia_daily", "range.positive", "FIX", bad.row_id,
             f"dropped {len(bad)} non-positive/non-finite prices")
    else:
        _log(decisions, "eia_daily", "range.positive", "PASS", "",
             "all prices are finite and positive")

    # Flag implausible daily jumps (>35% in one series step) but keep them.
    df = df.sort_values(["series_id", "date"])
    df["pct_change"] = df.groupby("series_id")["value"].pct_change()
    jumps = df[df["pct_change"].abs() > 0.35]
    if len(jumps):
        _log(decisions, "eia_daily", "outlier.daily_jump", "FLAG", jumps.row_id,
             f"{len(jumps)} daily moves exceed 35%; kept because energy spot "
             "markets can genuinely gap (e.g. 2020, 2022) - model uses robust loss")
    else:
        _log(decisions, "eia_daily", "outlier.daily_jump", "PASS", "", "")
    df = df.drop(columns=["pct_change"])
    return df


def check_pbs_weekly(df: pd.DataFrame, decisions: list[Decision]) -> pd.DataFrame:
    req = ["row_id", "week_end", "product", "price_pkr_l"]
    if _schema_check("pbs_weekly_pk", df, req, decisions):
        return df
    df = df.copy()
    dup = df[df.duplicated("row_id", keep=False)]
    if len(dup):
        df = df.drop_duplicates("row_id", keep="first")
        _log(decisions, "pbs_weekly_pk", "duplicates.row_id", "FIX", dup.row_id,
             f"removed {len(dup)} duplicate rows")
    else:
        _log(decisions, "pbs_weekly_pk", "duplicates.row_id", "PASS", "", "")

    flagged = []
    for product, (lo, hi) in RANGES.items():
        sub = df[df["product"] == product]
        bad = sub[(sub.price_pkr_l < lo) | (sub.price_pkr_l > hi)]
        if len(bad):
            flagged.extend(bad.row_id)
            _log(decisions, "pbs_weekly_pk", f"range.{product}", "FLAG",
                 bad.row_id,
                 f"price outside plausible [{lo},{hi}] PKR/L; kept but excluded "
                 "from model training")
        else:
            _log(decisions, "pbs_weekly_pk", f"range.{product}", "PASS", "",
                 f"all prices within [{lo},{hi}] PKR/L")
    df["flagged_range"] = df.row_id.isin(flagged)

    # Flag unusually large week-on-week domestic moves but keep the published
    # value. This catches the 9 Apr 2026 HSD jump (337.60 -> 522.29) without
    # pretending it is a missing value or a data-entry error.
    df = df.sort_values(["product", "week_end"])
    df["pct_change"] = df.groupby("product")["price_pkr_l"].pct_change()
    jumps = df[df["pct_change"].abs() > 0.35]
    df["flagged_jump"] = df.row_id.isin(jumps.row_id)
    if len(jumps):
        _log(decisions, "pbs_weekly_pk", "outlier.weekly_jump", "FLAG",
             jumps.row_id,
             f"{len(jumps)} weekly moves exceed 35%; kept and annotated because "
             "the published price is real and is not replaced")
    else:
        _log(decisions, "pbs_weekly_pk", "outlier.weekly_jump", "PASS", "", "")
    df = df.drop(columns=["pct_change"])

    # Completeness: expected weekly cadence per product.
    for product in df["product"].unique():
        sub = df[df["product"] == product].sort_values("week_end")
        if len(sub) < 2:
            continue
        gaps = pd.to_datetime(sub.week_end).diff().dt.days
        big = sub[gaps > 28]
        if len(big):
            _log(decisions, "pbs_weekly_pk", f"completeness.{product}", "FLAG",
                 big.row_id,
                 f"{len(big)} gaps longer than 28 days; NOT filled because "
                 "publication gaps are not the same as missing observations")
        else:
            _log(decisions, "pbs_weekly_pk", f"completeness.{product}", "PASS",
                 "", "weekly cadence has no gap > 28 days")

    # Staleness check
    latest = pd.to_datetime(df.week_end).max()
    age = (pd.Timestamp.utcnow().tz_localize(None) - latest).days
    action = "PASS" if age <= 14 else "FLAG"
    _log(decisions, "pbs_weekly_pk", "freshness.latest_observation", action,
         "", f"latest weekly observation is {latest.date()} ({age} days old)")
    return df


def check_worldbank(df: pd.DataFrame, decisions: list[Decision]) -> pd.DataFrame:
    req = ["row_id", "month", "commodity", "value"]
    if _schema_check("wb_monthly_energy", df, req, decisions):
        return df
    bad = df[~np.isfinite(df["value"]) | (df["value"] < 0)]
    if len(bad):
        df = df.drop(bad.index)
        _log(decisions, "wb_monthly_energy", "range.non_negative", "FIX",
             bad.row_id, f"dropped {len(bad)} non-finite/negative values")
    else:
        _log(decisions, "wb_monthly_energy", "range.non_negative", "PASS", "", "")
    return df


def run() -> dict:
    tables = {
        "eia_daily": CLEAN / "eia_daily.parquet",
        "pbs_weekly_pk": CLEAN / "pbs_weekly_pk.parquet",
        "wb_monthly_energy": CLEAN / "wb_monthly_energy.parquet",
    }
    decisions: list[Decision] = []
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "tables": {}}

    for name, path in tables.items():
        if not path.exists():
            _log(decisions, name, "existence", "FAIL", "", "clean table missing")
            report["tables"][name] = {"status": "FAIL", "rows": 0}
            continue
        df = pd.read_parquet(path)
        if name == "eia_daily":
            df = check_eia(df, decisions)
        elif name == "pbs_weekly_pk":
            df = check_pbs_weekly(df, decisions)
        else:
            df = check_worldbank(df, decisions)
        df.to_parquet(CLEAN / f"{name}.parquet", index=False)
        status = "PASS"
        if any(d.table == name and d.action in ("FAIL", "FLAG")
               for d in decisions):
            status = "WARN"
        report["tables"][name] = {"status": status, "rows": int(len(df)),
                                  "columns": list(df.columns)}

    fails = [d for d in decisions if d.action == "FAIL"]
    warns = [d for d in decisions if d.action == "FLAG"]
    report["status"] = "FAIL" if fails else ("WARN" if warns else "PASS")
    report["decisions"] = {"total": len(decisions), "fix": sum(
        d.action == "FIX" for d in decisions), "flag": len(warns),
        "fail": len(fails)}
    report["generated_at"] = datetime.now(timezone.utc).isoformat()

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    new = not DECISIONS.exists()
    with DECISIONS.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(asdict(decisions[0]).keys()))
        if new:
            w.writeheader()
        for d in decisions:
            w.writerow(asdict(d))
    write_json(ARTIFACTS / "quality_report.json", report)
    return report


if __name__ == "__main__":
    import json

    print(json.dumps(run(), indent=2))
