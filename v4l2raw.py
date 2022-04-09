# Augment v4l2py with some additional structs and constants
# This could be upstreamed into v4l2py, or alternatively, sections of that
# could be incorporated here, but it's simpler to just import and extend.
# All of the real content here is just translations of videodev2.h.
from v4l2py.raw import * # ImportError? pip install v4l2py
from v4l2py.raw import _IOR, _IOW, _IOWR
import ctypes

V4L2_EVENT_SUB_FL_SEND_INITIAL = 0x1
V4L2_EVENT_CTRL_CH_VALUE = 0x1 # If this isn't in event.changes, the value didn't change
V4L2_EVENT_CTRL = 3

class v4l2_event_subscription(ctypes.Structure):
	_fields_ = [
		("type", ctypes.c_uint32),
		("id", ctypes.c_uint32),
		("flags", ctypes.c_uint32),
		("reserved", ctypes.c_uint32 * 5),
	]
class v4l2_event_ctrl(ctypes.Structure):
	class _sizedval(ctypes.Union):
		_fields_ = [
			("value", ctypes.c_uint32),
			("value64", ctypes.c_uint64),
		]
	_fields_ = [
		("changes", ctypes.c_uint32),
		("type", ctypes.c_uint32),
		("value", _sizedval),
		("flags", ctypes.c_uint32),
		("minimum", ctypes.c_uint32),
		("maximum", ctypes.c_uint32),
		("step", ctypes.c_uint32),
		("default_value", ctypes.c_uint32),
	]
	_anonymous_ = ("value",)
class timespec(ctypes.Structure):
	_fields_ = [
		("tv_sec", ctypes.c_long), # probably?
		("tv_nsec", ctypes.c_long)
	]
class v4l2_event(ctypes.Structure):
	class _u(ctypes.Union):
		_fields_ = [
			("ctrl", v4l2_event_ctrl),
			# A bunch of others too
			("data", ctypes.c_char * 64),
		]
	_fields_ = [
		("type", ctypes.c_uint32),
		("_u", _u),
		("pending", ctypes.c_uint32),
		("sequence", ctypes.c_uint32),
		("timestamp", timespec),
		("id", ctypes.c_uint32),
		("reserved", ctypes.c_uint32 * 8),
	]
	_anonymous_ = ("_u",)

VIDIOC_SUBSCRIBE_EVENT = _IOW('V', 90, v4l2_event_subscription)
VIDIOC_DQEVENT = _IOR('V', 89, v4l2_event)
