# This is an example of what should be in config.py. Save this file as config.py
# and then change the defaults as needed. See README.md for details.

# Host that has the audio devices to control
host = "localhost"

# Port that TellMeVLC is listening on
vlc_port = 4221

# User to SSH as for WebcamFocus modules
webcam_user = "biobox"

# Path to camera.py on host with webcams
webcam_control_path = "/home/biobox/BioBox/camera.py"

# Set of webcams as names to devices
webcams = {"Webcam #1 Focus": "/dev/video0", "Webcam #2 Focus": "/dev/video1"}

# Port to connect to OBS WebSocket server
obs_port = 4444
