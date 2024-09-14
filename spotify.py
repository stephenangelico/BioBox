import asyncio
import socket
import json
import secrets
import time
import base64
import webbrowser
import urllib.parse
import aiohttp
from aiohttp import web

spotify_config = {}
try:
	with open('spotify.json', 'r') as f:
		spotify_config = json.load(f)
except FileNotFoundError:
	pass # TODO: disable until configured (chained TODO: make config dialog)

redirect_uri = "http://localhost:8889/spotify_login"
state = None # Set in user_auth() and checked in get_auth_code()
scope = "user-modify-playback-state user-read-playback-state"
base_uri = "https://api.spotify.com/v1"
session = None
auth_runner = None

spotify_channel = None
vol_retry_claimed = False
last_values_sent = {}
next_vol = None
next_vol_time = time.monotonic()

class Spotify(Channel):
	group_name = "Spotify"
	
	def __init__(self):
		super().__init__(name="Spotify")
	
	def write_external(self, value):
		global next_vol
		if not self.mute.get_active(): # TODO: this check belongs in vol_update()
			next_vol = value
			spawn(vol_update())
	
	def muted(self, widget):
		# Spotify does not seem to have a mute function, instead the mute button sets
		# volume to zero for muting and sets volume to the "last" volume when unmuting.
		# However, this is somewhat inconsistent in the web interface as it sometimes
		# restores an old volume instead.
		global next_vol
		mute_state = super().muted(widget) # Handles label change and IIDPIO
		if mute_state:
			next_vol = 0
		else:
			next_vol = self.slider.get_value()

	def refract_value(self, value, source):
		"""Send value to multiple places, keeping track of sent value to avoid bounce or slider fighting."""
		if abs(value - self.oldvalue) >= 1: # Prevent feedback loop when moving slider
			# TODO: Put this all in poll_volume() - this may render subclassing refract_value unnecessary entirely
			if source == "backend" and value == 0:
				self.mute.set_active(True) # Question: This sends volume=0 to Spotify. When the player unmutes, what does it restore to? Probably the same as otherwise.
			else:
				super().refract_value(value, source)
			if source == "backend" and value > 0 and self.mute.get_active():
				self.mute.set_active(False)

async def get_auth_code(request):
	params = request.query
	if params["state"] == state:
		if "code" in params:
			spawn(get_access_token(params["code"]))
		else:
			print(params["error"]) # If we got a response and didn't get a code, we should have an error
	try:
		return web.Response(body="")
	finally:
		global auth_runner
		await auth_runner.cleanup()
		auth_runner = None

async def get_access_token(request_code, mode="new"):
	if "authorization" not in spotify_config:
		gen_auth_header()
	params_new = {"grant_type": "authorization_code", "code": request_code, "redirect_uri": redirect_uri}
	params_refresh = {"grant_type": "refresh_token", "refresh_token": request_code}
	headers = {"Content-Type": "application/x-www-form-urlencoded", "Authorization": spotify_config["authorization"]}
	if mode == "refresh":
		params = params_refresh
	else:
		params = params_new	
	async with session.post('https://accounts.spotify.com/api/token', params=params, headers=headers) as resp:
		resp.raise_for_status()
		token_response = await resp.json()
		for key in token_response:
			spotify_config[key] = token_response[key]
		# Generate renewal time (5 seconds before actual expiry)
		spotify_config["expires_at"] = time.time() + spotify_config["expires_in"] - 5
		save_config()
		print("New access token stored.")

def save_config():
	with open('spotify.json', 'w') as f:
		json.dump(spotify_config, f)

def gen_auth_header():
	# TODO: Find out when this needs to be rerun if invalid (eg if client secret changes)
	spotify_config["authorization"] = "Basic " + base64.b64encode((spotify_config["client_id"] + ":" + spotify_config["client_secret"]).encode()).decode()
	save_config()

async def poll_playback():
	path = "/me/player" # Get Playback State
	headers = {"Authorization": "Bearer " + spotify_config["access_token"]}
	global spotify_channel
	inactive = False
	while True:
		await asyncio.sleep(2) # Subject to experimentation
		async with session.get(base_uri + path, headers=headers) as resp:
			if resp.status == 200:
				inactive = False
				playback_state = await resp.json()
				value = playback_state["device"]["volume_percent"]
				if spotify_channel:
					if value != spotify_channel.slider.get_value():
						if time.time() > last_values_sent.get(value, 0) + 3:
							# Value was sent over 3 sec ago or never, probably not feedback (subject to experimentation)
							spotify_channel.refract_value(value, "backend")
				else:
					spotify_channel = Spotify()
					spotify_channel.refract_value(value, "backend")
			if resp.status == 204:
				if not inactive:
					print("Player inactive")
					inactive = True

async def vol_update():
	global vol_retry_claimed
	global next_vol
	global next_vol_time
	path = "/me/player/volume" # Set Playback Volume
	headers = {"Authorization": "Bearer " + spotify_config["access_token"]}
	if next_vol is not None and next_vol_time < time.monotonic():
		params = {"volume_percent": next_vol}
		async with session.put(base_uri + path, params=params, headers=headers) as resp:
			if resp.status == 204:
				last_values_sent[next_vol] = time.monotonic()
				next_vol = None
			else:
				error = await resp.json()
				print(str(resp.status) + ":", error["message"])
				# TODO: Handle each error specifically
				if resp.status == 429:
					backoff_time = resp.headers["Retry-After"]
					print("Will retry in", backoff_time, "seconds")
					next_vol_time = time.monotonic() + backoff_time
					if not vol_retry_claimed:
						# Ensure only one instance of vol_update runs after a 429
						vol_retry_claimed = True
						await asyncio.sleep(backoff_time + 1)
						vol_retry_claimed = False
						spawn(vol_update())
	# TODO: If volume was zero, unmute

async def user_auth():
	auth_server = web.Application()
	auth_server.add_routes([web.get('/spotify_login', get_auth_code)])
	global auth_runner
	auth_runner = web.AppRunner(auth_server)
	await auth_runner.setup()
	global state
	state = secrets.token_urlsafe()
	auth_uri = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({"response_type": "code", "client_id": spotify_config["client_id"], "redirect_uri": redirect_uri, "state": state, "scope": scope})
	webbrowser.open(auth_uri) # TODO: Only do this on interaction - mechanism TBC
	try:
		site = web.TCPSite(auth_runner, 'localhost', 8889)
		await site.start()
		await asyncio.sleep(300) # Five minutes to click through OAuth in a browser should be plenty
	except web.GracefulExit:
		pass

async def spotify(start_time):
	global session
	try:
		temp_conn = aiohttp.TCPConnector(family=socket.AF_INET) # Force IPv4 until IPv6 routing is fixed
		session = aiohttp.ClientSession(connector=temp_conn)
		authorized_scopes = " ".join(sorted(spotify_config["scope"].split(sep=" ")))
		if ("scope" not in spotify_config # Noscope!
			or scope != authorized_scopes # Scope mismatch
			or "access_token" not in spotify_config # First auth
			or "refresh_token" not in spotify_config): # Shouldn't happen but if it does just reauth
			print("Re-auth required")
			await user_auth()
		if time.time() > spotify_config["expires_at"]:
			print("Refreshing access token...")
			await get_access_token(spotify_config["refresh_token"], mode="refresh")
		await poll_playback() # This is where we will proceed from
	finally:
		global spotify_channel
		if spotify_channel:
			spotify_channel.remove()
		spotify_channel = None
		await session.close()
