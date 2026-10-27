(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const recordButton = $("recordButton"), recordLabel = $("recordLabel"), status = $("status");
  const wave = $("wave"), bars = [...wave.children], resultCard = $("resultCard"), result = $("result");
  const endpointInput = $("endpoint"), tokenInput = $("token"), settings = $("settings");
  let stream, context, source, processor, chunks = [], recording = false, starting = false, stopRequested = false, startedAt = 0;

  let saved = {};
  try { saved = JSON.parse(localStorage.getItem("hufivoice.web") || "{}"); } catch { localStorage.removeItem("hufivoice.web"); }
  endpointInput.value = saved.endpoint || "/api/transcribe";
  tokenInput.value = sessionStorage.getItem("hufivoice.token") || "";
  $("privacyLabel").textContent = endpointInput.value.startsWith("http") ? "Dein privater Server" : "Lokal auf diesem Gerät";

  function setState(text, busy = false) { status.textContent = text; recordButton.disabled = busy; }
  function checkedEndpoint() {
    const raw = endpointInput.value.trim() || "/api/transcribe", url = new URL(raw, location.href);
    if (url.origin !== location.origin && url.protocol !== "https:") throw new Error("Online-Endpunkte müssen HTTPS benutzen");
    return raw;
  }
  function setBars(level = 0) {
    const shapes = [.3,.7,1,.85,.5,.9,.4,.7,.3];
    bars.forEach((bar, i) => { bar.style.height = `${12 + Math.max(0, level * shapes[i]) * 64}px`; });
  }

  async function startRecording(event) {
    event?.preventDefault();
    if (recording || starting) return;
    starting = true; stopRequested = false;
    try {
      stream = await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true},video:false});
      if (stopRequested) { stream.getTracks().forEach(t => t.stop()); setState("Zu kurz – Taste etwas länger halten."); return; }
      context = new AudioContext();
      source = context.createMediaStreamSource(stream);
      processor = context.createScriptProcessor(4096, 1, 1);
      chunks = []; recording = true; startedAt = performance.now();
      processor.onaudioprocess = (e) => {
        if (!recording) return;
        const samples = new Float32Array(e.inputBuffer.getChannelData(0));
        chunks.push(samples);
        let sum = 0; for (let i=0;i<samples.length;i+=8) sum += samples[i]*samples[i];
        setBars(Math.min(1, Math.sqrt(sum/(samples.length/8))*5));
      };
      source.connect(processor); processor.connect(context.destination);
      recordButton.classList.add("active"); wave.classList.add("active");
      recordLabel.textContent = "Loslassen zum Senden"; setState("Ich höre zu …");
      if (Number.isInteger(event?.pointerId)) recordButton.setPointerCapture?.(event.pointerId);
    } catch (error) { setState(error.name === "NotAllowedError" ? "Mikrofon wurde nicht erlaubt." : "Mikrofon konnte nicht gestartet werden."); }
    finally { starting = false; }
  }

  async function stopRecording(event) {
    event?.preventDefault();
    if (starting && !recording) { stopRequested = true; return; }
    if (!recording) return;
    recording = false; recordButton.classList.remove("active"); wave.classList.remove("active"); setBars(0);
    recordLabel.textContent = "Zum Sprechen halten";
    processor?.disconnect(); source?.disconnect(); stream?.getTracks().forEach(t => t.stop());
    const rate = context.sampleRate; await context.close();
    if (performance.now() - startedAt < 350) { setState("Zu kurz – Taste etwas länger halten."); return; }
    setState("Wird in Text verwandelt …", true);
    try {
      const wav = encodeWav(chunks, rate, 16000);
      const headers = {"Content-Type":"audio/wav"};
      if (tokenInput.value) headers.Authorization = `Bearer ${tokenInput.value}`;
      const response = await fetch(checkedEndpoint(), {method:"POST",headers,body:wav});
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.fehler || `Serverfehler ${response.status}`);
      result.value = data.text || ""; $("sourceLabel").textContent = data.quelle || "HufiVoice";
      resultCard.hidden = false; setState("Fertig"); result.focus();
    } catch (error) { setState(`Fehler: ${error.message}`); }
    finally { recordButton.disabled = false; }
  }

  function encodeWav(inputChunks, inputRate, outputRate) {
    const input = new Float32Array(inputChunks.reduce((n,c)=>n+c.length,0));
    let offset=0; inputChunks.forEach(c=>{input.set(c,offset);offset+=c.length;});
    const ratio = inputRate/outputRate, length = Math.floor(input.length/ratio), output = new Float32Array(length);
    for(let i=0;i<length;i++){
      const start=Math.floor(i*ratio), end=Math.min(input.length,Math.floor((i+1)*ratio));
      let sum=0; for(let j=start;j<end;j++) sum+=input[j]; output[i]=sum/Math.max(1,end-start);
    }
    const buffer=new ArrayBuffer(44+output.length*2), view=new DataView(buffer);
    const text=(p,s)=>{for(let i=0;i<s.length;i++)view.setUint8(p+i,s.charCodeAt(i));};
    text(0,"RIFF");view.setUint32(4,36+output.length*2,true);text(8,"WAVE");text(12,"fmt ");
    view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,outputRate,true);
    view.setUint32(28,outputRate*2,true);view.setUint16(32,2,true);view.setUint16(34,16,true);text(36,"data");view.setUint32(40,output.length*2,true);
    output.forEach((sample,i)=>view.setInt16(44+i*2,Math.max(-1,Math.min(1,sample))*0x7fff,true));
    return new Blob([buffer],{type:"audio/wav"});
  }

  recordButton.addEventListener("pointerdown", startRecording);
  ["pointerup","pointercancel","lostpointercapture"].forEach(name=>recordButton.addEventListener(name, stopRecording));
  recordButton.addEventListener("keydown", event=>{if(!event.repeat && (event.key===" " || event.key==="Enter")) startRecording(event);});
  recordButton.addEventListener("keyup", event=>{if(event.key===" " || event.key==="Enter") stopRecording(event);});
  recordButton.addEventListener("contextmenu", e=>e.preventDefault());
  $("copyButton").addEventListener("click", async()=>{try{await navigator.clipboard.writeText(result.value);setState("Text kopiert");}catch{result.select();setState("Bitte Strg+C drücken");}});
  $("clearButton").addEventListener("click",()=>{result.value="";resultCard.hidden=true;setState("Bereit");});
  function toggleSettings(show){settings.hidden=!show;$("settingsButton").setAttribute("aria-expanded",String(show));}
  $("settingsButton").addEventListener("click",()=>toggleSettings(settings.hidden)); $("closeSettings").addEventListener("click",()=>toggleSettings(false));
  $("saveSettings").addEventListener("click",()=>{try{const endpoint=checkedEndpoint();localStorage.setItem("hufivoice.web",JSON.stringify({endpoint}));sessionStorage.setItem("hufivoice.token",tokenInput.value);$("privacyLabel").textContent=endpoint.startsWith("http")?"Dein privater Server":"Lokal auf diesem Gerät";toggleSettings(false);setState("Einstellungen gespeichert");}catch(error){setState(error.message);}});
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(()=>{});
})();
