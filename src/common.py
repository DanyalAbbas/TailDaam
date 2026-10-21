"""Shared paths, hashing and manifest helpers for HACK INSIGHT."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
CLEAN = DATA / "clean"
GOLD = DATA / "gold"
ARTIFACTS = ROOT / "artifacts"
MANIFEST = DATA / "manifest.csv"

for _p in (RAW, CLEAN, GOLD, ARTIFACTS):
    _p.mkdir(parents=True, exist_ok=True)

MANIFEST_COLUMNS = [
    "file", "source", "publisher", "url", "query", "fetch_time_utc",
    "sha256", "licence", "bytes",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def append_manifest(rows: list[dict]) -> None:
    """Append rows to data/manifest.csv, de-duplicating on sha256+file."""
    existing: set[tuple[str, str]] = set()
    if MANIFEST.exists():
        with MANIFEST.open(newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                existing.add((r["file"], r["sha256"]))
    new_file = not MANIFEST.exists()
    with MANIFEST.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_COLUMNS)
        if new_file:
            w.writeheader()
        for r in rows:
            key = (r["file"], r["sha256"])
            if key in existing:
                continue
            w.writerow({k: r.get(k, "") for k in MANIFEST_COLUMNS})
            existing.add(key)


def record_file(path: Path, source: str, publisher: str, url: str,
                licence: str, query: str = "") -> dict:
    rel = str(path.relative_to(ROOT))
    row = {
        "file": rel,
        "source": source,
        "publisher": publisher,
        "url": url,
        "query": query,
        "fetch_time_utc": utc_now(),
        "sha256": sha256_file(path),
        "licence": licence,
        "bytes": path.stat().st_size,
    }
    append_manifest([row])
    return row


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def load_json(path: Path, default=None):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))
