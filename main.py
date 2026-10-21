"""FastAPI Cloud entrypoint.

FastAPI Cloud auto-detects ``main:app``. The service itself lives in
``src/rag/api.py`` so the local CLI, tests and the deployment import exactly the
same object.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from rag.api import app  # noqa: E402,F401

__all__ = ["app"]
