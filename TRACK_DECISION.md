# Track decision — Energy demand: Pakistani fuel prices and Brent risk

This is the final scope, not the original brainstorm. The early plan in this
file proposed a fortnightly domestic-price model and sources that were not
actually used; it has been rewritten to match the submitted repository.

## Final track

**Track:** Energy demand. **Proposed problem:** Pakistani fuel-price volatility
and pass-through. The submission is allowed to self-propose a problem under
this track, provided the data and evaluation meet the same standard.

The product is **TailDaam**: a governed record of Pakistani petrol and
high-speed diesel prices, a forecast of global Brent volatility, and a
refusal-first insight agent that cites every number.

## Why this problem

- Fuel prices are a high-salience public number in Pakistan and are set at
  fortnightly reviews.
- The evidence is scattered across PBS weekly SPI reports, a monthly city
  annex and global benchmark feeds; public claims are rarely traceable.
- Domestic prices are administered and the PBS weekly history is short, so a
  domestic price forecast would overclaim. The defensible modelling target is
  the risk dimension of the oil import bill: next-month Brent realised
  volatility, where a HAR model can beat a declared persistence baseline.

## What was actually built

| Layer | Final implementation |
|---|---|
| Acquisition | 41 PBS weekly SPI reports + 9 PBS monthly city annexes (Jan–Sep 2026) + 11 EIA daily petroleum series + World Bank Pink Sheet = **62 raw files** |
| Provenance | `data/manifest.csv` with source URL, publisher, query, fetch time, SHA-256, licence and bytes for every file |
| Clean layer | **91,672 rows**: EIA 84,546; World Bank 6,720; PBS weekly 82; PBS monthly city 324 (9 months) |
| Quality agent | 14 deterministic rules; every FIX / FLAG / FAIL logged; current status **WARN** (1 fix, 4 flags) |
| Model | Next-month Brent realised volatility; persistence baseline MAE **17.8044** vs HAR ridge **16.5102** (**7.269%** lower); 90% interval covers **89.25%**; group errors published |
| Insight agent | Retrieval over 2,417 gold facts; scope/confidence/time/product/city gates; citation tags and row ids; structural refusal |
| Pipeline | Prefect flow: acquire → clean → quality → gold → model → index; two real runs (34.8 s, 42.5 s), no backfill |
| Deployment | FastAPI Cloud API + free static Hugging Face Space; no login |

## Sources and independence

| Publisher | Role | Licence |
|---|---|---|
| Pakistan Bureau of Statistics (PBS) | Domestic weekly petrol/HSD and monthly city prices | Government of Pakistan open publication |
| U.S. Energy Information Administration (EIA) | Daily petroleum spot series; Brent is the model target | Public domain (US Government) |
| World Bank Pink Sheet | Independent monthly energy benchmark and cross-check | CC BY 4.0 |

Three independent publishers are used. EIA and the World Bank are outside the
suggested track source list, so the off-list requirement is satisfied. PBS is
the Pakistani anchor. No Kaggle mirror, blog or re-upload is used.

## Volume gate

A single fortnightly Pakistani series cannot reach 50,000 rows. The honest
solution is a multi-series daily/Monthly warehouse: EIA daily observations
(84,546 clean rows) plus World Bank monthly energy (6,720) plus the domestic
PBS tables. Total **91,672 clean rows**, above the 50,000 minimum, with two
independent publishers plus a third for cross-checking.

## Model scope (and what is not claimed)

- **Claimed target:** next calendar month Brent realised volatility,
  annualised, from daily log returns.
- **Declared baseline:** persistence (next month = this month's realised
  volatility).
- **Challenger:** ridge(α=10) on monthly/quarterly/annual lagged realised
  volatility (HAR features), pre-registered; no test-set tuning.
- **Uncertainty:** residual quantiles; nominal 90% interval, 89.25% empirical
  coverage on 93 held-out months.
- **Group errors:** by year, month and volatility regime in
  `artifacts/group_errors.csv`.
- **Not claimed:** a domestic retail-price forecast, a causal pass-through
  estimate, or a meaningful price-level win. The price-level attempt
  (6.0963 → 5.8876 USD/bbl) is reported and explicitly not claimed.

## Pakistani pass-through

The weekly PBS petrol series and EIA Brent are joined on week-end dates:
39 overlapping weeks, correlation 0.6928, slope 0.5821 PKR per USD/bbl. This is
a small-sample descriptive estimate; domestic prices are administered, so it
is not a causal estimate and is not used to train the Brent model.

## Data-quality caveats

- PBS weekly history has genuine publication gaps (2 gaps > 28 days); gaps are
  flagged and **not filled**.
- The 9 April 2026 HSD value (522.29 PKR/L against 380.56 petrol) is a real
  published outlier. It triggers the weekly-jump flag, is kept, and is
  annotated in the gold note; it is not silently removed.
- The PBS monthly city annexes cover January–September 2026; 2025 editions are
  not included in this build.
- No synthetic, interpolated or AI-generated observations are used for
  training or evaluation.
- Freshness is bounded by the latest collected PBS week (2026-10-15); the
  frontend shows this rather than implying a live OGRA feed.

## Submission documents

- `Dataset_Proposal.pdf` — credible sources, volume, licences, model use and
  limitations.
- `Summary.pdf` — one-page summary.
- `BUSINESS_MODEL.md` — user, payer, value and running cost.
- `IMPACT_ANALYSIS.md` — approach, impact pathways, risks and measurement plan.
- `OPTIMIZATION_LOG.md` — changes and their effect on accuracy, speed and
  memory.
- `AI_Use_Log.md` — AI assistance disclosure.

There is no separate “dataset declaration” form in this submission. The
manifest and the dataset proposal are the declaration of provenance.
