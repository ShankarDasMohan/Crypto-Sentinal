# ingestion/binance_producer.py
import websocket, json, os 
from kafka import KafkaProducer 
from dotenv import load_dotenv

load_dotenv()
SYMBOLS = ["btcusdt", "ethusdt"]
KAFKA_TOPIC = "binance_trades"
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BROKER,
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

def on_message(ws, message):
    data = json.loads(message)
    producer.send(KAFKA_TOPIC, data)

def on_error(ws, error):
    print(f"WS Error: {error}")

shutdown_requested = False

def on_close(ws, *args):
    if shutdown_requested:
        print("WS closed — shutting down.")
    else:
        print("WS closed unexpectedly — reconnecting...")
        run()

def run():
    streams = "/".join([f"{s}@trade" for s in SYMBOLS])
    url = f"wss://stream.binance.com:9443/stream?streams={streams}"
    ws = websocket.WebSocketApp(
        url,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    try:
        ws.run_forever()
    except KeyboardInterrupt:
        global shutdown_requested
        shutdown_requested = True
        ws.close()
        print("Interrupted — closing WebSocket and exiting.")

if __name__ == "__main__":
    run()