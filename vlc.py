import time
import asyncio
import config # ImportError? See config_example.py

class VLC(Channel):
	group_name = "VLC"
	step = 1.0

	def __init__(self, writer):
		super().__init__(name="VLC")
		self.writer = writer

	def write_external(self, value):
		self.writer.write(b"volume %d \r\n" %value)
		spawn(self.writer.drain())
		print("To VLC: ", value)

	def muted(self, widget):
		mute_state = super().muted(widget) # Handles label change and IIDPIO
		self.writer.write(b"muted %d \r\n" %mute_state)
		spawn(self.writer.drain())

async def vlc(start_time):
	vlc_module = None
	try:
		reader, writer = await asyncio.open_connection(config.host, config.vlc_port)
		writer.write(b"volume\r\nmuted\r\n") # Ask volume and mute state
		await writer.drain()
		vlc_module = VLC(writer)
		print("[" + str(time.monotonic() - start_time) + "] VLC connected.")
		await vlc_buf_read(vlc_module, reader)
	except ConnectionRefusedError:
		print("Could not connect to VLC on %s:%s - is TMV running?" % (config.host, config.vlc_port))
		# TODO: Retry connection if lost
	finally:
		if vlc_module:
			vlc_module.remove()
			writer.close() # Close connection and remove module
			await writer.wait_closed()
		print("VLC cleanup done")

async def vlc_buf_read(vlc_module, reader):
	while True:
		data = await reader.readline()
		if not data:
			break
		line = data.decode("utf-8")
		attr, value = line.split(":", 1)
		if attr == "volume":
			vlc_module.refract_value(float(value), "backend")
		elif attr == "muted":
			vlc_module.mute.set_active(int(value))
		else:
			print("From VLC:", attr, value)
