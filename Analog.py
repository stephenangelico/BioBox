import os
import asyncio
import time
import collections
import contextlib
import busio # ImportError? python3 -m pip install -r requirements.txt
import digitalio # ImportError? python3 -m pip install -r requirements.txt

no_slider = False
try:
	import RPi.GPIO as GPIO
	import board
	import adafruit_mcp3xxx.mcp3008 as MCP
	from adafruit_mcp3xxx.analog_in import AnalogIn
	import Motor
except (ImportError, NotImplementedError, RuntimeError):
	no_slider = True

TOLERANCE = 1

selected_channel = None
slider = None
goal = None
next_goal = None
next_goal_time = time.monotonic()

# Stub to fix running Analog.py without BioBox context
try:
	Channel
except NameError:
	class Channel():
		def __init__(self, **kw):
			pass

class Slider(Channel):
	group_name = "Slider"
	step = 1.0
	min = 0
	max = 1023
	hidden = True

	def __init__(self):
		super().__init__(name="Slider")

	def write_external(self, value):
		global next_goal
		next_goal = value

	def refract_value(self, value, source):
		"""Send value to multiple places, keeping track of sent value to avoid bounce or slider fighting."""
		if abs(value - self.oldvalue) >= 1: # Prevent feedback loop when moving slider
			#print(self.channel_name, source, value)
			if source != "gtk":
				self.update_position(value)
			if source != "channel":
				if selected_channel:
					if selected_channel is not self:
						# Scale 0-1023 to scale_max
						# So far I have no reason for a module with a non-zero minimum
						# Webcam exposure can be 3-2048 but this can basically be ignored
						level = value * selected_channel.max / 1023
						selected_channel.refract_value(level, "analog")
			if source != "backend":
				self.write_external(value)
			self.oldvalue = value


def remap_range(raw):
	"""Bound and invert values from ADC"""
	if raw >= 1023: # Check if at extremities
		raw = 1023
	elif raw <= 0:
		raw = 0
	# Invert value - by default on this potentiometer, 0 is top. May change
	# if wires are other way round on 1'/2'/3' or by using 1/2/3.
	pos = 1023 - raw
	return pos

async def read_position():
	"""Read the raw value from the ADC"""
	last_read = 0	# this keeps track of the last potentiometer value
	while True:
		await asyncio.sleep(0.015625)
		# read the analog pin
		# ADC provides a 16-bit value, but the low 5 bits are always floored,
		# so divide by 64 to get more usable numbers without losing precision.
		pot = chan0.value // 64
		# how much has it changed since the last read?
		pot_adjust = abs(pot - last_read)
		if pot_adjust > TOLERANCE or next_goal is not None or goal is not None:
			pos = remap_range(pot)
			# save the potentiometer reading for the next loop
			last_read = pot
			yield(pos)

@contextlib.contextmanager
def init_slider():
	"""Initialize MCP object and start the hidden channel"""
	global slider
	slider = None
	try:
		# Set pin numbering mode
		GPIO.setmode(GPIO.BCM)
		# create the spi bus
		spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)
		# create the cs (chip select)
		cs = digitalio.DigitalInOut(board.D22)
		# create the mcp object
		mcp = MCP.MCP3008(spi, cs)
		# create an analog input channel on pin 0
		global chan0
		chan0 = AnalogIn(mcp, MCP.P0)
		print('Raw ADC Value: ', chan0.value)
		print('ADC Voltage: ' + str(chan0.voltage) + 'V')
		yield # Context manager takes over here
	finally:
		if slider:
			slider.remove()
		Motor.cleanup()
		GPIO.cleanup()
		slider = None

async def read_value(start_time):
	"""Move the slider if it has somewhere to go, otherwise send values to BioBox"""
	# Reset goal attributes in case of slider restart
	global goal
	global next_goal
	global next_goal_time
	goal = None
	next_goal = None
	next_goal_time = time.monotonic()
	last_speed = None
	last_dir = None
	goal_completed = 0
	#safety = collections.deque([0] * 2, 5)
	# Let's get this motor on the MOVE!
	Motor.init()
	Motor.sleep(False)
	# Spawn the channel
	global slider
	slider = Slider()
	print("[" + str(time.monotonic() - start_time) + "] Slider online.")
	# Initialize slider position after giving other channels a chance to initialize themselves
	await asyncio.sleep(0.5)
	if selected_channel:
		normalized_value = selected_channel.slider.get_value() / selected_channel.max * 1023 # Scale to the slider's range
		slider.refract_value(normalized_value, "channel")
	else:
		slider.refract_value(1023, "channel")
	try:
		async for pos in read_position():
			if next_goal is not None:
				if time.monotonic() > next_goal_time:
					print("Accepting goal:", next_goal)
					goal = next_goal
					next_goal = None
					next_goal_time = time.monotonic() + 0.15
				# Else wait until the next iteration, eventually it will be.
			if goal is not None:
				braked = False
				#safety.append(pos)
				if goal < 0:
					goal = 0
					print("Goal set to 0")
				if goal > 1023:
					goal = 1023
					print("Goal set to 1023")
				if goal > pos:
					dir = Motor.forward
				elif goal < pos:
					dir = Motor.backward
				else:
					dir = Motor.stop # If exactly equal, we don't need to move, but in case we *ever* get NaN, don't do weird stuff.
					# Not strictly necessary becuase distance is checked below but good for logic.
				dist = abs(pos - goal)
				if dist >= 256:
					speed = 100
				elif dist >= 16:
					speed = 80
				elif dist >= 1:
					speed = 20
					# TODO: Prevent changing speed by more that ±20% per tick
				else:
					# If dist is NaN for any reason, all above statements will be False and the motor will stop.
					speed = 0
					dir = Motor.stop
					# TODO: only unset goal if we're stable here - set a flag for next iteration to check or clear if we've overshot.
					goal = None
					goal_completed = time.monotonic()
					#safety.append(-1)
				#if max(safety) - min(safety) < 1: # Guard against getting stuck
				#	# This does not solve slider fighting, but it should stop the motor wearing out as fast
				#	braked = True # Use in print call below like `braked * "Brakes engaged"`
				#	speed = 0
				#	dir = Motor.brake
				#	goal = None
				#	goal_completed = time.monotonic()
				print(goal, pos, dist, speed, dir.__name__)
				if speed != last_speed:
					Motor.speed(speed)
					last_speed = speed
				if dir is not last_dir:
					dir()
					last_dir = dir
			else:
				if not next_goal and time.monotonic() > goal_completed + 0.15:
					slider.refract_value(pos, "backend")
	finally:
		goal = None
		Motor.sleep(True)

async def start_slider(start_time):
	"""Wrapper for init_slider"""
	if no_slider:
		return
	with init_slider():
		# Start reading - await so it holds here until interrupted
		await read_value(start_time)

def test_slider():
	# Test progression of slider with slow movement to tell the difference
	# between acceleration and getting stuck
	# Start with slider at *top* of travel, slider will stop close to middle
	Motor.sleep(False)
	Motor.backward()
	Motor.speed(10)
	start = chan0.value
	while chan0.value < 36800:
		print(chan0.value, chan0.value - start)
		start = chan0.value
		time.sleep(1/32)
	print(chan0.value, chan0.value - start)
	Motor.sleep(True)

def print_value():
	# TODO: fix now that initialization is in start_slider()
	last = None
	if no_slider:
		return
	with init_slider():
		while True:
			value = 1023 - chan0.value // 64
			if value != last:
				print(value, end="\x1b[K\r")
				last = value
			time.sleep(0.015625)

if __name__ == "__main__":
	try:
		print_value()
	finally:
		Motor.cleanup()
		GPIO.cleanup()
