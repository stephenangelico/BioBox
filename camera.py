# Called by BioBox.WebCamFocus over SSH to send camera commands
import sys
import subprocess

while True:
	try:
		cmd, *args = input().strip().split()
		if cmd == "quit":
			print("Bye!")
			break
		elif cmd == "cam_check":
			cam_check = subprocess.run(["v4l2-ctl", "-d", args[0], "-C", "focus_auto,focus_absolute"], text=True, check=True, capture_output=True)
			for line in cam_check.stdout.split("\n"):
				if line:
					print(args[0] + ": " + line)
		elif cmd == "focus_auto":
			subprocess.run(["v4l2-ctl", "-d", args[1], "-c", "focus_auto=%d" %int(args[0])], check=True) # TODO: Add error boundary
		elif cmd == "focus_absolute":
			subprocess.run(["v4l2-ctl", "-d", args[1], "-c", "focus_absolute=%d" %int(args[0])], check=True)
		else:
			print("Unknown command", cmd)
	except EOFError:
		break