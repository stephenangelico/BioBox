//In theory, this could use declarativeContent to look for a video tag
//How does that signal that a page no longer meets the criterion?
//NOTE: This broadly assumes only one important video object, which is
//always present. It might work with multiple but isn't guaranteed.
let extID = "oejgabkmelnodicghenecnopnnninpmm"
// Content scripts runnning in the MAIN world basically become page scripts, and
// therefore lose their extension ID. Because it is extremely difficult for a
// page script to communicate with an extension without knowing the ID for that
// extension, it is easier to simply embed that ID here for all communications.
// This ID is current for me, on my systems, with an unpacked extension. For
// distribution, a new and stable extension ID will be generated.

function init(extID)
{
	let port = chrome.runtime.connect(extID);
	port.postMessage({cmd: "newtab", host: location.host})
	port.onMessage.addListener(extListen)
	if (location.host === "www.youtube.com" || location.host === "music.youtube.com") {
		const player = document.getElementById('movie_player');
		document.querySelectorAll("video").forEach(vid =>
		(vid.onvolumechange = e => port.postMessage({cmd: "volumechanged", volume: player.getVolume() / 100, muted: player.isMuted()}))()
		);
	}
	else document.querySelectorAll("video").forEach(vid =>
		(vid.onvolumechange = e => port.postMessage(extID, {cmd: "volumechanged", volume: vid.volume, muted: vid.muted}))()
	);
}
//TODO: check if extListen gets those arguments
function extListen(message, sender, response)
{
	switch (message.cmd) {
		case "volume":
			if (location.host === "www.youtube.com" || location.host === "music.youtube.com") {
				const player = document.getElementById('movie_player');
				player.setVolume(message.value * 100);
				sessionStorage.setItem("yt-player-volume", JSON.stringify({
					creation: +new Date, expiration: +new Date + 2592000000, data: JSON.stringify({volume: player.getVolume(), muted: player.isMuted()})
				}));
			}
			else document.querySelectorAll("video").forEach(vid => vid.volume = message.value);
		case "mute":
			if (location.host === "www.youtube.com" || location.host === "music.youtube.com") {
				const player = document.getElementById('movie_player');
				if (message.value) {
					player.mute();
				}
				else player.unMute();
			}
			else document.querySelectorAll("video").forEach(vid => vid.muted = message.value);
	}
	response({});
}

console.log("Extension ID:", chrome.runtime.id);

if (document.readyState !== "loading") init(extID);
else window.addEventListener("DOMContentLoaded", init(extID));
