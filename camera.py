import select
from linuxpy.video.device import Device
from linuxpy.video.raw import EventType, EventSubscriptionFlag

poll = select.poll()
poll.register(0, select.POLLIN)

ranges = {
	"focus": "focus_absolute",
	"exposure": "exposure_time_absolute"
}
ctrls = (
	"focus_absolute",
	"focus_automatic_continuous",
	"exposure_time_absolute",
	"auto_exposure",
)
devices = { }
fds = { }

# Autoflush stdout
_print = print
def print(*a, **kw): _print(*a, **kw, flush=True)

print("Info: Hi")
#print("Info: Dump", os.environ['LANGUAGE'])
calm = True # If you keep calm, we will carry on.
while calm:
	for fd, ev in poll.poll():
		if fd:
			dev = devices[fd]
			ev = dev.deque_event()
			print("%s: %s: %d" % (dev.filename, dev.controls[ev.id].config_name, ev.u.ctrl.value))
			# TODO: Do we still get abs,auto,abs,auto events whenever auto exposure is toggled?
			continue
		try: cmd, *args, dev = input().strip().split()
		except EOFError: cmd = "quit"
		if cmd == "quit":
			print("Info: Bye")
			calm = False
		elif cmd == "cam_check":
			try:
				fd = Device(dev); fd.open() # Devices must be opened before querying/configuring
				# fd is now the webcam device, not the FD the command came from (which, being stdin, was 0)
			except FileNotFoundError:
				print("%s: Error: Device not found" % dev)
				continue
			devices[fd.fileno()] = fd # Retain the device ID for the client
			fds[dev] = fd # And the file descriptor for us
			for ctrl in ctrls:
				fd.subscribe_event(EventType.CTRL, fd.controls[ctrl].id, EventSubscriptionFlag.SEND_INITIAL)
				# Subscribe to events of each type of control which we are interested in (see ctrls)
			for kwd, ctrl in ranges.items():
				ctrl = fd.controls[ctrl]
				print("%s: set_range: %s: %d %d %d" % (dev, kwd, ctrl.minimum, ctrl.maximum, ctrl.step))
				# Sends range for whatever slider controls we want
			poll.register(fd, select.POLLPRI) # Events come through as urgent flags
		elif cmd in ctrls and dev in fds:
			fds[dev].controls[cmd].value = int(args[0])
			# Do we know the device and the command already? Just set the thing!
		else:
			print("Unknown command:", cmd)
