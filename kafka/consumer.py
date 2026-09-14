# kafka/consumer.py
import json
import os
from datetime import datetime, timezone

import psycopg2
from dotenv import load_dotenv

from kafka import KafkaConsumer

load_dotenv()
KAFKA_TOPIC = "binance_trades"
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DB = os.getenv("PG_DB", "cryptosentinel")
PG_USER = os.getenv("PG_USER", "csuser")
PG_PASSWORD = os.getenv("PG_PASSWORD", "cspass")

INSERT_SQL = """
INSERT INTO raw_trades (symbol, price, quantity, trade_time, is_buyer_mm, trade_id)
VALUES (%s, %s, %s, %s, %s, %s)
"""

def get_conn():
    return psycopg2.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASSWORD
    )

def run():
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BROKER,
        value_deserializer=lambda v: v,  # raw bytes — parse inside the loop, not here
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        group_id="raw_trades_writer"
    )
    conn = get_conn()
    conn.autocommit = True
    cur = conn.cursor()
    print("Consumer started, writing to raw_trades...")

    count = 0
    for msg in consumer:
        try:
            payload = json.loads(msg.value.decode("utf-8"))
            data = payload.get("data", payload)  # handles both wrapped and unwrapped messages
            trade_time = datetime.fromtimestamp(data["T"] / 1000, tz=timezone.utc)
            cur.execute(INSERT_SQL, (
                data["s"],
                data["p"],
                data["q"],
                trade_time,
                data["m"],
                data["t"]
            ))
            count += 1
            if count % 100 == 0:
                print(f"Inserted {count} trades")
        except Exception as e:
            print(f"Insert error: {e} | raw: {msg.value}")

if __name__ == "__main__":
    run()
