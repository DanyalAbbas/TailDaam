# TailDaam — Pakistan fuel prices, with receipts

An end-to-end, reproducible data product for **Pakistani petrol and diesel
prices**: a governed data warehouse, a baseline-beating risk model, and a RAG
insight agent that is structurally incapable of inventing a number.

The name combines **tail risk** with **daam**, Urdu for price.

Built for the HACK INSIGHT hackathon (19–22 October 2026). **Track:** Energy demand — proposed problem: Pakistani fuel-price volatility and pass-through.

**Live:** [hack-insight.fastapicloud.dev](https://hack-insight.fastapicloud.dev) ·
**Hugging Face Space:** [TailDaam](https://danyalabbas-hack-insight.static.hf.space) ·
**Demo video:** [`artifacts/demo.mp4`](artifacts/demo.mp4) ·
**API docs:** [hack-insight.fastapicloud.dev/docs](https://hack-insight.fastapicloud.dev/docs)

**Submission pack:** [`Summary.pdf`](Summary.pdf) ·
[`Dataset_Proposal.pdf`](Dataset_Proposal.pdf) ·
[`AI_Use_Log.md`](AI_Use_Log.md) ·
[`BUSINESS_MODEL.md`](BUSINESS_MODEL.md) ·
[`IMPACT_ANALYSIS.md`](IMPACT_ANALYSIS.md) ·
[`OPTIMIZATION_LOG.md`](OPTIMIZATION_LOG.md) ·
[`TRACK_DECISION.md`](TRACK_DECISION.md)

---

## 1. The problem

Fuel prices are the most politically sensitive number in Pakistan. Every
fortnight, OGRA notifies new petrol and high-speed diesel prices; households,
transporters and small businesses feel the change immediately. Public discussion
is full of claims about *why* prices moved and *what happens next*, but the
underlying evidence is scattered across weekly PBS SPI reports, monthly city
tables, and global benchmark feeds.

We asked a narrow, answerable question:

> **Can we build a system that answers questions about Pakistani fuel prices —
> and refuses when the data does not support an answer — while forecasting the
> risk dimension of the oil import bill better than a naive baseline?**

Three deliverables follow: a governed dataset, a model with a declared baseline,
and an agent whose every number is traceable to a row id.

---

## 2. What is in the box

| Layer | What it does | Where |
|---|---|---|
| **Acquire** | Downloads 41 PBS weekly SPI reports, the PBS monthly city annex, 11 EIA daily petroleum series, and the World Bank Pink Sheet. Hashes every raw file into `data/manifest.csv`. | `src/acquire.py` |
| **Clean** | Typed long-format tables with stable `row_id`s and source paths. | `src/clean.py` |
| **Quality agent** | Deterministic rules; every decision logged as FIX / FLAG / FAIL with a reason. | `src/quality.py` |
| **Gold** | The only layer the agent may quote. Fixed contract + citation registry. | `src/build_gold.py` |
| **Model** | Next-month Brent volatility vs persistence baseline, intervals, group errors, price-level attempt reported honestly. | `src/model.py` |
| **Insight Agent** | Chroma retrieval over gold facts, constrained generation, structural refusal. | `src/rag/` |
| **Pipeline** | Hourly Prefect flow: acquire → clean → quality → gold → model → index. | `src/pipeline/flows.py` |
| **Frontend** | Hand-written single-page app served by FastAPI: Overview / Model / Insight agent, EN + Urdu. | `frontend/dist/` |

---

## 3. Dataset: real, cited, and big enough to matter

| Source | Publisher | Rows (clean) | Licence |
|---|---|---|---|
| PBS weekly SPI reports (41 weeks) | Pakistan Bureau of Statistics | 82 product-weeks (petrol + HSD) | Government of Pakistan open publication |
| PBS monthly city annex | Pakistan Bureau of Statistics | 36 city-product prices (18 reporting locations: 17 cities + national average, × 2 products) | Government of Pakistan open publication |
| EIA daily petroleum spot prices (11 series) | U.S. Energy Information Administration | **84,546** daily observations | public domain (US Government work) |
| World Bank Pink Sheet | World Bank | 6,720 energy observations | CC BY 4.0 |

The EIA block supplies the volume and the global input market; the PBS block is
the Pakistani anchor (national weekly series and city-level monthly averages).
Two independent publishers are used, plus a third for cross-checking.

**Volume check:** 84,546 + 6,720 + 82 + 36 = **91,384 clean rows**. The raw
files and the manifest are committed so the record can be audited without a
network call; `make data` re-downloads them and records fresh SHA-256 hashes.

**Manifest contract** (`data/manifest.csv`): `file, source, publisher, url,
query, fetch_time_utc, sha256, licence, bytes`. Every gold row stores the
`row_ids` it came from and a `citation_tag` that resolves in
`data/gold/citation_registry.csv`.

### What we deliberately did *not* do

- No synthetic, interpolated or back-filled prices in the gold layer.
- No re-uploaded Kaggle mirrors: only original publishers are fetched.
- No missing weeks invented. Publication gaps stay gaps; the frontend labels
  them.
- No 2024 petrol history invented. If asked for a period outside the collected
  weeks, the agent refuses.

---

## 4. Model: volatility, where a model can actually win

Monthly average Brent is close to a random walk. We tried a price-level model
and report the result honestly rather than hiding it:

| Price-level attempt (USD/bbl) | MAE |
|---|---|
| Persistence baseline | 6.10 |
| Ridge challenger | 5.89 |

That is not a meaningful win, so we do **not** claim one. The modelled target is
the risk dimension that is predictable — next-month Brent realised volatility
(annualised %, from daily log returns):

| Next-month volatility | MAE | RMSE | MAPE | R² |
|---|---|---|---|---|
| **Baseline: persistence** | 17.80 | 37.53 | 36.25% | 0.008 |
| **Challenger: HAR ridge (α = 10)** | **16.51** | **35.48** | **35.91%** | **0.113** |

- **7.27% lower MAE** than the declared baseline on a chronological 80/20 split
  (369 train / 93 test months, Feb 2019 – Oct 2026).
- Nominal **90% prediction interval** has **89.25%** empirical coverage.
- Errors are reported by year, month and volatility regime in
  `artifacts/group_errors.csv` — including where the model is weak.
- The model is pre-registered (`ridge(α=10)` on HAR features); no test-set
  tuning.
- Pakistani pass-through is estimated separately and labelled small-sample
  (39 overlapping weeks, correlation 0.69, slope 0.58 PKR per USD/bbl).

Why volatility? For an import-dependent economy, the risk around the oil bill
matters as much as the point forecast. Volatility also has genuine
short-horizon memory, which is why a simple HAR model can beat persistence.

---

## 5. The Insight Agent: honesty as a code path

The agent answers questions such as:

- *What is the current petrol price in Pakistan?* → 396.06 PKR/L, week ended
  2026-10-15, citation `PBS-SPI`, row `pbs:2026-10-15:petrol_super`.
- *What was the diesel price in Karachi in September 2026?* → 401.14 PKR/L,
  citation `PBS-SPI`, row `pbsm:2026-09:hsd:Karachi`.
- *How much better is the model than the baseline?* → 7.27% MAE improvement,
  citation `MODEL-CARD`.
- *What is the weather in Lahore?* → **refusal**, because the question is
  outside the declared scope.
- *What was the petrol price in January 2024?* → **refusal**, because no gold
  fact covers that period.

### How refusal works (not a prompt trick)

1. **Scope gate** — a question needs a fuel/price/model term (or a price + place)
   to be in scope.
2. **Retrieval confidence gate** — if the best cosine score is below the
   backend's calibrated floor, refuse.
3. **Time / product / city filters** — explicit constraints are applied to
   retrieved facts. If nothing survives, refuse.
4. **Post-hoc verification** — in LLM mode, every number and citation tag in
   the draft is checked against retrieved evidence; a single unsupported number
   replaces the whole answer with a refusal.
5. **Extractive fallback** — with no API key, answers are assembled from the
   retrieved gold facts themselves, so hallucination is impossible by
   construction.

The agent never generates a number from the model's weights. It quotes facts.
Every answer carries its citation tags and row ids, and the API returns them in
a separate `citations` / `row_ids` field.

### Languages

English is primary. An Urdu toggle produces Urdu templates and accepts Urdu
questions through a small, auditable Urdu→English glossary for lexical
retrieval. With `MISTRAL_API_KEY`, the multilingual embedder handles Urdu
directly.

### Embeddings

- With `MISTRAL_API_KEY`: `mistral-embed`.
- Without a key (offline judging): a local TF-IDF embedder fitted on the gold
  corpus and persisted beside the Chroma index. `/health` reports which mode is
  active. The trade-off (lexical rather than semantic matching) is explicit.

---

## 6. Data Quality Agent

`src/quality.py` runs deterministic rules and logs **every** decision to
`artifacts/quality_decisions.csv`:

| Rule | Action |
|---|---|
| Schema / required columns | FAIL if missing |
| Duplicate `row_id` | FIX (keep first) |
| Non-positive or non-finite price | FIX (drop) |
| Daily move > 35% | FLAG (kept: energy markets genuinely gap) |
| Weekly domestic move > 35% | FLAG (kept and annotated; catches the 9 Apr 2026 HSD jump) |
| Petrol outside 50–800 PKR/L | FLAG (kept, excluded from training) |
| Weekly cadence gap > 28 days | FLAG, **not filled** |
| Freshness > 14 days | FLAG |

The agent's philosophy: **repair only what is provably wrong; never invent a
missing observation.** The report is in `artifacts/quality_report.json`.

---

## 7. Automation

`src/pipeline/flows.py` is a Prefect flow:

```
acquire → clean → quality → gold → model → rag index
```

Every real run appends to `artifacts/pipeline_runs.csv` inside a `finally`
block (PASS / WARN / FAIL). `make export-runs` converts that append-only log to
`prefect_runs.csv` at the repo root, enriched with Prefect flow-run ids when
the local API is reachable.

**Honesty note on the requested window:** the brief asked for runs covering
Tue 20 Oct 16:00 → Wed 21 Oct 16:00. The pipeline was wired and first executed
on Wed 21 Oct after that window had elapsed. `prefect_runs.csv` therefore
contains **real** runs with their true timestamps from first execution onward —
we did not backfill or fabricate earlier runs. The flow is scheduled hourly and
can be left running (`make serve`) to accumulate further real runs.

Run one cycle now:

```bash
make pipeline
```

Run hourly and keep real history (the flow loop, not the API server):

```bash
make pipeline-serve
```

---

## 8. Reproduce from a clean clone

Requirements: Python 3.12, `uv`, network access for source downloads.

```bash
git clone https://github.com/DanyalAbbas/hack-insight.git
cd hack-insight
make setup          # uv venv + uv pip install -r requirements.txt
make data           # acquire → clean → quality → gold
make model          # metrics, intervals, group errors
make rag-index      # Chroma index over gold facts
make test           # contract + honesty tests
make api            # FastAPI + frontend on http://127.0.0.1:8000
```

The retrieval index is ignored by git (109 MB). On a fresh clone the service
fits the same TF-IDF model over `data/gold` in memory on the first question, so
startup is fast and the 109 MB upload is unnecessary; `make rag-index` builds
the persistent Chroma index explicitly.

One command for everything:

```bash
make all
```

`make all` is the reproducibility claim: it rebuilds the data layer, refits the
model, rebuilds the index, runs tests, regenerates `Summary.pdf` and
`Dataset_Proposal.pdf`, and exports `prefect_runs.csv`.

### Optional keys

```bash
cp .env.example .env
# GROQ_API_KEY=...        # enables LLM generation + verification path
# MISTRAL_API_KEY=...     # enables multilingual semantic embeddings
```

Without keys everything still runs offline in extractive + TF-IDF mode.

---

## 9. API and deployment

```bash
make api          # uvicorn + static frontend on :8000
```

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | status, embedding mode, gold fact count (the SPA uses this) |
| `GET /health` | same response locally; FastAPI Cloud reserves the bare path, so use `/api/health` there |
| `GET /api/overview` | latest prices, weekly series, city annex, quality, model summary |
| `GET /api/model` | metrics, held-out predictions, group errors, model card |
| `POST /ask` | `{question, lang, history}` → answer + citations + row_id previews |
| `POST /api/ask` | alias of `/ask` |
| `POST /ask/stream` | SSE stream of the verified answer |

The same `app` object is exported at the repository root (`main:app`) and
declared in `pyproject.toml`, so FastAPI Cloud can build it without a Docker
file:

```bash
.venv/bin/fastapi login
.venv/bin/fastapi deploy
```

The static frontend is mounted with `app.frontend("/", directory="frontend/dist")`.
If `MISTRAL_API_KEY` is unavailable, the service fits the local TF-IDF model
over `data/gold` in memory on first use, so the deployed app has no external
index to fetch and no large index to upload.

### Hugging Face Space

**Live:** <https://danyalabbas-hack-insight.static.hf.space>

The Space is a free **Static Space** in `space/`. It serves the same SPA and
calls the verified FastAPI Cloud API; the API base is set in
`space/config.js`. Docker and Gradio Spaces on free `cpu-basic` now require a
PRO subscription, so the static Space is the reproducible free option.

To redeploy it:

```bash
.venv/bin/python - <<'PY'
from huggingface_hub import HfApi
HfApi().upload_folder(
    folder_path="space",
    repo_id="DanyalAbbas/hack-insight",
    repo_type="space",
    commit_message="Update the TailDaam static dashboard",
)
PY
```

The Space card is `space/README.md` (`sdk: static`). The same frontend is mounted
by FastAPI at `/` when the backend runs locally or on FastAPI Cloud.

Example:

```bash
curl -s localhost:8000/ask -H 'content-type: application/json' \
  -d '{"question":"What is the current petrol price in Pakistan?","lang":"en"}'
```

---

## 10. Repository layout

```
src/
  acquire.py clean.py quality.py build_gold.py model.py export_runs.py
  common.py
  pipeline/flows.py
  rag/            # retrieval, prompts, verification, API, CLI
frontend/dist/    # hand-written SPA served by FastAPI (no build step)
space/            # static Hugging Face Space (same SPA, remote API base)
main.py           # FastAPI Cloud entrypoint: main:app
pyproject.toml    # deployment dependencies + entrypoint
tests/            # gold contract, citation registry, honesty gate
data/
  gold/           # committed, small, the only quotable layer
  manifest.csv    # committed provenance ledger
artifacts/        # metrics, predictions, group errors, quality log, model card,
                  # frontend screenshots, demo.mp4
models/           # fitted model
Summary.pdf       # one-page summary
Dataset_Proposal.pdf  # sources, volume, licences and model-use rationale
BUSINESS_MODEL.md     # user, payer, value, running cost
IMPACT_ANALYSIS.md    # approach, impact pathways, risks, measurement plan
OPTIMIZATION_LOG.md   # accuracy / speed / memory changes and rejected paths
TRACK_DECISION.md     # final track scope and what is not claimed
prefect_runs.csv      # real pipeline run history
AI_Use_Log.md         # what AI helped with, and what it did not
```

---

## 11. Limitations

- **Pakistani history is short.** PBS only serves 41 weekly reports; gaps are
  real publication gaps. We do not interpolate them.
- **Administered prices.** Domestic prices move at policy reviews, so global
  pass-through is incomplete by design. The pass-through estimate is
  descriptive, not causal.
- **Global target.** The primary model forecasts Brent volatility, not the
  domestic retail price. The domestic link is documented but not modelled with
  enough observations to claim a win.
- **Lexical fallback.** Without a Mistral key, retrieval is TF-IDF; paraphrases
  can be missed. The scope/time filters compensate, and refusals are preferred
  to guesses.
- **Notifications.** The frontend shows the latest collected week, not a live
  OGRA feed. Freshness is displayed explicitly.

---

## 12. Responsible AI

- No number in an answer comes from a language model.
- Every answer carries citations and row ids; unsupported claims are replaced
  by a refusal.
- The quality agent's decisions are logged and auditable.
- The model's failures are published by group, not hidden behind a headline
  metric.
- The price-level attempt that did **not** beat the baseline is included in the
  model card.

See `AI_Use_Log.md` for the full disclosure of AI assistance.

---

## 13. Team

| Member | Area |
|---|---|
| Danyal Abbas | Data pipeline, model, RAG agent, frontend, deployment, submission |

_Solo submission. AI assistance is disclosed in `AI_Use_Log.md`.
