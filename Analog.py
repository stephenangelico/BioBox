import os
import time
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
			pos = remap_range(pot, 32700, 65472, 0, 100)
			# save the potentiometer reading for the next loop
			last_read = pot
			yield(pos)
		time.sleep(0.015625)

def read_value():
	global goal
	last_speed = None
	last_dir = None
	for pos in read_position():
		if goal is not None:
			if goal < 0:
				goal = 0
			if goal > 100:
				goal = 100
			dist = abs(pos - goal)
			if dist >= 25:
				speed = 100
			elif dist >= 5:
				speed = 80
			elif dist >= 2:
				speed = 25
			elif dist >= 1:
				speed = 10
			else:
				speed = 0
			if goal > pos:
				dir = Motor.forward
			elif goal < pos:
				dir = Motor.backward
			elif goal == pos:
				dir = Motor.stop
				goal = None
			if speed != last_speed:
				Motor.speed(speed)
				last_speed = speed
			if dir is not last_dir:
				dir()
				last_dir = dir
			print(dir, speed, dist)
		else:
			yield(pos)

if __name__ == "__main__":
	goal = 75
	try:
		for volume in read_value():
			print("Volume = %d%%" % volume)
			print(volume)
	finally:
		Motor.cleanup()
