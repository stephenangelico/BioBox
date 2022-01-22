import os
import sys
import time
import subprocess
import threading
import asyncio
import WebSocket
import websockets # ImportError? pip install websockets
import json


import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

import asyncio_glib
asyncio.set_event_loop_policy(asyncio_glib.GLibEventLoopPolicy())

try:
	import Analog
	from Motor import cleanup as motor_cleanup
except (ImportError, NotImplementedError): # Provide a dummy for testing
	def motor_cleanup():
		pass
	class Analog():
		goal = None
		def read_value():
			yield 0 # Yield once and then stop
			# Just as a function is destined to yield once, and then face termination...

import config # ImportError? See config_example.py

selected_channel = None
slider_last_wrote = time.monotonic() + 0.5
webcams = {}
ssh = None
tabs = {}
obs_sources = {}
source_types = ['browser_source', 'pulse_input_capture', 'pulse_output_capture']
# TODO: Configure OBS modules within BioBox

def report(msg):
	print(time.time(), msg)

# Slider
def read_analog():
	global slider_last_wrote
	# Get analog value from Analog.py and write to selected channel's slider
	for volume in Analog.read_value():
		if selected_channel:
			print("From slider:", volume)
			# TODO: Scale 0-100% to 0-150%
			GLib.idle_add(selected_channel.update_position, volume)
			slider_last_wrote = time.monotonic()

def init_motor_pos():
	if selected_channel:
		Analog.goal = round(selected_channel.slider.get_value())
	else:
		Analog.goal = 100

# Webcam
async def webcam(stop):
	global ssh
	if ssh is not None:
		# TODO: Revisit this when on-demand modules are working
		ssh.stdin.write("quit")
		try:
			asyncio.wait_for(ssh.stdin.drain(), timeout=10)
		except asyncio.TimeoutError:
			ssh.terminate()
	try:
		ssh = await asyncio.create_subprocess_exec("ssh", "-oBatchMode=yes", (config.webcam_user + "@" + config.host), "python3", config.webcam_control_path, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
		print("SSH:", ssh.pid)
	except ConnectionResetError:
		print("SSH connection lost")
	# TODO: Handle connection failures
	while True:
		try:
			done, pending = await asyncio.wait([ssh.stdout.readline(), stop.wait(), ssh.wait()], return_when=asyncio.FIRST_COMPLETED)
		except ConnectionResetError:
			print("SSH connection lost")
			break
		if ssh.returncode is not None or stop.is_set():
			break
		try:
			data = next(iter(done)).result()
		except BaseException as e:
			print(type(e))
			print(e)
			break
		line = data.decode("utf-8")
		device, sep, attr = line.rstrip().partition(": ")
		if sep:
			if device == "Unknown command":
				print(line)
			elif device == "Info":
				if attr == "Hi":
					for cam_name, cam_path in config.webcams.items():
						webcams[cam_path] = WebcamFocus(cam_name, cam_path)
					await ssh.stdin.drain()
				elif attr == "Bye":
					break
			else:
				cmd, sep, value = attr.partition(": ")
				if not sep:
					continue
				if cmd == "focus_absolute":
					webcams[device].update_position(int(value))
				elif cmd == "focus_auto":
					webcams[device].mute.set_active(int(value))
				elif cmd == "Error":
					print("Received error on %s: " %device, value)
	print("SSH connection done")
	for cam in webcams:
		webcams[cam].remove() # FIXME. For some unknown reason, this doesn't make the modules disappear.
		print(webcams[cam])
		print(type(webcams[cam]))

# OBS
async def obs_ws(stop):
	obs_uri = "ws://%s:%d" % (config.host, config.obs_port)
	global obs
	async with websockets.connect(obs_uri) as obs:
		await obs.send(json.dumps({"request-type": "GetCurrentScene", "message-id": "init"}))
		while True:
			done, pending = await asyncio.wait([obs.recv(), stop.wait()], return_when=asyncio.FIRST_COMPLETED)
			if stop.is_set():
				break
			try:
				data = next(iter(done)).result()
			except websockets.exceptions.ConnectionClosedOK:
				report("OBS Connection lost")
				break
			except BaseException as e:
				print(type(e))
				print(e)
				break
			msg = json.loads(data)
			collector = {}
			if msg.get("update-type") == "SourceVolumeChanged":
				obs_sources[msg["sourceName"]].update_position(int(max(msg["volume"], 0) ** 0.5 * 100))
			elif msg.get("update-type") == "SourceMuteStateChanged":
				obs_sources[msg["sourceName"]].mute.set_active(msg["muted"])
			elif msg.get("update-type") == "SwitchScenes":
				print(msg["scene-name"])
				list_scene_sources(msg['sources'], collector)
				for source in list(obs_sources):
					if source not in collector:
						print("Removing", source)
						obs_sources[source].remove()
						obs_sources.pop(source, None)
			elif msg.get("message-id") == "init":
				obs_sources.clear()
				list_scene_sources(msg['sources'], collector)
			elif msg.get("message-id") == "mute":
				pass # Clean up message
			elif msg.get("message-id"):
				print(msg)
		await obs.close()
	for source in obs_sources.values():
		source.remove()
	obs_sources.clear()

def obs_send(request):
	asyncio.run_coroutine_threadsafe(obs.send(json.dumps(request)), loop)

def list_scene_sources(sources, collector):
	for source in sources:
		if source['type'] in source_types:
			print(source['id'], source['name'], source['volume'], "Muted:", source['muted'])
			collector[source['name']] = source
			if source['name'] not in obs_sources:
				obs_sources[source['name']] = OBS(source)
		elif source['type'] == 'group':
			list_scene_sources(source['groupChildren'], collector)
		elif source['type'] == 'scene':
			#TODO: get this scene's sources and recurse
			pass

# Browser
def new_tab(tabid):
	# TODO: Some browser media, including YouTube, reports volume to
	# BioBox as 41% when its UI shows 100%. Can the we run multiple
	# instances of volsock with separate manifests for different
	# sites in order to separate the ones which require scaling and
	# the ones which don't?
	print("Creating channel for new tab:", tabid)
	newtab = Browser(tabid)
	tabs[tabid] = newtab

def closed_tab(tabid):
	print("Destroying channel for closed tab:", tabid)
	tabs[tabid].remove()
	tabs.pop(tabid, None)

def tab_volume_changed(tabid, volume, mute_state):
	print("On", tabid, ": Volume:", volume, "Muted:", bool(mute_state))
	channel = tabs[tabid]
	channel.update_position(int(volume * 100)) # Truncate or round?
	channel.mute.set_active(int(mute_state))

class Channel(Gtk.Frame):
	mute_labels = ("Mute", "Muted")
	step = 0.01

	def __init__(self, name):
		super().__init__(label=name, shadow_type=Gtk.ShadowType.ETCHED_IN)
		super().set_label_align(0.5,0)
		# Box stuff
		box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
		box.set_size_request(50, 300) #TODO: Optimize size and widget scaling for tablet
		self.add(box)
		self.channel_name = name
		#channel_label = Gtk.Label(label=self.channel_name)
		#box.pack_start(channel_label, False, False, 0)
		# Slider stuff
		self.slider = Gtk.Adjustment(value=100.0, lower=0.0, upper=150.0, step_increment=1.0, page_increment=10.0, page_size=0)
		level = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL, adjustment=self.slider, inverted=True, draw_value=False)
		level.add_mark(value=100, position=Gtk.PositionType.LEFT, markup=None)
		level.add_mark(value=100, position=Gtk.PositionType.RIGHT, markup=None)
		box.pack_start(level, True, True, 0)
		level.connect("focus", self.focus_delay)
		self.slider.connect("value-changed", self.refract_value)
		# Spinner
		spinvalue = Gtk.SpinButton(adjustment=self.slider, digits=2)
		box.pack_start(spinvalue, False, False, 0)
		spinvalue.connect("focus", self.focus_delay) # TODO: get signal for +/- presses
		# Mute button
		self.mute = Gtk.ToggleButton(label=self.mute_labels[0])
		box.pack_start(self.mute, False, False, 0)
		self.mute.connect("toggled", self.muted)
		self.mute.connect("focus", self.focus_delay)
		# Channel selector
		self.selector = Gtk.RadioButton.new_from_widget(chan_select)
		self.selector.set_label("Selected")
		box.pack_start(self.selector, False, False, 0)
		self.selector.connect("toggled", self.check_selected)
		self.connect("event", self.click_anywhere)
		self.last_wrote = time.monotonic()
		# Add self to group
		self.group.pack_start(self, True, True, 0)
		self.group.show_all()

	def focus_delay(self, widget, direction):
		GLib.idle_add(self.focus_select, widget)

	def focus_select(self, widget):
		# Select a module if it gains focus
		# This will also select the first module on startup as its scale
		# will be the first object and will be given focus initially.
		if widget.is_focus():
			self.selector.set_active(True)
			print(self.channel_name, "selected")

	def click_anywhere(self, widget, event):
		if "BUTTON" in event.get_event_type().value_name:
			# TODO: Get scroll wheel changing Gtk.Scale
			self.selector.set_active(True)
			return False
		elif event.get_event_type().value_name != "GDK_MOTION_NOTIFY":
			print(event.get_event_type().value_name)

	def check_selected(self, widget):
		global selected_channel
		if widget.get_active():
			selected_channel = self
			print(selected_channel.channel_name)
			self.write_analog(round(selected_channel.slider.get_value()))

	def refract_value(self, widget):
		# Send adjustment value to multiple places - one will echo back
		# to the source of the change, any others are echoing forward,
		# hence 'refraction'.
		value = round(widget.get_value())
		if time.monotonic() > self.last_wrote + 0.01:
			# TODO: drop only writes that would result in bounce loop
			self.write_external(value)
			self.last_wrote = time.monotonic()
		if selected_channel is self:
			self.write_analog(value)

	def write_analog(self, value):
		global slider_last_wrote
		if time.monotonic() > slider_last_wrote + 0.01:
			Analog.goal = value
			slider_last_wrote = time.monotonic()
			print("Slider goal: %s" % Analog.goal)

	def read_external(self, level_cmd, mute_cmd):
		buffer = b""
		while True:
			data = self.data_source()
			if not data:
				break
			buffer += data
			while b"\n" in buffer:
				line, buffer = buffer.split(b"\n", 1)
				line = line.rstrip().decode("utf-8")
				attr, value = line.split(":", 1)
				if attr == level_cmd:
					GLib.idle_add(self.update_position, int(value))
				elif attr == mute_cmd:
					GLib.idle_add(self.mute.set_active, int(value))
				else:
					print(attr, value)

	async def read_asyncio(self, level_cmd, mute_cmd, device=None):
		if device:
			level_cmd = device + " " + level_cmd
			mute_cmd = device + " " + mute_cmd
		while True:
			line = await self.data_source()
			if not line:
				break
			line = line.rstrip().decode("utf-8")
			attr, value = line.split(":", 1)
			if attr == level_cmd:
				self.update_position(int(value))
			elif attr == mute_cmd:
				self.mute.set_active(int(value))
			else:
				print("From", self.channel_name +":", attr, value)


	# Fallback function if subclasses don't provide write_external()
	def write_external(self, value):
		print(value)

	# Fallback/superclass functions
	def muted(self, widget):
		mute_state = widget.get_active()
		self.mute.set_label(self.mute_labels[mute_state])
		print(self.channel_name, "un" * (not mute_state) + "muted")
		return mute_state

	def update_position(self, value):
		self.slider.set_value(value)
		self.last_wrote = time.monotonic()

	def remove(self):
		global selected_channel
		if selected_channel is self:
			selected_channel = None # Because it doesn't make sense to select another module
		self.group.remove(self)

class VLC(Channel):
	step = 1.0
	
	def __init__(self, stop):
		super().__init__(name="VLC")
		asyncio.create_task(self.conn(stop))

	async def conn(self, stop):
		try:
			self.reader, self.writer = await asyncio.open_connection(config.host, config.vlc_port)
		except ConnectionRefusedError:
			self.remove()
			# TODO: This creates then removes the VLC module. The
			# scale is given focus on startup, causing the VLC module
			# to be selected for write_analog. Thus, upon removal, no
			# module is selected, even though this happens on startup.
			# I could have it select the next module but that will be
			# rife with potential problems. The best solution, and the
			# most consistent one, would be to start the connection
			# to VLC before attempting to create its module. If we do
			# that, we should do it properly by having each Channel
			# subclass also have a backend object to manage its
			# connection. This would be a significant architectural
			# change, but will also make on-the-fly module adding
			# and removing easier.
		self.writer.write(b"volume\r\nmuted\r\n") # Ask volume and mute state
		await self.writer.drain()
		await asyncio.wait([self.read_asyncio("volume", "muted"), stop.wait()], return_when=asyncio.FIRST_COMPLETED)
		self.writer.close() # If above returns, we're shutting down this module
		await self.writer.wait_closed()
		self.remove() # Remove module once we're done

	async def data_source(self):
		return await self.reader.readline()
		#TODO: check if protection against missing connection is necessary:
		#if self.sock:
		#	...
		#else:
		#	return b""

	def write_external(self, value):
		self.writer.write(b"volume %d \r\n" %value)
		asyncio.create_task(self.writer.drain())
		print("To VLC: ", value)

	def muted(self, widget):
		mute_state = super().muted(widget)
		self.writer.write(b"muted %d \r\n" %mute_state)
		asyncio.create_task(self.writer.drain())
		print("VLC Mute status:", mute_state)

class WebcamFocus(Channel):
	mute_labels = ("AF Off", "AF On")
	step = 1.0 # Cameras have different steps but v4l2 will round any int to the step for the camera in question

	def __init__(self, cam_name, cam_path):
		self.device_name = cam_name
		super().__init__(name=self.device_name)
		self.device = cam_path
		ssh.stdin.write(("cam_check %s \n" %self.device).encode("utf-8"))

	def write_external(self, value):
		# v4l2-ctl throws an error if focus_absolute is changed while AF is on.
		# Therefore, if AF is on, quietly do nothing.
		# When AF is toggled, this is called again anyway.
		if not self.mute.get_active():
			ssh.stdin.write(("focus_absolute %d %s\n" % (int(value), self.device)).encode("utf-8"))
			async def write_ssh():
				try:
					await ssh.stdin.drain()
				except ConnectionResetError as e:
					print("SSH connection lost")
			asyncio.create_task(write_ssh())

	def muted(self, widget):
		mute_state = super().muted(widget)
		ssh.stdin.write(("focus_auto %d %s\n" % (mute_state, self.device)).encode("utf-8"))
		asyncio.create_task(ssh.stdin.drain())
		print("%s Autofocus " %self.device_name + ("Dis", "En")[mute_state] + "abled")
		self.write_external(round(self.slider.get_value()))

class OBS(Channel):
	def __init__(self, source):
		self.name = source['name']
		super().__init__(name=self.name)
		self.update_position(int(max(source['volume'], 0) ** 0.5 * 100))
		self.mute.set_active(source['muted'])

	def write_external(self, value):
		obs_send({"request-type": "SetVolume", "message-id": "volume", "source": self.name, "volume": ((value / 100) ** 2)})

	def muted(self, widget):
		mute_state = super().muted(widget)
		obs_send({"request-type": "SetMute", "message-id": "mute", "source": self.name, "mute": mute_state})

class Browser(Channel):
	def __init__(self, tabid):
		super().__init__(name="Browser")
		self.tabid = tabid

	def write_external(self, value):
		asyncio.create_task(WebSocket.set_volume(self.tabid, (value / 100)))
	
	def muted(self, widget):
		mute_state = super().muted(widget)
		asyncio.create_task(WebSocket.set_muted(self.tabid, mute_state))

async def main():
	stopper, stoppew = os.pipe()
	stop = asyncio.Event()
	loop.add_reader(stopper, stop.set)
	main_ui = Gtk.Window(title="Bio Box")
	main_ui.set_border_width(10)
	main_ui.set_resizable(False)
	modules = Gtk.Box()
	main_ui.add(modules)
	global chan_select
	chan_select = Gtk.RadioButton()
	threading.Thread(target=read_analog, daemon=True).start()
	for category in Channel.__subclasses__():
		group = Gtk.Box(name=category.__name__)
		category.group = group
		modules.add(group)
	VLC(stop)
	GLib.timeout_add(500, init_motor_pos)
	# Show window
	def halt(*a): # We could use a lambda function unless we need IIDPIO
		os.write(stoppew, b"*")
	main_ui.connect("destroy", halt)
	main_ui.show_all()
	obs_task = asyncio.create_task(obs_ws(stop))
	browser_task = asyncio.create_task(WebSocket.listen(connected=new_tab, disconnected=closed_tab, volumechanged=tab_volume_changed, stop=stop))
	webcam_task = asyncio.create_task(webcam(stop))
	await stop.wait()
	await obs_task
	await browser_task
	await webcam_task
	motor_cleanup()
	os.close(stopper); os.close(stoppew)

if __name__ == "__main__":
	css = b"""
		window {-gtk-dpi: 90;}
		scale slider {
			background-size: 20px 40px;
			min-width: 20px;
			min-height: 40px;
		}
	"""
	# TODO: Make this look good without hard-coding
	style_provider = Gtk.CssProvider()
	style_provider.load_from_data(css)
	Gtk.StyleContext.add_provider_for_screen(
		Gdk.Screen.get_default(),
		style_provider,
		Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
	)

	loop = asyncio.new_event_loop()
	asyncio.set_event_loop(loop)
	loop.run_until_complete(main())
