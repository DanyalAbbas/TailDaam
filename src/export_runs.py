"""Export real pipeline run history to prefect_runs.csv.

The source of truth is artifacts/pipeline_runs.csv, which the Prefect flow
appends to inside a `finally` block on every real run (pass, warn or fail).
No rows are fabricated or backfilled. If Prefect's local API is reachable we
also attach the Prefect flow-run id; otherwise the local append-only log is
exported as-is.
"""

from __future__ import annotations

import asyncio
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "artifacts" / "pipeline_runs.csv"
OUT = ROOT / "prefect_runs.csv"
ARTIFACT_OUT = ROOT / "artifacts" / "prefect_runs.csv"
COLUMNS = ["run_id", "flow_name", "state", "started_utc", "finished_utc",
           "duration_s", "rows_gold", "quality_status", "notes"]


def prefect_ids() -> dict[str, str]:
    try:
        from prefect.client.orchestration import get_client

        async def _read():
            async with get_client() as client:
                runs = await client.read_flow_runs(limit=200)
                return {
                    r.start_time.strftime("%Y%m%dT%H%M%SZ"): str(r.id)
                    for r in runs if r.start_time
                }
        return asyncio.run(_read())
    except Exception:
        return {}


def main() -> int:
    if not LOCAL.exists():
        print("No runs recorded yet. Run `make pipeline` first.")
        return 1
    with LOCAL.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    ids = prefect_ids()
    for out in (OUT, ARTIFACT_OUT):
        with out.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS)
            w.writeheader()
            for r in rows:
                w.writerow({
                    "run_id": ids.get(r["run_id"], r["run_id"]),
                    "flow_name": r["flow_name"],
                    "state": r["status"],
                    "started_utc": r["started_utc"],
                    "finished_utc": r["finished_utc"],
                    "duration_s": r["duration_s"],
                    "rows_gold": r["rows_gold"],
                    "quality_status": r["quality_status"],
                    "notes": r["notes"],
                })
    print(f"wrote {len(rows)} real runs to {OUT.relative_to(ROOT)} and {ARTIFACT_OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
