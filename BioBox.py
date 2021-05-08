import sys
import time
import subprocess
import socket
import threading

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

try:
	from Analog import read_value
except (ImportError, NotImplementedError): # Provide a dummy for testing
	def read_value():
		yield 0

selected_channel = None

class MainUI(Gtk.Window):
	def __init__(self):
		super().__init__(title="Bio Box")
		self.set_border_width(10)
		modules = Gtk.Box()
		self.add(modules)
		global chan_select
		chan_select = Gtk.RadioButton()
		threading.Thread(target=self.read_analog, daemon=True).start()
		vlcmodule = VLC(chan_select)
		modules.pack_start(vlcmodule, True, True, 0)
		c922module = WebcamFocus(chan_select)
		modules.pack_start(c922module, True, True, 0)

	def read_analog(self):
		# Get analog value from Analog.py and write to selected channel's slider
		for volume in read_value():
			if selected_channel:
				print("From slider:", volume)
				# TODO: Scale 0-100% to 0-150%
				GLib.idle_add(selected_channel.update_position, volume)

class Channel(Gtk.Box):
	mute_labels = ("Mute", "Muted")

	def __init__(self, name, chan_select):
		# Box stuff
		super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=5)
		self.set_size_request(50, 300)
		self.channel_name = name
		channel_label = Gtk.Label(label=self.channel_name)
		self.pack_start(channel_label, False, False, 0)
		# Slider stuff
		self.slider = Gtk.Adjustment(value=100, lower=0, upper=150, step_increment=1, page_increment=10, page_size=0)
		level = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL, adjustment=self.slider, inverted=True)
		level.add_mark(value=100, position=Gtk.PositionType.LEFT, markup=None)
		level.add_mark(value=100, position=Gtk.PositionType.RIGHT, markup=None)
		self.pack_start(level, True, True, 0)
		self.slider.connect("value-changed", self.refract_value)
		# Spinner
		spinvalue = Gtk.SpinButton(adjustment=self.slider)
		self.pack_start(spinvalue, False, False, 0)
		# Mute button
		self.mute = Gtk.ToggleButton(label=self.mute_labels[0])
		self.pack_start(self.mute, False, False, 0)
		self.mute.connect("toggled", self.muted)
		# Channel selector
		# TODO: investigate event box to select channel by any interaction
		self.selector = Gtk.RadioButton.new_from_widget(chan_select)
		self.selector.set_label("Selected")
		self.pack_start(self.selector, False, False, 0)
		self.selector.connect("toggled", self.check_selected)

	def check_selected(self, widget):
		global selected_channel
		if widget.get_active():
			selected_channel = self
			print(selected_channel.channel_name)

	def refract_value(self, widget):
		# Send adjustment value to multiple places - one will echo back
		# to the source of the change, any others are echoing forward,
		# hence 'refraction'.
		value = round(widget.get_value())
		self.write_external(value)
		self.write_analog(value)

	def write_analog(self, value):
		pass

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

	# Fallback/superclass function
	def muted(self, widget):
		mute_state = widget.get_active()
		self.mute.set_label(self.mute_labels[mute_state])
		print("Channel " + "un" * (not mute_state) + "muted")
		return mute_state

class VLC(Channel):
	def __init__(self, chan_select):
		super().__init__(name="VLC", chan_select=chan_select)
		self.sock = None
		threading.Thread(target=self.conn, daemon=True).start()
		self.last_wrote = time.monotonic()

	def conn(self):
		self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		try:
			self.sock.connect(('localhost',4221)) # TODO: don't show module on ConnectionRefusedError
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

	def __init__(self, chan_select):
		super().__init__(name="C922 Focus", chan_select=chan_select)
		threading.Thread(target=self.conn, daemon=True).start()
		# TODO: use 'quit' command in camera.py

	def conn(self):
		self.ssh = subprocess.Popen(["ssh", "biobox@F-22Raptor", "python3", "/home/stephen/BioBox/camera.py"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
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

	def update_position(self, value):
		self.slider.set_value(value)

	def muted(self, widget):
		mute_state = super().muted(widget)
		self.ssh.stdin.write(("focus_auto %d\n" %mute_state).encode("utf-8"))
		self.ssh.stdin.flush()
		print("C922 Autofocus " + ("Dis", "En")[mute_state] + "abled")
		self.write_external(round(self.slider.get_value()))

if __name__ == "__main__":
	win = MainUI()
	win.connect("destroy", Gtk.main_quit)
	win.show_all()
	Gtk.main()
