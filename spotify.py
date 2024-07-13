import asyncio
import json
import secrets
import base64
import hashlib
import webbrowser
import urllib.parse
import config

client_id = "9319838553fc4afda3ce43086ba73cb6"
response_type = "code"
redirect_uri = "http://localhost:8888/spotify_login"
state = secrets.token_urlsafe()
#scope = "app-remote-control"

class Spotify():
	group_name = "Spotify"
	
	def __init__(self):
		pass
	
	def write_external(self, value):
		pass
	
	def muted(self, widget):
		pass

auth_uri = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({"response_type": response_type, "client_id": client_id, "redirect_uri": redirect_uri, "state": state})
webbrowser.open(auth_uri, new=2)
