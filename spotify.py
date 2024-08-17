import asyncio
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
state = None
scope = "user-modify-playback-state user-read-playback-state"
base_uri = "https://api.spotify.com/v1"

class Spotify(Channel):
	group_name = "Spotify"
	
	def __init__(self):
		pass
	
	def write_external(self, value):
		pass
		# if no current buffer timer, start one (1 sec)
		# set flag to suspend poll of volume
		# hold/update current value as temp value
		# if timer has run out, send value
		# keep value sent with timestamp for future check
		# unset flag to resume polling
		# If volume is now zero, mute (button only)
		# If volume was zero, unmute (button only)
	
	def muted(self, widget):
		# Spotify does not seem to have a mute function, instead the mute button sets
		# volume to zero for muting and sets volume to the "last" volume when unmuting.
		# However, this is somewhat inconsistent in the web interface as it sometimes
		# restores an old volume instead.
		pass
		# If not muted:
		#	Store current volume
		#	Set volume to zero
		# If muted:
		#	Restore stored volume - may soon be overwritten by next poll

async def get_auth_code(request):
	params = request.query
	if params["state"] == state:
		if "code" in params:
			spawn(get_access_token(params["code"]))
		else:
			print(params["error"]) # If we got a response and didn't get a code, we should have an error
	return web.Response(body="")

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
	async with aiohttp.ClientSession() as session:
		async with session.post('https://accounts.spotify.com/api/token', params=params, headers=headers) as resp:
			resp.raise_for_status()
			token_response = await resp.json()
			for key in token_response:
				spotify_config[key] = token_response[key]
			# Generate renewal time (5 seconds before actual expiry)
			spotify_config["expires_at"] = time.time() + spotify_config["expires_in"] - 5
			save_config()
			print("Access token:", spotify_config["access_token"])
			print("Expiry:", spotify_config["expires_at"])
			print("Getting playback state...")
			await hello_world()

def save_config():
	with open('spotify.json', 'w') as f:
		json.dump(spotify_config, f)

def gen_auth_header():
	# TODO: Find out when this needs to be rerun if invalid (eg if client secret changes)
	spotify_config["authorization"] = "Basic " + base64.b64encode((spotify_config["client_id"] + ":" + spotify_config["client_secret"]).encode()).decode()
	save_config()

async def hello_world():
	# TODO: run a wrapper to check if the access token is valid
	path = "/me/player" # Get Playback State
	headers = {"Authorization": "Bearer " + spotify_config["access_token"]}
	async with aiohttp.ClientSession() as session: # TODO: use the same session
		async with session.get(base_uri + path, headers=headers) as resp: # TODO: break this out into a single request function
			print(resp.status)
			if resp.status == 200:
				playback_state = await resp.json()
				print("Volume:", playback_state["device"]["volume_percent"])
			if resp.status == 204:
				print("Player inactive")

async def poll_playback():
	pass
	# check flag to see if polling is suspended
	# get volume from playback state
	# if volume is same as current, all is fine
	# if volume is same as previous request in last 3(?) seconds, ignore
	# else, refract_value("backend")

async def user_auth():
	pass

async def spotify(start_time):
	authorized_scopes = " ".join(sorted(spotify_config["scope"].split(sep=" ")))
	if "scope" not in spotify_config or scope != authorized_scopes:
		# If no scopes or wrong scopes authorized
		print("Authorized scopes and required scopes differ:")
		print("Required:", scope)
		print("Authorized:", authorized_scopes)
		await user_auth()
	if "access_token" in spotify_config:
		if time.time() < spotify_config["expires_at"]:
			await hello_world() # This is where we will proceed from
		else:
			if "refresh_token" in spotify_config:
				await get_access_token(spotify_config["refresh_token"], mode="refresh")
			else: 
				# Shouldn't happen, access token and refresh token are given in the same response
				# If it does though, just redo the whole auth phase
				user_auth()
	else: # This belongs in user_auth once the server only fills one request, and there is some other "hold open" here
		auth_server = web.Application()
		auth_server.add_routes([web.get('/spotify_login', get_auth_code)])
		global state
		state = secrets.token_urlsafe()
		auth_uri = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({"response_type": "code", "client_id": spotify_config["client_id"], "redirect_uri": redirect_uri, "state": state, "scope": scope})
		webbrowser.open(auth_uri) # TODO: Only do this on interaction - mechanism TBC
		try:
			await web._run_app(auth_server, port=8889) # Normal web.run_app creates a new event loop, _run_app does not
		except web.GracefulExit:
			pass
