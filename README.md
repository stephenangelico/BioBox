# The Bio Box

## Audio slider control for Raspberry Pi

![BioBox UI showing multiple channels](GUI_BioBox.png)

This project arose out of the desire for a smooth volume control interface for
various sources, especially when livestreaming. Inspired by digital sound desks,
this project allows use of a motorised slider to smoothly adjust a number of
audio or analog sources, such as:

- OBS: Mic, desktop capture, other inputs
- VLC
- Media in Chrome - see unpacked extension in VolumeSocket
- Webcam focus and exposure
- Pulseaudio - TODO

BioBox can be run on a PC without any kind of analog slider, but its usefulness
will be limited. You still have the benefit of multiple sources controlled in
one place, but adjustment is still done by click-dragging or scrolling.

Reference hardware uses a [Bourns PSM01-082A-103B2](https://www.mouser.com/ProductDetail/Bourns/PSM01-082A-103B2?qs=MAZTpT1IVl8rvdecO07rRA%3D%3D)
motorized 10kΩ slide potentiometer attached to a MCP3008 analog-to-digital
converter (ADC), and the motor connected to a TB6612FNG motor controller. See
[Wiring](#wiring) for details.


Dependencies:
=============

- `python3-gi` from your package manager
- Python packages as per `requirements.txt`:
  - `gbulb` - Required to run main event loop
  - `adafruit-blinka` and `adafruit-circuitpython-mcp3xxx` - for interfacing with slider
  - `RPi.GPIO` - for motor driver in Motor.py
  - `websockets` - for connecting to OBS and browser extension
  - `v4l2py` - for interfacing with webcams
- [TellMeVLC](https://github.com/Rosuav/TellMeVLC) for VLC integration
- OBS 28+ for OBS integration

Setup:
======

SPI must be enabled to connect to the ADC. This can be done with `raspi-config`
(see [here](https://raspberrypi.stackexchange.com/a/47398/134450) for installation
instructions) or by following [these instructions](https://www.raspberrypi.org/documentation/hardware/raspberrypi/spi/README.md#software).

1. Install dependencies as required for the modules/features you intend to run
2. Copy `config_example.py` to `config.py` and change values as required (some values explained below)
3. For VLC integration, see [TellMeVLC](https://github.com/Rosuav/TellMeVLC)
4. For OBS integration, OBS -> Tools -> WebSocket Server Settings -> Enable WebSocket server, copy port number and password (if applicable) into config.py


TODO: finish writing (ie webcam)

Wiring:
=======

TODO: Update for new slider and include Fritzing image(s)

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
