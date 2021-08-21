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
		- L1 -> R3 ("bragging wire")
		- L2 NC
		- L3 unused
		- L4 unused
		- R1 -> CH0 (MCP pin 1)
		- R2 -> 3.3V (MCP pin 16)
		- R3 -> L1 ("bragging wire")
		- R4 -> GND (MCP pin 9)

The "bragging wire" tells you how great the range of the potentiometer is. The
reason this is necessary for this slider is because the MCP3008 needs the full
range of resistance to be present between +3.3V and GND. For most 3-pin
potentiometers, this is simply done by wiring the outside pins to +3.3v and GND,
and the middle pin to a channel. With this slider, there are two independent
2-pin scales which work in opposite directions. When added together, the scales
always add up to the full range, irrespective of the position of the slider.
Therefore, by linking the opposite scales and measuring one of them, we can
emulate a single 3-pin potentiometer to the MCP3008.

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

Resistance testing over time:
=============================

Problem: When the slider is not moved, sometimes it drifts over time or is
unable to reach extremities (causing secondary issue where motor keeps pushing
slider beyond top of scale). Could be caused by change in temperature as on cold
days, slider often cannot reach 100 at top of scale (observed as low as 80)
until some time later such as middle of stream. Testing methodology: test all
resistance values at cold, warmer and warm times. If observable drift in
resistance values, test against static resistor and see if static resistor can
be used to provide baseline resistance to compare with potentiometer "bragging
wire" value and possibly use to calculate scaling factor to stabilize resultant
percentage* values (*Before scaling to linear position values).

20210821 10:26:
Baseline 1.8Ω (probe to probe)
R2 - L1 10.61kΩ irrespective of slider position
Slider at top:
R2 - R1 3.8Ω
R1 - L1 10.62kΩ
Slider at bottom:
R1 - L1 ~13Ω (trending downward)
R2 - R1 10.62kΩ

20210821 11:21:
Baseline 1.8Ω
10kΩ "chunky" resistor 9.87kΩ
R2 - L1 10.6kΩ
Slider at top:
R2 - R1 3.2Ω
R1 - L1 10.6kΩ
Slider at bottom:
R1 - L1 12.3Ω
R2 - R1 10.61kΩ
