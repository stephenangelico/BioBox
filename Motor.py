import time
import RPi.GPIO as GPIO
from RpiMotorLib import rpi_dc_lib

mot = rpi_dc_lib.TB6612FNGDc(18, 27, 17, 50, True, "Slider Motor")
type(mot).standby(23, True)

def up_a_bit(sec):
	mot.forward(100)
	time.sleep(sec)
	mot.stop()

def down_a_bit(sec):
	mot.backward(100)
	time.sleep(sec)
	mot.stop()
