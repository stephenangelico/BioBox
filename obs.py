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

events_seen = []

class OBSModule(Channel):
	group_name = "OBS (new)"
	
	def __init__(self, source_name, vol, mute):
		self.name = source_name
		super().__init__(name=self.name)
		self.refract_value(vol, "backend")
		self.mute.set_active(mute)

	def write_external(self, value):
		asyncio.create_task(send_request("SetInputVolume", {"inputName": self.name, "inputVolumeMul": ((value / 100) ** 2)}))

	def muted(self, widget):
		mute_state = super().muted(widget)
		asyncio.create_task(send_request("SetInputMute", {"inputName": self.name, "inputMuted": mute_state}))

class OBSError(Exception):
	pass

class OBSEvents:
	async def Identified(ev):
		scene_name = (await send_request("GetCurrentProgramScene"))["currentProgramSceneName"]
		await list_scene_sources(scene_name)

	async def InputVolumeChanged(ev):
		obs_sources[ev["inputName"]].refract_value(max(ev["inputVolumeMul"], 0) ** 0.5 * 100, "backend") # FIXME: make this work from a separate file

	async def InputMuteStateChanged(ev):
		obs_sources[ev["inputName"]].mute.set_active(ev["inputMuted"])

	async def CurrentProgramSceneChanged(ev):
		print(ev["sceneName"])
		await list_scene_sources(ev["sceneName"])

	async def UnknownEvent(ev):
		global events_seen
		if ev["eventType"] not in events_seen:
			events_seen.append(ev["eventType"])
			print(ev)

async def send_request(request_type, request_data={}):
	request_id = str(next(request_id_source))
	future = pending_requests[request_id] = asyncio.Future()
	request = {"op": 6, "d": {"requestType": request_type, "requestId": request_id, "requestData": request_data}}
	await conn.send(json.dumps(request))
	return(await future)

async def event_handler(event):
	method = getattr(OBSEvents, event["eventType"], None)
	if not method:
		await OBSEvents.UnknownEvent(event)
	else:
		await method(event["eventData"])

async def obs_ws():
	obs_uri = "ws://%s:%d" % (config.host, config.obs_port)
	# TODO: Support obs-websocket v5 - coming in OBS 28
	global conn
	auth_key = ""
	rpc_version = 1
	try:
		# Begin cancellable section
		async with websockets.connect(obs_uri) as conn:
			while True:
				data = await conn.recv()
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
					await conn.send(json.dumps(ident))
				elif msg.get("op") == 2: # Identified
					if msg.get("d")["negotiatedRpcVersion"] != rpc_version: # Warn if RPC version is ever bumped
						print("Warning: negotiated RPC version:", msg.get("d")["rpcVersion"])
					asyncio.create_task(OBSEvents.Identified(msg)) # Hack to put the handling all in OBSEvents
				elif msg.get("op") == 5: # Event
					asyncio.create_task(event_handler(msg["d"]))
				elif msg.get("op") == 7: # RequestResponse
					#if msg.get("d")["requestId"] == "init":
						#scene_name = msg.get("d")["responseData"]["currentProgramSceneName"]
						#await obs.send(json.dumps({"op": 6, "d": {"requestType": "GetSceneItemList", "requestId": "init2", "requestData": {"sceneName": scene_name}}}))
					#elif msg.get("d")["requestId"] == "init2":
						#print(msg)
						#obs_sources.clear()
						#list_scene_sources(msg["d"]["responseData"]["sceneItems"], collector)
					future = pending_requests.pop(msg["d"]["requestId"])
					if msg["d"]["requestStatus"]["result"]:
						future.set_result(msg["d"]["responseData"])
					else:
						future.set_exception(OBSError(msg["d"]["requestStatus"]["comment"]))
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

async def list_scene_sources(scene_name):
	sources = (await send_request("GetSceneItemList", request_data={"sceneName": scene_name}))["sceneItems"]
	# TODO: filter to just source names
	collector = {}
	for source in sources:
		if source['inputKind'] in source_types: # TODO: get volume and mute state from source name
			vol = max((await send_request("GetInputVolume", request_data={"inputName": source['sourceName']}))["inputVolumeMul"], 0) ** 0.5 * 100
			mute = (await send_request("GetInputMute", request_data={"inputName": source['sourceName']}))["inputMuted"]
			print(source['sourceName'], vol, "Muted:", mute)
			collector[source['sourceName']] = source
			if source['sourceName'] not in obs_sources:
				obs_sources[source['sourceName']] = OBSModule(source['sourceName'], vol, mute)
		elif source['inputKind'] == None and source['sourceType'] == 'OBS_SOURCE_TYPE_SCENE':
			# Catches scenes and groups, though groups are deprecated
			#TODO: get this scene's sources and recurse
			pass
	for source in list(obs_sources):
		if source not in collector:
			print("Removing", source)
			obs_sources[source].remove()
			obs_sources.pop(source, None)

if __name__ == "__main__":
	loop = asyncio.new_event_loop()
	asyncio.set_event_loop(loop)
	loop.run_until_complete(obs_ws())
