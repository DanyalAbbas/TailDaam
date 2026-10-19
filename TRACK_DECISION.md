# Track decision — Pakistan petrol price fluctuations (self-proposed Energy problem)

## Is it allowed?
Yes. Tracks allow a self-proposed problem as long as the data meets the same
standard. It sits under the **Energy** umbrella (petroleum products are energy)
and also touches **Urban mobility** (fuel cost -> commuting). We declare
"Energy (petroleum prices)" as the track on the Dataset Declaration.

## Volume gate (the hard part)
Pakistan's notified petrol price changes only every fortnight (~26 rows/yr).
We satisfy the 50,000-row minimum by building a **multi-series daily
petroleum warehouse**, not a single series:

- Global petroleum benchmarks (daily, EIA/World Bank Pink Sheet/IMF PCM):
  Brent, WTI, US Gulf Coast conventional gasoline, NY Harbor gasoline,
  US Gulf Coast diesel — each ~9,000 rows since 1986 => ~45,000 rows.
- Exchange rate PKR/USD daily (SBP) — ~9,000 rows.
- Domestic notified petrol price fortnightly (OGRA/PBS SPI) — ~600 rows,
  joined on nearest prior notification date.

Total ~55,000 rows, 6+ independent series, all original publishers, public
domain / open licence. This is the honest data shape and the model must be
built around it (daily global features -> fortnightly domestic target).

## How we model it
- Target: next fortnight's notified petrol price (PKR/L).
- Baseline (declared): naive "same as last notification" (or 14-day lag).
- Features: lagged global Brent/WTI/gasoline/diesel + PKR/USD + month.
- Model: gradient boosting (scikit-learn/LightGBM) — beats baseline.
- Groups for error analysis: price regime (pre/post subsidy change), quarter,
  and high-vs-low volatility periods. Uncertainty: prediction intervals via
  quantile loss.
- Insight Agent (RAG, this branch): answers like "why did petrol go up in
  September?" by citing the gold-table facts (Brent level, PKR rate, the
  notified price), refusing when asked about things outside the warehouse
  (e.g. future prices, tax breakdowns we never fetched).

## Pakistan Impact Bonus angle
- Primary user: commuter / small fleet operator budgeting for fuel.
- Urdu output toggle (bonus) via the Insight Agent.
- Pakistani publishers (PBS, SBP, OGRA) -> off-track-list credible source.

## Data sources (all original publishers)
1. US EIA (track-listed? No — EIA is NOT on the track list) — daily petroleum spot prices.
2. World Bank Pink Sheet (NOT on track list) — monthly commodity prices.
3. IMF Primary Commodity Prices (NOT on track list).
4. State Bank of Pakistan (Pakistani source) — daily PKR/USD.
5. Pakistan Bureau of Statistics SPI (Pakistani source) — weekly petrol price.
6. OGRA notifications (Pakistani source) — fortnightly notified prices.

>= 2 independent sources, >= 1 off-track-list credible source: satisfied.

## Caution
- PBS SPI "petrol" entry is retail price in major cities — may differ from
  OGRA notified price. Pick ONE definition and document it in the manifest.
- robots.txt / ToS: EIA, IMF, WB are all public-domain / open-data portals;
  PBS/SBP publish under open-data terms; OGRA publishes PDF notifications
  (fetch with pdfplumber, no ToS issue).
- No personal/identifiable data: none involved.
