# Called by BioBox.WebCamFocus over SSH to send camera commands
import sys
import subprocess

device = sys.argv[1]

while True:
	try:
		cmd, *args = input().strip().split()
		if cmd == "quit":
			print("Bye!")
			break
		elif cmd == "cam_check":
			subprocess.run(["v4l2-ctl", "-d", device, "-C", "focus_auto,focus_absolute"], check=True)
		elif cmd == "focus_auto":
			subprocess.run(["v4l2-ctl", "-d", device, "-c", "focus_auto=%d" %int(args[0])], check=True) # TODO: Add error boundary
		elif cmd == "focus_absolute":
			subprocess.run(["v4l2-ctl", "-d", device, "-c", "focus_absolute=%d" %int(args[0])], check=True)
		else:
			print("Unknown command", cmd)
	except EOFError:
		break