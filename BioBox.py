import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

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
		level = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL)
		self.pack_start(level, True, True, 0)
		mute = Gtk.ToggleButton(label="Mute")
		self.pack_start(mute, False, False, 0)

if __name__ == "__main__":
	win = MainUI()
	win.connect("destroy", Gtk.main_quit)
	win.show_all()
	Gtk.main()
