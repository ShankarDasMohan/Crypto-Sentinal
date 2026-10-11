"""
api/main.py  --  CryptoSentinel API

Serves the anomaly scores over HTTP. Data source (set via env vars):
    CS_DATA_SOURCE = csv (default) | postgres
    CS_DATA_PATH   = path to the CSV (default: <repo>/data/scores.csv)

CSV mode needs only: fastapi, uvicorn, pandas  (no Docker/Kafka/Spark/TensorFlow).
Postgres mode additionally needs sqlalchemy + psycopg2-binary, and reads the
POSTGRES_* env vars (defaults match docker-compose.yml).

Run from the repo root:
    uvicorn api.main:app --reload
    -> http://127.0.0.1:8000/docs  (interactive docs)
"""

import json
import os
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query

ROOT = Path(__file__).resolve().parents[1]
DATA_SOURCE = os.getenv("CS_DATA_SOURCE", "csv").lower()
DATA_PATH = Path(os.getenv("CS_DATA_PATH", ROOT / "data" / "scores.csv"))

FEATURES = ["price_velocity", "volume_surge_z", "trade_frequency", "spread_anomaly_score"]

POSTGRES_QUERY = f"""
    SELECT f.id AS feature_id, f.symbol, f.window_start, {', '.join('f.' + c for c in FEATURES)},
           s.forest_severity, s.autoencoder_severity, s.combined_severity
    FROM feature_store f JOIN anomaly_scores s ON s.feature_id = f.id
    ORDER BY f.window_start, f.symbol
"""

app = FastAPI(
    title="CryptoSentinel API",
    version="0.1.0",
    description="Real-time crypto anomaly severity (0-100) per symbol per 1-minute window.",
)


def load_scores() -> pd.DataFrame:
    if DATA_SOURCE == "postgres":
        from sqlalchemy import create_engine  # lazy: CSV mode doesn't need it
        url = "postgresql+psycopg2://{u}:{p}@{h}:{port}/{db}".format(
            u=os.getenv("POSTGRES_USER", "csuser"),
            p=os.getenv("POSTGRES_PASSWORD", "cspass"),
            h=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            db=os.getenv("POSTGRES_DB", "cryptosentinel"),
        )
        df = pd.read_sql(POSTGRES_QUERY, create_engine(url))
    else:
        if not DATA_PATH.exists():
            raise HTTPException(status_code=503, detail=f"Data file not found: {DATA_PATH}")
        df = pd.read_csv(DATA_PATH)
    df["window_start"] = pd.to_datetime(df["window_start"], utc=True)
    return df.sort_values("window_start").reset_index(drop=True)


def to_records(df: pd.DataFrame) -> list:
    out = df.copy()
    out["window_start"] = out["window_start"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return json.loads(out.to_json(orient="records"))


def filter_symbol(df: pd.DataFrame, symbol: Optional[str]) -> pd.DataFrame:
    if symbol is None:
        return df
    symbol = symbol.upper()
    if symbol not in set(df["symbol"]):
        raise HTTPException(status_code=404, detail=f"Unknown symbol '{symbol}'. Try /symbols.")
    return df[df["symbol"] == symbol]


@app.get("/", include_in_schema=False)
def root():
    return {
        "name": "CryptoSentinel API",
        "docs": "/docs",
        "endpoints": ["/health", "/symbols", "/scores/latest", "/scores/top"],
    }


@app.get("/health")
def health():
    df = load_scores()
    return {
        "status": "ok",
        "source": DATA_SOURCE,
        "rows": int(len(df)),
        "latest_window": None if df.empty else df["window_start"].max().strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


@app.get("/symbols")
def symbols():
    return sorted(load_scores()["symbol"].unique().tolist())


@app.get("/scores/latest")
def latest_scores(
    symbol: Optional[str] = Query(None, description="e.g. BTCUSDT; omit for all symbols"),
    limit: int = Query(60, ge=1, le=1000, description="number of most recent windows"),
):
    df = filter_symbol(load_scores(), symbol)
    return to_records(df.tail(limit))


@app.get("/scores/top")
def top_anomalies(
    symbol: Optional[str] = Query(None),
    n: int = Query(10, ge=1, le=100),
):
    df = filter_symbol(load_scores(), symbol)
    return to_records(df.nlargest(n, "combined_severity"))
