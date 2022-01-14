# Called by BioBox.WebCamFocus over SSH to send camera commands
import sys
import subprocess

while True:
	try:
		cmd, *args, dev = input().strip().split()
		if cmd == "quit":
			break
		elif cmd == "cam_check":
			cam_check = subprocess.run(["v4l2-ctl", "-d", dev, "-C", "focus_auto,focus_absolute"], text=True, capture_output=True)
			if cam_check.returncode:
				print(dev + ": Error: " + cam_check.stderr.rstrip())
			else:
				for line in cam_check.stdout.split("\n"):
					if line:
						print(dev + ": " + line)
		elif cmd == "focus_auto" or cmd == "focus_absolute":
			try:
				focus_cmd = subprocess.run(["v4l2-ctl", "-d", dev, "-c", "%s=%d" % (cmd, int(args[0]))], text=True, capture_output=True)
				if focus_cmd.returncode:
					print(dev + ": Error: " + focus_cmd.stderr.rstrip())
			except ValueError:
				print(dev + ": Error: Unknown value '%s' for %s" % (args[0], cmd))
		else:
			print("Unknown:", cmd)
	except EOFError:
		break