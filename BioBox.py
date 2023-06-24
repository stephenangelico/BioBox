import time
import json
import builtins
import traceback
import asyncio

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib

import gbulb
gbulb.install(gtk=True)

try:
	import Analog
	from Motor import cleanup as motor_cleanup
except (ImportError, NotImplementedError, RuntimeError): # Provide a dummy for testing
	def motor_cleanup():
		pass
	class Analog():
		goal = None
		next_goal_time = 0
		async def read_value():
			yield 0 # Yield once and then stop
			# Just as a function is destined to yield once, and then face termination...
			# TODO: instead of creating dummy function, disable slider task on startup

import config # ImportError? See config_example.py

winconfig = {}
try:
	with open('window.json', 'r') as f:
		winconfig = json.load(f)
except FileNotFoundError:
	pass # Later references to winconfig should already handle no data

selected_channel = None

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

# Slider
async def read_analog():
	# Get analog value from Analog.py and write to selected channel's slider
	# TODO: Turn the above line and other similar comments into docstrings
	async for pos in Analog.read_value():
		if selected_channel:
			print("From slider:", pos)
			# So far I have no reason for a module with a non-zero minimum
			# TODO: Yes I do now - Webcam exposure can be 3-2048
			scale_max = selected_channel.max
			# Scale 0-1023 to scale_max
			value = pos * scale_max / 1023
			selected_channel.refract_value(value, "analog")
			Analog.next_goal_time = time.monotonic() + 0.15

def init_motor_pos():
	for module in modules.get_children():
		for channel in module.get_children():
			channel.selector.set_active(True)
			channel.mute.grab_focus()
			break
		if selected_channel:
			break
	if selected_channel:
		scale_max = selected_channel.max
		Analog.goal = selected_channel.slider.get_value() / scale_max * 1023
	else:
		Analog.goal = 1023

@export
class Channel(Gtk.Frame):
	mute_labels = ("Mute", "Muted")
	step = 0.01
	max = 150
	min = 0
	channel_types = []

	def __init_subclass__(cls, **kwargs):
		# This ensures that subclasses defined elsewhere are counted for menus
		cls.channel_types.append(cls)
		super().__init_subclass__(**kwargs)

	def __init__(self, name):
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
		level.connect("focus", self.focus_delay)
		self.slider_signal = self.slider.connect("value-changed", self.adjustment_changed)
		# Spinner
		spinvalue = Gtk.SpinButton(adjustment=self.slider, digits=2)
		box.pack_start(spinvalue, False, False, 0)
		spinvalue.connect("focus", self.focus_delay)
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
			print(self.channel_name, "pulled focus")

	def click_anywhere(self, widget, event):
		if "BUTTON" in event.get_event_type().value_name:
			self.selector.set_active(True)
			return False
		elif event.get_event_type().value_name != "GDK_MOTION_NOTIFY":
			print(event.get_event_type().value_name)

	def check_selected(self, widget):
		global selected_channel
		if widget.get_active():
			selected_channel = self
			print(selected_channel.channel_name, "selected")
			self.write_analog(selected_channel.slider.get_value())

	def adjustment_changed(self, widget):
		value = widget.get_value()
		self.refract_value(value, "gtk")
		self.selector.set_active(True)
		# Gtk.Adjustment::value-changed appears to only emit when the
		# value has been changed by user interaction, not when the slider
		# is moved or the backend emits a change. Thus, we can use this
		# to select the radio button.

	def refract_value(self, value, source):
		# Send value to multiple places, keeping track of sent value to
		# avoid bounce or slider fighting.
		if abs(value - self.oldvalue) >= 1: # Prevent feedback loop when moving slider
			#print(self.channel_name, source, value)
			if source != "gtk":
				self.update_position(value)
			if source != "analog":
				if selected_channel is self:
					self.write_analog(value)
			if source != "backend":
				self.write_external(value)
			self.oldvalue = value

	def write_analog(self, value):
		Analog.next_goal = value / self.max * 1023
		print("Slider goal: %s" % Analog.next_goal)

	# Fallback function if subclasses don't provide write_external()
	def write_external(self, value):
		print(self.channel_name, value)

	# Fallback/superclass functions
	def muted(self, widget):
		mute_state = widget.get_active()
		self.mute.set_label(self.mute_labels[mute_state])
		print(self.channel_name, "un" * (not mute_state) + "muted")
		return mute_state

	def update_position(self, value):
		with self.slider.handler_block(self.slider_signal):
			self.slider.set_value(value)

	def remove(self):
		global selected_channel
		if selected_channel is self:
			selected_channel = None # Because it doesn't make sense to select another module
		print("Removing:", self.channel_name)
		self.group.remove(self)

import vlc
import webcam
import obs
import browser

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
			return vlc.vlc()
		def Webcam():
			return webcam.webcam()
		def OBSModule():
			return obs.obs_ws()
		def Browser():
			return browser.listen()
	def toggle_menu_item(widget):
		toggle_group = widget.get_name()
		if widget.get_active():
			start_task(toggle_group)
		else:
			spawn(cancel_task(toggle_group))
	def start_task(task):
		obj = asyncio.create_task(getattr(Task, task)()) # TODO: check if this can become spawn()
		Task.running[task] = obj
		obj.add_done_callback(handle_errors)
	async def cancel_task(task):
		t = Task.running.pop(task)
		print("Cancelling", task)
		t.cancel()
		print(task, "cancelled")
		try:
			await t
		except asyncio.CancelledError:
			pass
		except:
			# Will only happen if the task raises during finalization
			print(task, "raised an exception")
			traceback.print_exc()
		finally:
			print(task, "cancellation complete")
	async def cancel_all():
		print("Shutting down - cancelling all tasks")
		await asyncio.gather(*[cancel_task(t) for t in Task.running])
		print("All tasks cancelled")
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

	GLib.timeout_add(1000, init_motor_pos)
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

	slider_task = asyncio.create_task(read_analog()) # TODO: Use spawn()?
	start_task("VLC")
	start_task("OBSModule")
	start_task("Browser")
	start_task("Webcam")
	await stop.wait()
	motor_cleanup()
	
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
