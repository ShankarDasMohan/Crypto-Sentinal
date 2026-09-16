"""
ml/train_autoencoder.py

Trains a small per-symbol Autoencoder on feature_store data, now with
a TIME-BASED train/test split. For an autoencoder specifically, the
held-out test reconstruction loss is a meaningful, direct signal of
whether it learned real structure or just memorized the training rows
— unlike the Isolation Forest, this isn't just a nice-to-have.

Design assumptions (flag to reviewer if these don't match project intent):
  - One model PER SYMBOL, same reasoning as before.
  - Time-based split (earliest -> train, latest -> test), same reasoning
    as the forest script — no random shuffle for time-series data.
  - TEST_SPLIT_FRACTION = 0.2, MIN_ROWS_FOR_SPLIT = 150 (same floors as
    the forest script, kept in sync deliberately).
  - Feature scaler (StandardScaler) is fit on TRAIN ONLY, then applied
    to test — fitting on all data (train+test) would leak test-set
    statistics into training, defeating the point of the split.
  - Severity scaler is also fit on TRAIN reconstruction error only;
    test rows are scored through that same scaler, same reasoning as
    the forest script's test-severity approach.
  - Below MIN_ROWS_FOR_SPLIT: falls back to training on everything, no
    test evaluation, and says so loudly rather than silently.

Run from repo root:
    source .venv/bin/activate
    python ml/train_autoencoder.py
"""

import os
from datetime import datetime, timezone

import joblib
import mlflow
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sqlalchemy import create_engine
from tensorflow import keras
from tensorflow.keras import layers

# --- Config -------------------------------------------------------------
DB_USER = os.getenv("POSTGRES_USER", "csuser")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "cspass")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "cryptosentinel")

MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://localhost:5050")
MLFLOW_EXPERIMENT_NAME = "cryptosentinel_autoencoder"

MODEL_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(MODEL_OUTPUT_DIR, exist_ok=True)

FEATURE_COLUMNS = [
    "price_velocity",
    "volume_surge_z",
    "trade_frequency",
    "spread_anomaly_score",
]

MIN_ROWS_FOR_SPLIT = 150
MIN_ROWS_TO_TRAIN = 50
TEST_SPLIT_FRACTION = 0.2

TRAINING_CUTOFF_UTC = "2026-09-14 15:17:00+00"
TRAINING_CUTOFF_END_UTC = None  # widen as more clean continuous data accumulates

EPOCHS = 100
BATCH_SIZE = 8


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
    if len(df) < MIN_ROWS_FOR_SPLIT:
        return df, None, False
    split_idx = int(len(df) * (1 - TEST_SPLIT_FRACTION))
    train_df = df.iloc[:split_idx].reset_index(drop=True)
    test_df = df.iloc[split_idx:].reset_index(drop=True)
    return train_df, test_df, True


def build_autoencoder(n_features: int) -> keras.Model:
    inputs = keras.Input(shape=(n_features,))
    encoded = layers.Dense(2, activation="relu")(inputs)
    decoded = layers.Dense(n_features, activation="linear")(encoded)
    model = keras.Model(inputs, decoded)
    model.compile(optimizer="adam", loss="mse")
    return model


def fit_and_score(train_df: pd.DataFrame):
    X_train_raw = train_df[FEATURE_COLUMNS].values

    feature_scaler = StandardScaler()
    X_train = feature_scaler.fit_transform(X_train_raw)

    model = build_autoencoder(n_features=X_train.shape[1])
    history = model.fit(X_train, X_train, epochs=EPOCHS, batch_size=BATCH_SIZE, shuffle=True, verbose=0)
    final_train_loss = history.history["loss"][-1]

    reconstructed_train = model.predict(X_train, verbose=0)
    train_mse = np.mean(np.square(X_train - reconstructed_train), axis=1)

    severity_scaler = MinMaxScaler(feature_range=(0, 100))
    train_severity = severity_scaler.fit_transform(train_mse.reshape(-1, 1)).ravel()

    return model, feature_scaler, severity_scaler, train_severity, final_train_loss


def score_with_fitted(model, feature_scaler, severity_scaler, df: pd.DataFrame):
    X_raw = df[FEATURE_COLUMNS].values
    X = feature_scaler.transform(X_raw)
    reconstructed = model.predict(X, verbose=0)
    per_row_mse = np.mean(np.square(X - reconstructed), axis=1)
    severity = severity_scaler.transform(per_row_mse.reshape(-1, 1)).ravel()
    return severity, per_row_mse


def log_and_save(symbol: str, model, feature_scaler, severity_scaler,
                  train_df, train_severity, final_train_loss,
                  test_df, test_severity, test_mse, did_split: bool):
    model_path = os.path.join(MODEL_OUTPUT_DIR, f"autoencoder_{symbol}.keras")
    feature_scaler_path = os.path.join(MODEL_OUTPUT_DIR, f"ae_feature_scaler_{symbol}.joblib")
    severity_scaler_path = os.path.join(MODEL_OUTPUT_DIR, f"ae_severity_scaler_{symbol}.joblib")

    model.save(model_path)
    joblib.dump(feature_scaler, feature_scaler_path)
    joblib.dump(severity_scaler, severity_scaler_path)

    with mlflow.start_run(run_name=f"autoencoder_{symbol}_{datetime.now(timezone.utc):%Y%m%dT%H%M%S}"):
        mlflow.log_param("symbol", symbol)
        mlflow.log_param("architecture", "4-2-4 dense")
        mlflow.log_param("epochs", EPOCHS)
        mlflow.log_param("batch_size", BATCH_SIZE)
        mlflow.log_param("n_training_rows", len(train_df))
        mlflow.log_param("did_train_test_split", did_split)
        mlflow.log_param("feature_columns", ",".join(FEATURE_COLUMNS))

        mlflow.log_metric("final_train_loss_mse", float(final_train_loss))
        mlflow.log_metric("train_severity_min", float(train_severity.min()))
        mlflow.log_metric("train_severity_max", float(train_severity.max()))
        mlflow.log_metric("train_severity_mean", float(train_severity.mean()))
        mlflow.log_metric("train_severity_p90", float(pd.Series(train_severity).quantile(0.9)))

        if did_split and test_severity is not None:
            mlflow.log_param("n_test_rows", len(test_df))
            mlflow.log_metric("test_loss_mse_mean", float(test_mse.mean()))
            mlflow.log_metric("test_severity_min", float(test_severity.min()))
            mlflow.log_metric("test_severity_max", float(test_severity.max()))
            mlflow.log_metric("test_severity_mean", float(test_severity.mean()))
            mlflow.log_metric("test_severity_p90", float(pd.Series(test_severity).quantile(0.9)))
            # The key generalization signal: how much worse (or not) is
            # reconstruction on data the model never saw during training.
            loss_ratio = float(test_mse.mean() / (final_train_loss + 1e-9))
            mlflow.log_metric("test_train_loss_ratio", loss_ratio)

        mlflow.log_artifact(model_path, artifact_path="autoencoder_model")
        mlflow.log_artifact(feature_scaler_path, artifact_path="feature_scaler")
        mlflow.log_artifact(severity_scaler_path, artifact_path="severity_scaler")

    print(f"[{symbol}] model saved -> {model_path}")
    print(f"[{symbol}] TRAIN loss (MSE): {final_train_loss:.4f} | "
          f"severity mean {train_severity.mean():.1f}, p90 {pd.Series(train_severity).quantile(0.9):.1f}")
    if did_split and test_severity is not None:
        loss_ratio = test_mse.mean() / (final_train_loss + 1e-9)
        print(f"[{symbol}] TEST  loss (MSE): {test_mse.mean():.4f} | "
              f"severity mean {test_severity.mean():.1f}, p90 {pd.Series(test_severity).quantile(0.9):.1f}")
        print(f"[{symbol}] Test/train loss ratio: {loss_ratio:.2f}x")
        if loss_ratio > 3:
            print(f"[{symbol}] [Flag] Test reconstruction loss is {loss_ratio:.1f}x the training loss — "
                  f"the model may be overfitting to the training window rather than learning general "
                  f"'normal' patterns. With only ~{len(train_df)} training rows, some of this is expected; "
                  f"worth re-checking once more data is available.")
        else:
            print(f"[{symbol}] Test loss reasonably close to train loss — model generalizes okay on this split.")
    else:
        print(f"[{symbol}] [Flag] No train/test split performed — only {len(train_df)} rows available "
              f"(< {MIN_ROWS_FOR_SPLIT} floor). Severity reflects fit-to-training-data only.")


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

        model, feature_scaler, severity_scaler, train_severity, final_train_loss = fit_and_score(train_df)

        test_severity, test_mse = None, None
        if did_split:
            test_severity, test_mse = score_with_fitted(model, feature_scaler, severity_scaler, test_df)

        log_and_save(symbol, model, feature_scaler, severity_scaler,
                     train_df, train_severity, final_train_loss,
                     test_df, test_severity, test_mse, did_split)

    print("Done.")


if __name__ == "__main__":
    main()
