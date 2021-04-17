# Called by BioBox.WebCamFocus over SSH to send camera commands
import shlex, subprocess
while True:
	cmd = input().strip()
	if cmd == "quit":
		print("Bye!")
		break
	args = shlex.split(cmd)
	args.insert(0,"v4l2-ctl")
	subprocess.run(args)
