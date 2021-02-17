import sys
import socket
import threading

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

def vlc_connection():
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sock.connect(('localhost',4221))
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


class MainUI(Gtk.Window):
	def __init__(self):
		super().__init__(title="Bio Box")
		self.set_border_width(10)
		
		modules = Gtk.Box()
		self.add(modules)
		module = Channel()
		modules.pack_start(module, True, True, 0)

class Channel(Gtk.Box):
	def __init__(self):
		super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=5)
		self.set_size_request(50, 300)
		channelname = Gtk.Label(label="Channel")
		self.pack_start(channelname, False, False, 0)
		slider = Gtk.Adjustment(value=100, lower=0, upper=150, step_increment=1, page_increment=10, page_size=0)
		level = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL, adjustment=slider, inverted=True)
		level.add_mark(value=100, position=Gtk.PositionType.LEFT, markup=None)
		level.add_mark(value=100, position=Gtk.PositionType.RIGHT, markup=None)
		self.pack_start(level, True, True, 0)
		mute = Gtk.ToggleButton(label="Mute")
		self.pack_start(mute, False, False, 0)

if __name__ == "__main__":
	vlc_connection()
	win = MainUI()
	win.connect("destroy", Gtk.main_quit)
	win.show_all()
	Gtk.main()
