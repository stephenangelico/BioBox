# Periodically change the goal, and watch the slider move smoothly
import asyncio
import random
import time
try:
	from Analog import chan0
	import Motor
	def hack(): pass
except RuntimeError:
	class chan0:
		value = 0 # start it at the top of its travel
	class Motor:
		dir = spd = 0
		def forward(self): self.dir = -1
		def backward(self): self.dir = 1
		def stop(self): self.dir = 0
		def speed(self, spd): self.spd = spd
		def sleep(self, state): pass
		def cleanup(self): pass
	Motor = Motor()
	def hack():
		chan0.value += Motor.spd * Motor.dir * 32
goal = None
goal_time = 0
ACCEL_LIMIT = 10

def randomly_change_goal():
	global goal, goal_time
	new_goal = random.randrange(1024 * 64 * 1) # On average, change the goal every 1 second
	if new_goal < 1024:
		print("SETTING A NEW GOAL:", new_goal)
		goal_time = 0
		goal = new_goal

def remap_range(raw): # could be imported from Analog if on the Pi
	return max(0, min(1023 - raw, 1023))

# Raw version of Analog.read_position - could be parameterized into the regular function,
# or this could replace read_position and the work of "has it actually changed?" could go
# into read_value() for the main loop.
async def read_position():
	while True:
		await asyncio.sleep(1/64)
		hack() # Feign a Pi if needed
		pot = chan0.value // 64
		yield remap_range(pot)

async def move_slider():
	global goal, goal_time
	last_speed = 0 # Assume we start out not moving
	last_pos = 0
	async for pos in read_position():
		goal_time += 1
		randomly_change_goal() # Simulate external signals that change the goal
		if goal is None: continue
		# Note that all values here are *signed*, but the limits are on their magnitudes.
		dist = abs(pos - goal)
		if dist < 1:
			speed = 0
		elif dist < 4:
			speed = 10
		elif dist < 16:
			speed = 20
		elif dist < 64:
			speed = 40
		elif dist < 256:
			speed = 60
		elif dist < 512:
			speed = 80
		else:
			speed = 100
		if goal < pos: speed = -speed

		accel = speed - last_speed # Desired acceleration
		accel = max(-ACCEL_LIMIT, min(accel, ACCEL_LIMIT)) # Actual acceleration
		last_speed = speed = last_speed + accel # Actual speed
		# Note that trying to limit the rate of change of acceleration (the jerk
		# force) is hard to do statelessly without ever exceeding the desired
		# speed. The only way to do it is to begin reducing the acceleration rate
		# as the desired speed is approached, which would be some fairly messy
		# calculations, and wouldn't really make a lot of difference to a simple
		# motor like this one.

		if speed > 0:
			Motor.forward()
		elif speed < 0:
			Motor.backward()
		else:
			Motor.stop()
			# Note that we might temporarily pause during a direction change;
			# this doesn't count as reaching the goal.
			if dist < 1:
				goal = None
				print("GOAL REACHED in", goal_time)
				continue
		Motor.speed(abs(speed)) # Is it okay to set speed to zero? If not, move this into both the conditions above.
		print(f"[{time.time():12f}] {pos=:4d} {speed=:4d} {accel=:3d} {dist=:4d} dpos={pos-last_pos}")
		last_pos = pos

if __name__ == "__main__":
	loop = asyncio.new_event_loop()
	asyncio.set_event_loop(loop)
	try:
		Motor.sleep(False)
		loop.run_until_complete(move_slider())
	finally:
		Motor.cleanup()
