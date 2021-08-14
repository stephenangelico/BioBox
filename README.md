# The Bio Box

## Audio slider control for Raspberry Pi

![BioBox UI showing multiple channels](GUI_BioBox.png)

This project arose out of the desire for a smooth volume control interface for
various sources, especially when livestreaming. Inspired by digital sound desks,
this project allows use of a motorised slider to smoothly adjust a number of
audio or analog sources, such as:

- OBS: Mic, desktop capture, other inputs - TODO
- VLC
- Media in Chrome - see unpacked extension in VolumeSocket
- Webcam focus

Reference hardware uses a motorized 10kΩ slide potentiometer from [SparkFun](https://www.sparkfun.com/products/10976)
with the potentiometer attached to a MCP3008 analog-to-digital converter (ADC),
and the motor connected to a TB6612FNG motor controller. See [Wiring](#wiring)
for details on where to connect everything.


Dependencies:
=============

- `python3-gi` from your package manager
- Python packages as per `requirements.txt`

Setup:
======

SPI must be enabled to connect to the ADC. This can be done with `raspi-config`
(see [here](https://raspberrypi.stackexchange.com/a/47398/134450) for installation
instructions) or by following [these instructions](https://www.raspberrypi.org/documentation/hardware/raspberrypi/spi/README.md#software).

TODO: finish writing

Wiring:
=======

- Analogue input
	- MCP3008 connections:
		- VDD -> 3.3V (pin 17)
		- VREF -> 3.3V (pin 17)
		- AGND -> GND (pin 25)
		- CLK -> SCLK (pin 23)
		- DOUT -> MISO (pin 21)
		- DIN -> MOSI (pin 19)
		- CS -> GPIO #22 (pin 15)
		- DGND -> GND (pin 25)
	- Slider connections:
		- L1 -> R3 (range)
		- L2 NC
		- L3 unused
		- L4 unused
		- R1 -> CH0 (MCP pin 1)
		- R2 -> 3.3V (MCP pin 16)
		- R3 -> L1 (range)
		- R4 -> GND (MCP pin 9)

- Motor control
	- TB6612FNG connections:
		- VM -> +5V (pin 2)
		- VCC -> +5V (pin 2)
		- GND 1 unused
		- A01 -> Motor yellow
		- A02 -> Motor green
		- B02 unused
		- B01 unused
		- GND 2 -> GND (pin 9)
		- PWMA -> GPIO 17 (pin 11)
		- AIN2 -> GPIO 27 (pin 13)
		- AIN1 -> GPIO 18 (pin 12)
		- STBY -> GPIO 23 (pin 16)
		- BIN1 unused
		- BIN2 unused
		- PWMB unused
		- GND 3 unused

When slider should snap to a position, set a goal position.
If a goal is set, don't yield to BioBox main.
Calculate difference between current position and goal, and adjust direction
and duty cycle based on table:
if goal < pos, use reverse
for abs(pos - goal): (subject to change)
	>50: speed 100
	>25: speed 75
	>10: speed 50
	>1: speed 25
	Else: stop/apply brake

After reaching goal, it may be necessary to not yield for another two ticks.
