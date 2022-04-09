import os, fcntl, select, ctypes
import sys; sys.path.append(os.path.dirname(__file__))
import v4l2raw
poll = select.poll()
poll.register(0, select.POLLIN)

ctrls = {
	v4l2raw.V4L2_CID_FOCUS_ABSOLUTE: "focus_absolute",
	v4l2raw.V4L2_CID_FOCUS_AUTO: "focus_auto",
}
cmds = dict(zip(ctrls.values(), ctrls))
devices = { }
fds = { }
buf = v4l2raw.v4l2_event()

# Autoflush stdout
_print = print
def print(*a, **kw): _print(*a, **kw, flush=True)

print("Info: Hi")
calm = True # If you keep calm, we will carry on.
while calm:
	for fd, ev in poll.poll():
		if fd:
			fcntl.ioctl(fd, v4l2raw.VIDIOC_DQEVENT, buf)
			print("%s: %s: %d" % (devices[fd], ctrls[buf.id], buf.ctrl.value64))
			continue
		try: cmd, *args, dev = input().strip().split()
		except EOFError: cmd = "quit"
		if cmd == "quit":
			print("Info: Bye")
			calm = False
		elif cmd == "cam_check":
			fd = os.open(dev, os.O_RDWR | os.O_NONBLOCK)
			for id in ctrls:
				fcntl.ioctl(fd, v4l2raw.VIDIOC_SUBSCRIBE_EVENT, v4l2raw.v4l2_event_subscription(
					type=v4l2raw.V4L2_EVENT_CTRL,
					id=id,
					flags=v4l2raw.V4L2_EVENT_SUB_FL_SEND_INITIAL,
				))
			r = v4l2raw.v4l2_queryctrl(id=v4l2raw.V4L2_CID_FOCUS_ABSOLUTE)
			fcntl.ioctl(fd, v4l2raw.VIDIOC_QUERYCTRL, r)
			print("%s: set_range: %d %d %d" % (dev, r.minimum, r.maximum, r.step))
			devices[fd] = dev # Retain the device ID for the client
			fds[dev] = fd # And the file descriptor for us
			poll.register(fd, select.POLLPRI) # Events come through as urgent flags
		elif cmd in cmds and dev in fds:
			fcntl.ioctl(fds[dev], v4l2raw.VIDIOC_S_EXT_CTRLS, v4l2raw.v4l2_ext_controls(
				count=1,
				controls=ctypes.pointer(v4l2raw.v4l2_ext_control(
					id=cmds[cmd], value=int(args[0])))))
		else:
			print("Unknown command:", cmd)
