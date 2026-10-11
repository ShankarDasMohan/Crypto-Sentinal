"""
dashboard/app.py  --  CryptoSentinel dashboard (Streamlit)

Data source (env vars):
    CS_DATA_SOURCE = csv (default) | postgres
    CS_DATA_PATH   = path to the CSV (default: <repo>/data/scores.csv)

Run from the repo root:
    streamlit run dashboard/app.py
"""

import os
from pathlib import Path

import pandas as pd
import streamlit as st

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

st.set_page_config(page_title="CryptoSentinel", layout="wide")


@st.cache_data(ttl=30)
def load_scores() -> pd.DataFrame:
    if DATA_SOURCE == "postgres":
        from sqlalchemy import create_engine
        url = "postgresql+psycopg2://{u}:{p}@{h}:{port}/{db}".format(
            u=os.getenv("POSTGRES_USER", "csuser"),
            p=os.getenv("POSTGRES_PASSWORD", "cspass"),
            h=os.getenv("POSTGRES_HOST", "localhost"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            db=os.getenv("POSTGRES_DB", "cryptosentinel"),
        )
        df = pd.read_sql(POSTGRES_QUERY, create_engine(url))
    else:
        df = pd.read_csv(DATA_PATH)
    df["window_start"] = pd.to_datetime(df["window_start"], utc=True)
    return df.sort_values("window_start").reset_index(drop=True)


st.title("CryptoSentinel")
st.caption("Real-time crypto anomaly detection: Binance trades -> Kafka -> Spark -> "
           "Isolation Forest + Autoencoder ensemble. Severity runs from 0 (normal) to 100 (most anomalous).")

if DATA_SOURCE == "csv" and not DATA_PATH.exists():
    st.error(f"Data file not found: {DATA_PATH}")
    st.stop()

df = load_scores()
if df.empty:
    st.warning("No scored rows yet.")
    st.stop()

# ---- sidebar controls -------------------------------------------------
symbol = st.sidebar.selectbox("Symbol", sorted(df["symbol"].unique()))
sym_df = df[df["symbol"] == symbol]
max_rows = len(sym_df)
n_rows = (st.sidebar.slider("Minutes shown", 10, max_rows, min(240, max_rows))
          if max_rows > 10 else max_rows)
threshold = st.sidebar.slider("Alert threshold (combined severity)", 0, 100, 60)
show_models = st.sidebar.checkbox("Show individual models", value=False)
if st.sidebar.button("Reload data"):
    st.cache_data.clear()
    st.rerun()

view = sym_df.tail(n_rows)

# ---- headline numbers -------------------------------------------------
c1, c2, c3, c4 = st.columns(4)
c1.metric("Latest severity", f"{view['combined_severity'].iloc[-1]:.1f}")
c2.metric("Peak in window", f"{view['combined_severity'].max():.1f}")
c3.metric(f"Alerts (>= {threshold})", int((view["combined_severity"] >= threshold).sum()))
c4.metric("Minutes shown", len(view))

# ---- severity over time ----------------------------------------------
st.subheader(f"{symbol}: severity over time (UTC)")
cols = ["combined_severity"]
if show_models:
    cols += ["forest_severity", "autoencoder_severity"]
st.line_chart(view.set_index("window_start")[cols])

# ---- top anomalies -----------------------------------------------------
st.subheader("Most anomalous windows")
shown = ["window_start", "combined_severity", "forest_severity", "autoencoder_severity"] + FEATURES
top = view.sort_values("combined_severity", ascending=False).head(15)[shown]
st.dataframe(top, hide_index=True)

# ---- honest notes ------------------------------------------------------
with st.expander("About this score"):
    st.markdown(
        """
- **Combined severity** is the simple average of an Isolation Forest score and an Autoencoder
  reconstruction-error score, each scaled to 0-100 against the training window.
- **`spread_anomaly_score` is a proxy, not the real bid-ask spread.** The trade stream has no
  order-book data, so it is built from the maker/taker (`isBuyerMaker`) ratio per window,
  z-scored against recent history. It measures order-flow imbalance, not a price gap.
- There are no ground-truth anomaly labels. Severity means "unusual compared with the training
  data", not "confirmed manipulation or an incident".
- Averaging the two models is a design choice, not a proven-optimal one.
        """
    )
