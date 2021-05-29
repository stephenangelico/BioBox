import os
import time
import busio
import digitalio
import board
import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn

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

def remap_range(value, left_min, left_max, right_min, right_max):
	# this remaps a value from original (left) range to new (right) range
	# Figure out how 'wide' each range is
	left_span = left_max - left_min
	right_span = right_max - right_min
	# Convert the left range into a 0-1 range (int)
	valueScaled = int(value - left_min) / int(left_span)
	# Convert the 0-1 range into a value in the right range.
	return int(right_min + (max(valueScaled, 0) * right_span))

def read_value():
	last_read = 0	# this keeps track of the last potentiometer value
	while True:
		# we'll assume that the pot didn't move
		pot_changed = False
		# read the analog pin
		pot = chan0.value
		# how much has it changed since the last read?
		pot_adjust = abs(pot - last_read)
		if pot_adjust > TOLERANCE:
		# convert 16bit adc0 (0-65535) trim pot read into 0-100 volume level
			volume = remap_range(pot, 32700, 65472, 0, 100)
			# save the potentiometer reading for the next loop
			last_read = pot
			yield(volume)
		time.sleep(0.015625)

if __name__ == "__main__":
	for volume in read_value():
		print("Volume = %d%%" % volume)
		print(volume)
