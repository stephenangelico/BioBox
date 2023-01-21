import asyncio
import itertools
import json
import base64
import hashlib
import websockets
import config

obs_sources = {}
source_types = ['browser_source', 'pulse_input_capture', 'pulse_output_capture']

request_id_source = itertools.count()

pending_requests = {}

async def obs_logic():
	print(await send_request("GetVersion"))

async def send_request(request_type, request_data={}):
	request_id = str(next(request_id_source))
	future = pending_requests[request_id] = asyncio.Future()
	request = {"op": 6, "d": {"requestType": request_type, "requestId": request_id, "requestData": request_data}}
	await obs.send(json.dumps(request))
	return(await future)

async def obs_ws():
	obs_uri = "ws://%s:%d" % (config.host, config.obs_port)
	# TODO: Support obs-websocket v5 - coming in OBS 28
	global obs
	auth_key = ""
	rpc_version = 1
	try:
		# Begin cancellable section
		async with websockets.connect(obs_uri) as obs:
			while True:
				data = await obs.recv()
				msg = json.loads(data)
				collector = {}
				if msg.get("op") == 0: # Hello
					if msg.get("d")["rpcVersion"] != rpc_version: # Warn if RPC version is ever bumped
						print("Warning: OBS-Websocket version", msg.get("d")["obsWebSocketVersion"], "has RPC version", msg.get("d")["rpcVersion"])
					if msg.get("d")["authentication"]:
						challenge = msg.get("d")["authentication"]["challenge"].encode("utf-8")
						salt = msg.get("d")["authentication"]["salt"].encode("utf-8")
						auth_key = base64.b64encode(hashlib.sha256(base64.b64encode(hashlib.sha256(config.obs_password + salt).digest()) + challenge).digest())
					ident = {"op": 1, "d": {"rpcVersion": rpc_version, "authentication": auth_key.decode("utf-8"), "eventSubscriptions": 13}}
					# Subscriptions: General (1), Scenes (4), Inputs (8)
					await obs.send(json.dumps(ident))
				elif msg.get("op") == 2: # Identified
					if msg.get("d")["negotiatedRpcVersion"] != rpc_version: # Warn if RPC version is ever bumped
						print("Warning: negotiated RPC version:", msg.get("d")["rpcVersion"])
					asyncio.create_task(obs_logic())
					#await obs.send(json.dumps({"op": 6, "d": {"requestType": "GetCurrentProgramScene", "requestId": "init"}}))
					# Now needs to become GetCurrentProgramScene followed by GetSceneItemList
				elif msg.get("op") == 5: # Event
					if msg.get("d")["eventType"] == "SourceVolumeChanged":
						obs_sources[msg["sourceName"]].refract_value(max(msg["volume"], 0) ** 0.5 * 100, "backend")
					elif msg.get("d")["eventType"] == "SourceMuteStateChanged":
						obs_sources[msg["sourceName"]].mute.set_active(msg["muted"])
					elif msg.get("d")["eventType"] == "CurrentProgramSceneChanged":
						print(msg["d"]["eventData"]["sceneName"])
						list_scene_sources(msg['sources'], collector) # Now need separate request GetSceneItemList
						for source in list(obs_sources):
							if source not in collector:
								print("Removing", source)
								obs_sources[source].remove()
								obs_sources.pop(source, None)
				elif msg.get("op") == 7: # RequestResponse
					#if msg.get("d")["requestId"] == "init":
						#scene_name = msg.get("d")["responseData"]["currentProgramSceneName"]
						#await obs.send(json.dumps({"op": 6, "d": {"requestType": "GetSceneItemList", "requestId": "init2", "requestData": {"sceneName": scene_name}}}))
					#elif msg.get("d")["requestId"] == "init2":
						#print(msg)
						#obs_sources.clear()
						#list_scene_sources(msg["d"]["responseData"]["sceneItems"], collector)
					future = pending_requests.pop(msg["d"]["requestId"])
					future.set_result(msg["d"]["responseData"])
	except websockets.exceptions.ConnectionClosedOK:
		pass # Context manager plus finally section should clean everything up, just catch the exception
	except OSError as e:
		if e.errno != 111: raise
		# Ignore connection-refused and just let the module get cleaned up
	finally:
		for source in obs_sources.values():
			source.remove()
		obs_sources.clear()
		print("OBS cleanup done")

def obs_send(request):
	asyncio.run_coroutine_threadsafe(obs.send(json.dumps(request)), loop)

def list_scene_sources(sources, collector):
	for source in sources:
		if source['inputType'] in source_types:
			print(source['id'], source['name'], source['volume'], "Muted:", source['muted'])
			collector[source['name']] = source
			if source['name'] not in obs_sources:
				obs_sources[source['name']] = OBS(source)
		elif source['type'] == 'group':
			list_scene_sources(source['groupChildren'], collector)
		elif source['type'] == 'scene':
			#TODO: get this scene's sources and recurse
			pass

if __name__ == "__main__":
	loop = asyncio.new_event_loop()
	asyncio.set_event_loop(loop)
	loop.run_until_complete(obs_ws())