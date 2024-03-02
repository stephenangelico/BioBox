// Service Worker for VolSock
// TODO: Migrate communication with BioBox here from volsock.js
// volsock.js will handle interaction with the page ie reading and writing to
// the slider in whatever way is appropriate for the site, while the service
// worker will handle the connection to BioBox. This will satisfy the Content
// Security Policy of YouTube, notably YT Music and Studio (YT main seems fine).
let tabs = {};
let retry_delay = 5000;
let socket = null;
function connect()
{
	socket = new WebSocket("wss://F-35LightningII.rosuav.com:8888/ws");
	socket.onopen = async () => {
		retry_delay = 0;
		console.log("VolSock connection established.");
	};
	socket.onclose = () => {
		console.log("VolSock connection lost.");
		setTimeout(connect, retry_delay || 250);
		if (retry_delay < 30000) retry_delay += 5000;
	};
	socket.onmessage = (ev) => {
		let data = JSON.parse(ev.data);
		if (data.cmd === "setvolume") {
			chrome.tabs.sendMessage(data.tabid, {cmd: "volume", value: data.volume});
		}
		if (data.cmd === "setmuted") {
			chrome.tabs.sendMessage(data.tabid, {cmd: "mute", value: data.muted});
		}
	};
}

function tabListen(message, sender, response)
{
	if (message.cmd === "newtab") {
		newtab(sender.tab);
	}
	if (message.cmd === "closetab") {
		closedtab(sender.tab);
		// TODO: There may be multiple reasons to close the channel or *not* close
		// it - check on page unload, navigate, and tab inactive (memory saving mode)
	}
	if (message.cmd === "volumechanged") {
		volumechanged(sender.tab, message.volume, message.muted);
		// TODO: Consider splitting into separate volume and mute
	}
	response({});
}

function newtab(tab)
{
	tabs[tab.id] = tab;
	let host = new URL(tab.url).hostname; // Technically "host" includes port but meh
	socket.send(JSON.stringify({cmd: "newtab", "host": host, "tabid": tab.id}));
}

function closedtab(tab)
{
	// Need to know from Chrome WHICH tab closed
	tabs[tab.id].remove();
	socket.send(JSON.stringify({cmd: "closedtab", "tabid": tab.id}));
}

function volumechanged(tab, volume, muted)
{
	socket.send(JSON.stringify({cmd: "setvolume", "tabid": tab.id, "volume": volume, "muted": muted}));
}

console.log("Extension ID:", chrome.runtime.id);

chrome.runtime.onMessage.addListener(tabListen);

connect();
