(() => {
  "use strict";

  const INJECT_SOURCE = "slither-bot-inject";
  const CONTENT_SOURCE = "slither-bot-content";
  const SCRIPT_ID = "slither-bot-injected-script";

  let backgroundPort = null;
  let connected = false;

  function log(...args) {
    console.log("[slither-bot/content]", ...args);
  }

  function warn(...args) {
    console.warn("[slither-bot/content]", ...args);
  }

  function injectPageScript() {
    if (document.getElementById(SCRIPT_ID)) {
      return;
    }

    const script = document.createElement("script");
    script.id = SCRIPT_ID;
    script.src = chrome.runtime.getURL("inject.js");
    script.onload = () => {
      script.remove();
      log("inject.js loaded into page context");
    };
    script.onerror = (event) => {
      warn("failed to load inject.js", event);
    };

    const target = document.documentElement || document.head || document.body;
    if (!target) {
      setTimeout(injectPageScript, 50);
      return;
    }

    target.appendChild(script);
  }

  function connectBackground() {
    if (connected && backgroundPort) {
      return;
    }

    backgroundPort = chrome.runtime.connect({ name: "slither-content" });
    connected = true;

    backgroundPort.onMessage.addListener((message) => {
      if (!message || typeof message !== "object") {
        return;
      }

      if (message.type === "COMMAND") {
        window.postMessage(
          {
            source: CONTENT_SOURCE,
            type: "COMMAND",
            command: message.command
          },
          "*"
        );
      }

      if (message.type === "BACKGROUND_STATUS") {
        window.postMessage(
          {
            source: CONTENT_SOURCE,
            type: "BACKGROUND_STATUS",
            status: message.status
          },
          "*"
        );
      }
    });

    backgroundPort.onDisconnect.addListener(() => {
      const err = chrome.runtime.lastError;
      if (err) {
        warn("background port disconnected:", err.message);
      } else {
        warn("background port disconnected");
      }

      connected = false;
      backgroundPort = null;
      setTimeout(connectBackground, 1000);
    });

    log("connected to extension service worker");
  }

  function sendToBackground(message) {
    if (!connected || !backgroundPort) {
      return;
    }

    try {
      backgroundPort.postMessage(message);
    } catch (error) {
      warn("failed to post message to background", error);
    }
  }

  window.addEventListener("message", (event) => {
    if (event.source !== window) {
      return;
    }

    const message = event.data;
    if (!message || typeof message !== "object") {
      return;
    }

    if (message.source !== INJECT_SOURCE) {
      return;
    }

    if (message.type === "STATE") {
      sendToBackground({
        type: "STATE",
        state: message.state
      });
      return;
    }

    if (message.type === "ACK") {
      sendToBackground({
        type: "ACK",
        ack: message.ack
      });
      return;
    }

    if (message.type === "INJECT_STATUS") {
      sendToBackground({
        type: "INJECT_STATUS",
        status: message.status
      });
    }
  });

  injectPageScript();
  connectBackground();
})();
