//In theory, this could use declarativeContent to look for a video tag
//How does that signal that a page no longer meets the criterion?
//NOTE: This broadly assumes only one important video object, which is
//always present. It might work with multiple but isn't guaranteed.
let extID = "oejgabkmelnodicghenecnopnnninpmm";
// Content scripts runnning in the MAIN world basically become page scripts, and
// therefore lose their extension ID. Because it is extremely difficult for a
// page script to communicate with an extension without knowing the ID for that
// extension, it is easier to simply embed that ID here for all communications.
// This ID is current for me, on my systems, with an unpacked extension. For
// distribution, a new and stable extension ID will be generated.
let player;
let port;

function init() {
	// Watch for the creation of a video element in case it doesn't exist yet when volsock starts
	new MutationObserver(mutationList =>
		[...mutationList].forEach(mutation =>
			mutation.addedNodes.forEach(node =>
				node.querySelectorAll && node.querySelectorAll("video").forEach(setup)))).observe(document, {subtree:1,childList:1});
	// Look for a video element now in case it already exists when the Mutation Observer starts
	document.querySelectorAll("video").forEach(setup);
}

function setup(vid) {
	port = chrome.runtime.connect(extID);
	port.postMessage({cmd: "newtab"});
	port.onMessage.addListener(extListen);
	if (location.host === "www.youtube.com" || location.host === "music.youtube.com") {
		if (location.host === "www.youtube.com") {
			player = document.getElementById('movie_player');
		}
		if (location.host === "music.youtube.com") {
			player = document.querySelector('ytmusic-player-bar').playerApi;
			// TODO: Rework for YT Music:
			// player = document.querySelector('ytmusic-player-bar')
			// setVolume = player.updateVolume(value)
			// mute = player.playerApi.mute()
			// unmute = player.playerApi.unMute()
		}
		(vid.onvolumechange = e => port.postMessage({cmd: "volumechanged", volume: player.getVolume() / 100, muted: player.isMuted()}))();
	}
	else (vid.onvolumechange = e => port.postMessage({cmd: "volumechanged", volume: vid.volume, muted: vid.muted}))();
}

function extListen(message)
{
	switch (message.cmd) {
		case "volume":
			if (location.host === "www.youtube.com" || location.host === "music.youtube.com") {
				player.setVolume(message.value * 100);
				sessionStorage.setItem("yt-player-volume", JSON.stringify({
					creation: +new Date, expiration: +new Date + 2592000000, data: JSON.stringify({volume: player.getVolume(), muted: player.isMuted()})
				}));
			}
			else document.querySelectorAll("video").forEach(vid => vid.volume = message.value);
			break;
		case "mute":
			if (location.host === "www.youtube.com" || location.host === "music.youtube.com") {
				if (message.value) {
					player.mute();
				}
				else player.unMute();
			}
			else document.querySelectorAll("video").forEach(vid => vid.muted = message.value);
			break;
		case "queryvolume":
			if (location.host === "www.youtube.com" || location.host === "music.youtube.com") {
				port.postMessage({cmd: "volumeresponse", volume: player.getVolume() / 100, muted: player.isMuted()});
			}
			else document.querySelectorAll("video").forEach(vid =>
				port.postMessage({cmd: "volumeresponse", volume: vid.volume, muted: vid.muted})
			);
			break;
	}
}

if (document.readyState !== "loading") init();
else window.addEventListener("DOMContentLoaded", init());
