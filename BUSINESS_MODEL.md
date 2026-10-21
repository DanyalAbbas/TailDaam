# Business model — TailDaam

**Status:** public-interest prototype, pre-revenue. No paying customer, revenue
or market-size claim is made here. This document states the user, the payer
hypothesis, the value proposition and the running cost so the viva can test
them.

## 1. Who uses it

**Primary user:** a Pakistani newsroom data or policy journalist on deadline.
They need one defensible number — petrol, high-speed diesel, a city price or a
Brent move — with the publisher, week and row id attached.

**Secondary users:**

- policy analysts and research assistants checking a claim before publishing;
- small fleet operators and transport businesses budgeting for fuel;
- students and civil-society groups who cannot afford a commodity-data
  terminal;
- developers who need a small, auditable Pakistani fuel API.

The job to be done is not “predict tomorrow's petrol price”. It is **verify a
price claim quickly, and know when the record does not support an answer**.
The volatility model is a second job: give an import-cost risk signal to an
analyst who already understands that the domestic price is administered.

## 2. Who pays

The public dashboard is free. The payer hypotheses, in order of plausibility:

| Payer | What they would buy | Status |
|---|---|---|
| Newsroom or research institute | A supported API/widget, embargoed alerts, a citation-ready weekly brief | Hypothesis; no signed customer |
| Commercial data/API user | Metered API access with an SLA and provenance export | Hypothesis; no price validated |
| Donor or public-interest funder | Free public deployment, Urdu access and maintenance | Hypothesis; no grant |
| University/newsroom training programme | A teaching instance and workshop | Hypothesis |

No customer discovery interviews have been completed, so this is a design
hypothesis, not evidence of demand. The honest answer in the viva is: **the
public tier is free; the likely first payer is a newsroom or research
organisation buying verification speed and an auditable API, not an individual
commuter.**

## 3. Value

| Value | How TailDaam delivers it | Evidence today |
|---|---|---|
| Faster verification | One question returns a price, source tag and row id; no PDF hunt | Live agent answers in ~0.04 s locally and ~0.65 s from FastAPI Cloud on 21 Oct 2026 |
| Lower error and defamation risk | Unsupported periods, places and topics are refused; every number is checked against retrieved facts | Contract tests cover scope, time/product/city filters and unsupported-number rejection |
| Risk rather than false certainty | Brent volatility model beats the declared persistence baseline by 7.27% MAE; 90% interval covers 89.25% of held-out months | `artifacts/model_metrics.json` |
| Auditability | `manifest.csv`, quality decisions, gold row ids and citation registry | Reproducible with `make data` |
| Language access | English and Urdu interface and answer templates | Urdu toggle in the SPA; lexical glossary in offline mode |
| Reuse | Open-source pipeline pattern for other administered-price markets | Repository and tests |

The value is **time saved and a lower cost of being wrong**, not a proprietary
price forecast. A newsroom can already find the PBS PDF; what it cannot easily
do is produce a cited answer in seconds and prove where the number came from.

## 4. Running cost

Current deployment is deliberately cheap because the default path uses no
paid inference.

| Item | Current choice | Estimated monthly cost | Notes |
|---|---|---|---|
| Dashboard hosting | Hugging Face **Static Space** | $0 | Free tier; static files call the API |
| API hosting | FastAPI Cloud | $0 on the current/free allowance; usage-based above it | One small Python service; cold starts possible |
| Data | PBS, EIA, World Bank original publishers | $0 | Public/open licences; acquisition is a few requests per run |
| Embeddings | Local TF-IDF by default | $0 | Chroma is optional; no hosted embedding bill |
| LLM generation | Extractive by default | $0 | Optional `GROQ_API_KEY`; token cost only if enabled |
| Vector index | In-memory fallback | $0 | Avoids storing/uploading the 109 MB Chroma index |
| Domain / TLS | Platform subdomain | $0 | A custom domain would add a small annual cost |
| Maintenance | Small hourly pipeline + occasional source fixes | A few hours per month | Not priced as labour |

**Order of magnitude:** at low public-interest traffic (thousands of questions
per month, no LLM key), hosting and data cost is effectively **$0–$20 per
month**. That is the defensible claim. A paid LLM path and heavier traffic would
add variable token and compute cost; those unit costs have **not** been measured
because the shipped default does not use them.

## 5. Revenue options and unit economics

1. **Free public tier** — the current dashboard, with attribution and citation.
2. **Supported API / widget** — a newsroom or research group pays for uptime,
   a clean JSON contract and provenance export. Price would be set from the
   cost of maintaining the pipeline, not from a fabricated market size.
3. **Sponsored public-interest deployment** — a donor or media-development
   fund pays for the free tier and Urdu access.
4. **Training/workshops** — teaching reproducible data and refusal-first RAG.
5. **Commercial alerts** — a paid volatility/price alert for businesses, only
   after the public record is trusted.

The default extractive path has near-zero marginal cost per answer. If an LLM
key is enabled, cost becomes variable per question; the verifier still rejects
unsupported numbers, so the paid path does not buy accuracy it cannot cite.

## 6. Risks to the model

- **Demand risk:** the public may prefer a free price ticker; a newsroom's
  willingness to pay is unproven.
- **Source risk:** PBS publication gaps and government PDF changes can break
  acquisition; the manifest and quality log make failures visible.
- **Trust risk:** a polished dashboard can look more authoritative than the
  data warrants. The UI labels freshness and WARN status; the agent refuses.
- **Legal/political risk:** fuel prices are politically sensitive. The product
  quotes published facts and makes no causal or future-price claim.
- **Cost risk:** a viral launch or an LLM-enabled path changes the cost base;
  the static/extractive default is the fallback.

## 7. What would falsify this model

- Newsrooms say they would not use a cited answer even when it saves time.
- Users consistently ask for forecasts of the administered domestic price,
  which the data cannot support.
- The free tier attracts traffic but no institution will pay for uptime,
  provenance or alerts.
- Maintenance exceeds the available volunteer time.

Those are legitimate outcomes. The current claim is a **useful, cheap
public-interest tool with a plausible institutional payer**, not a validated
business.
