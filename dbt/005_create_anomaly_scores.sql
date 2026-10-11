-- dbt/005_create_anomaly_scores.sql
-- Stores the ensemble severity for each scored feature_store row.
-- feature_id points at feature_store.id (UNIQUE so a row is never scored twice).
--
-- NOTE: if you ever TRUNCATE feature_store again, TRUNCATE anomaly_scores too.
-- The scorer resumes from MAX(feature_id); a stale pointer would make it
-- silently skip the new rows after feature_store ids restart from 1.

CREATE TABLE IF NOT EXISTS anomaly_scores (
    id                    BIGSERIAL PRIMARY KEY,
    feature_id            BIGINT NOT NULL UNIQUE,
    symbol                VARCHAR(20) NOT NULL,
    window_start          TIMESTAMPTZ NOT NULL,
    forest_severity       DOUBLE PRECISION,
    autoencoder_severity  DOUBLE PRECISION,
    combined_severity     DOUBLE PRECISION,
    scored_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_anomaly_scores_symbol_time
    ON anomaly_scores (symbol, window_start DESC);
