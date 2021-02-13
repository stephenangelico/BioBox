# The Bio Box

## Audio slider control for Raspberry Pi

Wanted controls:

- OBS: Mic, desktop capture, other inputs
- VLC
- Specific app via Pulseaudio

TODO:

- Find a way to power motor in slider
	- Requires ~10V
	- Double 5V? Need 2:1 transformer, powered from Pi
	- Use external power adapter @ 9V?
- Analogue input
	- Pi Pico has analogue input
		- More complex, requires USB connection to Pi
		- Code is uPython
	- MCP3008 is simpler and probably more appropriate
		- Uses 3.3V
		- Pins align on one side of GPIO header
		- Need to learn about SPI interface
- Free up both breadboards from Char LCD
	- Use one for ADC
	- Use other for motor controller


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
