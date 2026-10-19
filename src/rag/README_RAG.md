# Insight Agent (RAG) — branch `rag-insight-agent`

My slice: chat answers grounded ONLY in the data team's gold tables, with
enforced citations, enforced refusal ("I don't know") and an audit trail.

## The 3 honesty rules I enforce structurally (not prompt-only)

1. **No number from the LLM.** `rag/verify.py` re-scans the generated answer,
   extracts every number and rejects the answer unless each number occurs in
   the retrieved gold-table facts. A violating reply is discarded and replaced
   with the structured refusal. Log: `artifacts/rag_integrity.csv`.
2. **No claim without a source.** The prompt requires a citation tag
   `[TAG]` per fact; verification drops answers citing tags absent from the
   retrieved evidence. Tags resolve to publisher + URL + licence through
   `data/gold/citation_registry.csv`.
3. **No synthetic data in eval.** The mock fixture under `data/mock/gold` is
   only for plumbing tests and is labelled MOCK.

## Contract with the data team (please follow this)

Write final gold tables to `data/gold/*.parquet` (or `.csv`) with columns:

    doc_id, table_name, row_ids, citation_tag, period_begin, period_end,
    entity, value, unit

Plus `data/gold/citation_registry.csv`:

    citation_tag, publisher, url, licence, accessed_at

`row_ids` must reference ids from the raw layer (manifest-level traceability).
The loader refuses to index files that miss columns or have duplicate
`doc_id`, so a broken `make data` can never produce untraceable answers.

## My commands (from repo root or src/)

    pip install -r rag-requirements.txt           # my stack only
    cp .env.example .env  # add GROQ/MISTRAL keys

    make mock-gold      # generate clearly-labelled mock fixture
    make rag-index      # rebuild Chroma index from data/gold
    make rag-test       # run my honesty-gate/contract tests
    make rag-run        # serve FastAPI on :8000

    # CLI
    python -m rag build-index
    python -m rag ask "اس س納ے ہفتوں میں پیٹرول کی قیمت کیا تھی؟" --lang ur
    python -m rag serve

## API (what dashboard integrates)

    GET  /health          -> {"status": "ok", "facts_indexed": N}
    POST /ask             -> {"answer", "refused", "citations", "row_ids", "confidence"}
    POST /ask/stream      -> Server-Sent Events stream:
                             meta frame {citations, row_ids} -> chunk frames -> done.frame
    GET  /index/status    -> count of indexed facts

Sample:

    curl -X POST localhost:8000/ask -H 'content-type: application/json' \
      -d '{"question": "What was petrol price in early September 2026?", "lang": "en"}'

The UI teammate can mount their React build with FastAPI ≥ 0.138:
`app.frontend("/", directory="frontend/dist")` once their dist exists — the
API above stays untouched; deploy as a single Docker HF Space.

## What I need from teammates

- data team: gold tables per contract above + keep `citation_registry.csv` in
  sync with citation tags.
- UI team: POST `/ask` or `/ask/stream`, show `citations` and `row_ids`
  alongside the answer (that display is part of the honesty story), and a
  language toggle that sets `lang: "en" | "ur"`.

## Stack (reused from urdu-tutor-ai-buddy)

Chroma (persistent) + Mistral `mistral-embed` for retrieval, Groq LLM for
generation, FastAPI (SSE for streaming, FastAPI ≥ 0.135). Scripts: `scripts/`
in this branch carry the fixture/index helpers.
