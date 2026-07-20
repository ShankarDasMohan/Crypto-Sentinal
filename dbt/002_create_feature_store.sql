-- migrations/002_create_feature_store.sql
CREATE TABLE IF NOT EXISTS feature_store (
    id              BIGSERIAL,
    symbol          VARCHAR(20)     NOT NULL,
    window_start    TIMESTAMPTZ     NOT NULL,
    window_end      TIMESTAMPTZ     NOT NULL,
    price_velocity  DOUBLE PRECISION,
    volume_surge_z  DOUBLE PRECISION
);

SELECT create_hypertable('feature_store', 'window_start', if_not_exists => TRUE);
CREATE INDEX ON feature_store (symbol, window_start DESC);
