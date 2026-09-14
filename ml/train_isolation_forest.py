"""
ml/train_isolation_forest.py

Trains a separate Isolation Forest per symbol on feature_store data,
converts raw anomaly scores into a 0-100 severity, logs each run to
MLflow, and saves the fitted model + scaler with joblib.

Design assumptions (flag to reviewer if these don't match project intent):
  - One model PER SYMBOL, not one shared model. price_velocity and
    trade_frequency scales differ a lot between BTCUSDT and ETHUSDT,
    so a shared model would let one symbol's noise dominate.
  - Rows with NULL in any feature column are dropped before training
    (expected for the first ~30 buckets while rolling history warms up).
  - Severity 0-100 = inverted, min-max-scaled decision_function output,
    scaled against the TRAINING set's own score range. This means
    severity is relative to what this symbol's history looked like at
    training time, not an absolute cross-symbol scale.
  - contamination="auto" (sklearn default) — no assumption made about
    what fraction of historical data is "actually" anomalous, since
    that number isn't known and shouldn't be guessed.

Run from repo root:
    source .venv/bin/activate
    python ml/train_isolation_forest.py
"""

import os
import sys
from datetime import datetime, timezone

import joblib
import mlflow
import mlflow.sklearn
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import MinMaxScaler
from sqlalchemy import create_engine

# --- Config -----------------------------------------------------------
# Pull from environment where possible so this doesn't hardcode secrets
# that already live in .env. Adjust var names if your .env uses different
# keys — these are guesses based on the compose file creds, not confirmed
# against an actual .env file. [Unverified]
DB_USER = os.getenv("POSTGRES_USER", "csuser")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "cspass")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")  # verify actual port before running — this has flip-flopped before
DB_NAME = os.getenv("POSTGRES_DB", "cryptosentinel")

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5050")
MLFLOW_EXPERIMENT_NAME = "cryptosentinel_isolation_forest"

MODEL_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(MODEL_OUTPUT_DIR, exist_ok=True)

FEATURE_COLUMNS = [
    "price_velocity",
    "volume_surge_z",
    "trade_frequency",
    "spread_anomaly_score",
]

MIN_ROWS_TO_TRAIN = 50  # arbitrary floor — below this a forest isn't meaningful; raise/lower as needed

# Filters training data to only the current honest continuous streaming run,
# excluding older fragmented sessions (restarts reset rolling-history state,
# so mixing old fragments with a fresh continuous block teaches noise).
# Set to None to use full history again once you trust it's all continuous.
TRAINING_CUTOFF_UTC = "2026-09-14 15:17:00+00"  # start of this session's clean run — update if you re-run later


def get_engine():
    conn_str = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(conn_str)


def load_feature_data(engine, symbol: str) -> pd.DataFrame:
    cutoff_clause = ""
    params = {"symbol": symbol}
    if TRAINING_CUTOFF_UTC:
        cutoff_clause = "AND window_start >= %(cutoff)s"
        params["cutoff"] = TRAINING_CUTOFF_UTC

    query = f"""
        SELECT window_start, window_end, {", ".join(FEATURE_COLUMNS)}
        FROM feature_store
        WHERE symbol = %(symbol)s
        {cutoff_clause}
        ORDER BY window_start ASC
    """
    df = pd.read_sql(query, engine, params=params)
    before = len(df)
    df = df.dropna(subset=FEATURE_COLUMNS)
    after = len(df)
    if before != after:
        print(f"[{symbol}] dropped {before - after} rows with NULL features "
              f"(likely early rolling-history warmup rows)")
    return df


def train_symbol_model(symbol: str, df: pd.DataFrame):
    X = df[FEATURE_COLUMNS].values

    model = IsolationForest(
        n_estimators=200,
        contamination="auto",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X)

    # decision_function: higher = more normal, lower/negative = more anomalous.
    # Invert so higher = more anomalous, then min-max scale to 0-100 against
    # this training set's own range.
    raw_scores = model.decision_function(X)
    inverted = -raw_scores  # now higher = more anomalous

    scaler = MinMaxScaler(feature_range=(0, 100))
    severity = scaler.fit_transform(inverted.reshape(-1, 1)).ravel()

    return model, scaler, severity


def log_and_save(symbol: str, model, scaler, df: pd.DataFrame, severity):
    model_path = os.path.join(MODEL_OUTPUT_DIR, f"isolation_forest_{symbol}.joblib")
    scaler_path = os.path.join(MODEL_OUTPUT_DIR, f"severity_scaler_{symbol}.joblib")
    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)

    with mlflow.start_run(run_name=f"isolation_forest_{symbol}_{datetime.now(timezone.utc):%Y%m%dT%H%M%S}"):
        mlflow.log_param("symbol", symbol)
        mlflow.log_param("n_estimators", model.n_estimators)
        mlflow.log_param("contamination", model.contamination)
        mlflow.log_param("n_training_rows", len(df))
        mlflow.log_param("feature_columns", ",".join(FEATURE_COLUMNS))

        mlflow.log_metric("severity_min", float(severity.min()))
        mlflow.log_metric("severity_max", float(severity.max()))
        mlflow.log_metric("severity_mean", float(severity.mean()))
        # top-of-training-set anomaly rate at a fixed 90th percentile cut,
        # just as a training-time sanity signal, not a production threshold
        mlflow.log_metric("severity_p90", float(pd.Series(severity).quantile(0.9)))

        mlflow.sklearn.log_model(model, artifact_path="isolation_forest_model")
        mlflow.log_artifact(scaler_path, artifact_path="severity_scaler")

    print(f"[{symbol}] model saved -> {model_path}")
    print(f"[{symbol}] scaler saved -> {scaler_path}")
    print(f"[{symbol}] severity range this training set: "
          f"{severity.min():.1f} - {severity.max():.1f} (mean {severity.mean():.1f})")


def main():
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

    engine = get_engine()

    symbols_df = pd.read_sql("SELECT DISTINCT symbol FROM feature_store", engine)
    symbols = symbols_df["symbol"].tolist()

    if not symbols:
        print("No symbols found in feature_store. Is the streaming job running / has it written any rows?")
        sys.exit(1)

    print(f"Found symbols in feature_store: {symbols}")

    for symbol in symbols:
        df = load_feature_data(engine, symbol)
        if len(df) < MIN_ROWS_TO_TRAIN:
            print(f"[{symbol}] only {len(df)} usable rows (< {MIN_ROWS_TO_TRAIN} floor) — skipping for now")
            continue

        print(f"[{symbol}] training on {len(df)} rows...")
        model, scaler, severity = train_symbol_model(symbol, df)
        log_and_save(symbol, model, scaler, df, severity)

    print("Done.")


if __name__ == "__main__":
    main()