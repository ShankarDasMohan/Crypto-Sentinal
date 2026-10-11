"""
ml/score_new_rows.py

Scores new feature_store rows with the trained Isolation Forest + Autoencoder
and writes the ensemble severity to the anomaly_scores table.

Usage (repo root, 3.11 venv active):
    python ml/score_new_rows.py                      # loop forever, every 60s
    python ml/score_new_rows.py --once               # score what's pending, exit
    python ml/score_new_rows.py --model-dir ml/models_old_sep14 --once
                                                     # plumbing test with the old models
    python ml/score_new_rows.py --export-csv data/scores.csv
                                                     # dump features + scores for the demo bundle
                                                     # (does not load TensorFlow)

Design notes (choices, not verified-optimal):
  - combined_severity = simple average of the two models (same as ensemble_score.py).
  - Severities are clipped to [0, 100]. The scalers were fit on the training
    window, so a new row more extreme than anything in training would otherwise
    score above 100.
  - Rows with any NULL feature (warm-up rows) are skipped, never scored.
  - Progress pointer = MAX(feature_id) in anomaly_scores. TRUNCATE both tables together.
"""

import argparse
import os
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

DB_USER = os.getenv("POSTGRES_USER", "csuser")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "cspass")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "cryptosentinel")

FEATURES = ["price_velocity", "volume_surge_z", "trade_frequency", "spread_anomaly_score"]
DEFAULT_MODEL_DIR = Path(__file__).resolve().parent / "models"


def get_engine():
    return create_engine(f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")


def load_models(symbol, model_dir):
    from tensorflow import keras  # imported lazily so --export-csv doesn't need TF
    return {
        "forest": joblib.load(model_dir / f"isolation_forest_{symbol}.joblib"),
        "forest_scaler": joblib.load(model_dir / f"severity_scaler_{symbol}.joblib"),
        "ae": keras.models.load_model(model_dir / f"autoencoder_{symbol}.keras"),
        "ae_feat": joblib.load(model_dir / f"ae_feature_scaler_{symbol}.joblib"),
        "ae_sev": joblib.load(model_dir / f"ae_severity_scaler_{symbol}.joblib"),
    }


def score_frame(df, m):
    X = df[FEATURES].values
    forest = m["forest_scaler"].transform((-m["forest"].decision_function(X)).reshape(-1, 1)).ravel()
    Xs = m["ae_feat"].transform(X)
    recon = m["ae"].predict(Xs, verbose=0)
    mse = np.mean(np.square(Xs - recon), axis=1)
    ae = m["ae_sev"].transform(mse.reshape(-1, 1)).ravel()
    return np.clip(forest, 0, 100), np.clip(ae, 0, 100)


def score_once(engine, model_dir, cache):
    last = pd.read_sql("SELECT COALESCE(MAX(feature_id), 0) AS m FROM anomaly_scores", engine)["m"].iloc[0]
    not_null = " AND ".join(f"{c} IS NOT NULL" for c in FEATURES)
    df = pd.read_sql(
        text(f"SELECT id, symbol, window_start, {', '.join(FEATURES)} "
             f"FROM feature_store WHERE id > :last AND {not_null} ORDER BY id"),
        engine, params={"last": int(last)},
    )
    if df.empty:
        return 0

    total = 0
    for symbol, part in df.groupby("symbol"):
        if symbol not in cache:
            try:
                cache[symbol] = load_models(symbol, model_dir)
            except Exception as e:
                print(f"[{symbol}] could not load models from {model_dir}: {e}")
                cache[symbol] = None
        if cache[symbol] is None:
            continue
        forest, ae = score_frame(part, cache[symbol])
        out = pd.DataFrame({
            "feature_id": part["id"].values,
            "symbol": symbol,
            "window_start": part["window_start"].values,
            "forest_severity": forest,
            "autoencoder_severity": ae,
            "combined_severity": (forest + ae) / 2.0,
        })
        out.to_sql("anomaly_scores", engine, if_exists="append", index=False)
        total += len(out)
    return total


def export_csv(engine, path):
    df = pd.read_sql(
        f"""SELECT f.id AS feature_id, f.symbol, f.window_start, {', '.join('f.' + c for c in FEATURES)},
                   s.forest_severity, s.autoencoder_severity, s.combined_severity
            FROM feature_store f JOIN anomaly_scores s ON s.feature_id = f.id
            ORDER BY f.window_start, f.symbol""",
        engine,
    )
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    print(f"Wrote {len(df)} rows to {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--model-dir", default=str(DEFAULT_MODEL_DIR))
    ap.add_argument("--export-csv")
    args = ap.parse_args()

    engine = get_engine()
    if args.export_csv:
        export_csv(engine, args.export_csv)
        return

    model_dir = Path(args.model_dir)
    cache = {}
    while True:
        n = score_once(engine, model_dir, cache)
        print(f"{time.strftime('%H:%M:%S')} scored {n} new rows")
        if args.once:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
