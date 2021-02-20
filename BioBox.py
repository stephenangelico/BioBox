import sys
import socket
import threading

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib


class MainUI(Gtk.Window):
	def __init__(self):
		super().__init__(title="Bio Box")
		self.set_border_width(10)
		
		modules = Gtk.Box()
		self.add(modules)
		module = VLC()
		modules.pack_start(module, True, True, 0)

class Channel(Gtk.Box):
	def __init__(self, name):
		super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=5)
		self.set_size_request(50, 300)
		channelname = Gtk.Label(label=name)
		self.pack_start(channelname, False, False, 0)
		self.slider = Gtk.Adjustment(value=100, lower=0, upper=150, step_increment=1, page_increment=10, page_size=0)
		level = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL, adjustment=self.slider, inverted=True)
		level.add_mark(value=100, position=Gtk.PositionType.LEFT, markup=None)
		level.add_mark(value=100, position=Gtk.PositionType.RIGHT, markup=None)
		self.pack_start(level, True, True, 0)
		spinvalue = Gtk.SpinButton(adjustment=self.slider)
		self.pack_start(spinvalue, False, False, 0)
		mute = Gtk.ToggleButton(label="Mute")
		self.pack_start(mute, False, False, 0)

class VLC(Channel):
	def __init__(self):
		super().__init__(name="VLC")
		threading.Thread(target=self.conn, daemon=True).start()

	def conn(self):
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.connect(('localhost',4221))
		sock.send(b"volume\r\n")
		buffer = b""
		with sock:
			while True:
				data = sock.recv(1024)
				if not data:
					break
				buffer += data
				if b"\n" in buffer:
					line, buffer = buffer.split(b"\n")
					line = line.rstrip().decode("utf-8")
					attr, value = line.split(":")
					value = int(value)
					if attr == "volume":
						print(value)
						GLib.idle_add(self.update_position, value)

	def update_position(self, value):
		self.slider.set_value(value)

if __name__ == "__main__":
	win = MainUI()
	win.connect("destroy", Gtk.main_quit)
	win.show_all()
	Gtk.main()
