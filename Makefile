# Shared entry points. Team branches merge their targets into this file, so
# no one needs to touch each other's code to run the full pipeline.

.PHONY: rag-index rag-test rag-run mock-gold help

# --- Insight Agent (rag-insight-agent branch) -------------------------------
mock-gold:
	python -m rag.make_mock 2>/dev/null || python src/rag/make_mock.py

rag-index: mock-gold
	cd src && python -m rag build-index --mock

rag-test:
	pytest tests/ -q

rag-run:
	cd src && python -m rag serve

help:
	@echo "targets: mock-gold | rag-index | rag-test | rag-run | help"
