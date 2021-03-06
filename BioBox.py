import sys
import time
import subprocess
import socket
import threading
import asyncio
import WebSocket

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
			yield 0

selected_channel = None
slider_last_wrote = time.monotonic() + 0.5
tabs = {}

class MainUI(Gtk.Window):
	def __init__(self):
		super().__init__(title="Bio Box")
		self.set_border_width(10)
		self.modules = Gtk.Box()
		self.add(self.modules)
		global chan_select
		chan_select = Gtk.RadioButton()
		threading.Thread(target=self.read_analog, daemon=True).start()
		self.add_module(VLC())
		self.add_module(WebcamFocus())
		GLib.timeout_add(500, self.init_motor_pos)
		# Establish websocket server
		threading.Thread(target=WebSocket.run, kwargs=dict(connected=self.idle_new_tab, disconnected=self.idle_closed_tab, volumechanged=self.idle_volume_changed)).start()

	# Create/destroy channels when tabs connect/disconnect
	# Get audio controls for current tab
	# Create read/write external functions for this tab

	def idle_new_tab(self, tabid):
		GLib.idle_add(self.new_tab, tabid)

	def new_tab(self, tabid):
		print("Creating channel for new tab:", tabid)
		newtab = Browser(tabid)
		tabs[tabid] = newtab
		self.add_module(newtab)
		self.show_all()

	def idle_closed_tab(self, tabid):
		GLib.idle_add(self.closed_tab, tabid)

	def closed_tab(self, tabid):
		print("Destroying channel for closed tab:", tabid)

	def idle_volume_changed(self, *args):
		GLib.idle_add(self.tab_volume_changed, *args)

	def tab_volume_changed(self, tabid, volume, mute_state):
		print("On", tabid, ": Volume:", volume, "Muted:", bool(mute_state))
		channel = tabs[tabid]
		channel.update_position(int(volume * 100)) # Truncate or round?
		channel.mute.set_active(int(mute_state))

	def add_module(self, module):
		self.modules.pack_start(module, True, True, 0)

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




class Channel(Gtk.Frame):
	mute_labels = ("Mute", "Muted")

	def __init__(self, name):
		super().__init__(label=name, shadow_type=Gtk.ShadowType.ETCHED_IN)
		# Box stuff
		box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
		box.set_size_request(50, 300)
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
					value = int(value)
					GLib.idle_add(self.update_position, value)
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
			self.sock.connect(('F-22Raptor',4221)) # TODO: Make config file
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
			if time.monotonic() > self.last_wrote + 0.01: # TODO: drop only writes that would result in bounce loop
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

	def __init__(self):
		super().__init__(name="C922 Focus")
		threading.Thread(target=self.conn, daemon=True).start()
		# TODO: use 'quit' command in camera.py

	def conn(self):
		self.ssh = subprocess.Popen(["ssh", "-oBatchMode=yes", "biobox@F-22Raptor", "python3", "/home/stephen/BioBox/camera.py"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
		# TODO: If the process fails, disable the channel (eg if authentication fails)
		# Check camera state (auto-focus, focal distance)
		self.ssh.stdin.write(("cam_check\n").encode("utf-8"))
		self.ssh.stdin.flush()
		self.read_external("focus_absolute", "focus_auto")

	def data_source(self):
		return self.ssh.stdout.read1(1024)

	def write_external(self, value):
		if not self.mute.get_active():
			self.ssh.stdin.write(("focus_absolute %d\n" %value).encode("utf-8"))
			self.ssh.stdin.flush()

	def muted(self, widget):
		mute_state = super().muted(widget)
		self.ssh.stdin.write(("focus_auto %d\n" %mute_state).encode("utf-8"))
		self.ssh.stdin.flush()
		print("C922 Autofocus " + ("Dis", "En")[mute_state] + "abled")
		self.write_external(round(self.slider.get_value()))

class OBS(Channel):
	# Establish websocket connection to OBS
	# On startup or scene change, create/destroy channels as necessary
	# Get audio devices on current scene
	# Create read/write external functions, which are mapped from channel to source
	...

class Browser(Channel):
	def __init__(self, tabid):
		super().__init__(name="Browser #x")
		self.tabid = tabid

	def write_external(self, value):
		WebSocket.set_volume(self.tabid, (value / 100))
	
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
