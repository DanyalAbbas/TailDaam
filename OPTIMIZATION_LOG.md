# Optimization log — TailDaam

Every change below is recorded with its effect on **accuracy**, **speed** and
**memory**, and with the evidence used. Measurements were taken on 21 October
2026 on the development machine unless marked remote. “Not measured” means the
effect was not benchmarked; it is not a claim of zero.

## Summary

| Change | Accuracy effect | Speed effect | Memory effect | Decision |
|---|---|---|---|---|
| Model the **risk** target (Brent volatility), not the price level | Final MAE 16.5102 vs 17.8044 persistence (**7.27% better**); R² 0.0076 → 0.1132 | Same data, same split; no extra inference cost | Model artifact **1.7 KB** | Kept |
| HAR features + ridge(α=10), pre-registered | Beats declared persistence baseline on 93 held-out months | Fit/inference negligible for one monthly series | Tiny model; no GPU | Kept |
| Residual-quantile **90% interval** | Empirical coverage **89.25%** on held-out months | No extra model; two stored quantiles | Negligible | Kept |
| **In-memory TF-IDF fallback** instead of requiring Chroma on deploy | No accuracy claim; lexical matching is weaker than hosted embeddings, disclosed | Removes a 100 MB index build from the startup/health-check path; warm local `/ask` **~0.04 s**, remote `/ask` **~0.65 s** | Removes **109 MB** `data/chroma` artifact from the deploy path; in-process index only | Kept for free/offline deployment |
| Hand-written **FastAPI + static SPA** instead of Streamlit | No model/agent accuracy change; one runtime serves UI and API | Local `/api/overview` **0.066 s**, `/api/model` **0.005 s**; no build step | Frontend directory **168 KB**; no Streamlit/WebSocket runtime | Kept |
| **Cache-busted assets** (`?v=20261021b`) | No accuracy change | Fixes stale-JS loads after deployment (observed during release) | Negligible | Kept |
| **Deterministic quality rules** | Prevents invalid rows entering gold/training; 91,384 clean rows; WARN, 1 fix, 4 flags | Pipeline run **34.8 s** end-to-end (real Prefect run) | Quality log is small CSV | Kept |
| **Extractive answering by default** | Eliminates generated-number risk by construction; LLM path still verifies | No token/network call; local answer ~0.04 s | No model weights loaded | Kept |
| **Static Hugging Face Space** instead of Docker Space | No change | Free tier; static files CDN-served | No container image | Forced by free-tier policy; kept |

## 1. Target choice: price level → volatility

**Change.** The first framing was next-fortnight Pakistani petrol price. The
data does not support a credible win: domestic prices are administered and the
PBS weekly history is short. We tested a price-level ridge on monthly Brent and
then moved the declared target to next-month Brent realised volatility.

**Evidence.**

| Target | Baseline MAE | Challenger MAE | Claim |
|---|---|---|---|
| Brent price level (USD/bbl) | 6.0963 (persistence) | 5.8876 (ridge) | **Not claimed**; close to a random walk |
| Brent volatility (annualised %) | 17.8044 (persistence) | **16.5102** (HAR ridge) | **Claimed**: 7.269% lower MAE |

**Accuracy trade-off.** The price-level challenger is 3.4% lower MAE than
persistence, but that is not a meaningful or stable win on 93 months. Reporting
it as a success would be overclaiming. Volatility is the dimension with genuine
short-horizon memory and a defensible risk interpretation.

**Speed/memory.** Both are monthly models on a few hundred rows; fit and
inference are negligible. The shipped model is **1.7 KB** on disk.

## 2. HAR features and pre-registered ridge

**Change.** Features are lagged monthly, quarterly and annual realised
volatility (HAR-style); the challenger is `ridge(alpha=10)`. The alpha and
feature set were fixed before looking at the held-out period; no test-set
tuning was performed.

**Accuracy.** The split is chronological 80/20: 369 train / 93 test months,
2019-02-01 to 2026-10-01. Persistence MAE 17.8044 → HAR 16.5102; RMSE 37.5323 →
35.4791; R² 0.0076 → 0.1132. This is a real but modest improvement, and the
group errors file shows where it is weak.

**Speed/memory.** A linear model on three lag features is effectively free to
fit and serve. The whole fitted artifact is 1.7 KB; no GPU, no external model
service.

**Why not a larger model.** With 462 monthly observations and a short
volatility history, a gradient-boosted or deep model would add variance and
tuning risk without evidence. The simple, pre-registered model is easier to
audit and matches the sample size.

## 3. Prediction intervals

**Change.** Store residual quantiles (5% and 95%) from the training residuals
and report the resulting 90% interval. The interval is explicitly labelled
nominal.

**Accuracy.** Empirical coverage on the 93 held-out months is **89.25%**
(0.8925), close to the nominal 90%. The lower residual quantile is −18.1407 and
the upper is +43.1977 volatility points; the asymmetry is visible rather than
hidden.

**Speed/memory.** Two extra numbers; no second model and no inference cost.

## 4. Retrieval: persistent Chroma → in-memory TF-IDF fallback

**Change.** The repository can build a persistent Chroma index
(`data/chroma`, **109 MB**), but the free deployment does not need to upload or
build it. If the index is absent and no Mistral key is set, the service fits
the same local TF-IDF embedder over the 2,129 gold facts in memory on first use.

**Accuracy.** TF-IDF is lexical, not semantic; paraphrases can be missed. This
is a real accuracy trade-off and is disclosed in the README, `/api/health` and
the Summary. The scope, time, product and city filters compensate by refusing
when retrieval is weak. With `MISTRAL_API_KEY`, the multilingual embedder is
used and the semantic path is available.

**Speed.** The deploy no longer blocks startup on a 100 MB index build. Measured
warm local `/ask`: **0.043 / 0.040 / 0.048 s** across three requests; remote
FastAPI Cloud `/ask`: **0.653 s** for the same question on 21 Oct 2026.
Cold-start time after a fresh process was not separately benchmarked and is not
claimed.

**Memory.** The production path drops the **109 MB** on-disk Chroma artifact and
keeps a small in-process TF-IDF matrix. Process RSS was not measured, so no
numeric memory saving is claimed beyond the removed artifact.

## 5. UI/runtime: Streamlit → FastAPI + static SPA

**Change.** An early Streamlit layout was discarded. The submitted UI is
hand-written HTML/CSS/JS served by FastAPI; the static Hugging Face Space uses
the same files and calls the API.

**Accuracy.** No model or agent accuracy effect. It does remove a second
runtime and makes the exact frontend that is tested locally the one deployed.

**Speed.** Local API timings: `/api/overview` **0.066 s** (3,708 bytes),
`/api/model` **0.005 s** (17,824 bytes). The frontend directory is **168 KB**
including fonts (35 KB app JS, 25 KB CSS). No head-to-head browser benchmark
against Streamlit was run, so no comparative speed claim is made.

**Memory.** Avoids a Streamlit server and WebSocket layer in the deployed
stack. Browser/runtime memory was not measured.

## 6. Cache-busted assets

**Change.** Asset URLs carry a version query (`?v=20261021b`) in both the
FastAPI-served SPA and the static Space.

**Effect.** During release, a browser served an older `app.js` after the app
changed. Bumping the version made the new UI load immediately. This is a
deployment correctness fix, not an accuracy or speed optimization.

## 7. Data quality rules

**Change.** 14 deterministic rules cover schema, duplicate row ids, non-positive
or non-finite prices, >35% daily moves, implausible petrol levels, cadence gaps
and freshness. Decisions are logged as FIX / FLAG / FAIL.

**Effect.** The clean layer contains **91,384** rows; the current quality status
is **WARN** with **1 fix** and **4 flags**. The 9 April 2026 HSD outlier
(522.29 PKR/L against 380.56 petrol) triggers the new weekly-jump rule; it is
kept and annotated in the gold note, not silently dropped. This protects the
training/retrieval input, but the accuracy effect of individual rules was not
ablated.

**Speed/memory.** The full real pipeline run took **34.8 s** (2026-10-21
11:31:11 → 11:31:45 UTC), including acquisition, cleaning, quality, gold, model
and indexing. The quality log is a small CSV.

## 8. Extractive answering instead of unconstrained generation

**Change.** With no LLM key, the agent assembles an answer from retrieved gold
facts. With a key, a draft is still checked number-by-number and
citation-by-citation; one unsupported number replaces the draft with a refusal.

**Accuracy/safety.** This is the main hallucination control: the default path
cannot generate a number from model weights. The trade-off is less fluent
paraphrase; the refusal contract is tested.

**Speed/cost.** No token call and no external generation latency in the default
path; local warm `/ask` is ~0.04 s. The optional LLM path’s latency and token
cost were not benchmarked.

## 9. Rejected or constrained optimizations

- **Price-level forecast:** rejected as a claimed win (see §1).
- **Gradient boosting / larger model:** rejected for this sample size; no
  evidence it would generalize better, and it adds tuning risk.
- **Persistent Chroma in the free deploy:** rejected because a 109 MB artifact
  and index build add startup/serving risk; the lexical fallback is disclosed.
- **Docker/Gradio Hugging Face Space:** blocked by the free-tier policy
  (`402 Payment Required`); switched to a free Static Space. No model effect.
- **Backfilling missed hourly runs:** rejected. `prefect_runs.csv` contains only
  the real run; the missed Tue–Wed window is disclosed.
- **Removing the HSD outlier:** rejected. It is a real published value; it is
  flagged and annotated instead of silently cleaned.

## 10. What is still unoptimized

- Cold-start latency on FastAPI Cloud is not measured or guaranteed.
- TF-IDF recall on paraphrased Urdu/English questions is weaker than a hosted
  multilingual embedder.
- The frontend has no automated Lighthouse/accessibility score.
- The pipeline is a single real run, not a long reliability record.
- No user-facing A/B test or newsroom pilot has been run.

These are the honest next optimization targets, in that order.
