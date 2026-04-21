// Tracks the last focused input/textarea/contenteditable element
let targetElement = null;
let highlightStyle = null;

function isInputable(el) {
  if (!el) return false;
  const tag = el.tagName.toLowerCase();
  return (
    tag === "input" ||
    tag === "textarea" ||
    el.isContentEditable ||
    el.getAttribute("role") === "textbox"
  );
}

function highlightElement(el) {
  if (!el) return;
  el.style.outline = "2px solid #6C3FC8";
  el.style.outlineOffset = "2px";
}

function removeHighlight(el) {
  if (!el) return;
  el.style.outline = "";
  el.style.outlineOffset = "";
}

document.addEventListener(
  "focus",
  (e) => {
    if (isInputable(e.target)) {
      removeHighlight(targetElement);
      targetElement = e.target;
      highlightElement(targetElement);
      chrome.runtime.sendMessage({ type: "FIELD_FOCUSED", tag: e.target.tagName });
    }
  },
  true
);

document.addEventListener(
  "click",
  (e) => {
    if (isInputable(e.target)) {
      removeHighlight(targetElement);
      targetElement = e.target;
      highlightElement(targetElement);
    }
  },
  true
);

// Insert transcribed text into the selected field
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "INSERT_TEXT") {
    const el = targetElement;
    if (!el) {
      sendResponse({ ok: false, error: "Kein Feld ausgewählt" });
      return;
    }

    if (el.isContentEditable) {
      const sel = window.getSelection();
      if (sel && sel.rangeCount > 0) {
        sel.deleteFromDocument();
        sel.getRangeAt(0).insertNode(document.createTextNode(msg.text));
      } else {
        el.textContent += msg.text;
      }
      el.dispatchEvent(new Event("input", { bubbles: true }));
    } else {
      const start = el.selectionStart ?? el.value.length;
      const end = el.selectionEnd ?? el.value.length;
      const before = el.value.slice(0, start);
      const after = el.value.slice(end);
      el.value = before + msg.text + after;
      el.selectionStart = el.selectionEnd = start + msg.text.length;
      el.dispatchEvent(new Event("input", { bubbles: true }));
      el.dispatchEvent(new Event("change", { bubbles: true }));
    }

    sendResponse({ ok: true });
  }

  if (msg.type === "GET_TARGET_INFO") {
    sendResponse({
      hasTarget: !!targetElement,
      tag: targetElement?.tagName ?? null,
    });
  }
});
