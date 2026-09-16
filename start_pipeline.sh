#!/bin/bash
# start_pipeline.sh
#
# Starts CryptoSentinel's full pipeline in the right order:
#   1. docker compose up -d (Kafka/Postgres/Zookeeper/MLflow), waits briefly
#   2. binance_producer.py — in its own new Terminal tab
#   3. consumer.py — in its own new Terminal tab (small delay after producer,
#      so Kafka has the topic/broker ready before the consumer connects)
#   4. streaming_job.py — in its own new Terminal tab (delay after consumer,
#      same reasoning — wants live data flowing before it starts batching)
#
# Assumes:
#   - Run from the repo root (cd here first, or edit REPO_DIR below)
#   - .venv already exists and has all packages installed
#   - Docker Desktop is already open (this does NOT launch Docker Desktop
#     itself — only runs `docker compose up`, which needs the app running)
#
# This does NOT clear the Spark checkpoint automatically — that's a
# deliberate choice, not an oversight. If you hit the stale-offset error
# again, clear it yourself first:
#   rm -rf /tmp/cryptosentinel_checkpoints/streaming_job
# then run this script.
#
# Usage:
#   chmod +x start_pipeline.sh   (only needed once)
#   ./start_pipeline.sh

set -e

REPO_DIR="/Users/joelsaji/Desktop/Programming/CryptoSentinal/Crypto-Sentinal"

echo "== Starting Docker services =="
cd "$REPO_DIR"
docker compose up -d

echo "== Waiting 8s for containers to settle =="
sleep 8

open_terminal_tab() {
    local title="$1"
    local command="$2"
    osascript <<EOF
tell application "Terminal"
    activate
    tell application "System Events" to keystroke "t" using command down
    delay 0.5
    do script "cd '$REPO_DIR' && source .venv/bin/activate && echo '== $title ==' && $command" in front window
end tell
EOF
}

echo "== Launching binance_producer.py =="
open_terminal_tab "binance_producer.py" "python ingestion/binance_producer.py"
sleep 5

echo "== Launching consumer.py =="
open_terminal_tab "consumer.py" "python kafka/consumer.py"
sleep 5

echo "== Launching streaming_job.py =="
open_terminal_tab "streaming_job.py" "python spark/streaming_job.py"

echo "== All three launched in separate Terminal tabs =="
echo "Check each tab to confirm no startup errors."
