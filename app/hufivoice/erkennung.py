"""Sprache zu Text.

Vorschau (live, immer lokal): Vosk, kleines deutsches Modell.
Endergebnis, je nach "modus":
  lokal   whisper.cpp auf diesem Rechner (ohne AVX gebaut). Nichts geht raus.
  server  eigener Whisper-Server, POST multipart an /transcribe.
  api     Whisper-API mit eigenem Schlüssel (OpenAI-kompatibel).
Fällt server oder api aus, wird (wenn erlaubt) lokal weitergemacht. Von lokal
geht es nie heimlich ins Internet."""
import json
import os
import re
import subprocess
import tempfile
import urllib.error
import urllib.request
import uuid

from . import aufnahme, einstellungen

# Typische Whisper-Erfindungen bei Stille oder Rauschen.
ERFINDUNGEN = (
    "untertitel im auftrag des zdf", "untertitel der amara.org-community",
    "untertitelung des zdf", "vielen dank fürs zuschauen", "danke fürs zuschauen",
    "swr 2020", "copyright", "www.", "amara.org",
)


def ist_erfindung(text):
    t = text.lower().strip(" .!?")
    if not t:
        return True
    return any(e in t for e in ERFINDUNGEN) and len(t) < 80


def aufraeumen(text):
    text = re.sub(r"\[[^\]]*\]|\([^)]*musik[^)]*\)", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    return "" if ist_erfindung(text) else text


class Vorschau:
    """Live-Text mit Vosk. Ohne Vosk oder Modell: macht einfach nichts."""

    def __init__(self, modell_pfad):
        self.ok = False
        self._fertig = ""
        try:
            from vosk import KaldiRecognizer, Model, SetLogLevel
            SetLogLevel(-1)
            pfad = einstellungen.pfad(modell_pfad)
            if os.path.isdir(pfad):
                self._modell = Model(pfad)
                self._KR = KaldiRecognizer
                self.ok = True
        except (ImportError, OSError, Exception):  # noqa: BLE001  Vorschau ist nur Zugabe
            self.ok = False
        self._erk = None

    def neu(self):
        self._fertig = ""
        if self.ok:
            self._erk = self._KR(self._modell, aufnahme.RATE)

    def block(self, pcm):
        """Neuen Ton hineingeben, aktuellen Vorschautext zurückbekommen."""
        if not self._erk:
            return ""
        if self._erk.AcceptWaveform(pcm):
            satz = json.loads(self._erk.Result()).get("text", "")
            if satz:
                self._fertig = (self._fertig + " " + satz).strip()
            teil = ""
        else:
            teil = json.loads(self._erk.PartialResult()).get("partial", "")
        return (self._fertig + " " + teil).strip()

    def ende(self):
        if not self._erk:
            return ""
        rest = json.loads(self._erk.FinalResult()).get("text", "")
        self._erk = None
        return (self._fertig + " " + rest).strip()


def _multipart(felder, datei_feld, datei_name, datei_daten):
    grenze = "----hufivoice" + uuid.uuid4().hex
    teile = []
    for name, wert in felder.items():
        werte = wert if isinstance(wert, (list, tuple)) else (wert,)
        for einzelwert in werte:
            teile.append(f'--{grenze}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'
                          f'{einzelwert}\r\n'.encode())
    teile.append((f'--{grenze}\r\nContent-Disposition: form-data; name="{datei_feld}"; '
                  f'filename="{datei_name}"\r\nContent-Type: audio/wav\r\n\r\n').encode())
    teile.append(datei_daten)
    teile.append(f"\r\n--{grenze}--\r\n".encode())
    return b"".join(teile), f"multipart/form-data; boundary={grenze}"


def _antwort_text(roh):
    daten = json.loads(roh)
    return (daten.get("text") or daten.get("transcript") or "").strip()


def lokal(cfg, wav):
    l = cfg["lokal"]
    programm = einstellungen.pfad(l["whisper_programm"])
    modell = einstellungen.pfad(l["whisper_modell"])
    if not (os.path.isfile(programm) and os.path.isfile(modell)):
        raise RuntimeError("Lokales Whisper fehlt. Bitte build-whisper.sh ausführen.")
    befehl = [programm, "-m", modell, "-l", cfg.get("sprache", "de"),
              "-t", str(l.get("threads", 2)), "-nt", "-np", "-f", wav]
    ctx = l.get("audio_ctx", "auto")
    if ctx == "auto":
        # Kurze Aufnahmen: nur so viel rechnen wie nötig (etwa doppelt so schnell).
        sek = max(0.0, (os.path.getsize(wav) - 44) / (aufnahme.RATE * 2))
        ctx = min(1500, ((int(sek / 30 * 1500) + 192) // 64 + 1) * 64)
    if ctx:
        befehl += ["-ac", str(int(ctx))]
    if cfg.get("woerter"):
        befehl += ["--prompt", cfg["woerter"]]
    erg = subprocess.run(befehl, capture_output=True, text=True, timeout=300)
    if erg.returncode != 0:
        raise RuntimeError("whisper.cpp Fehler: " + erg.stderr.strip()[-200:])
    return erg.stdout.strip()


def server(cfg, wav):
    s = cfg["server"]
    with open(wav, "rb") as fh:
        koerper, art = _multipart({"language": cfg.get("sprache", "de")},
                                  s.get("feldname", "audio"), "aufnahme.wav", fh.read())
    anfrage = urllib.request.Request(s["url"], data=koerper, headers={"Content-Type": art})
    with urllib.request.urlopen(anfrage, timeout=s.get("wartezeit_s", 60)) as antwort:
        return _antwort_text(antwort.read())


def api(cfg, wav):
    a = cfg["api"]
    schluessel = einstellungen.lade_schluessel(a)
    if not schluessel:
        raise RuntimeError("Kein API-Schlüssel. Setze HUFIVOICE_API_KEY oder lege "
                           "~/.hufi/geheim/hufivoice_api_key an.")
    modell = a.get("modell", "gpt-transcribe")
    felder = {"model": modell}
    if modell == "gpt-transcribe":
        if cfg.get("sprache"):
            felder["languages[]"] = [cfg["sprache"]]
        woerter = [wort.strip() for wort in cfg.get("woerter", "").split(",")
                   if wort.strip() and not any(zeichen in wort for zeichen in "<>\r\n")]
        if woerter:
            felder["keywords[]"] = woerter[:50]
    else:
        felder["language"] = cfg.get("sprache", "de")
        felder["response_format"] = "json"
        if cfg.get("woerter"):
            felder["prompt"] = cfg["woerter"]
    with open(wav, "rb") as fh:
        koerper, art = _multipart(felder, "file", "aufnahme.wav", fh.read())
    anfrage = urllib.request.Request(a["url"], data=koerper, headers={
        "Content-Type": art, "Authorization": "Bearer " + schluessel})
    try:
        with urllib.request.urlopen(anfrage, timeout=a.get("wartezeit_s", 60)) as antwort:
            return _antwort_text(antwort.read())
    except urllib.error.HTTPError as fehler:
        # Nur den Status melden, nie Kopfzeilen (dort steckt der Schlüssel).
        raise RuntimeError(f"API antwortet mit Fehler {fehler.code}") from None


def transkribieren(cfg, pcm, vorschau_text=""):
    """Gibt (text, quelle) zurück. quelle: lokal, server, api oder vosk."""
    modus = cfg["modus"]
    datei = os.path.join(tempfile.gettempdir(), f"hufivoice-{uuid.uuid4().hex}.wav")
    aufnahme.als_wav(pcm, datei)
    try:
        if modus in ("server", "api"):
            try:
                text = (server if modus == "server" else api)(cfg, datei)
                return aufraeumen(text), modus
            except (OSError, ValueError, RuntimeError, urllib.error.URLError) as fehler:
                print(f"{modus} nicht erreichbar: {fehler}", flush=True)
                if not cfg[modus].get("bei_fehler_lokal", True):
                    raise
        if cfg["lokal"].get("endtext") == "vosk" and vorschau_text:
            return vorschau_text, "vosk"   # am schnellsten, aber ungenauer
        try:
            return aufraeumen(lokal(cfg, datei)), "lokal"
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as fehler:
            if vorschau_text:
                print("Nehme Vosk-Text, weil:", fehler, flush=True)
                return vorschau_text, "vosk"
            raise
    finally:
        try:
            os.unlink(datei)  # Aufnahme sofort löschen
        except OSError:
            pass
