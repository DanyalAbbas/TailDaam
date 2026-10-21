# AI Use Log

Honest disclosure of how AI assistance was used on this submission, as required
by the hackathon rules. The short version: **AI helped write and review code and
prose; AI did not generate data, results, or citations.**

## Tools used

| Tool | Role |
|---|---|
| DeepSeek V4.1 Flash Free in OpenCode | Code scaffolding, refactoring, test writing, documentation editing, debugging |
| No generative model at inference (default mode) | The shipped agent uses extractive answering over gold facts |

## What AI was used for

| Date (2026) | Area | What the assistant did | Human check |
|---|---|---|---|
| 19 Oct | RAG scaffold | Drafted the gold-table contract, Chroma retrieval, prompt templates, verification and refusal gate | Reviewed line by line; tests written for contract + refusal |
| 19 Oct | Mock fixture | Wrote a clearly labelled MOCK fixture for plumbing tests only | Confirmed it is never used for evaluation/training and is excluded from gold |
| 21 Oct | Data pipeline | Scaffolded acquisition, cleaning and manifest hashing | Verified every URL against the original publisher; checked row counts and sample values |
| 21 Oct | Quality agent | Drafted rule set and decision-log schema | Reviewed thresholds; confirmed no value invention |
| 21 Oct | Model | Drafted HAR feature code and metrics code | Ran the split ourselves; read the metrics; kept the failed price-level attempt in the model card |
| 21 Oct | Frontend | Drafted a Streamlit layout, then replaced it with a hand-written SPA served by FastAPI | Ran both locally; the Streamlit version was discarded before submission |
| 21 Oct | Docs | Edited README, model card, dataset proposal, business model, impact analysis, optimization log and this log | Every claim cross-checked against artifacts and measured timings |
| 21 Oct | Deployment | Prepared `main:app`, `pyproject.toml` and the FastAPI Cloud entrypoint | Verified locally, on FastAPI Cloud, and on the static Hugging Face Space |
| 21 Oct | Demo | Recorded the captioned walkthrough with Playwright and ffmpeg | Reviewed every frame; captions match the real UI and live numbers |

## What AI was **not** used for

- **No synthetic data.** Every price in the gold layer comes from PBS, EIA or the
  World Bank. The mock fixture is labelled MOCK and used only to test plumbing.
- **No generated numbers.** Model metrics are computed by `src/model.py` from
  downloaded observations; they were not written by a model.
- **No invented citations.** Every citation tag resolves to a real publisher URL
  in `data/gold/citation_registry.csv`.
- **No hidden prompt-only safety.** Refusal is implemented as retrieval and
  verification code paths, not as a request in a prompt.
- **No fabricated pipeline history.** `prefect_runs.csv` contains only runs that
  actually executed, with true timestamps. The missed Tue–Wed window is
  disclosed rather than backfilled.

## Residual risks

- The assistant suggested the HAR volatility framing after a price-level model
  failed to beat persistence. The choice is documented, the failed attempt is
  reported, and the metric is reproducible from `make model`.
- Documentation prose was AI-assisted; numerical claims were verified against
  `artifacts/*.json` before submission.
- The local TF-IDF fallback is weaker than a hosted multilingual embedder; this
  is disclosed in the README and in `/health`.

## Declaration

I can explain every line of the code I submit. The assistant's output was treated
as a draft: reviewed, executed, and corrected by me.

