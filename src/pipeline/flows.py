"""Hourly automated pipeline (Prefect).

Flow: acquire -> clean -> quality agent -> gold -> model -> RAG index.

Every run appends a real row to artifacts/pipeline_runs.csv. That local log is
the source for prefect_runs.csv (see export_runs.py) and is deliberately
append-only: we never backfill or edit timestamps.
"""

from __future__ import annotations

import csv
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from prefect import flow, task  # noqa: E402

RUN_LOG = ROOT / "artifacts" / "pipeline_runs.csv"
RUN_COLUMNS = ["run_id", "flow_name", "started_utc", "finished_utc",
               "duration_s", "status", "rows_gold", "quality_status", "notes"]


def _append_run(row: dict) -> None:
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not RUN_LOG.exists()
    with RUN_LOG.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=RUN_COLUMNS)
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in RUN_COLUMNS})


@task(retries=1, retry_delay_seconds=20, log_prints=True)
def acquire() -> None:
    import acquire as a

    a.main()


@task(log_prints=True)
def clean() -> None:
    import clean as c

    c.main()


@task(log_prints=True)
def quality() -> dict:
    import quality as q

    return q.run()


@task(log_prints=True)
def gold() -> None:
    import build_gold as g

    g.main()


@task(log_prints=True)
def model() -> dict:
    import model as m

    return m.main()


@task(log_prints=True)
def rag_index() -> int:
    from rag.retrieval import build_index

    return build_index()


@flow(name="hack-insight-hourly", log_prints=True)
def pipeline(rebuild_index: bool = True) -> dict:
    started = datetime.now(timezone.utc)
    run_id = started.strftime("%Y%m%dT%H%M%SZ")
    status, notes, qstatus, rows = "PASS", "", "", ""
    try:
        acquire()
        clean()
        report = quality()
        qstatus = report.get("status", "")
        gold()
        model()
        if rebuild_index:
            n = rag_index()
            notes = f"indexed {n} gold facts"
        import pandas as pd

        gold_dir = ROOT / "data" / "gold"
        rows = sum(
            len(pd.read_csv(p))
            for p in gold_dir.glob("*.csv")
            if p.name != "citation_registry.csv"
        )
        if qstatus == "WARN":
            status = "WARN"
    except Exception as e:
        status = "FAIL"
        notes = f"{type(e).__name__}: {e}"
        raise
    finally:
        finished = datetime.now(timezone.utc)
        _append_run({
            "run_id": run_id,
            "flow_name": "hack-insight-hourly",
            "started_utc": started.isoformat(timespec="seconds"),
            "finished_utc": finished.isoformat(timespec="seconds"),
            "duration_s": round((finished - started).total_seconds(), 1),
            "status": status,
            "rows_gold": rows,
            "quality_status": qstatus,
            "notes": notes,
        })
    return {"status": status, "rows_gold": rows, "quality": qstatus}


def serve(hours: int | None = None) -> None:
    """Run now, then hourly; `hours` bounds the loop for a demo."""
    pipeline()
    end = (datetime.now(timezone.utc) + timedelta(hours=hours)) if hours else None
    while end is None or datetime.now(timezone.utc) < end:
        time.sleep(3600)
        pipeline()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        serve()
    else:
        pipeline()
