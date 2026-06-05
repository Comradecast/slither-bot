const NATIVE_HOST = "com.slither.bot";

let nativePort = null;
let nativeConnected = false;
let contentPorts = new Map();
let nextContentPortId = 1;
let pendingMessages = [];
const MAX_PENDING_MESSAGES = 200;

function log(...args) {
  console.log("[slither-bot/background]", ...args);
}

function warn(...args) {
  console.warn("[slither-bot/background]", ...args);
}

function makeStatus() {
  return {
    nativeConnected,
    contentPortCount: contentPorts.size,
    pendingMessageCount: pendingMessages.length,
    ts: Date.now()
  };
}

function broadcastToContent(message) {
  for (const [id, port] of contentPorts.entries()) {
    try {
      port.postMessage(message);
    } catch (error) {
      warn(`failed to post to content port ${id}`, error);
      contentPorts.delete(id);
    }
  }
}

function flushPendingMessages() {
  if (!nativeConnected || !nativePort) {
    return;
  }

  while (pendingMessages.length > 0) {
    const message = pendingMessages.shift();

    try {
      nativePort.postMessage(message);
    } catch (error) {
      warn("failed to flush pending native message", error);
      pendingMessages.unshift(message);
      return;
    }
  }
}

function queueNativeMessage(message) {
  if (nativeConnected && nativePort) {
    try {
      nativePort.postMessage(message);
      return;
    } catch (error) {
      warn("failed to post to native host; queuing message", error);
    }
  }

  pendingMessages.push(message);

  if (pendingMessages.length > MAX_PENDING_MESSAGES) {
    pendingMessages.shift();
  }

  connectNative();
}

function connectNative() {
  if (nativeConnected && nativePort) {
    return;
  }

  try {
    nativePort = chrome.runtime.connectNative(NATIVE_HOST);
  } catch (error) {
    nativeConnected = false;
    nativePort = null;
    warn("connectNative failed", error);
    broadcastToContent({
      type: "BACKGROUND_STATUS",
      status: makeStatus()
    });
    return;
  }

  nativeConnected = true;
  log("connected to native host", NATIVE_HOST);

  nativePort.onMessage.addListener((message) => {
    if (!message || typeof message !== "object") {
      return;
    }

    if (message.kind === "command" && message.command) {
      broadcastToContent({
        type: "COMMAND",
        command: message.command
      });
      return;
    }

    if (message.angle !== undefined) {
      broadcastToContent({
        type: "COMMAND",
        command: message
      });
      return;
    }

    if (message.kind === "status") {
      broadcastToContent({
        type: "BACKGROUND_STATUS",
        status: {
          ...makeStatus(),
          native: message.status
        }
      });
    }
  });

  nativePort.onDisconnect.addListener(() => {
    const err = chrome.runtime.lastError;

    if (err) {
      warn("native host disconnected:", err.message);
    } else {
      warn("native host disconnected");
    }

    nativeConnected = false;
    nativePort = null;

    broadcastToContent({
      type: "BACKGROUND_STATUS",
      status: makeStatus()
    });
  });

  flushPendingMessages();

  broadcastToContent({
    type: "BACKGROUND_STATUS",
    status: makeStatus()
  });
}

chrome.runtime.onConnect.addListener((port) => {
  if (port.name !== "slither-content") {
    return;
  }

  const portId = nextContentPortId;
  nextContentPortId += 1;
  contentPorts.set(portId, port);

  log("content port connected", portId);
  connectNative();

  port.postMessage({
    type: "BACKGROUND_STATUS",
    status: makeStatus()
  });

  port.onMessage.addListener((message) => {
    if (!message || typeof message !== "object") {
      return;
    }

    if (message.type === "STATE") {
      queueNativeMessage({
        kind: "state",
        payload: message.state,
        content_port_id: portId,
        extension_ts: Date.now()
      });
      return;
    }

    if (message.type === "ACK") {
      queueNativeMessage({
        kind: "ack",
        payload: message.ack,
        content_port_id: portId,
        extension_ts: Date.now()
      });
      return;
    }

    if (message.type === "INJECT_STATUS") {
      queueNativeMessage({
        kind: "inject_status",
        payload: message.status,
        content_port_id: portId,
        extension_ts: Date.now()
      });
    }
  });

  port.onDisconnect.addListener(() => {
    contentPorts.delete(portId);
    log("content port disconnected", portId);

    broadcastToContent({
      type: "BACKGROUND_STATUS",
      status: makeStatus()
    });
  });
});

chrome.runtime.onInstalled.addListener(() => {
  log("installed");
});
