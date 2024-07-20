import asyncio
import json
import secrets
import base64
import hashlib
import webbrowser
import urllib.parse
import aiohttp
from aiohttp import web
import config

redirect_uri = "http://localhost:8889/spotify_login"
state = secrets.token_urlsafe()
#scope = "app-remote-control"

class Spotify(Channel):
	group_name = "Spotify"
	
	def __init__(self):
		pass
	
	def write_external(self, value):
		pass
	
	def muted(self, widget):
		pass

async def get_auth_code(request):
	params = request.query
	# TODO: check state and error
	print(params)
	if params["code"]:
		spawn(get_access_token(params["code"]))
	return web.Response(body="")

async def get_access_token(auth_code):
	print("Auth code:", auth_code)
	authorization = "Basic " + base64.b64encode((config.spotify_id + ":" + config.spotify_secret).encode()).decode()
	params = {"grant_type": "authorization_code", "code": auth_code, "redirect_uri": redirect_uri}
	headers = {"Content-Type": "application/x-www-form-urlencoded", "Authorization": authorization}
	async with aiohttp.ClientSession() as session:
		async with session.post('https://accounts.spotify.com/api/token', params=params, headers=headers) as resp:
			print(resp.status)
			print(await resp.text())
			# TODO: store access and refresh tokens to disk and use on startup if available

async def spotify(start_time):
	auth_server = web.Application()
	auth_server.add_routes([web.get('/spotify_login', get_auth_code)])
	auth_uri = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({"response_type": "code", "client_id": config.spotify_id, "redirect_uri": redirect_uri, "state": state})
	webbrowser.open(auth_uri) # TODO: Only do this on interaction - mechanism TBC
	try:
		await web._run_app(auth_server, port=8889) # Normal web.run_app creates a new event loop, _run_app does not
	except web.GracefulExit:
		pass
