# WebSocket server for potential integration with BioBox
# Uses asyncio. If the rest of the project does too, create listen() as a task;
# otherwise, spin off run() as a thread.
import asyncio # ImportError? Upgrade to Python 3.7+
import json
import ssl
from pprint import pprint
import websockets # ImportError? pip install websockets

sockets = { }
callbacks = { }
tabs = {}
sites = {
	"music.youtube.com": "YT Music",
	"www.youtube.com": "YouTube",
	"www.twitch.tv": "Twitch",
	"clips.twitch.tv": "Twitch Clips",
	"": "Browser: File",
}

# YouTube only gives a "normalised" value which is different per video. Raising
# the volume above this value has no aural effect in YouTube but is accepted by
# the page. With no way to get the raw volume or the max normalised volume, it
# is impossible to rescale the value to match a 0-100 scale, so the best we can
# do is to use what we have as is.
# TODO: Explore interactively setting YouTube tab to "100%" and scaling normalised
# to 100%

class Browser(Channel):
	group_name = "Browser"
	
	def __init__(self, tabid, tabname):
		super().__init__(name=tabname)
		self.tabid = tabid

	def write_external(self, value):
		spawn(WebSocket.set_volume(self.tabid, (value / 100)))
	
	def muted(self, widget):
		mute_state = super().muted(widget)
		spawn(WebSocket.set_muted(self.tabid, mute_state))

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
				host = str(msg["host"])
				tabid = str(msg["group"])
				if tabid not in sockets:
					cb = callbacks.get("connected")
					if cb: cb(tabid, host)
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

async def set_volume(tabid, vol):
	# What happens if the buffer fills up and we start another send?
	# Ideally: prevent subsequent sends until the first one finishes, but remember the latest
	# volume selection made. If that's not the same as the first volume, send another after.
	await send_message(tabid, {"cmd": "setvolume", "volume": vol})

async def set_muted(tabid, muted):
	await send_message(tabid, {"cmd": "setmuted", "muted": bool(muted)})

async def listen(*, host="", port=8888):
	callbacks.update(connected=new_tab, disconnected=closed_tab, volumechanged=tab_volume_changed)
	ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
	try:
		ssl_context.load_cert_chain("fullchain.pem", "privkey.pem")
	except FileNotFoundError:
		# No cert found. Not an error, just don't support encryption.
		ssl_context = None
	try:
		async with websockets.serve(volume, host, port, ssl=ssl_context) as ws_server:
			print("Websocket listening.")
			await asyncio.Future()
	except OSError as e:
		if e.errno!=(98): # 98: Address already in use
			raise # Task should automatically complete on return if it was errno 98
	finally:
		print("Websocket shutting down.") # I don't hate you!

# Channel management
def new_tab(tabid, host):
	if host in sites:
		tabname = sites[host]
	else:
		tabname = host
	print("Creating channel for new tab:", tabid)
	newtab = Browser(tabid, tabname)
	tabs[tabid] = newtab

def closed_tab(tabid):
	print("Destroying channel for closed tab:", tabid)
	tabs[tabid].remove()
	tabs.pop(tabid, None)

def tab_volume_changed(tabid, volume, mute_state):
	print("On", tabid, ": Volume:", volume, "Muted:", bool(mute_state))
	channel = tabs[tabid]
	channel.refract_value(float(volume * 100), "backend")
	channel.mute.set_active(int(mute_state))

# Non-asyncio entry-point
def run(**kw): asyncio.run(listen(**kw))
if __name__ == "__main__":
	try:
		run()
	except KeyboardInterrupt:
		pass
