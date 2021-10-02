import os
import time
import collections
import busio
import digitalio
import board
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn
import Motor

# create the spi bus
spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)

# create the cs (chip select)
cs = digitalio.DigitalInOut(board.D22)

# create the mcp object
mcp = MCP.MCP3008(spi, cs)

# create an analog input channel on pin 0
chan0 = AnalogIn(mcp, MCP.P0)

print('Raw ADC Value: ', chan0.value)
print('ADC Voltage: ' + str(chan0.voltage) + 'V')

TOLERANCE = 250	# to keep from being jittery we'll only change
		# volume when the pot has moved a significant amount
		# on a 16-bit ADC

pot_min = 32700
pot_max = 65472
goal = None
Motor.standby(False)

def remap_range(value, left_min, left_max, right_min, right_max):
	# this remaps a value from original (left) range to new (right) range
	# Figure out how 'wide' each range is
	left_span = left_max - left_min
	right_span = right_max - right_min
	# Convert the left range into a 0-1 range (int)
	valueScaled = int(value - left_min) / int(left_span)
	# Convert the 0-1 range into a value in the right range.
	return int(right_min + (max(valueScaled, 0) * right_span))

def read_position():
	last_read = 0	# this keeps track of the last potentiometer value
	while True:
		# we'll assume that the pot didn't move
		pot_changed = False
		# read the analog pin
		pot = chan0.value
		# how much has it changed since the last read?
		pot_adjust = abs(pot - last_read)
		if pot_adjust > TOLERANCE or goal is not None:
		# convert 16bit adc0 (0-65535) trim pot read into 0-100 volume level
			pos = remap_range(pot, 33024, 65472, 0, 100)
			# save the potentiometer reading for the next loop
			last_read = pot
			yield(pos)
		time.sleep(0.015625)

def init_bounds():
	if chan0.value < (pot_max+pot_min)/2:
		bounds_test("top")
		bounds_test("bottom")
	else:
		bounds_test("top")
		bounds_test("bottom")

def bounds_test(test_dir):
	if test_dir == "top":
		Motor.forward()
	elif test_dir == "bottom":
		Motor.backward()
	Motor.speed(100)
	span = collections.deque(maxlen=5)
	while True:
		span.append((chan0.value // 64))
		if len(span) == span.maxlen:
			if max(span) - min(span) < 2:
				return span[-1]
		time.sleep(0.015625)

def test_span():
	high_set = []
	low_set = []
	try:
		for int in range(100):
			high_set.append(bounds_test("top"))
			low_set.append(bounds_test("bottom"))
	finally:
		Motor.cleanup()
	print(high_set)
	print(low_set)

def read_value():
	global goal
	last_speed = None
	last_dir = None
	goal_completed = 0
	for pos in read_position():
		if goal is not None:
			if goal < 0:
				goal = 0
			if goal > 100:
				goal = 100
			dist = abs(pos - goal)
			if dist >= 25:
				speed = 100
			elif dist >= 1:
				speed = 80
			else:
				speed = 0
			if goal > pos:
				dir = Motor.forward
			elif goal < pos:
				dir = Motor.backward
			elif goal == pos:
				dir = Motor.brake
				goal = None
				goal_completed = time.monotonic()
			print(dir.__name__, speed, dist)
			if speed != last_speed:
				Motor.speed(speed)
				last_speed = speed
			if dir is not last_dir:
				dir()
				last_dir = dir
		else:
			if time.monotonic() > goal_completed + 0.15:
				yield(pos)

def test_slider():
	Motor.forward()
	Motor.speed(10)
	start = chan0.value
	while chan0.value < 36800:
		print(chan0.value, chan0.value - start)
		start = chan0.value
		time.sleep(1/32)
	print(chan0.value, chan0.value - start)
	Motor.stop()
	Motor.speed(0)

def time_boundaries():
	boundaries = [None] * 11
	with open("README.md") as f:
		for line in f:
			try:
				idx, val = line.split(":")
				boundaries[int(idx) // 10] = int(val)
			except ValueError: pass
	# print(boundaries)
	# TODO: Seek to bottom first?
	Motor.forward()
	Motor.speed(100)
	start = time.time()
	next = 0
	safety = collections.deque([0] * 10)
	while True:
		cur = chan0.value // 64
		if cur >= next:
			print("%3d: %4d --> %.2f\x1b[K" % (cur * 10, next, time.time() - start))
			next += 1
			if next >= len(boundaries): break
		else:
			print("%3d: %4d ... %.2f\x1b[K" % (cur * 10, next, time.time() - start))
		safety.append(cur)
		if max(safety) - min(safety) < 2: break # Guard against getting stuck
		time.sleep(1 / 64)

if __name__ == "__main__":
	goal = 75
	try:
		last = None
		while True:
			value = chan0.value
			if value != last:
				print(value, end="\x1b[K\r")
				last = value
			time.sleep(0.015625)
	finally:
		Motor.cleanup()
