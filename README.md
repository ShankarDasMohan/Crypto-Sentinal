# CryptoSentinel

Real-time anomaly detection on live crypto trades. A Binance WebSocket feeds Kafka, Spark turns the
trade stream into four features per symbol per minute, and an Isolation Forest + Autoencoder
ensemble scores each minute from 0 (normal) to 100 (most anomalous). A FastAPI service and a
Streamlit dashboard serve the scores.

This is a **demonstration project**, built to show an end-to-end streaming data pipeline with an ML
stage. It was not built or tested for production use.

## Architecture

```
Binance WebSocket (BTCUSDT, ETHUSDT trades)
        -> Kafka (topic: binance_trades)
        -> Spark Structured Streaming (4 features per 1-minute window)
        -> PostgreSQL / TimescaleDB (raw_trades, feature_store)
        -> Isolation Forest + Autoencoder -> anomaly_scores (severity 0-100)
        -> FastAPI + Streamlit dashboard
MLflow tracks the training runs.
```

## The four features (per symbol, per 1-minute window)

| Feature | Meaning |
|---|---|
| `price_velocity` | Price change per second over the window |
| `volume_surge_z` | Z-score of the window's volume against the previous ~30 windows |
| `trade_frequency` | Number of trades in the window |
| `spread_anomaly_score` | **A proxy, not the real bid-ask spread.** The trade stream has no order-book data, so this is the maker/taker ratio of trades, z-scored against recent history. It measures order-flow imbalance. |

## Results

See [`data/RESULTS.md`](data/RESULTS.md), generated from `data/scores.csv` by `ml/make_report.py`
(dataset size, severity distribution, model agreement, train vs held-out, top anomalies).

Key limits: a few hours of data from one market regime, no ground-truth anomaly labels (so
"anomalous" means "unusual compared with the training data"), and the combined score is a simple
average of two models.

## Run the demo (no Docker, Kafka or Spark needed)

The dashboard and API read the pre-computed scores in `data/scores.csv`.

**Windows (PowerShell)** (written for Windows but not tested on it yet):
```powershell
git clone <repo-url>
cd Crypto-Sentinal
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1          # if blocked: Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
pip install -r requirements-demo.txt
streamlit run dashboard\app.py
```

**macOS / Linux:**
```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements-demo.txt
streamlit run dashboard/app.py
```

API (second terminal, same venv, repo root): `uvicorn api.main:app` then open
http://127.0.0.1:8000/docs. Endpoints: `/health`, `/symbols`, `/scores/latest`, `/scores/top`.

To regenerate the results report: `python ml/make_report.py`.

## Run the full pipeline (macOS, needs Docker Desktop, Java 17, Python 3.11)

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install websocket-client kafka-python python-dotenv psycopg2-binary pyspark==3.5.1
pip install "pyarrow>=22.0" pandas tensorflow scikit-learn joblib mlflow sqlalchemy

docker compose up -d
for f in dbt/00*.sql; do docker exec -i crypto-sentinal-postgres-1 psql -U csuser -d cryptosentinel < "$f"; done

./start_pipeline.sh        # producer, consumer, Spark job, each in its own Terminal tab
./status.sh                # health check: processes, row counts, gaps
./stop_pipeline.sh         # graceful stop

python ml/train_isolation_forest.py
python ml/train_autoencoder.py
python ml/score_new_rows.py --once
python ml/score_new_rows.py --export-csv data/scores.csv
python ml/make_report.py
```
Once it is running, leave it alone: any restart breaks the continuous run the models train on.
After wiping `feature_store`, also truncate `anomaly_scores` and delete
`/tmp/cryptosentinel_checkpoints/streaming_job`.

## Repo layout

```
ingestion/binance_producer.py   WebSocket -> Kafka
kafka/consumer.py               Kafka -> raw_trades
spark/streaming_job.py          features -> feature_store (applyInPandasWithState)
spark/features.py               plain-Python feature formulas
dbt/00*.sql                     table migrations
ml/                             training, scoring, report scripts (models in ml/models/)
api/main.py                     FastAPI
dashboard/app.py                Streamlit
data/                           scores.csv + RESULTS.md (the demo data)
```

## Not built

Airflow scheduling, dbt models and tests, CI, cross-exchange comparison, drift monitoring.

## Lessons from the build

- Kafka had no persistent volume at first. Each Docker restart wiped the topic and made Spark's
  saved offsets invalid, so Kafka and Zookeeper now have named volumes.
- Spark hands timestamps to pandas functions in the session timezone. On an IST machine this
  shifted every window label by 5.5 hours until `spark.sql.session.timeZone=UTC` was set.
- TensorFlow crashed when imported alongside an older `pyarrow` on Python 3.9; moving to Python
  3.11 and `pyarrow>=22` fixed it.
- An unguarded `json.loads` in the Kafka consumer silently killed it on one bad message.