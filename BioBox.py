import sys
import time
import subprocess
import socket
import threading

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

import Analog

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
		for volume in Analog.read_value():
			# TODO: Scale 0-100% to 0-150%
			selected_channel.write_value(volume)

class Channel(Gtk.Box):
	def __init__(self, name, chan_select):
		super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=5)
		self.set_size_request(50, 300)
		self.channel_name = name
		channel_label = Gtk.Label(label=self.channel_name)
		self.pack_start(channel_label, False, False, 0)
		self.slider = Gtk.Adjustment(value=100, lower=0, upper=150, step_increment=1, page_increment=10, page_size=0)
		level = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL, adjustment=self.slider, inverted=True)
		level.add_mark(value=100, position=Gtk.PositionType.LEFT, markup=None)
		level.add_mark(value=100, position=Gtk.PositionType.RIGHT, markup=None)
		self.pack_start(level, True, True, 0)
		spinvalue = Gtk.SpinButton(adjustment=self.slider)
		self.pack_start(spinvalue, False, False, 0)
		# TODO: Make label change on toggle
		# TODO: Change label in subclass
		self.mute = Gtk.ToggleButton(label="Mute")
		self.pack_start(self.mute, False, False, 0)
		self.slider.connect("value-changed", self.write_value)
		self.mute.connect("toggled", self.muted)
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

	# Fallback functions if subclasses don't provide write_value() or muted()
	def write_value(self, widget):
		value = round(widget.get_value())
		print(value)

	def muted(self, widget):
		mute_state = widget.get_active()
		print("Channel " + "un" * (not mute_state) + "muted")

class VLC(Channel):
	def __init__(self, chan_select):
		super().__init__(name="VLC", chan_select=chan_select)
		threading.Thread(target=self.conn, daemon=True).start()
		self.last_wrote = time.time() # TODO: use time.monotonic()

	def conn(self):
		self.sock = sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.connect(('localhost',4221))
		sock.send(b"volume\r\n")
		buffer = b""
		with sock:
			while True:
				data = sock.recv(1024)
				if not data:
					break
				buffer += data
				while b"\n" in buffer:
					line, buffer = buffer.split(b"\n", 1)
					line = line.rstrip().decode("utf-8")
					attr, value = line.split(":", 1)
					if attr == "volume":
						value = int(value)
						print(value)
						GLib.idle_add(self.update_position, value)
					else:
						print(attr, value)
					# TODO: Respond to "muted" signals

	def write_value(self, widget):
		if time.time() > self.last_wrote + 0.01: # TODO: drop only writes that would result in bounce loop
			value = round(widget.get_value())
			self.sock.send(b"volume %d \r\n" %value)
			print("VLC: ", value)

	def update_position(self, value):
		self.slider.set_value(value)
		self.last_wrote = time.time()

	def muted(self, widget): # TODO: send to VLC (depends on support in TellMeVLC)
		mute_state = widget.get_active()
		print("VLC Mute status:", mute_state)

class WebcamFocus(Channel):
	def __init__(self, chan_select):
		super().__init__(name="C922 Focus", chan_select=chan_select)

	def write_value(self, widget):
		value = round(widget.get_value() / 5) * 5
		if not self.mute_state:
			subprocess.run(["v4l2-ctl", "-d", "/dev/webcam_c922", "-c", "focus_absolute=%d" %value])

	def update_position(self, value):
		self.slider.set_value(value)

	def muted(self, widget):
		mute_state = widget.get_active()
		# TODO: Network this
		subprocess.run(["v4l2-ctl", "-d", "/dev/webcam_c922", "-c", "focus_auto=%d" %mute_state])
		print("C922 Autofocus " + ("Dis", "En")[mute_state] + "abled")
		# TODO: When autofocus is unset, set focus_absolute to slider position

if __name__ == "__main__":
	win = MainUI()
	win.connect("destroy", Gtk.main_quit)
	win.show_all()
	Gtk.main()
