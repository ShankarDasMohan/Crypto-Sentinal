-- dbt/004_alter_feature_store.sql
ALTER TABLE feature_store
    ADD COLUMN IF NOT EXISTS spread_anomaly_score DOUBLE PRECISION;
