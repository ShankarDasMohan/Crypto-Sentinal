-- migrations/001_create_tables.sql
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS raw_trades (
    id          BIGSERIAL,
    symbol      VARCHAR(20)     NOT NULL,
    price       NUMERIC(18, 8)  NOT NULL,
    quantity    NUMERIC(18, 8)  NOT NULL,
    trade_time  TIMESTAMPTZ     NOT NULL,
    is_buyer_mm BOOLEAN,
    trade_id    BIGINT
);

SELECT create_hypertable('raw_trades', 'trade_time', if_not_exists => TRUE);
CREATE INDEX ON raw_trades (symbol, trade_time DESC);
