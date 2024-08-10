import time
start_time = time.monotonic()
#print("Start time:", start_time)
import json
import builtins
import traceback
import warnings
import asyncio

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

import gbulb
gbulb.install(gtk=True)

import config # ImportError? See config_example.py

winconfig = {}
try:
	with open('window.json', 'r') as f:
		winconfig = json.load(f)
except FileNotFoundError:
	pass # Later references to winconfig should already handle no data

warnings.filterwarnings("ignore", category=DeprecationWarning)

UI_HEADER = """
<ui>
	<menubar name='MenuBar'>
		<menu action='ModulesMenu'>
"""
UI_MIDDLE = """
		</menu>
	</menubar>
	<toolbar name ='ToolBar'>
"""
UI_FOOTER = """
	</toolbar>
</ui>
"""
def export(f):
	setattr(builtins, f.__name__, f)
	return f

def report(msg):
	print(time.time(), msg)

def handle_errors(task):
	try:
		exc = task.exception() # Also marks that the exception has been handled
		if exc: traceback.print_exception(type(exc), exc, exc.__traceback__)
	except asyncio.exceptions.CancelledError:
		pass

all_tasks = [] # kinda like threading.all_threads()

def task_done(task):
	all_tasks.remove(task)
	handle_errors(task)

@export
def spawn(awaitable):
	"""Spawn an awaitable as a stand-alone task"""
	task = asyncio.create_task(awaitable)
	all_tasks.append(task)
	task.add_done_callback(task_done)
	return task

def init_select_channel():
	# TODO: Why does this sometimes not select anything?
	# Selecting a channel, in normal state, already sets position to its
	# value. Do we need to set it again?
	for module in modules.get_children():
		#print("[" + str(time.monotonic() - start_time) + "] Selecting from module:", module.get_name())
		for channel in module.get_children():
			if not channel.hidden:
				#print("[" + str(time.monotonic() - start_time) + "] Selecting:", channel.channel_name)
				channel.mute.grab_focus()
				break
		if Analog.selected_channel:
			break

@export
class Channel(Gtk.Frame):
	group_name = "Channel"
	mute_labels = ("Mute", "Muted")
	mute_names = ("unmuted", "muted")
	step = 0.01
	max = 150
	min = 0
	hidden = False
	channel_types = []

	def __init_subclass__(cls, **kwargs):
		"""Ensure that subclasses defined elsewhere are counted for menus"""
		cls.channel_types.append(cls)
		super().__init_subclass__(**kwargs)

	def __init__(self, name):
		"""Build the channel's GTK elements"""
		super().__init__(label=name, shadow_type=Gtk.ShadowType.ETCHED_IN)
		super().set_label_align(0.5,0)
		self.set_border_width(5)
		# Box stuff
		box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
		box.set_size_request(125, 300) #TODO: Optimize size and widget scaling for tablet
		self.add(box)
		self.channel_name = name
		# Slider stuff
		self.oldvalue = 100.0
		self.slider = Gtk.Adjustment(value=self.oldvalue, lower=self.min, upper=self.max, step_increment=1.0, page_increment=1.0, page_size=0)
		level = Gtk.Scale(orientation=Gtk.Orientation.VERTICAL, adjustment=self.slider, inverted=True, draw_value=False)
		level.add_mark(value=100, position=Gtk.PositionType.LEFT, markup=None)
		level.add_mark(value=100, position=Gtk.PositionType.RIGHT, markup=None)
		box.pack_start(level, True, True, 0)
		level.connect("focus", self.focus_select)
		level.connect("event-after", self.click_anywhere)
		self.slider_signal = self.slider.connect("value-changed", self.adjustment_changed)
		# Spinner
		spinvalue = Gtk.SpinButton(adjustment=self.slider, digits=2)
		box.pack_start(spinvalue, False, False, 0)
		spinvalue.connect("focus", self.focus_select)
		spinvalue.connect("event-after", self.click_anywhere)
		# Mute button
		self.mute = Gtk.ToggleButton(label=self.mute_labels[0])
		box.pack_start(self.mute, False, False, 0)
		self.mute.connect("toggled", self.muted)
		self.mute.connect("focus", self.focus_select)
		self.mute.connect("event-after", self.click_anywhere)
		# Channel selector
		self.selector = Gtk.RadioButton.new_from_widget(chan_select)
		self.selector.set_label("Selected")
		box.pack_start(self.selector, False, False, 0)
		self.selector.connect("toggled", self.check_selected)
		self.selector.connect("event-after", self.click_anywhere)
		self.connect("event", self.click_anywhere)
		# Add self to group
		self.group.pack_start(self, True, True, 0)
		if not self.hidden: self.group.show_all()

	def focus_select(self, widget, *args):
		"""Select a channel if it gains focus.
		This will also select the first channel on startup as its scale
		will be the first object and will be given focus initially."""
		if widget.is_focus():
			self.selector.set_active(True)
			#print(self.channel_name, "pulled focus")

	def click_anywhere(self, widget, event):
		"""Select a channel if it is clicked on or touched. Connect to
		'event' signal on channel AND 'event-after' signal on widgets,
		otherwise not all events will be captured."""
		ev = event.get_event_type().value_name
		if ev not in {"GDK_MOTION_NOTIFY", "GDK_ENTER_NOTIFY", "GDK_LEAVE_NOTIFY"}:
			# Ignore the spammy events
			#print(widget, ev)
			pass
		if ev == "GDK_FOCUS_CHANGE":
			# For some reason, changes of widget focus by touch do
			# not fire the focus event, so if we get the event, pass
			# the widget to focus_select as it should have been.
			self.focus_select(widget)
			return False
		if "BUTTON" in ev or "TOUCH_BEGIN" in ev:
			# Mouse or touch events - keyboard actions don't matter
			# because if they select a widget, the focus signal is
			# handled by focus_select().
			self.selector.set_active(True)
			return False

	def check_selected(self, widget):
		"""When a channel is selected, move the slider to its position"""
		if widget.get_active():
			Analog.selected_channel = self
			print(Analog.selected_channel.channel_name, "selected")
			self.write_analog(Analog.selected_channel.slider.get_value())

	def adjustment_changed(self, widget):
		"""React to an update from the scale or spinbutton.
		Gtk.Adjustment::value-changed appears to only emit when the
		value has been changed by user interaction, not when the slider
		is moved or the backend emits a change. Thus, we can use this
		to select the radio button."""
		value = widget.get_value()
		self.refract_value(value, "gtk")
		if not self.selector.get_active():
			print(self.name, "adjusted")
		self.selector.set_active(True)

	def refract_value(self, value, source):
		"""Send value to multiple places, keeping track of sent value to avoid bounce or slider fighting."""
		if abs(value - self.oldvalue) >= 1: # Prevent feedback loop when moving slider
			#print(self.channel_name, source, value)
			if source != "gtk":
				self.update_position(value)
			if source != "analog":
				if Analog.selected_channel is self:
					if self.group_name != "Slider":
						self.write_analog(value)
			if source != "backend":
				self.write_external(value)
			self.oldvalue = value

	def write_analog(self, value):
		"""Send a new goal to the special Analog channel if present"""
		normalized_value = value / self.max * 1023 # Scale to the slider's range
		if Analog.slider:
			Analog.slider.refract_value(normalized_value, "channel") # Special source only used by slider channel
		print("Slider goal:", normalized_value)

	# Fallback function if subclasses don't provide write_external()
	def write_external(self, value):
		"""Send the new value to channel backend"""
		print(self.channel_name, value)

	# Fallback/superclass functions
	def muted(self, widget):
		"""React to mute button being pressed - changes label and emits debug print call"""
		mute_state = widget.get_active()
		self.mute.set_label(self.mute_labels[mute_state])
		print(self.channel_name, self.mute_names[mute_state])
		return mute_state

	def update_position(self, value):
		"""Update GTK adjustment (ie scale and spinbutton)"""
		with self.slider.handler_block(self.slider_signal): # Debounce
			self.slider.set_value(value)

	def remove(self):
		"""Remove channel from group, destroying its displayed elements"""
		if Analog.selected_channel is self:
			Analog.selected_channel = None # Because it doesn't make sense to select another module
		#print("Removing:", self.channel_name)
		self.group.remove(self)

import vlc
import webcam
import obs
import browser
import spotify
import Analog

async def main():
	stop = asyncio.Event() # Hold open until destroy signal triggers this event
	main_ui = Gtk.Window(title="Bio Box")
	# TODO: Figure out why the window doesn't pull focus on launch on Pi, instead only requesting attention
	try:
		main_ui.set_icon_from_file("/usr/share/icons/mate/48x48/categories/preferences-desktop.png")
	except gi.repository.GLib.Error:
		pass # No icon
	main_ui.move(0,0)
	action_group = Gtk.ActionGroup(name="biobox_actions")

	menubox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
	main_ui.add(menubox)
	global modules
	modules = Gtk.Box()
	modules.set_border_width(4)
	global chan_select
	chan_select = Gtk.RadioButton()
	menuitems = ""
	toolitems = ""
	menu_entries = []
	class Task():
		running = {}
		def VLC():
			return vlc.vlc(start_time)
		def Webcams():
			return webcam.webcam(start_time)
		def OBS():
			return obs.obs_ws(start_time)
		def Browser():
			return browser.listen(start_time)
		def Spotify():
			return spotify.spotify(start_time)
		def Slider():
			return Analog.start_slider(start_time)
	def toggle_menu_item(widget):
		task_name = widget.get_name()
		if widget.get_active():
			start_task(task_name)
		else:
			spawn(cancel_task(task_name))
	def restart_shim(task):
		spawn(restart_task(task))
	async def restart_task(task):
		for task_name, running_task in Task.running.items():
			if running_task is task:
				await cancel_task(task_name)
				await asyncio.sleep(5)
				start_task(task_name)
				break
	def start_task(task_name):
		task = spawn(getattr(Task, task_name)())
		Task.running[task_name] = task
		task.add_done_callback(handle_errors)
		task.add_done_callback(restart_shim)
	async def cancel_task(task_name):
		try:
			task = Task.running.pop(task_name)
		except KeyError:
			# If a task is cancelled but is not in the list, it probably wasn't running in the first place
			print(task_name, "was not running")
			return
		#print("Cancelling", task_name)
		task.cancel()
		#print(task_name, "cancelled")
		try:
			await task
		except asyncio.CancelledError:
			pass
		except:
			# Will only happen if the task raises during finalization
			print(task_name, "raised an exception")
			traceback.print_exc()
		finally:
			#print(task_name, "cancellation complete")
			pass
	async def cancel_all():
		#print("Shutting down - cancelling all tasks")
		await asyncio.gather(*[cancel_task(task_name) for task_name in Task.running])
		#print("All tasks cancelled")
		stop.set()
	for category in Channel.__subclasses__():
		category_ref = category.__name__
		group_name = category.group_name
		group = Gtk.Box(name=group_name)
		category.group = group
		modules.add(group)
		menuitem = "<menuitem action='%s' />" %category_ref
		menuitems += menuitem
		toolitem = "<toolitem action='%s' />" %category_ref
		toolitems += toolitem
		menu_entry = (category_ref, None, group_name, None, None, toggle_menu_item, True)
			    # Action name   ID	  Label	      Accel Tooltip Callback func   Default state
		menu_entries.append(menu_entry)
	ui_tree = UI_HEADER + menuitems + UI_MIDDLE + toolitems + UI_FOOTER
	action_group.add_action(Gtk.Action(name="ModulesMenu", label="Modules"))
	action_group.add_toggle_actions(menu_entries)
	ui_manager = Gtk.UIManager()
	ui_manager.add_ui_from_string(ui_tree)
	ui_manager.insert_action_group(action_group)
	menubar = ui_manager.get_widget("/MenuBar")
	menubox.pack_start(menubar, False, False, 0)
	toolbar = ui_manager.get_widget("/ToolBar")
	menubox.pack_start(toolbar, False, False, 0)
	scrollbar = Gtk.ScrolledWindow(overlay_scrolling=False)
	scrollbar.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
	scrollbar.set_size_request(0, 355)
	menubox.add(scrollbar)
	scrollbar.add(modules)

	# Show window
	def save_win_pos(*a):
		global winconfig
		# Width and height are set in win_ch to prevent overwrite from a maximized state
		winconfig['maximized'] = main_ui.is_maximized()
		with open('window.json', 'w') as f:
			json.dump(winconfig, f)
	main_ui.connect("delete_event", save_win_pos)

	def win_ch(widget, *a):
		if not widget.is_maximized():
			winconfig['width'] = widget.get_size().width
			winconfig['height'] = widget.get_size().height
	main_ui.connect("check_resize", win_ch) # Fires not just on resize but also on mouseover and interaction with some widgets

	def halt(*a): # We could use a lambda function unless we need IIDPIO
		spawn(cancel_all())
	main_ui.connect("destroy", halt)

	if 'width' in winconfig and 'height' in winconfig: main_ui.resize(winconfig['width'], winconfig['height'])
	if winconfig.get('maximized'): main_ui.maximize()
	main_ui.show_all()

	start_task("VLC")
	start_task("OBS")
	start_task("Browser")
	start_task("Webcams")
	#start_task("Spotify")
	for child in action_group.list_actions():
		if child.get_label() == "Spotify":
			child.set_active(False)
			# Temporary: While running the Spotify module automatically opens the OAuth page,
			# make it at least somewhat interactive until a better solution is made
	if Analog.no_slider:
		for child in action_group.list_actions():
			if child.get_label() == "Slider":
				child.set_active(False)
				child.set_sensitive(False)
	else:
		start_task("Slider")
	#print("[" + str(time.monotonic() - start_time) + "] Starting select_channel timer...")
	GLib.timeout_add(500, init_select_channel)
	await stop.wait()
	
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
	print("Unfinished tasks:", all_tasks) # Should always be empty.
