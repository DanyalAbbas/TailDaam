# Model card

Task: next calendar month Brent realised volatility, annualised % (from daily log returns)
Split: chronological 80/20 (369 train / 93 test, test 2019-02-01 to 2026-10-01)

| model | MAE (vol points) | RMSE | MAPE % | R2 |
|---|---|---|---|---|
| baseline: persistence (next month = this month's RV) | 17.8044 | 37.5323 | 36.254 | 0.0076 |
| challenger: har_ridge_alpha_10 | 16.5102 | 35.4791 | 35.91 | 0.1132 |

Improvement over baseline: **7.269% MAE** (beats baseline: True).
90% interval empirical coverage: 0.8925.

## Price-level attempt (reported, not claimed)
- persistence MAE 6.0963 USD/bbl vs challenge MAE 5.8876 USD/bbl on 93 held-out months.
- Price level is close to a random walk; no meaningful win is claimed. Volatility is the modelled target.

## Limitations
- The target is global Brent volatility, not the Pakistani retail price; domestic prices are administered and change at fortnightly reviews.
- The Pakistani weekly series is short (41 publication weeks). Pass-through estimates are reported as small-sample evidence only.
- No causal claim is made: features are lagged volatility, not policy variables.

## Pakistan pass-through (descriptive)
- overlapping weeks: 39
- corr(weekly change petrol, weekly change Brent): 0.6928
- slope: 0.5821 PKR per USD/bbl
- naive MAE 11.2225 PKR vs pass-through MAE 13.139 PKR (not a claimed win)
