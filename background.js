// Service Worker – keeps offscreen document for MediaRecorder
let recording = false;

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "PING") {
    sendResponse({ alive: true });
  }
});
