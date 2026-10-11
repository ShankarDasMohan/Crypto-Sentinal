# Presenting CryptoSentinel: talk track

Total about 5 minutes. Keep the demo on the dashboard; use the recording only for the live pipeline.

## 1. The problem (30 s)
"Crypto markets move fast, and unusual activity shows up as spikes in volume, trade rate and price
movement. This project watches live trades and gives every minute a score from 0 to 100 for how
unusual it looks."

## 2. Architecture (60 s)
Show the diagram in the README. Say it left to right: Binance streams trades, Kafka buffers them,
Spark turns them into four features per minute, Postgres stores them, two models score them, the
API and dashboard serve the scores.
Mention: two symbols is a small scale; the point is the architecture, which would scale out.

## 3. Live pipeline recording (90 s)
Play the screen recording: producer running, Spark printing `[batch N] rows: X`, new rows appearing
in `feature_store`. One sentence only: "this is the live path; for today's demo I'm using the scored
data it produced."

## 4. Dashboard (90 s)
- Pick a symbol and point at the severity line: mostly low, with a few spikes.
- Open the "Most anomalous windows" table and read one row: "volume was N standard deviations above
  normal and the trade rate was far higher than usual, so both models scored it near the top."
- Tick "Show individual models" to show the two models mostly agree.
- Move the alert threshold slider to show how many windows would alert at each level.

## 5. Honest limits (30 s, say these before they are asked)
- Hours of data, one market regime.
- No ground-truth labels: "anomalous" means "unusual versus the training data", not "confirmed event".
- The spread feature is a proxy built from maker/taker order flow, because the trade stream has no order book.

## Likely questions
- **Is it accurate?** There are no labels, so accuracy can't be measured. What is checked: the two
  models agree (see `data/RESULTS.md`) and the top-scored windows have genuinely extreme feature values.
- **Why two models?** They fail differently: the forest reacts to a single extreme feature, the
  autoencoder to an unusual combination. Agreement raises confidence; disagreement is informative.
- **Why Kafka and Spark for two symbols?** To demonstrate the architecture. At this scale a single
  script would do.
- **Could it trade on this?** No. It flags unusual minutes; it does not predict direction.
- **What next?** Longer collection across market conditions, labeled events to evaluate against,
  real order-book data for the spread feature, and scheduled retraining.
