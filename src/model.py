"""Model layer: declared baseline, challenger, uncertainty, errors by group.

Primary task
------------
Forecast **next-month Brent realised volatility** (annualised %, from daily log
returns). Volatility is the risk dimension of Pakistan's oil import bill and,
unlike the price level, has genuine short-horizon predictability. The model is
a HAR-style ridge regression on lagged monthly, quarterly and annual realised
volatility.

Declared baseline: persistence (next month's volatility = this month's).
Challenger: ridge(alpha=10), pre-registered; no tuning on the held-out period.

We also report a price-level forecast attempt honestly: monthly average Brent
is close to a random walk and our challenger does not meaningfully beat
persistence, so no price-level win is claimed.

Outputs
-------
artifacts/model_metrics.json
artifacts/predictions.csv
artifacts/group_errors.csv
artifacts/pakistan_passthrough.json
artifacts/model_card.md
models/brent_model.joblib
"""

from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from common import ARTIFACTS, CLEAN, ROOT, write_json

MODELS = ROOT / "models"
MODELS.mkdir(exist_ok=True)

TARGET_SERIES = "brent_europe_spot"
ALPHA = 10.0


def _metrics(y, pred) -> dict:
    y = np.asarray(y, dtype=float)
    pred = np.asarray(pred, dtype=float)
    mae = float(mean_absolute_error(y, pred))
    rmse = float(np.sqrt(mean_squared_error(y, pred)))
    mape = float(np.mean(np.abs((y - pred) / np.maximum(y, 1e-9))) * 100)
    return {"mae": round(mae, 4), "rmse": round(rmse, 4),
            "mape_pct": round(mape, 3), "r2": round(float(r2_score(y, pred)), 4),
            "n": int(len(y))}


def realised_vol(eia: pd.DataFrame) -> pd.Series:
    b = eia[eia.series_name == TARGET_SERIES].copy()
    b["date"] = pd.to_datetime(b["date"])
    b = b.set_index("date")["value"].sort_index()
    r = np.log(b).diff()
    return (r.groupby(pd.Grouper(freq="MS")).std() * np.sqrt(252) * 100).dropna()


def vol_features(eia: pd.DataFrame) -> pd.DataFrame:
    rv = realised_vol(eia)
    f = pd.DataFrame(index=rv.index)
    for lag in (1, 2, 3):
        f[f"rv_lag{lag}"] = rv.shift(lag)
    for win in (3, 6, 12):
        f[f"rv_ma{win}"] = rv.rolling(win).mean().shift(1)
    f["rv_std6"] = rv.rolling(6).std().shift(1)
    f["target"] = rv
    return f.dropna()


def _price_level_attempt(eia: pd.DataFrame) -> dict:
    """Report honestly that the price level is near a random walk."""
    b = eia[eia.series_name == TARGET_SERIES].copy()
    b["date"] = pd.to_datetime(b["date"])
    m = b.set_index("date")["value"].sort_index().resample("MS").mean().dropna()
    f = pd.DataFrame(index=m.index)
    for lag in (1, 2, 3, 6, 12):
        f[f"l{lag}"] = m.shift(lag)
    for win in (3, 6, 12):
        f[f"ma{win}"] = m.rolling(win).mean().shift(1)
    for h in (1, 3, 12):
        f[f"ret{h}"] = m.pct_change(h).shift(1)
    f["target"] = m
    f = f.dropna()
    split = int(len(f) * 0.8)
    tr, te = f.iloc[:split], f.iloc[split:]
    cols = [c for c in f.columns if c != "target"]
    base = te["l1"]
    model = make_pipeline(StandardScaler(), Ridge(alpha=ALPHA)).fit(
        tr[cols], tr["target"])
    pred = model.predict(te[cols])
    return {"baseline_mae": round(float(mean_absolute_error(te.target, base)), 4),
            "challenger_mae": round(float(mean_absolute_error(te.target, pred)), 4),
            "n_test": int(len(te)),
            "note": "Price level is close to a random walk; no meaningful win "
                    "is claimed. Volatility is the modelled target."}


def train_primary(eia: pd.DataFrame) -> dict:
    feat = vol_features(eia)
    split = int(len(feat) * 0.8)
    train, test = feat.iloc[:split], feat.iloc[split:]
    cols = [c for c in feat.columns if c != "target"]
    Xtr, ytr = train[cols], train["target"]
    Xte, yte = test[cols], test["target"]

    baseline_pred = test["rv_lag1"].to_numpy()
    base_m = _metrics(yte, baseline_pred)

    model = make_pipeline(StandardScaler(), Ridge(alpha=ALPHA))
    model.fit(Xtr, ytr)
    pred = model.predict(Xte)
    model_m = _metrics(yte, pred)

    resid = yte.to_numpy() - pred
    lo, hi = np.quantile(resid, [0.05, 0.95])
    pred_df = pd.DataFrame({
        "date": yte.index.date,
        "actual": yte.to_numpy(),
        "prediction": np.round(pred, 4),
        "interval_low_90": np.round(pred + lo, 4),
        "interval_high_90": np.round(pred + hi, 4),
        "baseline_prediction": np.round(baseline_pred, 4),
    })
    cover = float(((yte.to_numpy() >= pred_df.interval_low_90.to_numpy()) &
                   (yte.to_numpy() <= pred_df.interval_high_90.to_numpy())).mean())
    pred_df.to_csv(ARTIFACTS / "predictions.csv", index=False)

    grp = pred_df.copy()
    grp["abs_error"] = (grp.actual - grp.prediction).abs()
    grp["year"] = pd.to_datetime(grp.date).dt.year
    grp["month"] = pd.to_datetime(grp.date).dt.month
    try:
        grp["vol_regime"] = pd.qcut(grp.actual, 3,
                                    labels=["low", "medium", "high"],
                                    duplicates="drop")
    except ValueError:
        grp["vol_regime"] = "all"
    rows = []
    for key in ("year", "month", "vol_regime"):
        for g, sub in grp.groupby(key, observed=True):
            rows.append({"group_type": key, "group": str(g), "n": len(sub),
                         "mae": round(float(sub.abs_error.mean()), 4),
                         "bias": round(float((sub.prediction - sub.actual).mean()), 4)})
    pd.DataFrame(rows).to_csv(ARTIFACTS / "group_errors.csv", index=False)

    improvement = (base_m["mae"] - model_m["mae"]) / base_m["mae"] * 100
    result = {
        "task": "next calendar month Brent realised volatility, annualised % "
                "(from daily log returns)",
        "target_series": TARGET_SERIES,
        "split": {
            "train_rows": int(len(train)), "test_rows": int(len(test)),
            "type": "chronological 80/20",
            "test_start": str(test.index.min().date()),
            "test_end": str(test.index.max().date()),
        },
        "baseline": {"name": "persistence (next month = this month's RV)", **base_m},
        "challenger": {"name": "har_ridge_alpha_10", **model_m},
        "selection": "pre-registered ridge(alpha=10) on HAR features; no "
                     "test-set tuning",
        "improvement_vs_baseline_pct": round(float(improvement), 3),
        "beats_baseline": bool(model_m["mae"] < base_m["mae"]),
        "uncertainty": {
            "interval": "90%",
            "residual_q05": round(float(lo), 4),
            "residual_q95": round(float(hi), 4),
            "empirical_coverage": round(cover, 4),
        },
        "price_level_attempt": _price_level_attempt(eia),
    }
    joblib.dump({"model": model, "features": cols, "best": "har_ridge_alpha_10"},
                MODELS / "brent_model.joblib")
    write_json(ARTIFACTS / "model_metrics.json", result)
    return result


def pakistan_passthrough(eia: pd.DataFrame, pbs: pd.DataFrame) -> dict:
    """Small-sample pass-through estimate, reported honestly as such."""
    b = eia[eia.series_id == "RBRTEd"].copy()
    b["date"] = pd.to_datetime(b.date)
    b = b.set_index("date")["value"].sort_index()
    brent_w = b.resample("W-THU").mean()

    pk = pbs[pbs["product"] == "petrol_super"].copy()
    if pk.empty:
        return {"available": False}
    pk["week_end"] = pd.to_datetime(pk.week_end)
    pk = pk.set_index("week_end").sort_index()
    df = pd.DataFrame({"petrol": pk.price_pkr_l, "brent": brent_w}).dropna()
    df["d_petrol"] = df.petrol.diff()
    df["d_brent"] = df.brent.diff()
    df["d_brent_lag1"] = df.d_brent.shift(1)
    d = df.dropna()
    if len(d) < 8:
        return {"available": False, "reason": "fewer than 8 overlapping weeks"}

    split = max(5, int(len(d) * 0.8))
    train, test = d.iloc[:split], d.iloc[split:]
    naive = np.zeros(len(test))
    coef = np.polyfit(train.d_brent_lag1, train.d_petrol, 1)
    model = coef[0] * test.d_brent_lag1 + coef[1]

    out = {
        "available": True,
        "note": "Small-sample domestic pass-through; not used to claim a "
                "beat-the-baseline result.",
        "n_overlapping_weeks": int(len(d)),
        "correlation_d_petrol_d_brent": round(float(
            d.d_petrol.corr(d.d_brent)), 4),
        "slope_pkr_per_usd": round(float(coef[0]), 4),
        "baseline_mae_pkr": round(float(np.mean(np.abs(test.d_petrol - naive))), 4),
        "passthrough_mae_pkr": round(float(np.mean(np.abs(test.d_petrol - model))), 4),
    }
    write_json(ARTIFACTS / "pakistan_passthrough.json", out)
    return out


def model_card(metrics: dict, passthrough: dict) -> str:
    b, c = metrics["baseline"], metrics["challenger"]
    p = metrics["price_level_attempt"]
    lines = [
        "# Model card",
        "",
        f"Task: {metrics['task']}",
        f"Split: {metrics['split']['type']} "
        f"({metrics['split']['train_rows']} train / {metrics['split']['test_rows']} test, "
        f"test {metrics['split']['test_start']} to {metrics['split']['test_end']})",
        "",
        "| model | MAE (vol points) | RMSE | MAPE % | R2 |",
        "|---|---|---|---|---|",
        f"| baseline: {b['name']} | {b['mae']} | {b['rmse']} | {b['mape_pct']} | {b['r2']} |",
        f"| challenger: {c['name']} | {c['mae']} | {c['rmse']} | {c['mape_pct']} | {c['r2']} |",
        "",
        f"Improvement over baseline: **{metrics['improvement_vs_baseline_pct']}% MAE** "
        f"(beats baseline: {metrics['beats_baseline']}).",
        f"90% interval empirical coverage: {metrics['uncertainty']['empirical_coverage']}.",
        "",
        "## Price-level attempt (reported, not claimed)",
        f"- persistence MAE {p['baseline_mae']} USD/bbl vs challenge MAE "
        f"{p['challenger_mae']} USD/bbl on {p['n_test']} held-out months.",
        f"- {p['note']}",
        "",
        "## Limitations",
        "- The target is global Brent volatility, not the Pakistani retail price; "
        "domestic prices are administered and change at fortnightly reviews.",
        "- The Pakistani weekly series is short (41 publication weeks). "
        "Pass-through estimates are reported as small-sample evidence only.",
        "- No causal claim is made: features are lagged volatility, not policy variables.",
    ]
    if passthrough.get("available"):
        lines += ["", "## Pakistan pass-through (descriptive)",
                  f"- overlapping weeks: {passthrough['n_overlapping_weeks']}",
                  f"- corr(weekly change petrol, weekly change Brent): "
                  f"{passthrough['correlation_d_petrol_d_brent']}",
                  f"- slope: {passthrough['slope_pkr_per_usd']} PKR per USD/bbl",
                  f"- naive MAE {passthrough['baseline_mae_pkr']} PKR vs "
                  f"pass-through MAE {passthrough['passthrough_mae_pkr']} PKR "
                  "(not a claimed win)"]
    text = "\n".join(lines) + "\n"
    (ARTIFACTS / "model_card.md").write_text(text, encoding="utf-8")
    return text


def main() -> int:
    eia = pd.read_parquet(CLEAN / "eia_daily.parquet")
    pbs = pd.read_parquet(CLEAN / "pbs_weekly_pk.parquet")
    metrics = train_primary(eia)
    passthrough = pakistan_passthrough(eia, pbs)
    model_card(metrics, passthrough)
    print(json.dumps(metrics, indent=2))
    print(json.dumps(passthrough, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
