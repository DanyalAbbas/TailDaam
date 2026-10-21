"""FastAPI service for the Insight Agent + the static frontend.

API
---
GET  /health                 status, embedding mode, facts indexed
GET  /api/overview           latest prices, weekly series, city table, data health
GET  /api/model              metrics, predictions, group errors, model card
POST /ask                    answer + citations + row_ids + confidence
POST /ask/stream             Server-Sent Events stream of the verified answer

The single-page frontend in ``frontend/dist`` is served with ``app.frontend()``
(FastAPI >= 0.147). API routes always win; the frontend handles everything else.
This is the same app that runs on FastAPI Cloud.
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Literal

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field

from rag.config import GROQ_API_KEY, GROQ_MODEL
from rag.rag import generate_answer
from rag.retrieval import embedding_mode, indexed_fact_count

APP_VERSION = "1.0.0"
ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "data" / "gold"
ARTIFACTS = ROOT / "artifacts"
FRONTEND = ROOT / "frontend" / "dist"

@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Keep startup fast enough for the platform health check.

    Chroma is prebuilt locally. On a fresh deploy the retrieval layer fits the
    same TF-IDF model over data/gold in memory on the first question, so the
    service never blocks startup on a 100 MB index build.
    """
    yield


app = FastAPI(
    title="TailDaam — Pakistan fuel prices",
    lifespan=lifespan,
    description=(
        "Grounded insight agent over governed gold tables. Every number is "
        "traceable to row ids and a licence; the agent refuses when evidence "
        "is missing."
    ),
    version=APP_VERSION,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    lang: Literal["en", "ur"] = "en"
    history: list[str] | None = None


def _records(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    return json.loads(df.to_json(orient="records", date_format="iso"))


@lru_cache(maxsize=4)
def _read_csv(name: str) -> pd.DataFrame:
    path = GOLD / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


@lru_cache(maxsize=4)
def _read_json(name: str) -> dict:
    path = ARTIFACTS / name
    return json.loads(path.read_text()) if path.exists() else {}


@lru_cache(maxsize=4)
def _read_artifact_csv(name: str) -> pd.DataFrame:
    path = ARTIFACTS / name
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def _last_pipeline_run() -> dict:
    path = ROOT / "prefect_runs.csv"
    if not path.exists():
        path = ROOT / "artifacts" / "prefect_runs.csv"
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path)
        if df.empty:
            return {}
        row = df.iloc[-1]
        return {
            "run_id": str(row.get("run_id", "")),
            "state": str(row.get("state", "")),
            "started_utc": str(row.get("started_utc", "")),
            "finished_utc": str(row.get("finished_utc", "")),
            "quality_status": str(row.get("quality_status", "")),
            "rows_gold": int(row.get("rows_gold", 0) or 0),
        }
    except Exception:
        return {}


def _latest_prices() -> list[dict]:
    df = _read_csv("pk_petrol_weekly.csv")
    if df.empty:
        return []
    df = df.copy()
    df["period_end"] = pd.to_datetime(df["period_end"])
    out = []
    for entity, g in df.groupby("entity"):
        g = g.sort_values("period_end")
        last = g.iloc[-1]
        prev = g.iloc[-2] if len(g) > 1 else last
        out.append({
            "entity": entity,
            "latest_date": last["period_end"].date().isoformat(),
            "latest_pkr": round(float(last["value"]), 2),
            "previous_pkr": round(float(prev["value"]), 2),
            "change_pkr": round(float(last["value"] - prev["value"]), 2),
            "change_pct": round(float((last["value"] - prev["value"]) /
                                      prev["value"] * 100), 2),
            "citation_tag": last["citation_tag"],
        })
    return out


def _weekly_series() -> dict:
    df = _read_csv("pk_petrol_weekly.csv")
    if df.empty:
        return {"dates": [], "series": []}
    df = df.copy()
    df["period_end"] = pd.to_datetime(df["period_end"])
    pivot = df.pivot_table(index="period_end", columns="entity", values="value")
    pivot = pivot.sort_index()
    dates = [d.date().isoformat() for d in pivot.index]
    series = []
    for col in pivot.columns:
        vals = [None if pd.isna(v) else round(float(v), 2) for v in pivot[col]]
        series.append({"name": str(col), "values": vals})
    return {"dates": dates, "series": series}


def _coverage() -> list[dict]:
    weekly = _read_csv("pk_petrol_weekly.csv")
    city = _read_csv("pk_city_prices_monthly.csv")
    glob = _read_csv("global_petroleum_monthly.csv")
    wb = _read_csv("worldbank_energy_monthly.csv")
    model = _read_csv("model_evaluation.csv")
    weeks = weekly["period_end"].nunique() if not weekly.empty else 0
    cities = city["entity"].nunique() if not city.empty else 0
    months = city["period_begin"].nunique() if not city.empty else 0
    return [
        {
            "label": "National weekly prices",
            "detail": f"{weeks} weeks · PBS",
            "rows": int(len(weekly)),
        },
        {
            "label": "City monthly prices",
            "detail": f"{cities // 2} locations · {months} months · PBS annex",
            "rows": int(len(city)),
        },
        {
            "label": "Global benchmarks",
            "detail": "11 EIA series · World Bank",
            "rows": int(len(glob) + len(wb)),
        },
        {
            "label": "Model evaluation",
            "detail": "metrics · errors · intervals",
            "rows": int(len(model)),
        },
    ]


def _city_table() -> dict:
    df = _read_csv("pk_city_prices_monthly.csv")
    if df.empty:
        return {"cities": [], "petrol": [], "diesel": [], "month": None}
    df = df.copy()
    df["period_begin"] = pd.to_datetime(df["period_begin"])
    # The city table is a snapshot: always show the latest month, never an
    # average across the monthly panel.
    latest = df["period_begin"].max()
    df = df[df["period_begin"] == latest].copy()
    df["city"] = df["entity"].str.rsplit(" in ", n=1).str[-1]
    df["product"] = df["entity"].str.contains("diesel", case=False).map(
        {True: "diesel", False: "petrol"})
    pivot = df.pivot_table(index="city", columns="product", values="value")
    pivot = pivot.sort_index()
    month = latest.strftime("%Y-%m")
    return {
        "cities": [str(c) for c in pivot.index],
        "petrol": [round(float(v), 2) for v in pivot.get("petrol", pd.Series())],
        "diesel": [round(float(v), 2) for v in pivot.get("diesel", pd.Series())],
        "month": month,
    }


@app.get("/health")
@app.get("/api/health")
async def health():
    n_facts = indexed_fact_count()
    return {
        "status": "ok",
        "version": APP_VERSION,
        "facts_indexed": n_facts,
        "embedding_mode": embedding_mode(),
        "generation_mode": "groq" if (GROQ_MODEL and GROQ_API_KEY)
        else "extractive",
    }


@app.get("/api/overview")
async def overview():
    quality = _read_json("quality_report.json")
    metrics = _read_json("model_metrics.json")
    manifest_path = ROOT / "data" / "manifest.csv"
    manifest = pd.read_csv(manifest_path) if manifest_path.exists() else pd.DataFrame()
    by_publisher = []
    if not manifest.empty and "publisher" in manifest:
        for publisher, g in manifest.groupby("publisher"):
            licences = sorted({str(x) for x in g.get("licence", []).dropna()})
            by_publisher.append({
                "publisher": str(publisher),
                "files": int(len(g)),
                "licences": licences[:2],
            })
        by_publisher.sort(key=lambda r: r["files"], reverse=True)
    return {
        "latest": _latest_prices(),
        "weekly": _weekly_series(),
        "city": _city_table(),
        "quality": quality,
        "model": {
            "improvement": metrics.get("improvement_vs_baseline_pct"),
            "baseline_mae": metrics.get("baseline", {}).get("mae"),
            "challenger_mae": metrics.get("challenger", {}).get("mae"),
        },
        "coverage": _coverage(),
        "pipeline": _last_pipeline_run(),
        "sources": {
            "files": int(len(manifest)),
            "publishers": int(manifest["publisher"].nunique())
            if not manifest.empty else 0,
            "names": sorted(manifest["publisher"].dropna().unique().tolist())
            if not manifest.empty else [],
            "by_publisher": by_publisher,
        },
    }


@app.get("/api/model")
async def model():
    metrics = _read_json("model_metrics.json")
    pred = _read_artifact_csv("predictions.csv")
    groups = _read_artifact_csv("group_errors.csv")
    card_path = ARTIFACTS / "model_card.md"
    return {
        "metrics": metrics,
        "predictions": _records(pred),
        "groups": _records(groups),
        "model_card": card_path.read_text() if card_path.exists() else "",
    }


def _row_id_preview(value: str, limit: int = 8) -> tuple[str, int]:
    ids = [rid for rid in str(value).split(";") if rid]
    shown = ";".join(ids[:limit])
    if len(ids) > limit:
        shown += f"; … (+{len(ids) - limit} more)"
    return shown, len(ids)


@app.post("/ask")
@app.post("/api/ask")
async def ask(req: AskRequest):
    try:
        answer = await generate_answer(req.question, req.lang, req.history)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    citations = sorted({e.citation_tag for e in answer.evidence})
    all_ids = sorted(
        {rid for e in answer.evidence for rid in e.row_ids.split(";") if rid}
    )
    evidence = []
    for e in answer.evidence[:6]:
        shown, count = _row_id_preview(e.row_ids)
        evidence.append({
            "citation": e.citation_tag,
            "entity": e.meta.get("entity", ""),
            "value": e.meta.get("value", ""),
            "unit": e.meta.get("unit", ""),
            "period_end": e.meta.get("period_end", ""),
            "row_ids": shown,
            "row_id_count": count,
            "score": round(float(e.score), 4),
        })
    return {
        "answer": answer.text,
        "refused": answer.refused,
        "citations": citations,
        "row_ids": all_ids[:8],
        "row_id_count": len(all_ids),
        "confidence": round(max((e.score for e in answer.evidence), default=0.0), 4),
        "evidence": evidence,
    }


@app.post("/ask/stream")
async def ask_stream(req: AskRequest):
    async def event_source():
        answer = await generate_answer(req.question, req.lang, req.history)
        citations = sorted({e.citation_tag for e in answer.evidence})
        yield ServerSentEvent({
            "type": "meta",
            "refused": answer.refused,
            "citations": citations,
            "row_ids": sorted({rid for e in answer.evidence
                               for rid in e.row_ids.split(";") if rid}),
        })
        text = answer.text
        for i in range(0, len(text), 64):
            yield ServerSentEvent({"type": "chunk", "text": text[i:i + 64]})
        yield ServerSentEvent({"type": "done"})

    return EventSourceResponse(event_source())


# Static frontend: API routes above take precedence; everything else is the SPA.
# `check_dir=False` lets tests and CI import the app before the frontend build
# exists; FastAPI Cloud deploys always include frontend/dist.
app.frontend("/", directory=str(FRONTEND), check_dir=False)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("rag.api:app", host="0.0.0.0", port=8000, reload=True)
