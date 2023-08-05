# Internal motor library for TB6612FNG controller
# Sets up motor and exposes simple methods for moving small distances
import time
import RPi.GPIO as GPIO

PIN_A = 18
PIN_B = 27
PIN_STBY = 23
PIN_PWM = 17
FREQ = 50

def init():
	GPIO.setmode(GPIO.BCM)
	GPIO.setwarnings(False)
	GPIO.setup(PIN_A, GPIO.OUT)
	GPIO.setup(PIN_B, GPIO.OUT)
	GPIO.setup(PIN_STBY, GPIO.OUT)
	GPIO.setup(PIN_PWM, GPIO.OUT)
	global pwm
	pwm = GPIO.PWM(PIN_PWM, FREQ)
	pwm.start(0)

def standby(state):
	# "Standby" means turning off the motor. The controller requires the
	# STBY pin to be pulled high to run the motor. Therefore, to enable the
	# motor to run, call standby(False).
	GPIO.output(PIN_STBY, not state)

def forward():
	GPIO.output(PIN_A, True)
	GPIO.output(PIN_B, False)

def backward():
	GPIO.output(PIN_A, False)
	GPIO.output(PIN_B, True)
	
def stop():
	GPIO.output(PIN_A, False)
	GPIO.output(PIN_B, False)

def brake():
	GPIO.output(PIN_A, True)
	GPIO.output(PIN_B, True)
	time.sleep(0.1)
	stop()

def sleep(state):
	# Wrapper for standby() to ensure motor is fully stopped
	speed(0)
	stop()
	standby(state)

def speed(duty_cycle):
	pwm.ChangeDutyCycle(duty_cycle)

def cleanup():
	sleep(True)
	pwm.stop()
	GPIO.cleanup()
