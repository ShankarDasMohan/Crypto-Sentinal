"""
ml/train_isolation_forest.py

Trains a separate Isolation Forest per symbol on feature_store data,
now with a TIME-BASED train/test split so severity on held-out data
can be reported honestly, not just on the rows the model was fit on.

Design assumptions (flag to reviewer if these don't match project intent):
  - One model PER SYMBOL, not one shared model — scale differences.
  - Split is TIME-BASED, not random shuffle: earliest rows -> train,
    latest rows -> test. Random shuffling would leak future information
    into training for time-series data like this — not appropriate here.
  - TEST_SPLIT_FRACTION = 0.2 (last 20% of the time range held out).
  - MIN_ROWS_FOR_SPLIT floor: below this, splitting leaves too few rows
    on either side to mean anything, so the script falls back to
    training on all data with NO test evaluation, and says so loudly —
    doesn't silently pretend a split happened when it didn't.
  - Severity 0-100 via inverted decision_function, min-max scaled
    against the TRAINING set's range only. Test-set severities are
    scored using that same scaler (not refit), which is the honest way
    to see how the model treats data it never trained on — a test row
    with severity >100 or <0 e.g. would mean it looked more extreme
    than anything in the training set, worth flagging when logged.

Run from repo root:
    source .venv/bin/activate
    python ml/train_isolation_forest.py
"""

import os
from datetime import datetime, timezone

import joblib
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import MinMaxScaler
from sqlalchemy import create_engine

# --- Config -------------------------------------------------------------
DB_USER = os.getenv("POSTGRES_USER", "csuser")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "cspass")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
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

# Below this, no split — not enough rows to make train/test meaningful.
MIN_ROWS_FOR_SPLIT = 150
# Below this even without a split, skip training entirely (same floor as before).
MIN_ROWS_TO_TRAIN = 50

TEST_SPLIT_FRACTION = 0.2

# Set either to None to drop that bound. Update after each fresh honest
# continuous run — these currently scope to the Sep 14 15:17-16:59 stretch.
TRAINING_CUTOFF_UTC = "2026-09-14 15:17:00+00"
TRAINING_CUTOFF_END_UTC = None  # None = no upper bound; widen this as more clean data accumulates


def get_engine():
    conn_str = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(conn_str)


def load_feature_data(engine, symbol: str) -> pd.DataFrame:
    cutoff_clauses = []
    params = {"symbol": symbol}
    if TRAINING_CUTOFF_UTC:
        cutoff_clauses.append("window_start >= %(cutoff_start)s")
        params["cutoff_start"] = TRAINING_CUTOFF_UTC
    if TRAINING_CUTOFF_END_UTC:
        cutoff_clauses.append("window_start < %(cutoff_end)s")
        params["cutoff_end"] = TRAINING_CUTOFF_END_UTC
    cutoff_clause = ("AND " + " AND ".join(cutoff_clauses)) if cutoff_clauses else ""

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
        print(f"[{symbol}] dropped {before - after} rows with NULL features")
    return df.reset_index(drop=True)


def split_train_test(df: pd.DataFrame):
    """Time-based split: earliest rows train, latest rows test. Returns
    (train_df, test_df, did_split: bool)."""
    if len(df) < MIN_ROWS_FOR_SPLIT:
        return df, None, False
    split_idx = int(len(df) * (1 - TEST_SPLIT_FRACTION))
    train_df = df.iloc[:split_idx].reset_index(drop=True)
    test_df = df.iloc[split_idx:].reset_index(drop=True)
    return train_df, test_df, True


def fit_and_score(train_df: pd.DataFrame):
    X_train = train_df[FEATURE_COLUMNS].values

    model = IsolationForest(n_estimators=200, contamination="auto", random_state=42, n_jobs=-1)
    model.fit(X_train)

    raw_train_scores = model.decision_function(X_train)
    inverted_train = -raw_train_scores

    scaler = MinMaxScaler(feature_range=(0, 100))
    train_severity = scaler.fit_transform(inverted_train.reshape(-1, 1)).ravel()

    return model, scaler, train_severity


def score_with_fitted(model, scaler, df: pd.DataFrame):
    X = df[FEATURE_COLUMNS].values
    raw_scores = model.decision_function(X)
    inverted = -raw_scores
    severity = scaler.transform(inverted.reshape(-1, 1)).ravel()
    return severity


def log_and_save(symbol: str, model, scaler, train_df, train_severity,
                  test_df, test_severity, did_split: bool):
    model_path = os.path.join(MODEL_OUTPUT_DIR, f"isolation_forest_{symbol}.joblib")
    scaler_path = os.path.join(MODEL_OUTPUT_DIR, f"severity_scaler_{symbol}.joblib")
    joblib.dump(model, model_path)
    joblib.dump(scaler, scaler_path)

    with mlflow.start_run(run_name=f"isolation_forest_{symbol}_{datetime.now(timezone.utc):%Y%m%dT%H%M%S}"):
        mlflow.log_param("symbol", symbol)
        mlflow.log_param("n_estimators", model.n_estimators)
        mlflow.log_param("contamination", model.contamination)
        mlflow.log_param("n_training_rows", len(train_df))
        mlflow.log_param("did_train_test_split", did_split)
        mlflow.log_param("feature_columns", ",".join(FEATURE_COLUMNS))

        mlflow.log_metric("train_severity_min", float(train_severity.min()))
        mlflow.log_metric("train_severity_max", float(train_severity.max()))
        mlflow.log_metric("train_severity_mean", float(train_severity.mean()))
        mlflow.log_metric("train_severity_p90", float(pd.Series(train_severity).quantile(0.9)))

        if did_split and test_severity is not None:
            mlflow.log_param("n_test_rows", len(test_df))
            mlflow.log_metric("test_severity_min", float(test_severity.min()))
            mlflow.log_metric("test_severity_max", float(test_severity.max()))
            mlflow.log_metric("test_severity_mean", float(test_severity.mean()))
            mlflow.log_metric("test_severity_p90", float(pd.Series(test_severity).quantile(0.9)))
            mean_shift = float(test_severity.mean() - train_severity.mean())
            mlflow.log_metric("test_vs_train_mean_shift", mean_shift)

        mlflow.sklearn.log_model(model, artifact_path="isolation_forest_model")
        mlflow.log_artifact(scaler_path, artifact_path="severity_scaler")

    print(f"[{symbol}] model saved -> {model_path}")
    print(f"[{symbol}] TRAIN severity: {train_severity.min():.1f}-{train_severity.max():.1f} "
          f"(mean {train_severity.mean():.1f}, p90 {pd.Series(train_severity).quantile(0.9):.1f})")
    if did_split and test_severity is not None:
        print(f"[{symbol}] TEST  severity: {test_severity.min():.1f}-{test_severity.max():.1f} "
              f"(mean {test_severity.mean():.1f}, p90 {pd.Series(test_severity).quantile(0.9):.1f})")
        shift = test_severity.mean() - train_severity.mean()
        if abs(shift) > 15:
            print(f"[{symbol}] [Flag] Test mean differs from train mean by {shift:+.1f} points — "
                  f"held-out data looks meaningfully different from training data. Worth investigating "
                  f"whether that's a real regime shift or just small-sample noise.")
    else:
        print(f"[{symbol}] [Flag] No train/test split performed — only {len(train_df)} rows available "
              f"(< {MIN_ROWS_FOR_SPLIT} floor). Severity above reflects fit-to-training-data only, "
              f"not validated on unseen data yet.")


def main():
    mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
    mlflow.set_experiment(MLFLOW_EXPERIMENT_NAME)

    engine = get_engine()
    symbols_df = pd.read_sql("SELECT DISTINCT symbol FROM feature_store", engine)
    symbols = symbols_df["symbol"].tolist()

    if not symbols:
        print("No symbols found in feature_store.")
        return

    print(f"Found symbols in feature_store: {symbols}")

    for symbol in symbols:
        df = load_feature_data(engine, symbol)
        if len(df) < MIN_ROWS_TO_TRAIN:
            print(f"[{symbol}] only {len(df)} usable rows (< {MIN_ROWS_TO_TRAIN} floor) — skipping")
            continue

        train_df, test_df, did_split = split_train_test(df)
        if did_split:
            print(f"[{symbol}] {len(df)} total rows -> train/test split: {len(train_df)}/{len(test_df)}")
        else:
            print(f"[{symbol}] {len(df)} total rows -> no split, training on all {len(train_df)}")

        model, scaler, train_severity = fit_and_score(train_df)

        test_severity = None
        if did_split:
            test_severity = score_with_fitted(model, scaler, test_df)

        log_and_save(symbol, model, scaler, train_df, train_severity, test_df, test_severity, did_split)

    print("Done.")


if __name__ == "__main__":
    main()
