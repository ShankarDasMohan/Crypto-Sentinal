"""
ml/train_autoencoder.py

Trains a small per-symbol Autoencoder on feature_store data as the
second ensemble member alongside the Isolation Forest. Reconstruction
error becomes the anomaly signal, converted to a 0-100 severity using
the same min-max approach as the forest so both models are comparable.

Design assumptions (flag to reviewer if these don't match project intent):
  - One model PER SYMBOL, same reasoning as the Isolation Forest script.
  - Same feature set, same TRAINING_CUTOFF_UTC filter (reused from
    train_isolation_forest.py — keep these two in sync manually for now).
  - Architecture: dense encoder-decoder, 4 -> 2 -> 4. Small on purpose —
    with ~67-90 training rows, a bigger network would just memorize
    rather than learn a compressed "normal" representation.
  - Features are standardized (zero mean, unit variance) before training,
    since MSE reconstruction loss is scale-sensitive and price_velocity /
    trade_frequency / volume_surge_z / spread_anomaly_score are on very
    different raw scales.
  - Severity = min-max scaled per-row reconstruction MSE, scaled against
    this training set's own error range (same convention as the forest).
  - Not enough data yet for a held-out validation split (uses all
    training rows for both fit and reconstruction-error scoring) —
    flagged as a known limitation, not something to silently ignore
    once more data exists.

Run from repo root:
    source .venv/bin/activate
    pip install tensorflow  # if not already installed
    python ml/train_autoencoder.py
"""

import os
from datetime import datetime, timezone

import joblib
import mlflow
import mlflow.tensorflow
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
DB_PORT = os.getenv("POSTGRES_PORT", "5432")  # verify actual port before running
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

MIN_ROWS_TO_TRAIN = 50  # same floor as the forest script — keep in sync

# Same cutoff as train_isolation_forest.py — update both together if you
# re-run after another restart. Set to None to use full history.
TRAINING_CUTOFF_UTC = "2026-09-14 15:17:00+00"

EPOCHS = 100
BATCH_SIZE = 8


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
        print(f"[{symbol}] dropped {before - after} rows with NULL features")
    return df


def build_autoencoder(n_features: int) -> keras.Model:
    inputs = keras.Input(shape=(n_features,))
    encoded = layers.Dense(2, activation="relu")(inputs)
    decoded = layers.Dense(n_features, activation="linear")(encoded)
    model = keras.Model(inputs, decoded)
    model.compile(optimizer="adam", loss="mse")
    return model


def train_symbol_model(symbol: str, df: pd.DataFrame):
    X_raw = df[FEATURE_COLUMNS].values

    feature_scaler = StandardScaler()
    X = feature_scaler.fit_transform(X_raw)

    model = build_autoencoder(n_features=X.shape[1])
    history = model.fit(
        X, X,
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        shuffle=True,
        verbose=0,
    )
    final_loss = history.history["loss"][-1]

    reconstructed = model.predict(X, verbose=0)
    per_row_mse = np.mean(np.square(X - reconstructed), axis=1)

    severity_scaler = MinMaxScaler(feature_range=(0, 100))
    severity = severity_scaler.fit_transform(per_row_mse.reshape(-1, 1)).ravel()

    return model, feature_scaler, severity_scaler, severity, final_loss


def log_and_save(symbol: str, model, feature_scaler, severity_scaler, df, severity, final_loss):
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
        mlflow.log_param("n_training_rows", len(df))
        mlflow.log_param("feature_columns", ",".join(FEATURE_COLUMNS))

        mlflow.log_metric("final_train_loss_mse", float(final_loss))
        mlflow.log_metric("severity_min", float(severity.min()))
        mlflow.log_metric("severity_max", float(severity.max()))
        mlflow.log_metric("severity_mean", float(severity.mean()))
        mlflow.log_metric("severity_p90", float(pd.Series(severity).quantile(0.9)))

        mlflow.log_artifact(model_path, artifact_path="autoencoder_model")
        mlflow.log_artifact(feature_scaler_path, artifact_path="feature_scaler")
        mlflow.log_artifact(severity_scaler_path, artifact_path="severity_scaler")

    print(f"[{symbol}] model saved -> {model_path}")
    print(f"[{symbol}] final training loss (MSE): {final_loss:.4f}")
    print(f"[{symbol}] severity range: {severity.min():.1f} - {severity.max():.1f} (mean {severity.mean():.1f})")


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

        print(f"[{symbol}] training autoencoder on {len(df)} rows...")
        model, feature_scaler, severity_scaler, severity, final_loss = train_symbol_model(symbol, df)
        log_and_save(symbol, model, feature_scaler, severity_scaler, df, severity, final_loss)

    print("Done.")


if __name__ == "__main__":
    main()
