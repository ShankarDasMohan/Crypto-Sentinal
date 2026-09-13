-- dbt/003_alter_feature_store.sql
ALTER TABLE feature_store
    ADD COLUMN IF NOT EXISTS trade_frequency INTEGER;