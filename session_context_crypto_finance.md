# Project Scope & Objectives

## Project Identity
- **Name:** CryptoSentinel
- **Type:** End-to-end real-time fintech data engineering + ML portfolio project
- **Team:** 2 members — Person A (primary builder), Person B (reviewer/tester, few tasks)
- **Timeline:** July 17 – July 31, 2026 (15 days, 2–3 hrs/day side project pace)
- **Goal:** Ingest live crypto tick data → compute manipulation signals → detect anomalies via ensemble ML → serve via FastAPI + Streamlit dashboard

## Role Split (Locked)
| Member | Role | Responsibilities |
|---|---|---|
| **Person A** | Primary Builder | Writes majority of code across all layers — ingestion, Spark, dbt, ML, API, dashboard |
| **Person B** | Reviewer + Tester | Reviews PRs, writes tests, handles docs, owns 1–2 assigned tasks per phase |

## Cut Features (Time-Constrained)
Given 2–3 hrs/day over 15 days (~30–45 total hours), the following are **cut from MVP** and moved to stretch goals:
- ❌ Cross-exchange comparison (CoinGecko as second feed)
- ❌ MLOps drift detection DAG
- ❌ Wallet Graph / NetworkX / PyVis
- ❌ News Correlation layer (VADER + NewsAPI)
- ❌ GitHub Actions CI

## MVP Scope (What Remains)
- ✅ Binance WebSocket → Kafka → PostgreSQL/TimescaleDB
- ✅ Spark Structured Streaming → 4 feature signals
- ✅ dbt staging + mart models with tests
- ✅ Airflow DAG for feature refresh
- ✅ Isolation Forest + Autoencoder ensemble → severity score 0–100
- ✅ MLflow experiment tracking
- ✅ FastAPI: `/anomalies`, `/severity/{coin}`, `/health`
- ✅ Streamlit: 3-page dashboard (Live Feed, Anomaly Log, Model Health)
- ✅ Docker Compose full stack
- ✅ Deployed at public URL + README + demo video

---

# Current Technical State

## Architecture (MVP, Compressed)
```
Binance WebSocket ──► Kafka ──► Spark Structured Streaming ──► 4 Feature Signals
                                                                        │
                                                              Isolation Forest + Autoencoder
                                                              Severity Scorer (0–100)
                                                                        │
                                                               PostgreSQL/TimescaleDB
                                                               dbt models (staging+marts)
                                                               Airflow DAG (feature refresh)
                                                                        │
                                                         FastAPI (/anomalies, /severity/{coin})
                                                                        │
                                                         Streamlit (3 pages: Live Feed,
                                                         Anomaly Log, Model Health)
```

## Tech Stack (Locked, MVP Only)
| Layer | Tool |
|---|---|
| Streaming | Apache Kafka + Binance WebSocket |
| Processing | Apache Spark Structured Streaming |
| Storage | PostgreSQL + TimescaleDB extension |
| Transform | dbt |
| Orchestration | Apache Airflow |
| ML | scikit-learn (Isolation Forest) + PyTorch (Autoencoder) |
| Experiment Tracking | MLflow |
| Backend | FastAPI |
| Dashboard | Streamlit + Plotly |
| DevOps | Docker + Docker Compose |
| Version Control | Git + GitHub |

## Data Sources (MVP)
- **Binance WebSocket:** `wss://stream.binance.com:9443/ws/<symbol>@trade` — free, unlimited, no key needed
- **Pairs:** BTC/USDT and ETH/USDT only
- CoinGecko, NewsAPI, Alpha Vantage — deferred to v2

## Repository Structure
```
cryptosentinel/
├── ingestion/
│   └── binance_producer.py
├── kafka/
│   └── consumer.py
├── spark/
│   └── streaming_job.py
├── dbt/
│   ├── models/
│   │   ├── staging/        (stg_trades)
│   │   └── marts/          (fct_features, fct_anomalies)
│   └── tests/
├── airflow/
│   └── dags/
│       └── feature_refresh_dag.py
├── ml/
│   ├── isolation_forest.py
│   ├── autoencoder.py
│   └── severity_scorer.py
├── api/
│   └── main.py
├── dashboard/
│   └── app.py
├── tests/
│   ├── test_ingestion.py
│   ├── test_features.py
│   ├── test_ml.py
│   └── test_api.py
├── mlflow/
├── docker-compose.yml
└── README.md
```

---

# 2-Week Sprint Roadmap (Jul 17–31, 2026)

## Phase Structure
| Phase | Days | Dates | Focus |
|---|---|---|---|
| Phase 1 | Days 1–3 | Jul 17–19 | Setup + Ingestion |
| Phase 2 | Days 4–6 | Jul 20–22 | Spark + Features + dbt |
| Phase 3 | Days 7–9 | Jul 23–25 | Airflow + ML + MLflow |
| Phase 4 | Days 10–12 | Jul 26–28 | FastAPI + Streamlit |
| Phase 5 | Days 13–15 | Jul 29–31 | Deploy + Polish + Demo |

---

## Phase 1 — Setup + Ingestion (Jul 17–19)

### 🟢 START HERE (Day 1, Jul 17)
A writes `docker-compose.yml` with Kafka + Zookeeper + PostgreSQL/TimescaleDB + MLflow. B creates GitHub repo with branch protection on main.

### Person A Tasks
- Write `docker-compose.yml` — Kafka, Zookeeper, PostgreSQL (timescale/timescaledb:latest-pg15), MLflow
- Write `ingestion/binance_producer.py` — Binance WebSocket → Kafka topic `binance_trades`
- Write `kafka/consumer.py` — Kafka consumer → PostgreSQL raw trades table
- Write SQL schema migration — `raw_trades` hypertable with TimescaleDB
- Verify end-to-end: BTC/USDT ticks landing in PostgreSQL

### Person B Tasks
- Create GitHub repo + branch rules (protect main, require 1 PR review)
- Write `.env.example` with all required keys
- Write `README.md` skeleton — project description, setup steps, architecture diagram placeholder

### Person B Review Checkpoints
- Review `docker-compose.yml` PR — check service dependencies, port conflicts, volume mounts
- Review `binance_producer.py` PR — check reconnect logic on WS close, error handling
- Write `tests/test_ingestion.py` — mock Kafka producer, assert message schema

### Day-by-Day
| Day | Date | A Focus | B Focus |
|---|---|---|---|
| 1 | Jul 17 | `docker-compose.yml` + verify `docker compose up` | GitHub repo + branch rules + `.env.example` |
| 2 | Jul 18 | `binance_producer.py` + `consumer.py` | README skeleton + review producer PR |
| 3 | Jul 19 | SQL schema migration + TimescaleDB hypertable | `test_ingestion.py` + verify data in DB |

### Deliverable
Live BTC/USDT + ETH/USDT tick data writing to PostgreSQL `raw_trades` hypertable via Kafka

---

## Phase 2 — Spark + Features + dbt (Jul 20–22)

### 🟢 START HERE (Day 4, Jul 20)
A sets up Spark session reading from Kafka topic `binance_trades`. Write each feature formula as a plain Python function and unit test it first — then port to Spark windows.

### Person A Tasks
- Write `spark/streaming_job.py` — read Kafka → compute 4 features → write to `feature_store` table
  - Feature 1: price velocity — rate of change per 1-min tumbling window
  - Feature 2: volume surge — z-score vs 1-hr sliding window mean
  - Feature 3: bid-ask spread anomaly score
  - Feature 4: trade frequency — count per 10-sec window
- Write `dbt/models/staging/stg_trades.sql` — clean raw trades
- Write `dbt/models/marts/fct_features.sql` — join all 4 feature signals

### Person B Tasks
- Write `dbt/tests/` — not_null, unique, accepted_values on all key columns in stg_trades and fct_features
- Run `dbt test` and document failures

### Person B Review Checkpoints
- Review `streaming_job.py` PR — check window types, watermark config, null handling
- Review dbt models PR — check refs, sources.yml, model dependencies
- Write `tests/test_features.py` — unit test each feature formula function in isolation

### Day-by-Day
| Day | Date | A Focus | B Focus |
|---|---|---|---|
| 4 | Jul 20 | Spark session + Feature 1 (price velocity) + Feature 2 (volume surge) | Review Phase 1 PRs + dbt init + `stg_trades.sql` |
| 5 | Jul 21 | Feature 3 (spread) + Feature 4 (trade freq) + write to feature_store | dbt tests + `fct_features.sql` review |
| 6 | Jul 22 | `fct_features.sql` mart + end-to-end Spark → dbt test | `test_features.py` + run `dbt test` + fix failures |

### Deliverable
4 feature signals writing to `feature_store` table every minute; dbt models passing all tests

---

## Phase 3 — Airflow + ML + MLflow (Jul 23–25)

### 🟢 START HERE (Day 7, Jul 23)
A adds Airflow to `docker-compose.yml` and writes feature refresh DAG first. Then load `feature_store` into a DataFrame and run Isolation Forest with default params before tuning.

### Person A Tasks
- Add Airflow service to `docker-compose.yml`
- Write `airflow/dags/feature_refresh_dag.py` — daily dbt run + feature table refresh
- Write `ml/isolation_forest.py` — train on feature_store data, log to MLflow
- Write `ml/autoencoder.py` — 3-layer PyTorch encoder-decoder, train on normal data, log to MLflow
- Write `ml/severity_scorer.py` — weighted fusion of IF + AE scores → int 0–100
- Register best model in MLflow model registry via `MlflowClient().transition_model_version_stage()`

### Person B Tasks
- Write `tests/test_ml.py` — assert severity_scorer output is int, 0–100 range, handles edge cases
- Evaluate both models: compute precision, recall, F1 on labelled anomaly subset
- Document model comparison results in `docs/model_eval.md`

### Person B Review Checkpoints
- Review Airflow DAG PR — check schedule_interval, task dependencies, on_failure_callback
- Review `isolation_forest.py` PR — check contamination param (start 0.05 not 0.1), feature normalization
- Review `autoencoder.py` PR — check reconstruction error normalization to 0–1 before scoring

### Day-by-Day
| Day | Date | A Focus | B Focus |
|---|---|---|---|
| 7 | Jul 23 | Airflow docker setup + `feature_refresh_dag.py` | Review Spark PRs + `test_ml.py` skeleton |
| 8 | Jul 24 | `isolation_forest.py` + MLflow logging + model registry | Evaluate IF output + `test_ml.py` assertions |
| 9 | Jul 25 | `autoencoder.py` + `severity_scorer.py` + MLflow registration | Model eval doc + review ML PRs |

### Deliverable
2 models registered in MLflow; severity scorer returning 0–100 per event; Airflow DAG running on schedule

---

## Phase 4 — FastAPI + Streamlit (Jul 26–28)

### 🟢 START HERE (Day 10, Jul 26)
A creates `api/main.py` with `/health` endpoint first — confirm it runs before adding DB queries. Create `dashboard/app.py` with one static Plotly chart before connecting live data.

### Person A Tasks
- Write `api/main.py`:
  - `GET /health` — service liveness check
  - `GET /anomalies` — paginated, filterable from `feature_store`
  - `GET /severity/{coin}` — latest severity score for BTC or ETH
- Write `dashboard/app.py` — 3-page Streamlit app:
  - Page 1: Live Feed — real-time price + severity score ticker
  - Page 2: Anomaly Log — filterable table with severity colour coding (🟢🟡🔴)
  - Page 3: Model Health — IF vs AE score distributions, last retrain timestamp

### Person B Tasks
- Write `tests/test_api.py` — test all 3 endpoints with FastAPI TestClient, assert response schemas
- Manual UI test checklist — verify all 3 pages load, data refreshes, filters work

### Person B Review Checkpoints
- Review `main.py` PR — check async endpoints, error handling (404 for unknown coin), pagination params
- Review `app.py` PR — check `st.cache_data` usage, no localStorage, session_state for filters
- Run `test_api.py` and report failures to A

### Day-by-Day
| Day | Date | A Focus | B Focus |
|---|---|---|---|
| 10 | Jul 26 | FastAPI `/health` + `/anomalies` + `/severity/{coin}` | `test_api.py` + review API PR |
| 11 | Jul 27 | Streamlit Page 1 (Live Feed) + Page 2 (Anomaly Log) | Manual UI test + report bugs |
| 12 | Jul 28 | Streamlit Page 3 (Model Health) + connect all pages to live DB | Fix bugs from B's test report |

### Deliverable
3 FastAPI endpoints live; 3-page Streamlit dashboard connected to real PostgreSQL data

---

## Phase 5 — Deploy + Polish + Demo (Jul 29–31)

### 🟢 START HERE (Day 13, Jul 29)
A focuses entirely on deployment. B writes final README. No new features. Fix only critical bugs that block the demo.

### Person A Tasks
- Deploy full Docker Compose stack on Railway or Render
- Confirm all services reachable at public URLs
- Tag `v1.0.0` release on GitHub
- Fix only critical deployment bugs (port mapping, env vars in production)

### Person B Tasks
- Write final `README.md` — setup guide, architecture diagram, feature list, screenshots, demo video link
- Prepare 5-min demo script — what to show, in what order, what metrics to highlight
- Take screenshots of all 3 dashboard pages for README

### Person B Review Checkpoints
- Verify deployed app end-to-end — data flows from Binance → dashboard at public URL
- Final code review — remove debug prints, hardcoded values, commented-out blocks

### Day-by-Day
| Day | Date | A Focus | B Focus |
|---|---|---|---|
| 13 | Jul 29 | Deploy to Railway/Render — get all services up | README final version + demo script |
| 14 | Jul 30 | Fix deployment bugs + verify live data at public URL | Screenshots + end-to-end verification |
| 15 | Jul 31 | Tag v1.0.0 + final cleanup | Record 5-min demo video (both narrate) |

### Deliverable
Deployed public URL + polished GitHub repo + README with screenshots + 5-min demo video + v1.0.0 tag

---

# Critical Hard Constraints & Exclusions

## Role Rules (Non-Negotiable)
- ✅ Person A writes majority of code in every phase
- ✅ Person B reviews every PR before merge — no direct push to main
- ✅ Person B writes all test files (`test_*.py`)
- ✅ Person B owns README, docs, demo script
- ❌ Person B does NOT write core pipeline code (producer, Spark, ML models, API)
- ❌ Person A does NOT merge their own PRs — B must approve

## Feature Cuts (Firm — Do Not Re-add Unless All MVP Items Done)
- ❌ CoinGecko second exchange feed
- ❌ NewsAPI + VADER sentiment layer
- ❌ NetworkX wallet graph + PyVis
- ❌ Louvain community detection
- ❌ MLOps drift detection DAG + auto-retraining
- ❌ GitHub Actions CI/CD
- ❌ Cross-exchange arbitrage detection
- ❌ Streamlit Pages 4 and 5

## Banned Patterns
- ❌ No hardcoded API keys — use `.env` + `python-dotenv`
- ❌ No `localStorage` or `sessionStorage` in Streamlit/HTML
- ❌ No `<form>` HTML tags in any frontend component
- ❌ No binary anomaly output — severity score 0–100 only
- ❌ No skipping MLflow — every model run must be logged
- ❌ No new features after Day 12 (Jul 28)
- ❌ No merging without B's PR approval

## Known Risks
- Binance WebSocket disconnects after 24hr — `binance_producer.py` must implement reconnect in `on_close`
- TimescaleDB requires PostgreSQL 14+ — use `timescale/timescaledb:latest-pg15` image specifically
- Isolation Forest `contamination` param — start at 0.05, not default 0.1 (too high for crypto)
- Autoencoder reconstruction error — normalize to 0–1 before passing to `severity_scorer.py`
- Streamlit re-runs on every interaction — use `st.cache_data` on all DB query functions
- Railway free tier may sleep containers — use Render always-on or paid tier for demo day
- MLflow model registry — `log_model` and `register_model` are separate steps; both required

---

# Immediate Next Steps

## Today — Jul 17 (Day 1)
1. **A:** Write `docker-compose.yml` with Kafka + Zookeeper + PostgreSQL (timescale/timescaledb:latest-pg15) + MLflow — run `docker compose up`, confirm all 4 services healthy
2. **B:** Create GitHub repo + enable branch protection on main (require 1 review, no direct push to main)
3. **A:** Write `ingestion/binance_producer.py` — connect to `wss://stream.binance.com:9443/ws/btcusdt@trade`, print raw JSON to console first before adding Kafka
4. **B:** Write `.env.example` with all placeholder environment variable names
5. **Both:** Sync at end of day — confirm Docker stack runs cleanly on both machines

## Priority Order for Entire Sprint
1. Docker stack running locally — blocker for everything
2. Binance → Kafka → PostgreSQL pipeline — blocker for Spark
3. Spark feature computation — blocker for ML
4. dbt models + tests — can parallel with Spark on Day 5
5. ML models + MLflow — blocker for API
6. Airflow DAG — can parallel with ML on Day 8
7. FastAPI endpoints — blocker for dashboard
8. Streamlit dashboard — final layer
9. Deployment — do not attempt before Day 13 (Jul 29)

---

# Appendices

## A. docker-compose.yml
```yaml
version: '3.8'
services:
  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on: [zookeeper]
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1

  postgres:
    image: timescale/timescaledb:latest-pg15
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: cryptosentinel
      POSTGRES_USER: csuser
      POSTGRES_PASSWORD: cspass
    volumes:
      - pgdata:/var/lib/postgresql/data

  mlflow:
    image: ghcr.io/mlflow/mlflow:latest
    ports:
      - "5000:5000"
    command: mlflow server --host 0.0.0.0

volumes:
  pgdata:
```

## B. binance_producer.py
```python
# ingestion/binance_producer.py
import websocket, json, os
from kafka import KafkaProducer
from dotenv import load_dotenv

load_dotenv()
SYMBOLS = ["btcusdt", "ethusdt"]
KAFKA_TOPIC = "binance_trades"
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKER,
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

def on_message(ws, message):
    data = json.loads(message)
    producer.send(KAFKA_TOPIC, data)

def on_error(ws, error):
    print(f"WS Error: {error}")

def on_close(ws, *args):
    print("WS closed — reconnecting...")
    run()

def run():
    streams = "/".join([f"{s}@trade" for s in SYMBOLS])
    url = f"wss://stream.binance.com:9443/stream?streams={streams}"
    ws = websocket.WebSocketApp(
        url,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

if __name__ == "__main__":
    run()
```

## C. TimescaleDB Schema Migration
```sql
-- migrations/001_create_tables.sql
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS raw_trades (
    id          BIGSERIAL,
    symbol      VARCHAR(20)     NOT NULL,
    price       NUMERIC(18, 8)  NOT NULL,
    quantity    NUMERIC(18, 8)  NOT NULL,
    trade_time  TIMESTAMPTZ     NOT NULL,
    is_buyer_mm BOOLEAN,
    trade_id    BIGINT
);

SELECT create_hypertable('raw_trades', 'trade_time', if_not_exists => TRUE);
CREATE INDEX ON raw_trades (symbol, trade_time DESC);

CREATE TABLE IF NOT EXISTS feature_store (
    symbol          VARCHAR(20)    NOT NULL,
    window_start    TIMESTAMPTZ    NOT NULL,
    price_velocity  NUMERIC(18, 8),
    volume_zscore   NUMERIC(18, 8),
    spread_score    NUMERIC(18, 8),
    trade_frequency INTEGER,
    severity_score  INTEGER        CHECK (severity_score BETWEEN 0 AND 100),
    created_at      TIMESTAMPTZ    DEFAULT NOW()
);

SELECT create_hypertable('feature_store', 'window_start', if_not_exists => TRUE);
```

## D. severity_scorer.py
```python
# ml/severity_scorer.py
def compute_severity(
    if_score: float,
    ae_reconstruction_error: float,
    weights: tuple = (0.5, 0.5)
) -> int:
    """
    if_score: normalized 0-1 (higher = more anomalous)
    ae_reconstruction_error: normalized 0-1
    returns: int 0-100
    Tiers: 0-30 Normal, 31-60 Suspicious, 61-100 Critical
    """
    w1, w2 = weights
    raw = (w1 * if_score) + (w2 * ae_reconstruction_error)
    return min(100, max(0, int(raw * 100)))
```

## E. FastAPI Skeleton
```python
# api/main.py
from fastapi import FastAPI, Query
from typing import Optional

app = FastAPI(title="CryptoSentinel API", version="1.0.0")

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/anomalies")
async def get_anomalies(
    coin: Optional[str] = None,
    min_severity: int = Query(default=0, ge=0, le=100),
    limit: int = Query(default=50, le=200),
    offset: int = 0
):
    # Query feature_store WHERE severity_score >= min_severity
    ...

@app.get("/severity/{coin}")
async def get_severity(coin: str):
    # SELECT severity_score FROM feature_store
    # WHERE symbol = coin ORDER BY window_start DESC LIMIT 1
    ...
```

## F. .env.example
```
KAFKA_BROKER=localhost:9092
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=cryptosentinel
POSTGRES_USER=csuser
POSTGRES_PASSWORD=cspass
MLFLOW_TRACKING_URI=http://localhost:5000
# Deferred to v2:
# NEWSAPI_KEY=
# ALPHAVANTAGE_KEY=
# COINGECKO_KEY=
```

## G. MLflow Logging Pattern
```python
import mlflow
import mlflow.sklearn

with mlflow.start_run(run_name="isolation_forest_v1"):
    mlflow.log_param("contamination", 0.05)
    mlflow.log_param("n_estimators", 100)
    mlflow.log_metric("precision", precision)
    mlflow.log_metric("recall", recall)
    mlflow.log_metric("f1", f1)
    mlflow.sklearn.log_model(model, "isolation_forest")
    mlflow.register_model(
        f"runs:/{mlflow.active_run().info.run_id}/isolation_forest",
        "CryptoSentinel_IF"
    )
```

## H. Stretch Goals (v2 — Post Jul 31)
- CoinGecko second exchange feed + cross-exchange spread detection
- NewsAPI + VADER sentiment layer + news-anomaly correlation
- NetworkX wallet graph + Louvain community detection + PyVis embed
- MLOps: PSI-based drift detection DAG + auto-retraining trigger
- GitHub Actions CI: flake8 + pytest on push to main
- Streamlit Pages 4 + 5: News Context, Wallet Graph

## I. Interview Statement (Both Can Use)
> "I built a real-time crypto anomaly detection system: Kafka ingests live Binance tick data,
> Spark computes 4 manipulation signals per sliding window, an Isolation Forest + Autoencoder
> ensemble scores anomalies 0–100, orchestrated by Airflow with dbt for warehouse transforms
> and MLflow for experiment tracking — deployed end-to-end with FastAPI and a 3-page
> Streamlit dashboard."

## J. Conversation History Summary
- Domain selected: Fintech → Crypto anomaly detection
- Rejected alternatives: Fraud detection (IEEE-CIS), Credit risk, Stock sentiment, Personal finance
- Uniqueness features decided: multi-signal fusion, graph ML, severity scoring, news correlation, cross-exchange — graph ML + news + cross-exchange CUT for MVP
- Two PDFs generated: `CryptoSentinel_Roadmap.pdf` (v1, Jun 4 start) and `CryptoSentinel_Roadmap_v2.pdf` (v2, Jun 10 start, daily breakdown) — both at `/mnt/user-data/outputs/`
- Timeline compressed from 8 weeks → 15-day sprint starting Jul 17
- Role change: from rotating Primary/Secondary → A always Primary, B always Reviewer/Tester
- No code written yet — architecture, roadmap, and context docs only
- Next action: generate Week 1 / Phase 1 starter code on request
