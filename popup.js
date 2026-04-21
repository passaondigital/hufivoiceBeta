"use strict";

// ── DOM refs ──────────────────────────────────────────────────────────────────
const micBtn        = document.getElementById("micBtn");
const micHint       = document.getElementById("micHint");
const statusDot     = document.getElementById("statusDot");
const statusText    = document.getElementById("statusText");
const transcriptBox = document.getElementById("transcriptBox");
const placeholder   = document.getElementById("placeholder");
const btnClear      = document.getElementById("btnClear");
const btnCopy       = document.getElementById("btnCopy");
const btnInsert     = document.getElementById("btnInsert");
const toastEl       = document.getElementById("toast");
const langSelect    = document.getElementById("langSelect");
const whisperUrlIn  = document.getElementById("whisperUrl");
const autoPunct     = document.getElementById("autoPunct");
const tabWeb        = document.getElementById("tabWeb");
const tabWhisper    = document.getElementById("tabWhisper");

// ── State ─────────────────────────────────────────────────────────────────────
let mode         = "web";   // "web" | "whisper"
let recording    = false;
let transcript   = "";
let hasTarget    = false;

// Web Speech API
let recognition  = null;
let interimText  = "";

// Whisper / MediaRecorder
let mediaRecorder  = null;
let audioChunks    = [];

// ── Persist settings ──────────────────────────────────────────────────────────
chrome.storage.local.get(["lang", "whisperUrl", "autoPunct", "mode"], (res) => {
  if (res.lang)       langSelect.value = res.lang;
  if (res.whisperUrl) whisperUrlIn.value = res.whisperUrl;
  if (res.autoPunct !== undefined) autoPunct.checked = res.autoPunct;
  if (res.mode)       setMode(res.mode);
});

langSelect.addEventListener("change", () => chrome.storage.local.set({ lang: langSelect.value }));
whisperUrlIn.addEventListener("change", () => chrome.storage.local.set({ whisperUrl: whisperUrlIn.value }));
autoPunct.addEventListener("change", () => chrome.storage.local.set({ autoPunct: autoPunct.checked }));

// ── Tab switching ─────────────────────────────────────────────────────────────
function setMode(m) {
  mode = m;
  tabWeb.classList.toggle("active", m === "web");
  tabWhisper.classList.toggle("active", m === "whisper");
  chrome.storage.local.set({ mode: m });
  updateMicHint();
}
tabWeb.addEventListener("click", () => setMode("web"));
tabWhisper.addEventListener("click", () => setMode("whisper"));

// ── Check whether a field is selected on the active tab ───────────────────────
function checkTarget() {
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (!tabs[0]) return;
    chrome.tabs.sendMessage(tabs[0].id, { type: "GET_TARGET_INFO" }, (resp) => {
      if (chrome.runtime.lastError) {
        setStatus(false, "Seite nicht unterstützt (reload nötig)");
        return;
      }
      hasTarget = resp?.hasTarget ?? false;
      setStatus(hasTarget, hasTarget
        ? `Feld bereit: <${resp.tag}>`
        : "Kein Feld ausgewählt – klicke zuerst ins Feld");
      micBtn.disabled = !hasTarget;
      if (hasTarget) micHint.textContent = "Mikrofon drücken und sprechen";
    });
  });
}

// Run check when popup opens
checkTarget();
// Refresh every second while popup is open
setInterval(checkTarget, 1200);

// ── Status bar ────────────────────────────────────────────────────────────────
function setStatus(active, text) {
  statusDot.className = "status-dot" + (recording ? " recording" : active ? "" : " inactive");
  statusText.textContent = text;
}

// ── Transcript helpers ────────────────────────────────────────────────────────
function setTranscript(text, interim = "") {
  transcript = text;
  placeholder.style.display = text || interim ? "none" : "";
  transcriptBox.textContent = "";
  if (text) {
    const span = document.createElement("span");
    span.textContent = text;
    transcriptBox.appendChild(span);
  }
  if (interim) {
    const i = document.createElement("span");
    i.style.color = "#7c6fa0";
    i.style.fontStyle = "italic";
    i.textContent = (text ? " " : "") + interim;
    transcriptBox.appendChild(i);
  }
  const hasText = !!(text || interim);
  btnClear.disabled  = !hasText;
  btnCopy.disabled   = !hasText;
  btnInsert.disabled = !hasText;
}

// ── Toast ─────────────────────────────────────────────────────────────────────
let toastTimer = null;
function showToast(msg) {
  toastEl.textContent = msg;
  toastEl.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove("show"), 2200);
}

// ── Mic hint ──────────────────────────────────────────────────────────────────
function updateMicHint() {
  if (!hasTarget) { micHint.textContent = "Feld auf der Seite auswählen"; return; }
  micHint.textContent = recording
    ? (mode === "web" ? "Spreche … (nochmal drücken = Stop)" : "Aufnahme läuft … (nochmal drücken = Stop)")
    : "Mikrofon drücken und sprechen";
}

// ── Mic button ────────────────────────────────────────────────────────────────
micBtn.addEventListener("click", () => {
  if (!recording) startRecording();
  else            stopRecording();
});

function startRecording() {
  recording = true;
  micBtn.classList.add("recording");
  micBtn.innerHTML = "⏹";
  statusDot.className = "status-dot recording";
  updateMicHint();

  if (mode === "web") startWebSpeech();
  else               startMediaRecorder();
}

function stopRecording() {
  recording = false;
  micBtn.classList.remove("recording");
  micBtn.innerHTML = "🎤";
  updateMicHint();

  if (mode === "web") stopWebSpeech();
  else               stopMediaRecorder();
}

// ── Web Speech API ────────────────────────────────────────────────────────────
function startWebSpeech() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { showToast("Web Speech nicht unterstützt – wechsle zu Whisper"); stopRecording(); return; }

  recognition = new SR();
  recognition.lang = langSelect.value;
  recognition.continuous = true;
  recognition.interimResults = true;

  let finalText = transcript;

  recognition.onresult = (e) => {
    let interim = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      if (r.isFinal) finalText += r[0].transcript;
      else           interim   += r[0].transcript;
    }
    setTranscript(finalText, interim);
  };

  recognition.onerror = (e) => {
    showToast("Fehler: " + e.error);
    stopRecording();
  };

  recognition.onend = () => {
    if (recording) recognition.start(); // keep alive
  };

  recognition.start();
}

function stopWebSpeech() {
  if (recognition) { recognition.stop(); recognition = null; }
  setStatus(true, `Feld bereit`);
}

// ── Whisper via local API ─────────────────────────────────────────────────────
async function startMediaRecorder() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioChunks = [];
    mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
    mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
    mediaRecorder.start();
    statusText.textContent = "Aufnahme läuft…";
  } catch {
    showToast("Mikrofon-Zugriff verweigert");
    stopRecording();
  }
}

function stopMediaRecorder() {
  if (!mediaRecorder) return;
  mediaRecorder.onstop = async () => {
    const blob = new Blob(audioChunks, { type: "audio/webm" });
    mediaRecorder.stream.getTracks().forEach((t) => t.stop());
    await transcribeWhisper(blob);
  };
  mediaRecorder.stop();
}

async function transcribeWhisper(blob) {
  micBtn.disabled = true;
  micBtn.innerHTML = `<span class="spinner"></span>`;
  statusText.textContent = "Transkribiere mit Whisper…";

  try {
    const url = whisperUrlIn.value.trim();
    const formData = new FormData();
    formData.append("audio", blob, "recording.webm");
    formData.append("language", langSelect.value.slice(0, 2));

    const res = await fetch(url, { method: "POST", body: formData });
    if (!res.ok) throw new Error(`Server: ${res.status}`);
    const json = await res.json();
    const text = json.text || json.transcript || "";
    setTranscript(transcript + text);
    showToast("Transkription abgeschlossen");
  } catch (err) {
    showToast("Whisper Fehler: " + err.message);
  } finally {
    micBtn.disabled = false;
    micBtn.innerHTML = "🎤";
    checkTarget();
  }
}

// ── Action buttons ────────────────────────────────────────────────────────────
btnClear.addEventListener("click", () => {
  setTranscript("");
  showToast("Transkript gelöscht");
});

btnCopy.addEventListener("click", () => {
  const text = transcript || transcriptBox.textContent;
  navigator.clipboard.writeText(text).then(() => showToast("Kopiert!"));
});

btnInsert.addEventListener("click", () => {
  const text = transcript || transcriptBox.textContent.trim();
  if (!text) return;

  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    if (!tabs[0]) return;
    chrome.tabs.sendMessage(tabs[0].id, { type: "INSERT_TEXT", text }, (resp) => {
      if (chrome.runtime.lastError || !resp?.ok) {
        showToast(resp?.error || "Einfügen fehlgeschlagen");
      } else {
        showToast("Text eingefügt!");
      }
    });
  });
});
