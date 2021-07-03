# The Bio Box

## Audio slider control for Raspberry Pi

Dependencies:
=============

- `python3-gi` from your package manager
- `raspi-config` to enable the SPI interface for the ADC
- `adafruit-blinka` and `adafruit-circuitpython-mcp3xxx` for the slider
- `RPi.GPIO` for the motor
- `websockets` for OBS and browser integration

Wanted controls:
================

- OBS: Mic, desktop capture, other inputs
- VLC - Done!
- Specific app via Pulseaudio
- Desk cam focus - Done!

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

TODO: Re-implement motor library

UI design:

```
+----------++----------++----------++----------++----------++----------+
|  Label   ||  Label   ||  Label   ||  Label   ||  Label   ||  Label   |
|    +     ||   [+]    ||    +     ||    +     ||    +     ||    +     |
|    |     ||    |     ||    |     ||    |     ||    |     ||    |     |
|    |     ||    |     ||    |     ||    |     ||    |     ||    |     |
|    |     ||    |     ||    |     ||    |     ||    |     ||    |     |
|   [|]    ||    |     ||    |     ||    |     ||   [|]    ||    |     |
|    |     ||    |     ||    |     ||    |     ||    |     ||    |     |
|    |     ||    |     ||    |     ||    |     ||    |     ||    |     |
|    |     ||    |     ||    |     ||   [|]    ||    |     ||    |     |
|    |     ||    |     ||    |     ||    |     ||    |     ||    |     |
|    |     ||    |     ||    |     ||    |     ||    |     ||   [|]    |
|    |     ||    |     ||    |     ||    |     ||    |     ||    |     |
|    -     ||    -     ||   [-]    ||    -     ||    -     ||    -     |
|  [Mute]  ||  [Mute]  ||  [Mute]  ||  [Mute]  ||  [Mute]  ||  [Mute]  |
+----------++----------++----------++----------++----------++----------+
```
