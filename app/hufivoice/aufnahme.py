"""Mikrofon lesen (16 kHz, mono, 16 Bit). Wie Hufi Desktop: parecord, die
Logitech C920 wird bevorzugt. Ersatz: arecord. Für Tests: eine WAV-Datei."""
import array
import math
import os
import shutil
import subprocess
import threading
import time
import wave

RATE = 16000
BLOCK = 3200  # 0,1 Sekunden


def finde_mikrofon():
    """Bevorzugt die Webcam C920, sonst das erste echte Mikrofon."""
    try:
        aus = subprocess.run(["pactl", "list", "short", "sources"],
                             capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    zeilen = [z.split() for z in aus.splitlines() if len(z.split()) > 1]
    for z in zeilen:
        if "C920" in z[1] or "Webcam" in z[1]:
            return z[1]
    for z in zeilen:
        if z[1].startswith("alsa_input"):
            return z[1]
    return None


class Aufnahme:
    """Startet eine Aufnahme. Jeder Block geht an bei_block(bytes)."""

    def __init__(self, mikrofon="auto", bei_block=None, testdatei=None):
        self.mikrofon = mikrofon
        self.bei_block = bei_block
        self.testdatei = testdatei or os.environ.get("HUFIVOICE_TESTDATEI")
        self.daten = bytearray()
        self._proz = None
        self._faden = None
        self._stopp = threading.Event()

    def _befehl(self):
        if shutil.which("parecord"):
            geraet = finde_mikrofon() if self.mikrofon == "auto" else self.mikrofon
            befehl = ["parecord", "--channels=1", f"--rate={RATE}",
                      "--format=s16le", "--raw", "--latency-msec=50"]
            if geraet:
                befehl.insert(1, "--device=" + geraet)
            return befehl
        if shutil.which("arecord"):
            return ["arecord", "-q", "-f", "S16_LE", "-r", str(RATE), "-c", "1", "-t", "raw"]
        raise RuntimeError("Kein Aufnahme-Programm gefunden (parecord oder arecord)")

    def start(self):
        self._stopp.clear()
        self.daten = bytearray()
        if self.testdatei:
            self._faden = threading.Thread(target=self._aus_datei, daemon=True)
        else:
            self._proz = subprocess.Popen(self._befehl(), stdout=subprocess.PIPE,
                                          stderr=subprocess.DEVNULL)
            self._faden = threading.Thread(target=self._lesen, daemon=True)
        self._faden.start()

    def _weiter(self, block):
        self.daten.extend(block)
        if self.bei_block:
            self.bei_block(bytes(block))

    def _lesen(self):
        while not self._stopp.is_set():
            block = self._proz.stdout.read(BLOCK)
            if not block:
                break
            self._weiter(block)

    def _aus_datei(self):
        with wave.open(self.testdatei, "rb") as w:
            if w.getframerate() != RATE or w.getnchannels() != 1 or w.getsampwidth() != 2:
                raise RuntimeError("Testdatei muss 16 kHz, mono, 16 Bit sein")
            while not self._stopp.is_set():
                block = w.readframes(BLOCK // 2)
                if not block:
                    break
                self._weiter(block)
                time.sleep(0.1)  # wie echtes Mikrofon: Echtzeit
        # Datei zu Ende: Stille, bis losgelassen wird
        while not self._stopp.is_set():
            time.sleep(0.05)

    def stopp(self):
        """Aufnahme beenden, gibt alle Daten (rohes PCM) zurück."""
        self._stopp.set()
        if self._proz:
            self._proz.terminate()
            try:
                self._proz.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proz.kill()
            self._proz = None
        if self._faden:
            self._faden.join(timeout=2)
        return bytes(self.daten)


def als_wav(pcm, ziel):
    with wave.open(ziel, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm)
    return ziel


def sekunden(pcm):
    return len(pcm) / (RATE * 2)


def pegel(pcm):
    """Lautstärke eines Blocks als Wert von 0 bis 1 (für die orange Anzeige).
    Leise Sprache soll schon sichtbar sein, darum logarithmisch."""
    if len(pcm) < 2:
        return 0.0
    werte = array.array("h", pcm[: len(pcm) // 2 * 2])
    schritt = max(1, len(werte) // 400)          # 400 Stichproben reichen, spart Zeit
    stich = werte[::schritt]
    rms = math.sqrt(sum(v * v for v in stich) / len(stich))
    if rms < 60:
        return 0.0
    return min(1.0, max(0.0, (20 * math.log10(rms / 32768) + 50) / 42))
