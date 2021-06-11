# WebSocket server for potential integration with BioBox
# Uses asyncio. If the rest of the project does too, create listen() as a task;
# otherwise, spin off run() as a thread.
# NOTE: As of 20210611, the current version of the websockets library (9.1) does
# not support Python 3.10, and will fail with several errors relating to loop=
# parameters. Downgrade to Python 3.9 until this is fixed.
import asyncio # ImportError? Upgrade to Python 3.7+
import json
from pprint import pprint
import websockets # ImportError? pip install websockets

sockets = { }
stop = None # If this exists, it's a Future that can be set to halt the event loop

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
					# TODO: Callback to elsewhere signalling a new client
					print("New socket with tab ID", tabid)
				else:
					... # TODO: Notify the other one that it's been disconnected
				sockets[tabid] = sock # Possible floop
			elif msg["cmd"] == "setvolume":
				# TODO: Callback to elsewhere with the tabid and volume
				print("Tab", tabid, "vol", msg.get("volume", 0), "(muted)" if msg.get("muted") else "")
	except websockets.ConnectionClosedError:
		pass
	# If this sock isn't in the dict, most likely another socket kicked us,
	# which is uninteresting.
	if sockets.get(tabid) is sock:
		print("Tab gone:", tabid)
		# TODO: Callback to elsewhere signalling a departing client
		del sockets[tabid]

async def send_message(tabid, msg):
	if tabid not in sockets:
		return "Gone" # Other end has gone away. Probably not a problem in practice.
	await sockets[tabid].send(json.dumps(msg))

def send_volume(tabid, vol):
	if not stop:
		return "Not operating" # Probably in the middle of shutdown/cleanup
	# What happens if the buffer fills up and we start another send?
	# Ideally: prevent subsequent sends until the first one finishes, but remember the latest
	# volume selection made. If that's not the same as the first volume, send another after.
	asyncio.run_coroutine_threadsafe(send_message(tabid, {"cmd": "setvolume", "volume": vol}), stop.get_loop())

async def listen():
	global stop; stop = asyncio.get_running_loop().create_future()
	# TODO: Add an SSL context so Chrome allows non-localhost connections
	async with websockets.serve(volume, "localhost", 8888):
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
		for tabid in sockets: send_volume(tabid, r / 100.0)
	halt()
	print("Halt requested.")
import threading; threading.Thread(target=fiddle).start()
# End don't do this

# Non-asyncio entry-point
def run(): asyncio.run(listen())
if __name__ == "__main__":
	try:
		run()
	except KeyboardInterrupt:
		pass
