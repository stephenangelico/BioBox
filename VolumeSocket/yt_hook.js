// Runs in MAIN world to hook into the YT player element

const player = document.getElementById('movie_player');
document.querySelectorAll("video").forEach(vid =>
	(vid.onvolumechange = e => window.postMessage({
		type: "from_player", cmd: "volumechanged", volume: player.getVolume() / 100, muted: player.isMuted()
	}))
);
