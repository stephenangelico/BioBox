//In theory, this could use declarativeContent to look for a video tag
//How does that signal that a page no longer meets the criterion?
//NOTE: This broadly assumes only one important video object, which is
//always present. It might work with multiple but isn't guaranteed.
let extID;
extID = chrome.runtime.id;
try {
	if (extID.length == 32) {
		init(extID);
	}
} catch (e) {
	if (e.name == "TypeError") {
		// Wait for an ID to come from background.js
	}
}

function init(extID)
{
	chrome.runtime.onMessage.addListener(extListen);
	if (location.host === "www.youtube.com") {
		const player = document.getElementById('movie_player');
		document.querySelectorAll("video").forEach(vid =>
		(vid.onvolumechange = e => chrome.runtime.sendMessage(extID, {cmd: "volumechanged", volume: player.getVolume() / 100, muted: player.isMuted()}))()
		);
		// TODO: communicate with yt_hook instead, also fix that scope
	}
	else document.querySelectorAll("video").forEach(vid =>
		(vid.onvolumechange = e => chrome.runtime.sendMessage(extID, {cmd: "volumechanged", volume: vid.volume, muted: vid.muted}))()
	);
}

function extListen(message, sender, response)
{
	switch (message.cmd) {
		case "init":
			if (message.value != extID) {
				extID = message.value;
				init(extID);
				// With this bootstrap method, new tabs are at the mercy of the service worker reloading.
				// This is not ideal, but we *need* the extension ID to communicate with the service worker.
				// TODO: get the extension ID in a way accessible to the content script, either by storing
				// something on install, or by generating and hard-coding a stable ID (also need to test that
				// ID in other browsers).
				// Update 20240217: Last week I added the above because I was not getting the extension ID in
				// content scripts, and assumed that content scripts do not have access to their extension ID
				// (in my defense, stranger restrictions apply in browsers). This morning, all running content
				// scripts got their extension IDs without issue. In case the issue occurs again, I will keep
				// this fallback with all its faults.
				// Update 20240224: It makes sense now - content scripts runnning in the MAIN world are
				// effectively orphaned from the extension, and therefore have no extension ID. To work around
				// this, there will be a new hook script for YT players (and other hooks for other players as
				// becomes known) which will run in the MAIN world, and volsock.js will migrate back to the
				// ISOLATED world. The service worker is probably still necessary for CSP reasons, but if nothing
				// else it may be helpful for making an options page.
			}
		case "volume":
			if (location.host === "www.youtube.com") {
				const player = document.getElementById('movie_player');
				player.setVolume(message.value * 100);
				sessionStorage.setItem("yt-player-volume", JSON.stringify({
					creation: +new Date, expiration: +new Date + 2592000000, data: JSON.stringify({volume: player.getVolume(), muted: player.isMuted()})
				}));
			}
			else document.querySelectorAll("video").forEach(vid => vid.volume = message.value);
		case "mute":
			if (location.host === "www.youtube.com") {
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

if (document.readyState !== "loading") chrome.runtime.onMessage.addListener(extListen);
else window.addEventListener("DOMContentLoaded", chrome.runtime.onMessage.addListener(extListen));
