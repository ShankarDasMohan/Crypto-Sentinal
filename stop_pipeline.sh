#!/bin/bash
# stop_pipeline.sh
#
# Gracefully stops the three CryptoSentinel Python processes by sending
# SIGINT (same signal as Ctrl+C) — NOT a hard kill. This matters for
# binance_producer.py specifically: it has a shutdown_requested flag that
# only triggers clean exit on KeyboardInterrupt/SIGINT. A hard kill (-9)
# would skip that and could leave the WebSocket connection in a bad state.
#
# Does NOT touch Docker containers — they're left running on purpose.
# If you also want those down, run `docker compose down` yourself after
# (never `down -v` unless you actually want to wipe pgdata/Kafka data).
#
# Usage:
#   chmod +x stop_pipeline.sh   (only needed once)
#   ./stop_pipeline.sh

PROCESS_PATTERNS=("binance_producer.py" "kafka/consumer.py" "spark/streaming_job.py")

for pattern in "${PROCESS_PATTERNS[@]}"; do
    pids=$(ps aux | grep "$pattern" | grep -v grep | awk '{print $2}')
    if [ -z "$pids" ]; then
        echo "No running process found for: $pattern"
        continue
    fi
    for pid in $pids; do
        echo "Sending SIGINT to $pattern (PID $pid)..."
        kill -SIGINT "$pid"
    done
done

echo ""
echo "== Waiting 5s for graceful shutdown =="
sleep 5

echo "== Remaining matches (should be empty except this grep) =="
ps aux | grep -E "binance_producer|kafka/consumer.py|spark/streaming_job.py" | grep -v grep

echo ""
echo "If any are still listed above, they didn't exit cleanly in time."
echo "Give it a bit longer, or as a last resort: kill -9 <PID>"
