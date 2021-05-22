# The Bio Box

## Audio slider control for Raspberry Pi

Wanted controls:

- OBS: Mic, desktop capture, other inputs
- VLC
- Specific app via Pulseaudio

TODO:

- Find a way to power motor in slider
	- Use external power adapter @ 9V
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
		- VM -> Barrel +9V
		- VCC -> +5V (pin 2)
		- GND 1 unused
		- A01 -> Motor yellow
		- A02 -> Motor green
		- B02 unused
		- B01 unused
		- GND 2 -> Barrel GND
		- PWMA -> GPIO 17 (pin 11)
		- AIN2 -> GPIO 27 (pin 13)
		- AIN1 -> GPIO 18 (pin 12)
		- STBY -> GPIO 23 (pin 16)
		- BIN1 unused
		- BIN2 unused
		- PWMB unused
		- GND 3 unused

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
