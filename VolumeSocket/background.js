// Service Worker for VolSock
// TODO: Migrate communication with BioBox here from volsock.js
// volsock.js will handle interaction with the page ie reading and writing to
// the slider in whatever way is appropriate for the site, while the service
// worker will handle the connection to BioBox. This will satisfy the Content
// Security Policy of YouTube, notably YT Music and Studio (YT main seems fine).
let tabs = {};
let retry_delay = 5000;
let socket = null;
let keepalive_timer = 0;
function connect()
{
	socket = new WebSocket("wss://F-35LightningII.rosuav.com:8888/ws");
	socket.onopen = async () => {
		retry_delay = 0;
		console.log("VolSock connection established.");
		// Possible bug exploit in Chrome 110+ to keep SW alive but seemingly accepted as a feature for now
		keepalive_timer = setInterval(chrome.runtime.getPlatformInfo, 20e3);
		let instanceID = Math.random() + "" + Math.random();
		socket.send(JSON.stringify({cmd: "init", type: "volume", group: instanceID}));
		Object.values(tabs).forEach(resendtab);
	};
	socket.onclose = () => {
		console.log("VolSock connection lost.");
		clearInterval(keepalive_timer);
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
function tabListen(message, port)
{
	if (message.cmd === "newtab") {
		newtab(port, message.host);
	}
	if (message.cmd === "closetab") {
		closedtab(port.sender.tab.id);
		// TODO: There may be multiple reasons to close the channel or *not* close
		// it - check on page unload, navigate, and tab inactive (memory saving mode)
		// Should receive a port.onDisconnect event for most of these
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
	//TODO: Stop sending host from content script and use method from resendtab
}

function resendtab(port)
{
	let tabid = port.sender.tab.id
	let origin = new URL(port.sender.origin)
	socket.send(JSON.stringify({cmd: "newtab", "host": origin.hostname, "tabid": tabid}));
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

function heartbeat(port)
{
	setInterval(beat => {port.sendMessage("ping")}, 30000);
}

chrome.runtime.onConnect.addListener(port => {heartbeat(port)});
chrome.runtime.onConnectExternal.addListener(port => {port.onMessage.addListener(tabListen)});

connect();
//TODO: create keepalive/heartbeat to reconnect when service worker is shut down
// Chrome shuts down workers that have been inactive for 30 seconds, but forcibly
// shuts down workers that have been active for 5 minutes. Shutdowns should result
// in an onDisconnect event at the other end of a port. This can be used to reconnect
// as necessary. Other options for persisting the service worker are:
// 1. Use chrome.runtime API every <30 sec - bug exploit
// 2. Use offscreen page for heartbeat/ping-pong
// 3. BioBox to VolSock heartbeat every <30 sec - Chrome feature
// 4. Reconnect ports every <300 sec
// See https://stackoverflow.com/questions/66618136/persistent-service-worker-in-chrome-extension
