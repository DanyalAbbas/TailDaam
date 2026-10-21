# TailDaam — reproducible entry points (uv-managed environment).
# `uv sync`/`uv pip install` handles dependencies; every target below runs the
# same code the hourly Prefect flow runs.

PY ?= .venv/bin/python
export PYTHONPATH := src

.PHONY: setup data acquire clean quality model gold rag-index pipeline \
        pipeline-serve api serve export-runs test summary dataset-proposal \
        all mock-gold help

setup:
	uv venv --python 3.12 .venv
	uv pip install --python .venv/bin/python -r requirements.txt

acquire:
	$(PY) src/acquire.py

clean:
	$(PY) src/clean.py

quality:
	$(PY) src/quality.py

gold:
	$(PY) src/build_gold.py

data: acquire clean quality gold
	@echo "data layer rebuilt; manifest at data/manifest.csv"

model: gold
	$(PY) src/model.py

rag-index: gold
	$(PY) -m rag build-index

pipeline:
	$(PY) src/pipeline/flows.py

pipeline-serve:
	$(PY) src/pipeline/flows.py serve

api:
	$(PY) -m uvicorn rag.api:app --host 0.0.0.0 --port 8000 --reload --app-dir src

serve: api

export-runs:
	$(PY) src/export_runs.py

summary:
	$(PY) src/make_summary.py

dataset-proposal:
	$(PY) src/make_dataset_proposal.py

test:
	$(PY) -m pytest tests/ -q

all: data model rag-index test summary dataset-proposal export-runs
	@echo "full pipeline complete"

mock-gold:
	$(PY) src/rag/make_mock.py

help:
	@echo "targets: setup data model rag-index pipeline pipeline-serve api export-runs test summary dataset-proposal all"
