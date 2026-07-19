import websocket, json

def on_message(ws, message):
    data = json.loads(message)
    print(data)

def on_error(ws, error):
    print(f"WS Error: {error}")

def on_close(ws, *args):
    print("WS closed")

if __name__ == "__main__":
    url = "wss://stream.binance.com:9443/ws/btcusdt@trade"
    ws = websocket.WebSocketApp(
        url,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()