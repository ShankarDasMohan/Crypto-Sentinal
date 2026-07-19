# dbt Test Log

Run after every `dbt test`. One entry per run.

## Run Template

**Date:**
**Command:** `dbt test`
**Result:** X passed, Y failed, Z errored

| Test | Model | Column | Status | Notes / Fix |
|---|---|---|---|---|
| not_null | stg_trades | trade_id | ✅ / ❌ | |
| unique | stg_trades | trade_id | ✅ / ❌ | |
| accepted_values | stg_trades | symbol | ✅ / ❌ | |
| not_null | fct_features | window_start | ✅ / ❌ | |
| unique_combination_of_columns | fct_features | symbol, window_start | ✅ / ❌ | |

## Known Failure Patterns to Watch For
- **Null `trade_id`** → usually means the WebSocket payload changed shape or the consumer wrote a partial record.
- **Duplicate `trade_id`** → Kafka consumer re-delivered a message without idempotent upsert (check offset commit logic).
- **`symbol` outside accepted_values** → new pair leaked in from producer, or casing mismatch (`BTCUSDT` vs `btcusdt`).
- **Null feature columns in `fct_features`** → Spark job wrote a partial window before all 4 features were computed; check join logic in the mart.

---

## Run 1

**Date:**
**Result:**

_(fill in after first `dbt test` run)_
