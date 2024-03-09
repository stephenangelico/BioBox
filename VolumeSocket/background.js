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
		socket.send(JSON.stringify({cmd: "init", type: "volume", group: ""}));
		//TODO: Should we run newtab here for everything already in tabs?
		// More importantly, under what circumstances should we not?
	};
	socket.onclose = () => {
		console.log("VolSock connection lost.");
		setTimeout(connect, retry_delay || 250);
		if (retry_delay < 30000) retry_delay += 5000;
	};
	socket.onmessage = (ev) => {
		let data = JSON.parse(ev.data);
		if (data.cmd === "setvolume") {
			tabs[data.tabid].postMessage({cmd: "volume", value: data.volume});
		}
		if (data.cmd === "setmuted") {
			tabs[data.tabid].postMessage({cmd: "mute", value: data.muted});
		}
	};
}
//TODO: New protocol for content script to service worker (newtab done). Port sends message,
// tabListen does not pass tab but port, functions can get the tab ID from port.sender.tab.id
function tabListen(message, port)
{
	if (message.cmd === "newtab") {
		newtab(port, message.host);
	}
	if (message.cmd === "closetab") {
		closedtab(port.sender.tab.id);
		// TODO: There may be multiple reasons to close the channel or *not* close
		// it - check on page unload, navigate, and tab inactive (memory saving mode)
	}
	if (message.cmd === "volumechanged") {
		volumechanged(port.sender.tab.id, message.volume, message.muted);
		// TODO: Consider splitting into separate volume and mute
	}
}

function newtab(port, host)
{
	let tabid = port.sender.tab.id
	tabs[tabid] = port;
	socket.send(JSON.stringify({cmd: "newtab", "host": host, "tabid": tabid}));
}

function closedtab(tabid)
{
	// Need to know from Chrome WHICH tab closed
	tabs[tabid].remove();
	socket.send(JSON.stringify({cmd: "closedtab", "tabid": tabid}));
}

function volumechanged(tabid, volume, muted)
{
	socket.send(JSON.stringify({cmd: "setvolume", "tabid": tabid, "volume": volume, "muted": muted}));
}

console.log("Extension ID:", chrome.runtime.id);

chrome.runtime.onConnectExternal.addListener(port => {port.onMessage.addListener(tabListen)});

connect();
