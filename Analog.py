import os
import asyncio
import time
import collections
import RPi.GPIO as GPIO
import busio
import digitalio
import board
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn
import Motor

# Set pin numbering mode
GPIO.setmode(GPIO.BCM)

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

TOLERANCE = 1
goal = None
next_goal = None
next_goal_time = time.monotonic() + 0.5 # TODO: Experiment with startup delay

async def read_position():
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

def remap_range(raw):
	# Bound and invert values from ADC
	if raw >= 1023: # Check if at extremities
		raw = 1023
	elif raw <= 0:
		raw = 0
	# Invert value - by default on this potentiometer, 0 is top. May change
	# if wires are other way round on 1'/2'/3' or by using 1/2/3.
	pos = 1023 - raw
	return pos

async def read_value():
	global goal
	global next_goal
	global next_goal_time
	Motor.sleep(False)
	last_speed = None
	last_dir = None
	goal_completed = 0
	#safety = collections.deque([0] * 2, 5)
	try:
		async for pos in read_position():
			if next_goal is not None:
				if time.monotonic() > next_goal_time:
					print("Accepting goal:", next_goal)
					goal = next_goal
					next_goal = None
					next_goal_time = time.monotonic() + 0.1
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
				if time.monotonic() > goal_completed + 0.15:
					yield(pos)
	finally:
		goal = None
		Motor.sleep(True)


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
	last = None
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
