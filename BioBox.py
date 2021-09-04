import sys
import time
import subprocess
import socket
import threading
import asyncio
import WebSocket
import websockets # ImportError? pip install websockets
import json


import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

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
tabs = {}
obs_sources = {}
source_types = ['browser_source', 'pulse_input_capture', 'pulse_output_capture']

class MainUI(Gtk.Window):
	def __init__(self):
		super().__init__(title="Bio Box")
		self.set_border_width(10)
		self.set_resizable(False)
		self.modules = Gtk.Box()
		self.add(self.modules)
		global chan_select
		chan_select = Gtk.RadioButton()
		threading.Thread(target=self.read_analog, daemon=True).start()
		self.add_module(VLC())
		self.add_module(WebcamFocus("C920"))
		self.add_module(WebcamFocus("C922"))
		GLib.timeout_add(500, self.init_motor_pos)
		# Establish websocket connections
		threading.Thread(target=self.ws_mgr).start()

	def idle_new_tab(self, tabid):
		GLib.idle_add(self.new_tab, tabid)

	def new_tab(self, tabid):
		# Always call with GLib.idle_add()
		print("Creating channel for new tab:", tabid)
		newtab = Browser(tabid)
		tabs[tabid] = newtab
		self.add_module(newtab)

	def closed_tab(self, tabid):
		print("Destroying channel for closed tab:", tabid)
		GLib.idle_add(self.remove_module, tabs[tabid])
		tabs.pop(tabid, None)

	def idle_volume_changed(self, *args):
		GLib.idle_add(self.tab_volume_changed, *args)

	def tab_volume_changed(self, tabid, volume, mute_state):
		# Always call with GLib.idle_add()
		print("On", tabid, ": Volume:", volume, "Muted:", bool(mute_state))
		channel = tabs[tabid]
		channel.update_position(int(volume * 100)) # Truncate or round?
		channel.mute.set_active(int(mute_state))

	def add_module(self, module):
		# Always call with GLib.idle_add()
		self.modules.pack_start(module, True, True, 0)
		self.show_all()

	def remove_module(self, module):
		# Always call with GLib.idle_add()
		self.modules.remove(module)
		self.resize(1,1) # Reset to minimum size

	def read_analog(self):
		global slider_last_wrote
		# Get analog value from Analog.py and write to selected channel's slider
		for volume in Analog.read_value():
			if selected_channel:
				print("From slider:", volume)
				# TODO: Scale 0-100% to 0-150%
				GLib.idle_add(selected_channel.update_position, volume)
				slider_last_wrote = time.monotonic()

	def init_motor_pos(self):
		Analog.goal = round(selected_channel.slider.get_value())

	def ws_mgr(self):
		global loop
		loop = asyncio.new_event_loop()
		asyncio.set_event_loop(loop)
		loop.create_task(self.obs_ws())
		loop.create_task(WebSocket.listen(connected=self.new_tab, disconnected=self.closed_tab, volumechanged=self.idle_volume_changed))
		loop.run_forever()

	async def obs_ws(self):
		obs_uri = "ws://%s:%d" % (config.host, config.obs_port)
		async with websockets.connect(obs_uri) as obs:
			await obs.send(json.dumps({"request-type": "GetCurrentScene", "message-id": "init"}))
			while True:
				data = await obs.recv()
				msg = json.loads(data)
				collector = {}
				if msg.get("update-type") == "SourceVolumeChanged":
					GLib.idle_add(obs_sources[msg["sourceName"]].update_position, int(msg["volume"] * 100))
					print(msg)
				elif msg.get("update-type") == "SourceMuteStateChanged":
					GLib.idle_add(obs_sources[msg["sourceName"]].mute.set_active, msg["muted"])
					print(msg)
				elif msg.get("update-type") == "SwitchScenes":
					print(msg["scene-name"])
					self.list_scene_sources(msg['sources'], collector)
					for source in list(obs_sources):
						if source not in collector:
							print("Removing", source)
							print(obs_sources)
							GLib.idle_add(self.remove_module, obs_sources[source])
							obs_sources.pop(source, None)
				elif msg.get("message-id") == "init":
					obs_sources.clear() # TODO: Clean up modules on connection loss
					self.list_scene_sources(msg['sources'], collector)

	def list_scene_sources(self, sources, collector):
		for source in sources:
			if source['type'] in source_types:
				print(source['id'], source['name'], source['volume'], "Muted:", source['muted'])
				collector[source['name']] = source
				if source['name'] not in obs_sources:
					GLib.idle_add(self.obs_new_source, source)
			elif source['type'] == 'group':
				self.list_scene_sources(source['groupChildren'], collector)
			elif source['type'] == 'scene':
				#TODO: get this scene's sources and recurse
				pass

	def obs_new_source(self, source):
		# Always call with GLib.idle_add()
		new_source = OBS(source)
		obs_sources[source['name']] = new_source
		self.add_module(new_source)

class Channel(Gtk.Frame):
	mute_labels = ("Mute", "Muted")

	def __init__(self, name):
		super().__init__(label=name, shadow_type=Gtk.ShadowType.ETCHED_IN)
		# Box stuff
		box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
		box.set_size_request(50, 300) #TODO: Optimize size and widget scaling for tablet
		self.add(box)
		self.channel_name = name
		#channel_label = Gtk.Label(label=self.channel_name)
		#box.pack_start(channel_label, False, False, 0)
		# Slider stuff
		self.slider = Gtk.Adjustment(value=100, lower=0, upper=150, step_increment=1, page_increment=10, page_size=0)
		level = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL, adjustment=self.slider, inverted=True, draw_value=False)
		level.add_mark(value=100, position=Gtk.PositionType.LEFT, markup=None)
		level.add_mark(value=100, position=Gtk.PositionType.RIGHT, markup=None)
		box.pack_start(level, True, True, 0)
		level.connect("focus", self.focus_delay)
		self.slider.connect("value-changed", self.refract_value)
		# Spinner
		spinvalue = Gtk.SpinButton(adjustment=self.slider)
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

	def focus_delay(self, widget, direction):
		GLib.idle_add(self.focus_select, widget)

	def focus_select(self, widget):
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
		self.write_external(value)
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


	# Fallback function if subclasses don't provide write_external()
	def write_external(self, value):
		print(value)

	# Fallback/superclass functions
	def muted(self, widget):
		mute_state = widget.get_active()
		self.mute.set_label(self.mute_labels[mute_state])
		print("Channel " + "un" * (not mute_state) + "muted")
		return mute_state

	def update_position(self, value):
		self.slider.set_value(value)

class VLC(Channel):
	def __init__(self):
		super().__init__(name="VLC")
		self.sock = None
		threading.Thread(target=self.conn, daemon=True).start()
		self.last_wrote = time.monotonic()

	def conn(self):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self.sock.connect((config.host,config.vlc_port)) # TODO: Make config file
		except ConnectionRefusedError:
			self.sock = None
			return
		self.sock.send(b"volume\r\nmuted\r\n") # Ask volume and mute state
		with self.sock:
			self.read_external("volume", "muted")
		self.sock = None # TODO: Disable channel in GUI if no connection

	def data_source(self):
		if self.sock:
			return self.sock.recv(1024)
		else:
			return b""

	def write_external(self, value):
		if self.sock:
			if time.monotonic() > self.last_wrote + 0.01:
				# TODO: drop only writes that would result in bounce loop
				# See also Browser.write_external with same debounce
				self.sock.send(b"volume %d \r\n" %value)
				print("To VLC: ", value)

	def update_position(self, value):
		self.slider.set_value(value)
		self.last_wrote = time.monotonic()

	def muted(self, widget):
		if self.sock:
			mute_state = super().muted(widget)
			self.sock.send(b"muted %d \r\n" %mute_state)
			print("VLC Mute status:", mute_state)

class WebcamFocus(Channel):
	mute_labels = ("AF Off", "AF On")

	def __init__(self, cam):
		self.device_name = cam
		super().__init__(name="%s Focus" %self.device_name)
		self.device = "/dev/webcam_%s" %self.device_name.lower()
		threading.Thread(target=self.conn, daemon=True).start()
		# TODO: use 'quit' command in camera.py

	def conn(self):
		self.ssh = subprocess.Popen(["ssh", "-oBatchMode=yes", (config.webcam_user + "@" + config.host), "python3", config.webcam_control_path, self.device], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
		# TODO: If the process fails, disable the channel (eg if authentication fails)
		# Check camera state (auto-focus, focal distance)
		self.ssh.stdin.write(("cam_check\n").encode("utf-8"))
		self.ssh.stdin.flush()
		self.read_external("focus_absolute", "focus_auto")

	def data_source(self):
		return self.ssh.stdout.read1(1024)

	def write_external(self, value):
		# v4l2-ctl throws an error if focus_absolute is changed while AF is on.
		# Therefore, if AF is on, quietly do nothing.
		# When AF is toggled, this is called again anyway.
		if not self.mute.get_active():
			self.ssh.stdin.write(("focus_absolute %d\n" %value).encode("utf-8"))
			self.ssh.stdin.flush()

	def muted(self, widget):
		mute_state = super().muted(widget)
		self.ssh.stdin.write(("focus_auto %d\n" %mute_state).encode("utf-8"))
		self.ssh.stdin.flush()
		print("%s Autofocus " %self.device_name + ("Dis", "En")[mute_state] + "abled")
		self.write_external(round(self.slider.get_value()))

class OBS(Channel):
	def __init__(self, source):
		super().__init__(name=source['name'])
		self.update_position(int(source['volume'] * 100))
		self.mute.set_active(source['muted'])

class Browser(Channel):
	def __init__(self, tabid):
		super().__init__(name="Browser")
		self.tabid = tabid
		self.last_wrote = time.monotonic()

	def write_external(self, value):
		if time.monotonic() > self.last_wrote + 0.01: # TODO: see VLC.write_external
			WebSocket.set_volume(self.tabid, (value / 100))
			self.last_wrote = time.monotonic()
	
	def muted(self, widget):
		mute_state = super().muted(widget)
		WebSocket.set_muted(self.tabid, mute_state)

if __name__ == "__main__":
	win = MainUI()
	win.connect("destroy", Gtk.main_quit)
	win.show_all()
	try:
		Gtk.main()
	finally:
		WebSocket.halt()
		motor_cleanup()
		loop.stop()
