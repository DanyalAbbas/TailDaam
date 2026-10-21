# Approach and impact analysis — TailDaam

This document separates what the project **does**, what it has **measured**,
and what impact is still a **hypothesis**. The viva should be able to challenge
any of the three.

## 1. Approach in one paragraph

TailDaam is a governed data product for Pakistani fuel prices. It acquires
original PBS, EIA and World Bank files, hashes them into a provenance manifest,
cleans them into typed tables, applies deterministic quality rules, and builds a
small gold layer that is the only thing the insight agent may quote. A
HAR-style ridge model forecasts next-month Brent realised volatility against a
declared persistence baseline, with prediction intervals and errors by group.
A retrieval agent answers price and model questions with citation tags and row
ids, and refuses when scope, time, product, city or retrieval confidence does
not support an answer. A Prefect flow rebuilds the chain hourly, and a static
Hugging Face Space plus FastAPI Cloud deployment make the result inspectable
without a login.

The design choice that matters is **refusal-first**: the agent is not asked in
a prompt to be careful. Scope filters, retrieval thresholds and a post-hoc
number/citation verifier make unsupported answers a code path. In offline mode
the answer is assembled from retrieved gold facts, so it cannot invent a number
by construction.

## 2. Why this problem

Fuel prices are a high-salience, low-trust public number in Pakistan. Petrol and
high-speed diesel are administered at fortnightly reviews, and the evidence is
spread across weekly PBS SPI reports, a monthly city annex and global benchmark
feeds. Public argument often mixes three different claims:

1. what the notified domestic price is;
2. why it moved (pass-through, taxes, margins, policy);
3. what will happen next.

The project deliberately answers (1) with citations, measures (2) only
descriptively on 39 overlapping weeks, and does **not** claim (3) for the
domestic price. The model's forecast is for global Brent volatility, where the
data has enough history and the risk question is meaningful for an import
bill. This narrowing is the main intellectual contribution: it avoids dressing
up a short, administered price series as a predictive win.

## 3. Who is affected, and how

| Actor | Need | What TailDaam changes | What it does not change |
|---|---|---|---|
| Journalist / fact-checker | Verify a price quickly with a source | One cited answer plus row id; refusal instead of a plausible guess | It does not write the story or establish intent |
| Policy analyst | Understand the import-cost risk around administered prices | Volatility baseline, intervals and group errors; descriptive pass-through | It does not model taxes, margins or policy decisions |
| Household / commuter | Know the current notified price | Free, mobile-friendly record with freshness | It does not predict the next fortnight or personalise advice |
| Small fleet operator | Budget for fuel-cost swings | Transparent price history and a risk signal | It is not a hedging or procurement tool |
| Developer / researcher | Reuse an auditable pipeline | Open manifest, quality log, tests and API | It is not a general commodity-data platform |
| PBS / EIA / World Bank | See their data used correctly | Attribution, licence tracking and no re-upload mirror | It does not replace the publishers' own services |

## 4. Impact pathways

| Pathway | Mechanism | Evidence today | What would prove it |
|---|---|---|---|
| **Faster verification** | Cited answer replaces a manual PDF search | Live agent returns a price + row id in ~0.65 s from Cloud; local warm request ~0.04 s | Timed newsroom task before/after; time-to-publish |
| **Fewer unsupported claims** | Structural refusal and number verification | Contract tests cover out-of-scope, unsupported period, bad city/product and unsupported-number rejection | Error rate in a controlled fact-check exercise |
| **Better risk framing** | Volatility forecast beats persistence; intervals and group errors are published | 7.27% MAE improvement; 89.25% coverage; price-level failure disclosed | Whether analysts use the interval/regime errors rather than a point number |
| **Auditable public record** | Manifest, quality log, gold row ids and citation registry | 54 raw files, 91,384 clean rows, 3 publishers, SHA-256 per file | Independent audit reproduces the same counts and citations |
| **Language access** | Urdu toggle and Urdu question glossary | Urdu UI and templates; live answers in English and Urdu | Urdu usability testing with non-English readers |
| **Reusable infrastructure** | Small, tested pipeline and refusal contract | 10 passing tests; one-command rebuild | Another team or market reuses the pattern |

The project has **not** run a user study, A/B test or newsroom pilot. It cannot
claim measured reductions in misinformation or measured time savings. Those are
plausible mechanisms, not results. The honest impact claim is: **a working,
auditable tool that makes a specific verification task cheaper and makes
unsupported answers visibly impossible**, with a clear plan to measure the rest.

## 5. What has actually been measured

- **Data scale:** 91,384 clean rows from 54 raw files and 3 independent
  publishers; at least one publisher (EIA/World Bank) is outside the suggested
  track list. Every raw file is hashed.
- **Model:** persistence MAE 17.8044 → HAR ridge 16.5102 (**7.269%** lower);
  R² 0.0076 → 0.1132; nominal 90% interval empirical coverage 89.25% on 93
  held-out months. The price-level attempt (6.0963 → 5.8876 USD/bbl) is
  reported and **not** claimed as a meaningful win.
- **Agent behaviour:** 10 contract/honesty tests pass, including scope refusal,
  unsupported period, city/product filtering and rounded-number verification.
- **Operations:** one real Prefect run, 34.8 s, WARN quality status, 2,129 gold
  facts indexed. The missed Tue–Wed window is disclosed; no history was
  backfilled.
- **Reach:** live public dashboard on a static Hugging Face Space and a FastAPI
  Cloud API; no login.

## 6. Equity and inclusion

- **Free and login-free.** The dashboard and demo need no account.
- **Low bandwidth.** The SPA is hand-written (about 35 KB JS and 25 KB CSS,
  168 KB total frontend directory) and uses no heavy charting framework.
- **Urdu.** A visible language toggle and Urdu templates lower the English-only
  barrier; the offline glossary is intentionally small and auditable.
- **Transparent uncertainty.** Showing WARN quality status and model intervals
  is more useful to a non-expert than a false precise forecast.
- **Limits.** The interface is still web-first and literacy-dependent; the
  weekly source is not a live OGRA feed; users without internet or with
  screen-reader needs have not been tested. A future SMS/radio brief or
  accessible audit is a design task, not a claim.

## 7. Risks and mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| **False authority** | A clean UI can make a short, administered series look predictive | Prominent limitations; model targets Brent volatility, not domestic price; price-level failure published |
| **Stale data** | A price answer is only valid for its week | Freshness and last successful run shown; time filters refuse unsupported periods |
| **Source failure** | PBS/EIA pages or formats change | Manifest records URL/hash; quality log surfaces failures; pipeline marks WARN/FAIL |
| **Hallucination** | A wrong number is the core harm | No LLM number generation by default; retrieval-only answers; verifier rejects unsupported numbers/citations |
| **Political sensitivity** | Fuel prices are contested | Quote published facts; no causal or future-price claim; no partisan framing |
| **Privacy** | User questions could reveal interests | No accounts, no analytics pipeline, no personal data collected by the app |
| **Dependence** | Free hosting and public sources can change | Static Space plus a portable FastAPI app; data and model committed; no proprietary lock-in |
| **Overclaiming impact** | A hackathon demo is not evidence of social change | This document labels hypotheses; a pilot and pre-registered metrics are the next step |

## 8. Measurement plan

A credible next step is a small, time-boxed pilot with one newsroom or research
group, not a vanity user count.

**30 days**

- Recruit 3–5 users who verify fuel-price claims regularly.
- Give them 10 real verification tasks; measure time-to-correct-answer and
  whether they would have used the source without the tool.
- Log refusal correctness on a fixed adversarial set (out-of-scope, unsupported
  period, wrong city, ambiguous product).
- Track freshness lag and pipeline success rate.

**90 days**

- Compare cited-answer error rate with the team's current manual workflow.
- Interview users about trust, the Urdu interface and the volatility framing.
- Decide whether a paid API/widget is worth building; do not assume it.
- Publish a short impact note with negative results included.

**Pre-registered success signals:** lower median verification time; zero
unsupported numbers in a sampled audit; users can explain why the agent refused;
no increase in false confidence about the next administered price.

## 9. Conclusion

TailDaam's impact is concentrated and honest: it makes a narrow verification
task faster and auditable, and it makes unsupported fuel-price answers refuse
instead of guess. The dataset, model and refusal tests are real and
reproducible. The social-impact claims are not yet measured, and the project
says so.
