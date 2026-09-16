#!/bin/bash
# status.sh
#
# One-shot health check for the CryptoSentinel pipeline:
#   - Are the three Python processes alive?
#   - Are the Docker containers up?
#   - What's the row count / continuity of feature_store per symbol?
#   - Have we crossed the 150-row/symbol floor for the train/test split
#     to actually activate in the training scripts?
#
# Read-only — doesn't touch anything, safe to run anytime, including
# while the pipeline is live.
#
# Usage:
#   chmod +x status.sh   (only needed once)
#   ./status.sh

echo "=================================================="
echo "PROCESSES"
echo "=================================================="
ps aux | grep -E "binance_producer|kafka/consumer.py|spark/streaming_job.py" | grep -v grep
if [ $? -ne 0 ]; then
    echo "(none of the three pipeline processes are running)"
fi

echo ""
echo "=================================================="
echo "DOCKER CONTAINERS"
echo "=================================================="
docker compose ps

echo ""
echo "=================================================="
echo "FEATURE_STORE — per-symbol counts and time range"
echo "=================================================="
docker exec -i crypto-sentinal-postgres-1 psql -U csuser -d cryptosentinel -c "
SELECT symbol, count(*), min(window_start), max(window_start)
FROM feature_store
GROUP BY symbol;
"

echo ""
echo "=================================================="
echo "FEATURE_STORE — this session's clean stretch (>= 2026-09-14 15:17 UTC)"
echo "=================================================="
docker exec -i crypto-sentinal-postgres-1 psql -U csuser -d cryptosentinel -c "
SELECT symbol, count(*), min(window_start), max(window_start)
FROM feature_store
WHERE window_start >= '2026-09-14 15:17:00+00'
GROUP BY symbol;
"

echo ""
echo "=================================================="
echo "MOST RECENT 5 ROWS (id DESC — real write-order, not window_start)"
echo "=================================================="
docker exec -i crypto-sentinal-postgres-1 psql -U csuser -d cryptosentinel -c "
SELECT symbol, window_start, id
FROM feature_store
ORDER BY id DESC
LIMIT 5;
"

echo ""
echo "=================================================="
echo "GAP CHECK — largest jump between consecutive window_starts per symbol"
echo "(within the clean stretch only; a gap > 5 min likely means a restart happened)"
echo "=================================================="
docker exec -i crypto-sentinal-postgres-1 psql -U csuser -d cryptosentinel -c "
WITH ordered AS (
  SELECT symbol, window_start,
         window_start - LAG(window_start) OVER (PARTITION BY symbol ORDER BY window_start) AS gap
  FROM feature_store
  WHERE window_start >= '2026-09-14 15:17:00+00'
)
SELECT symbol, max(gap) AS largest_gap
FROM ordered
GROUP BY symbol;
"

echo ""
echo "=================================================="
echo "SPLIT READINESS (training scripts need 150+ rows/symbol to activate the split)"
echo "=================================================="
docker exec -i crypto-sentinal-postgres-1 psql -U csuser -d cryptosentinel -c "
SELECT symbol, count(*) AS rows,
       CASE WHEN count(*) >= 150 THEN 'READY for split' ELSE 'not yet — need ' || (150 - count(*)) || ' more' END AS status
FROM feature_store
WHERE window_start >= '2026-09-14 15:17:00+00'
GROUP BY symbol;
"
