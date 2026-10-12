# CryptoSentinel: results

_Generated from `scores.csv` by `ml/make_report.py`. All numbers are computed from that file._

## Dataset

| Symbol | Scored 1-min windows | From (UTC) | To (UTC) | Hours |
|---|---|---|---|---|
| BTCUSDT | 251 | 2026-10-11 10:55 | 2026-10-11 15:05 | 4.2 |
| ETHUSDT | 251 | 2026-10-11 10:55 | 2026-10-11 15:05 | 4.2 |

## Severity distribution (0 = normal, 100 = most anomalous)

| Symbol | Model | Mean | Median | p90 | p99 | Max |
|---|---|---|---|---|---|---|
| BTCUSDT | forest | 19.2 | 15.1 | 43.4 | 75.2 | 100.0 |
| BTCUSDT | autoencoder | 6.9 | 3.1 | 11.9 | 80.9 | 100.0 |
| BTCUSDT | combined | 13.0 | 8.6 | 27.1 | 76.4 | 100.0 |
| ETHUSDT | forest | 16.7 | 11.3 | 36.4 | 78.2 | 100.0 |
| ETHUSDT | autoencoder | 2.0 | 0.7 | 4.0 | 16.8 | 100.0 |
| ETHUSDT | combined | 9.3 | 5.9 | 19.5 | 44.5 | 100.0 |

## Windows above an alert threshold (combined severity)

| Symbol | >= 60 | >= 80 |
|---|---|---|
| BTCUSDT | 5 (2.0%) | 3 (1.2%) |
| ETHUSDT | 1 (0.4%) | 1 (0.4%) |

## Do the two models agree?

| Symbol | Pearson r | Spearman rho | Top-10 overlap |
|---|---|---|---|
| BTCUSDT | 0.74 | 0.29 | 7/10 |
| ETHUSDT | 0.59 | 0.75 | 6/10 |

Agreement between models is not the same as accuracy: there are no ground-truth anomaly labels.

## Train vs held-out (last 20% of windows)

| Symbol | Model | Train n | Train mean | Held-out n | Held-out mean | Difference |
|---|---|---|---|---|---|---|
| BTCUSDT | forest | 200 | 19.2 | 51 | 19.0 | -0.2 |
| BTCUSDT | autoencoder | 200 | 7.4 | 51 | 4.9 | -2.6 |
| ETHUSDT | forest | 200 | 14.7 | 51 | 24.4 | 9.7 |
| ETHUSDT | autoencoder | 200 | 1.7 | 51 | 3.0 | 1.3 |

Held-out rows are scored with scalers fit on the training rows only. A large difference means the latest windows look different from the earlier ones (or the sample is small).

## Most anomalous windows

| Symbol | Window (UTC) | Combined | Forest | Autoencoder | price_velocity | volume_surge_z | trade_frequency | spread_anomaly_score |
|---|---|---|---|---|---|---|---|---|
| BTCUSDT | 10-11 12:44 | 100.0 | 100.0 | 100.0 | 0.667 | 27.36 | 1376 | -1.18 |
| ETHUSDT | 10-11 13:10 | 100.0 | 100.0 | 100.0 | 0.009 | 32.73 | 2124 | 0.14 |
| BTCUSDT | 10-11 12:14 | 81.7 | 68.2 | 95.2 | -0.503 | 0.43 | 2029 | 1.02 |
| BTCUSDT | 10-11 11:55 | 81.4 | 69.4 | 93.3 | -0.626 | 1.82 | 1827 | 0.68 |
| BTCUSDT | 10-11 14:32 | 71.4 | 74.3 | 68.4 | 0.527 | 3.65 | 2512 | -0.59 |
| BTCUSDT | 10-11 13:28 | 60.7 | 80.2 | 41.3 | -0.306 | 13.30 | 949 | 0.97 |
| BTCUSDT | 10-11 13:51 | 57.6 | 55.0 | 60.2 | -0.601 | -0.03 | 1482 | 1.41 |
| BTCUSDT | 10-11 11:49 | 57.3 | 66.1 | 48.4 | 0.900 | 2.19 | 1449 | -1.22 |

## Limits of these results

- The data covers only the hours listed above, one market regime. Severity is relative to that window.
- No ground-truth labels exist, so 'anomalous' means 'unusual compared with the training data'.
- `spread_anomaly_score` is a maker/taker order-flow proxy, not a real bid-ask spread.
- Combined severity is a simple average of two models, a design choice rather than a tuned one.
