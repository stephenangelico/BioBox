import time
import subprocess
import asyncio
import config

webcams = {}

class Webcam(Channel):
	group_name = "Webcams"
	mute_labels = ("Manual", "Auto")
	mute_names = ("Manual", "Auto")
	step = 1.0 # Cameras have different steps but v4l2 will round any value to the step for the camera in question

	def __init__(self, cam_name, cam_path, mode, ssh):
		self.name = cam_name + " " + mode
		super().__init__(name=self.name)
		self.device = cam_path
		self.ssh = ssh
		if mode == "Focus":
			self.vol_cmd = "focus_absolute"
			self.mute_cmd = "focus_auto"
			self.mute_states = (0, 1)
		elif mode == "Exposure":
			self.vol_cmd = "exposure_absolute"
			self.mute_cmd = "exposure_auto"
			self.mute_states = (1, 3) # Applicable for most webcams


	def write_external(self, value):
		# v4l2-ctl throws an error if value is changed while in auto.
		# Therefore, if auto is enabled, quietly do nothing.
		# Feedback continues when in auto, so theoretically value should be correct.
		if not self.mute.get_active():
			self.ssh.stdin.write(("%s %d %s\n" % (self.vol_cmd, value, self.device)).encode("utf-8"))
			spawn(self.write_ssh())

	async def write_ssh(self):
		try:
			await self.ssh.stdin.drain()
		except ConnectionResetError as e:
			print("SSH connection lost")

	def muted(self, widget):
		mute_state = super().muted(widget) # Handles label change and IIDPIO
		self.ssh.stdin.write(("%s %d %s\n" % (self.mute_cmd, self.mute_states[mute_state], self.device)).encode("utf-8"))
		spawn(self.ssh.stdin.drain())

async def webcam(start_time):
	ssh = None
	async def cleanup():
		ssh.stdin.write(b"quit foo\n")
		try:
			await asyncio.wait_for(ssh.stdin.drain(), timeout=5)
		except asyncio.TimeoutError:
			ssh.terminate()
	try:
		# Begin cancellable section
		ssh = await asyncio.create_subprocess_exec("ssh", "-oBatchMode=yes", (config.webcam_user + "@" + config.host), "python3", config.webcam_control_path, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
		print("[" + str(time.monotonic() - start_time) + "] Opening SSH connection...")
		while True:
			try:
				data = await ssh.stdout.readline()
			except ConnectionResetError:
				print("SSH connection lost")
				break
			if not data:
				print("SSH connection lost")
				ssh = None
				break
			line = data.decode("utf-8")
			device, sep, attr = line.rstrip().partition(": ")
			if sep:
				if device == "Unknown command":
					print(line)
				elif device == "Info":
					if attr == "Hi":
						print("[" + str(time.monotonic() - start_time) + "] Webcams connected.")
						for cam_name, cam_path in config.webcams.items():
							ssh.stdin.write(("cam_check %s \n" %cam_path).encode("utf-8"))
							webcams[cam_path + "focus"] = Webcam(cam_name, cam_path, "Focus", ssh)
							webcams[cam_path + "exposure"] = Webcam(cam_name, cam_path, "Exposure", ssh)
						await ssh.stdin.drain()
					elif attr == "Bye":
						print("camera.py quit")
						break
					else:
						print(line)
				else:
					cmd, sep, value = attr.partition(": ")
					if not sep:
						continue
					if cmd == "set_range":
						mode, sep, params = value.partition(": ")
						channel = webcams[device + mode]
						min, max, step = map(int, params.split())
						channel.min = min
						channel.max = max
						channel.slider.set_lower(channel.min)
						channel.slider.set_upper(channel.max)
						channel.slider.set_page_increment(step)
					elif cmd == "focus_absolute":
						webcams[device + "focus"].refract_value(int(value), "backend")
					elif cmd == "focus_auto":
						webcams[device + "focus"].mute.set_active(int(value))
					elif cmd == "exposure_absolute":
						webcams[device + "exposure"].refract_value(int(value), "backend")
					elif cmd == "exposure_auto":
						if value == "1":
							muted = False # 1 is Manual
						else:
							muted = True # 0, 2 and 3 are all Auto modes
						webcams[device + "exposure"].mute.set_active(muted)
					elif cmd == "Error" and value == "Device not found":
						print("Device not found:", device)
						webcams[device + "focus"].remove()
						webcams[device + "exposure"].remove()
					elif cmd == "Error":
						print("Received error on %s: " %device, value)
	finally:
		for cam in list(webcams):
			webcams[cam].remove()
		#print("Done removing webcams")
		if ssh:
			await cleanup()
			#print("SSH cleanup done")

