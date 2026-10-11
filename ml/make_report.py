"""
ml/make_report.py

Writes data/RESULTS.md from data/scores.csv using pandas only (no TensorFlow, Spark or
database), so it also runs on the presenter's machine.

    python ml/make_report.py                 # reads data/scores.csv
    python ml/make_report.py path/to/other.csv

Every number in the report is computed from the CSV, nothing is typed in by hand.
Assumption: the training scripts held out the LAST 20% of each symbol's rows (time-based
split). The train-vs-held-out comparison below assumes the CSV holds the same rows the
models were trained on.
"""

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "scores.csv"
OUT = ROOT / "data" / "RESULTS.md"
FEATURES = ["price_velocity", "volume_surge_z", "trade_frequency", "spread_anomaly_score"]
SCORES = ["forest_severity", "autoencoder_severity", "combined_severity"]
TEST_FRACTION = 0.2
ALERT_LEVELS = (60, 80)


def table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def f(x, d=1):
    return f"{x:.{d}f}"


def main():
    if not SRC.exists():
        sys.exit(f"Not found: {SRC}")
    df = pd.read_csv(SRC, parse_dates=["window_start"]).sort_values("window_start")
    out = ["# CryptoSentinel: results", "", f"_Generated from `{SRC.name}` by `ml/make_report.py`. "
           "All numbers are computed from that file._", ""]

    # --- dataset ---
    rows = []
    for sym, g in df.groupby("symbol"):
        hrs = (g["window_start"].max() - g["window_start"].min()).total_seconds() / 3600
        rows.append([sym, len(g), g["window_start"].min().strftime("%Y-%m-%d %H:%M"),
                     g["window_start"].max().strftime("%Y-%m-%d %H:%M"), f(hrs, 1)])
    out += ["## Dataset", "", table(["Symbol", "Scored 1-min windows", "From (UTC)", "To (UTC)", "Hours"], rows), ""]

    # --- severity distribution ---
    rows = []
    for sym, g in df.groupby("symbol"):
        for col in SCORES:
            s = g[col]
            rows.append([sym, col.replace("_severity", ""), f(s.mean()), f(s.median()),
                         f(s.quantile(0.9)), f(s.quantile(0.99)), f(s.max())])
    out += ["## Severity distribution (0 = normal, 100 = most anomalous)", "",
            table(["Symbol", "Model", "Mean", "Median", "p90", "p99", "Max"], rows), ""]

    # --- alerts ---
    rows = []
    for sym, g in df.groupby("symbol"):
        rows.append([sym] + [f"{int((g['combined_severity'] >= t).sum())} ({(g['combined_severity'] >= t).mean():.1%})"
                             for t in ALERT_LEVELS])
    out += ["## Windows above an alert threshold (combined severity)", "",
            table(["Symbol"] + [f">= {t}" for t in ALERT_LEVELS], rows), ""]

    # --- agreement between the two models ---
    rows = []
    for sym, g in df.groupby("symbol"):
        pear = g["forest_severity"].corr(g["autoencoder_severity"])
        spear = g["forest_severity"].rank().corr(g["autoencoder_severity"].rank())
        n = min(10, len(g))
        top_f = set(g.nlargest(n, "forest_severity").index)
        top_a = set(g.nlargest(n, "autoencoder_severity").index)
        rows.append([sym, f(pear, 2), f(spear, 2), f"{len(top_f & top_a)}/{n}"])
    out += ["## Do the two models agree?", "",
            table(["Symbol", "Pearson r", "Spearman rho", "Top-10 overlap"], rows), "",
            "Agreement between models is not the same as accuracy: there are no ground-truth anomaly labels.", ""]

    # --- train vs held-out ---
    rows = []
    for sym, g in df.groupby("symbol"):
        k = int(len(g) * (1 - TEST_FRACTION))
        tr, te = g.iloc[:k], g.iloc[k:]
        for col in ("forest_severity", "autoencoder_severity"):
            rows.append([sym, col.replace("_severity", ""), len(tr), f(tr[col].mean()),
                         len(te), f(te[col].mean()), f(te[col].mean() - tr[col].mean())])
    out += ["## Train vs held-out (last 20% of windows)", "",
            table(["Symbol", "Model", "Train n", "Train mean", "Held-out n", "Held-out mean", "Difference"], rows), "",
            "Held-out rows are scored with scalers fit on the training rows only. A large difference "
            "means the latest windows look different from the earlier ones (or the sample is small).", ""]

    # --- top anomalies ---
    top = df.nlargest(8, "combined_severity")
    rows = [[r.symbol, r.window_start.strftime("%m-%d %H:%M"), f(r.combined_severity), f(r.forest_severity),
             f(r.autoencoder_severity), f(r.price_velocity, 3), f(r.volume_surge_z, 2),
             int(r.trade_frequency), f(r.spread_anomaly_score, 2)] for r in top.itertuples()]
    out += ["## Most anomalous windows", "",
            table(["Symbol", "Window (UTC)", "Combined", "Forest", "Autoencoder", "price_velocity",
                   "volume_surge_z", "trade_frequency", "spread_anomaly_score"], rows), ""]

    out += ["## Limits of these results", "",
            "- The data covers only the hours listed above, one market regime. Severity is relative to that window.",
            "- No ground-truth labels exist, so 'anomalous' means 'unusual compared with the training data'.",
            "- `spread_anomaly_score` is a maker/taker order-flow proxy, not a real bid-ask spread.",
            "- Combined severity is a simple average of two models, a design choice rather than a tuned one.", ""]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
