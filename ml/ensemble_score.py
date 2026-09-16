"""
ml/ensemble_score.py

Loads the trained Isolation Forest and Autoencoder for each symbol,
scores the same feature_store rows with both, combines them into one
ensemble severity, and — importantly — checks whether the two models
actually AGREE on what's anomalous before trusting the combination.

Design assumptions (flag to reviewer if these don't match project intent):
  - Combined severity = simple average of the two models' 0-100 severities.
    This is a real design choice, not a verified "correct" approach — could
    just as easily be max(), a weighted average, or something learned
    later. Flagged, not asserted as right.
  - Scores the SAME rows the models were trained on (same cutoff window),
    since that's the only labeled-ish data available right now. This means
    the "agreement" check below tells you how the two models relate to
    each other on training data, not on genuinely unseen data — same
    no-holdout limitation as both training scripts.
  - Agreement is measured with Pearson correlation between the two
    severity series, plus a look at whether the two models' TOP-5
    highest-severity rows overlap. Low correlation / no overlap would
    mean the "ensemble" is really just noise-averaging two models that
    don't agree on anything — worth knowing before presenting this as
    a working ensemble.

Run from repo root (same venv used for training):
    source .venv/bin/activate
    python ml/ensemble_score.py
"""

import os

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from tensorflow import keras

# --- Config (mirrors the training scripts — keep in sync) ---------------
DB_USER = os.getenv("POSTGRES_USER", "csuser")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "cspass")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "cryptosentinel")

MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")

FEATURE_COLUMNS = [
    "price_velocity",
    "volume_surge_z",
    "trade_frequency",
    "spread_anomaly_score",
]

TRAINING_CUTOFF_UTC = "2026-09-14 15:17:00+00"
TRAINING_CUTOFF_END_UTC = "2026-09-15 00:00:00+00"

TOP_N_TO_SHOW = 5


def get_engine():
    conn_str = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    return create_engine(conn_str)


def load_feature_data(engine, symbol: str) -> pd.DataFrame:
    query = f"""
        SELECT window_start, window_end, {", ".join(FEATURE_COLUMNS)}
        FROM feature_store
        WHERE symbol = %(symbol)s
        AND window_start >= %(cutoff_start)s
        AND window_start < %(cutoff_end)s
        ORDER BY window_start ASC
    """
    df = pd.read_sql(query, engine, params={
        "symbol": symbol,
        "cutoff_start": TRAINING_CUTOFF_UTC,
        "cutoff_end": TRAINING_CUTOFF_END_UTC,
    })
    return df.dropna(subset=FEATURE_COLUMNS)


def score_isolation_forest(symbol: str, df: pd.DataFrame) -> np.ndarray:
    model = joblib.load(os.path.join(MODEL_DIR, f"isolation_forest_{symbol}.joblib"))
    scaler = joblib.load(os.path.join(MODEL_DIR, f"severity_scaler_{symbol}.joblib"))

    X = df[FEATURE_COLUMNS].values
    raw_scores = model.decision_function(X)
    inverted = -raw_scores
    severity = scaler.transform(inverted.reshape(-1, 1)).ravel()
    return severity


def score_autoencoder(symbol: str, df: pd.DataFrame) -> np.ndarray:
    model = keras.models.load_model(os.path.join(MODEL_DIR, f"autoencoder_{symbol}.keras"))
    feature_scaler = joblib.load(os.path.join(MODEL_DIR, f"ae_feature_scaler_{symbol}.joblib"))
    severity_scaler = joblib.load(os.path.join(MODEL_DIR, f"ae_severity_scaler_{symbol}.joblib"))

    X_raw = df[FEATURE_COLUMNS].values
    X = feature_scaler.transform(X_raw)
    reconstructed = model.predict(X, verbose=0)
    per_row_mse = np.mean(np.square(X - reconstructed), axis=1)
    severity = severity_scaler.transform(per_row_mse.reshape(-1, 1)).ravel()
    return severity


def analyze_symbol(symbol: str, df: pd.DataFrame, forest_sev: np.ndarray, ae_sev: np.ndarray):
    combined = (forest_sev + ae_sev) / 2.0

    result = df.copy()
    result["forest_severity"] = forest_sev
    result["autoencoder_severity"] = ae_sev
    result["combined_severity"] = combined

    correlation = np.corrcoef(forest_sev, ae_sev)[0, 1]

    forest_top = set(result.nlargest(TOP_N_TO_SHOW, "forest_severity").index)
    ae_top = set(result.nlargest(TOP_N_TO_SHOW, "autoencoder_severity").index)
    overlap = forest_top & ae_top

    print(f"\n=== {symbol} ===")
    print(f"Pearson correlation between forest and autoencoder severity: {correlation:.3f}")
    print(f"Top-{TOP_N_TO_SHOW} overlap between the two models: {len(overlap)}/{TOP_N_TO_SHOW} rows")
    if correlation < 0.3:
        print("[Flag] Low correlation — the two models are NOT agreeing much on what's anomalous. "
              "Averaging them may just be noise-cancelling rather than a meaningful ensemble.")
    elif correlation < 0.6:
        print("[Flag] Moderate correlation — partial agreement. Worth eyeballing the actual "
              "top rows below before trusting the combined score.")
    else:
        print("Reasonable agreement between the two models.")

    print(f"\nTop-{TOP_N_TO_SHOW} rows by combined severity:")
    top_combined = result.nlargest(TOP_N_TO_SHOW, "combined_severity")
    cols_to_show = ["window_start"] + FEATURE_COLUMNS + [
        "forest_severity", "autoencoder_severity", "combined_severity"
    ]
    print(top_combined[cols_to_show].to_string(index=False))

    return result


def main():
    engine = get_engine()
    symbols_df = pd.read_sql("SELECT DISTINCT symbol FROM feature_store", engine)
    symbols = symbols_df["symbol"].tolist()

    if not symbols:
        print("No symbols found in feature_store.")
        return

    all_results = []
    for symbol in symbols:
        df = load_feature_data(engine, symbol)
        if df.empty:
            print(f"[{symbol}] no rows in the configured training window — skipping")
            continue

        forest_sev = score_isolation_forest(symbol, df)
        ae_sev = score_autoencoder(symbol, df)
        result = analyze_symbol(symbol, df, forest_sev, ae_sev)
        all_results.append(result)

    if all_results:
        combined_df = pd.concat(all_results, ignore_index=True)
        out_path = os.path.join(MODEL_DIR, "ensemble_scored_rows.csv")
        combined_df.to_csv(out_path, index=False)
        print(f"\nFull scored dataset written to: {out_path}")


if __name__ == "__main__":
    main()
