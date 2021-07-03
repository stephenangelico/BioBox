# Listen for hype trains and alert when they happen
import json
import subprocess
import time
import websocket # ImportError? Try: pip install websocket-client

while True:
	try:
		ws = websocket.create_connection("ws://localhost:8888/ws")
		break
	except ConnectionRefusedError:
		print("Unable to connect, retrying...")
		time.sleep(10)
ws.send(json.dumps({"cmd": "init", "type": "volume", "group": "example-id"}))
print("Connected.")
while ws.connected:
	data = ws.recv()
	if not data: break
	data = json.loads(data)
	if data.get("cmd") != "setvolume": continue
	print("Setting volume to", data["volume"])
