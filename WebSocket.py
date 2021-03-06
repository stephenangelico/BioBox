# WebSocket server for potential integration with BioBox
# Uses asyncio. If the rest of the project does too, create listen() as a task;
# otherwise, spin off run() as a thread.
# NOTE: As of 20210611, the current version of the websockets library (9.1) does
# not support Python 3.10, and will fail with several errors relating to loop=
# parameters. Downgrade to Python 3.9 until this is fixed.
import asyncio # ImportError? Upgrade to Python 3.7+
import json
import ssl
from pprint import pprint
import websockets # ImportError? pip install websockets

sockets = { }
stop = None # If this exists, it's a Future that can be set to halt the event loop
callbacks = { }

async def volume(sock, path):
	if path != "/ws": return # Can we send back a 404 or something?
	tabid = None
	try:
		async for msg in sock:
			try: msg = json.loads(msg)
			except json.decoder.JSONDecodeError: continue # Ignore malformed messages
			if not isinstance(msg, dict): continue # Everything should be a JSON object
			if "cmd" not in msg: continue # Every message has to have a command
			if msg["cmd"] == "init":
				if msg.get("type") != "volume": continue # This is the only socket type currently supported
				if "group" not in msg: continue
				tabid = str(msg["group"])
				if tabid not in sockets:
					cb = callbacks.get("connected")
					if cb: cb(tabid)
				else:
					await send_message(tabid, {"cmd": "disconnect"})
				sockets[tabid] = sock # Possible floop
			elif msg["cmd"] == "setvolume":
				cb = callbacks.get("volumechanged")
				if cb: cb(tabid, msg.get("volume", 0), bool(msg.get("muted")))
	except websockets.ConnectionClosedError:
		pass
	# If this sock isn't in the dict, most likely another socket kicked us,
	# which is uninteresting.
	if sockets.get(tabid) is sock:
		cb = callbacks.get("disconnected")
		if cb: cb(tabid)
		del sockets[tabid]

async def send_message(tabid, msg):
	if tabid not in sockets:
		return "Gone" # Other end has gone away. Probably not a problem in practice.
	await sockets[tabid].send(json.dumps(msg))

def set_volume(tabid, vol):
	if not stop:
		return "Not operating" # Probably in the middle of shutdown/cleanup
	# What happens if the buffer fills up and we start another send?
	# Ideally: prevent subsequent sends until the first one finishes, but remember the latest
	# volume selection made. If that's not the same as the first volume, send another after.
	asyncio.run_coroutine_threadsafe(send_message(tabid, {"cmd": "setvolume", "volume": vol}), stop.get_loop())

def set_muted(tabid, muted):
	if not stop:
		return "Not operating"
	asyncio.run_coroutine_threadsafe(send_message(tabid, {"cmd": "setmuted", "muted": bool(muted)}), stop.get_loop())

async def listen(*, connected=None, disconnected=None, volumechanged=None, host="", port=8888):
	callbacks.update(connected=connected, disconnected=disconnected, volumechanged=volumechanged)
	global stop; stop = asyncio.get_running_loop().create_future()
	ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
	try:
		ssl_context.load_cert_chain("fullchain.pem", "privkey.pem")
	except FileNotFoundError:
		# No cert found. Not an error, just don't support encryption.
		ssl_context = None
	async with websockets.serve(volume, host, port, ssl=ssl_context):
		print("Listening.")
		await stop
		print("Shutting down.") # I don't hate you!
	stop = None

def halt():
	if not stop: return "Already stopping"
	stop.get_loop().call_soon_threadsafe(stop.set_result, "halt() called")

# Yeah don't do this
def fiddle():
	while True:
		import time; time.sleep(2)
		import random; r = random.randrange(100)
		print("Fiddling!", r)
		if not r: break
		for tabid in sockets: set_volume(tabid, r / 100.0)
	halt()
	print("Halt requested.")
#import threading; threading.Thread(target=fiddle).start()
# End don't do this

# Non-asyncio entry-point
def run(**kw): asyncio.run(listen(**kw))
if __name__ == "__main__":
	try:
		run()
	except KeyboardInterrupt:
		pass
