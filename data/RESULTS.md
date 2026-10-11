# CryptoSentinel: results

_Generated from `scores.csv` by `ml/make_report.py`. All numbers are computed from that file._

## Dataset

| Symbol | Scored 1-min windows | From (UTC) | To (UTC) | Hours |
|---|---|---|---|---|
| BTCUSDT | 261 | 2026-10-11 10:45 | 2026-10-11 15:05 | 4.3 |
| ETHUSDT | 261 | 2026-10-11 10:45 | 2026-10-11 15:05 | 4.3 |

## Severity distribution (0 = normal, 100 = most anomalous)

| Symbol | Model | Mean | Median | p90 | p99 | Max |
|---|---|---|---|---|---|---|
| BTCUSDT | forest | 17.9 | 13.8 | 41.5 | 72.2 | 100.0 |
| BTCUSDT | autoencoder | 1.5 | 0.4 | 2.1 | 19.9 | 100.0 |
| BTCUSDT | combined | 9.7 | 7.1 | 21.6 | 47.0 | 100.0 |
| ETHUSDT | forest | 15.6 | 9.6 | 34.7 | 83.9 | 100.0 |
| ETHUSDT | autoencoder | 1.4 | 0.3 | 2.2 | 11.8 | 100.0 |
| ETHUSDT | combined | 8.5 | 5.0 | 17.9 | 46.6 | 94.3 |

## Windows above an alert threshold (combined severity)

| Symbol | >= 60 | >= 80 |
|---|---|---|
| BTCUSDT | 1 (0.4%) | 1 (0.4%) |
| ETHUSDT | 2 (0.8%) | 1 (0.4%) |

## Do the two models agree?

| Symbol | Pearson r | Spearman rho | Top-10 overlap |
|---|---|---|---|
| BTCUSDT | 0.55 | 0.46 | 8/10 |
| ETHUSDT | 0.54 | 0.85 | 8/10 |

Agreement between models is not the same as accuracy: there are no ground-truth anomaly labels.

## Train vs held-out (last 20% of windows)

| Symbol | Model | Train n | Train mean | Held-out n | Held-out mean | Difference |
|---|---|---|---|---|---|---|
| BTCUSDT | forest | 208 | 17.5 | 53 | 19.3 | 1.7 |
| BTCUSDT | autoencoder | 208 | 1.6 | 53 | 1.5 | -0.0 |
| ETHUSDT | forest | 208 | 14.0 | 53 | 21.8 | 7.8 |
| ETHUSDT | autoencoder | 208 | 1.4 | 53 | 1.1 | -0.3 |

Held-out rows are scored with scalers fit on the training rows only. A large difference means the latest windows look different from the earlier ones (or the sample is small).

## Most anomalous windows

| Symbol | Window (UTC) | Combined | Forest | Autoencoder | price_velocity | volume_surge_z | trade_frequency | spread_anomaly_score |
|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 10-11 12:44 | 100.0 | 100.0 | 100.0 | 0.667 | 27.36 | 1376 | -1.18 |
| ETHUSDT | 10-11 10:45 | 94.3 | 88.6 | 100.0 | 0.000 | 0.32 | 466 | 58.88 |
| ETHUSDT | 10-11 13:10 | 70.6 | 100.0 | 41.2 | 0.009 | 32.73 | 2124 | 0.14 |
| ETHUSDT | 10-11 12:07 | 51.2 | 86.3 | 16.0 | -0.041 | 1.60 | 2541 | 1.11 |
| BTCUSDT | 10-11 13:28 | 50.7 | 80.5 | 20.9 | -0.306 | 13.30 | 949 | 0.97 |
| BTCUSDT | 10-11 14:13 | 50.7 | 75.7 | 25.6 | 0.343 | 13.97 | 880 | -0.98 |
| BTCUSDT | 10-11 14:32 | 44.5 | 69.9 | 19.2 | 0.527 | 3.65 | 2512 | -0.59 |
| ETHUSDT | 10-11 11:53 | 43.5 | 82.3 | 4.7 | 0.030 | 7.09 | 1730 | -0.05 |

## Limits of these results

- The data covers only the hours listed above, one market regime. Severity is relative to that window.
- No ground-truth labels exist, so 'anomalous' means 'unusual compared with the training data'.
- `spread_anomaly_score` is a maker/taker order-flow proxy, not a real bid-ask spread.
- Combined severity is a simple average of two models, a design choice rather than a tuned one.
