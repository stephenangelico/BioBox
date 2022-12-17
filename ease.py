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
	Motor = Motor()
	def hack():
		chan0.value += Motor.spd * Motor.dir * 4
goal = None
ACCEL_LIMIT = 10

def randomly_change_goal():
	global goal
	new_goal = random.randrange(1024 * 64 * 4) # On average, change the goal every 4 seconds
	if new_goal < 1024:
		print("SETTING A NEW GOAL:", new_goal)
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
	global goal
	last_speed = 0 # Assume we start out not moving
	async for pos in read_position():
		randomly_change_goal() # Simulate external signals that change the goal
		if goal is None: continue
		# Note that all values here are *signed*, but the limits are on their magnitudes.
		dist = abs(pos - goal)
		if dist >= 256:
			speed = 100
		elif dist >= 16:
			speed = 40
		elif dist >= 5:
			speed = 20
		elif dist >= 1:
			speed = 10
		else:
			speed = 0
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
				print("GOAL REACHED")
				continue
		Motor.speed(abs(speed)) # Is it okay to set speed to zero? If not, move this into both the conditions above.
		print(f"[{time.time():12f}] {pos=:4d} {speed=:4d} {accel=:3d}")

if __name__ == "__main__":
	loop = asyncio.new_event_loop()
	asyncio.set_event_loop(loop)
	loop.run_until_complete(move_slider())
