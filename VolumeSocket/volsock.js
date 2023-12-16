//In theory, this could use declarativeContent to look for a video tag
//How does that signal that a page no longer meets the criterion?
//NOTE: This broadly assumes only one important video object, which is
//always present. It might work with multiple but isn't guaranteed.

//Content scripts aren't allowed to see the actual tab ID, so hack in an unlikely-to-be-duplicated one
const tabid = Math.random() + "" + Math.random();
let retry_delay = 5000;
function connect()
{
	let socket = new WebSocket("wss://F-35LightningII.rosuav.com:8888/ws");
	socket.onopen = () => {
		retry_delay = 0;
		console.log("VolSock connection established.");
		socket.send(JSON.stringify({cmd: "init", type: "volume", "host": location.hostname, group: tabid}));
		if (location.host === "www.youtube.com") {
			const player = document.getElementById('movie_player');
			document.querySelectorAll("video").forEach(vid =>
			(vid.onvolumechange = e => socket.send(JSON.stringify({cmd: "setvolume", volume: player.getVolume() / 100, muted: player.isMuted()})))()
			);
		}
		else document.querySelectorAll("video").forEach(vid =>
			(vid.onvolumechange = e => socket.send(JSON.stringify({cmd: "setvolume", volume: vid.volume, muted: vid.muted})))()
		);
	};
	socket.onclose = () => {
		console.log("VolSock connection lost.");
		setTimeout(connect, retry_delay || 250);
		if (retry_delay < 30000) retry_delay += 5000;
	};
	socket.onmessage = (ev) => {
		let data = JSON.parse(ev.data);
		if (data.cmd === "setvolume") {
			if (location.host === "www.youtube.com") {
				const player = document.getElementById('movie_player');
				player.setVolume(data.volume * 100)
				sessionStorage.setItem("yt-player-volume", JSON.stringify({
					creation: +new Date, expiration: +new Date + 2592000000, data: JSON.stringify({volume: player.getVolume(), muted: player.isMuted()})
				}));
			}
			else document.querySelectorAll("video").forEach(vid => vid.volume = data.volume);
		}
		if (data.cmd === "setmuted") {
			if (location.host === "www.youtube.com") {
				const player = document.getElementById('movie_player');
				if (data.muted) {
					player.mute()
				}
				else player.unMute()
			}
			else document.querySelectorAll("video").forEach(vid => vid.muted = data.muted);
		}
	};
}
if (document.readyState !== "loading") connect();
else window.addEventListener("DOMContentLoaded", connect);
