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
	if (location.host === "www.youtube.com") {
		ytplayer = document.getElementById('movie_player');
		player = {
			getVolume: () => ytplayer.getVolume(),
			setVolume: (value) => ytplayer.setVolume(value),
			getMuted: () => ytplayer.isMuted(),
			setMuted: (bool) => {if (bool) {ytplayer.mute()} else ytplayer.unMute()},
		}
	}
	if (location.host === "music.youtube.com") {
		ytmplayer = document.querySelector('ytmusic-player-bar');
		player = {
			getVolume: () => ytmplayer.playerApi.getVolume(),
			setVolume: (value) => ytmplayer.updateVolume(value),
			getMuted: () => ytmplayer.playerApi.isMuted(),
			setMuted: (bool) => {if (bool) {ytmplayer.playerApi.mute()} else ytmplayer.playerApi.unMute()},
			// TODO: setMuted does not affect the UI button
		}
	}
	// if (location.host === "")
	else player = {
			getVolume: () => vid.volume * 100,
			setVolume: (value) => vid.volume = value / 100,
			getMuted: () => vid.muted,
			setMuted: (bool) => vid.muted = bool,
		};
	(vid.onvolumechange = e => port.postMessage({cmd: "volumechanged", volume: player.getVolume(), muted: player.getMuted()}))();
}

function extListen(message)
{
	switch (message.cmd) {
		case "volume":
			player.setVolume(message.value);
			if (location.host === "www.youtube.com" || location.host === "music.youtube.com") {
				sessionStorage.setItem("yt-player-volume", JSON.stringify({
					creation: +new Date, expiration: +new Date + 2592000000, data: JSON.stringify({volume: player.getVolume(), muted: player.getMuted()})
				}));
			}
			break;
		case "mute":
			player.setMuted(message.value);
			break;
		case "queryvolume":
			port.postMessage({cmd: "volumeresponse", volume: player.getVolume(), muted: player.getMuted()});
			break;
	}
}

if (document.readyState !== "loading") init();
else window.addEventListener("DOMContentLoaded", init());
