// Service Worker for VolSock
// TODO: Migrate communication with BioBox here from volsock.js
// volsock.js will handle interaction with the page ie reading and writing to
// the slider in whatever way is appropriate for the site, while the service
// worker will handle the connection to BioBox. This will satisfy the Content
// Security Policy of YouTube, notably YT Music and Studio (YT main seems fine).
let tabs = {}
let retry_delay = 5000;
function connect()
{
	let socket = new WebSocket("wss://F-35LightningII.rosuav.com:8888/ws");
	socket.onopen = async () => {
		retry_delay = 0;
		console.log("VolSock connection established.");
		socket.send(JSON.stringify({cmd: "init", type: "volume", group: ""}));
		var openTabs = await chrome.tabs.query({"url": "*://*.youtube.com"});
		// TODO: get all tabs the extension runs on, not just YT
		openTabs.forEach(newtab);
	};
	socket.onclose = () => {
		console.log("VolSock connection lost.");
		setTimeout(connect, retry_delay || 250);
		if (retry_delay < 30000) retry_delay += 5000;
	};
	socket.onmessage = (ev) => {
		let data = JSON.parse(ev.data);
		if (data.cmd === "setvolume") {
			// Pseudo code
			new event(data.tabid, "volume", data.volume);
		}
		if (data.cmd === "setmuted") {
			// Pseudo code
			new event(data.tabid, "mute", data.muted);
		}
	};
}
// Pseudo code
new listener("onPageLoad", newtab);
new listener("onTabClose", closedtab);
new listener("onVolumeChanged", volumechanged);

function newtab(tab)
{
	tabs[tab.tabid] = tab;
	socket.send(JSON.stringify({cmd: "newtab", "host": tab.location.hostname, "tabid": tabid}));
}

function closedtab(tab)
{
	// Need to know from Chrome WHICH tab closed
	tab[tab.tabid].remove()
	socket.send(JSON.stringify({cmd: "closedtab", "tabid": tabid}));
}

function volumechanged(tab, volume, muted)
{
	socket.send(JSON.stringify({cmd: "setvolume", "tabid": tabid, "volume": volume, "muted": muted}));
}

// TODO: figure out how to run connect()
if (document.readyState !== "loading") connect();
else window.addEventListener("DOMContentLoaded", connect);
