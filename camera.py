# Called by BioBox.WebCamFocus over SSH to send camera commands
import subprocess
while True:
	try:
		cmd, *args = input().strip().split()
		if cmd == "quit":
			print("Bye!")
			break
		elif cmd == "cam_check":
			subprocess.run(["v4l2-ctl", "-d", "/dev/webcam_c922", "-C", "focus_auto,focus_absolute"])
		elif cmd == "focus_auto":
			subprocess.run(["v4l2-ctl", "-d", "/dev/webcam_c922", "-c", "focus_auto=%d" %int(args[0])]) # TODO: Add error boundary
		elif cmd == "focus_absolute":
			subprocess.run(["v4l2-ctl", "-d", "/dev/webcam_c922", "-c", "focus_absolute=%d" %int(args[0])])
		else:
			print("Unknown command", cmd)
	except EOFError:
		break