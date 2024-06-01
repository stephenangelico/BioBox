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
	// TODO: Figure out why volsock causes YT to blank the player
	}
	if (location.host === "music.youtube.com") {
		ytmplayer = document.querySelector('ytmusic-player-bar');
		player = {
			getVolume: () => ytmplayer.playerApi.getVolume(),
			setVolume: (value) => ytmplayer.updateVolume(value),
			getMuted: () => ytmplayer.playerApi.isMuted(),
			setMuted: (bool) => {
				muteButton = document.querySelector('[title="Mute"]');
				// qSA yields two elements but the first always seems to be in the bar
				if (!!bool != player.getMuted()) {muteButton.click()};
				// I would like to use playerApi.mute/unMute but these are not reflected in the UI
			},
		}
	}
	if (location.host === "www.twitch.tv") {
		let twitchplayer;
		// Begin magic blob, thanks Rosuav and Nightdev
		for (let a = Object.entries(document.querySelector('div[data-a-target="player-overlay-click-handler"],.video-player')
				).find(([k, v]) => k.startsWith("__reactFiber"))[1]; !twitchplayer; a = a.return)
			twitchplayer = a.memoizedProps.mediaPlayerInstance?.core;
		// End magic blob
		player = {
			getVolume: () => twitchplayer.getVolume() * 100,
			setVolume: (value) => twitchplayer.setVolume(value / 100),
			getMuted: () => twitchplayer.isMuted(),
			setMuted: (bool) => twitchplayer.setMuted(bool),
		};
	}
	// TODO: Add Spotify? Disney+?
	// if (location.host === "")
	else player = {
			getVolume: () => vid.volume * 100,
			setVolume: (value) => vid.volume = value / 100,
			getMuted: () => vid.muted,
			setMuted: (bool) => vid.muted = bool,
		};
	(vid.onvolumechange = e => port.postMessage({cmd: "volumechanged", volume: player.getVolume(), muted: player.getMuted()}))();
	// It's easier to get one trigger for both volume changes and mute changes
	// and send that all the way through than to split them at any point
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
