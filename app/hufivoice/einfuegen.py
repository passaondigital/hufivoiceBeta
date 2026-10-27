"""Text ins aktive Fenster bringen. Standard: über die Zwischenablage und
Strg+V (im Terminal Strg+Umschalt+V), danach alte Zwischenablage zurück.
Ersatz: xdotool tippt den Text Buchstabe für Buchstabe."""
import subprocess
import threading
import time


def _lauf(befehl, eingabe=None, zeit=10):
    return subprocess.run(befehl, input=eingabe, capture_output=True, timeout=zeit)


def zwischenablage_lesen():
    try:
        erg = _lauf(["xclip", "-selection", "clipboard", "-o"], zeit=3)
        return erg.stdout if erg.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def zwischenablage_setzen(daten):
    # xclip bleibt im Hintergrund, bis jemand anderes die Ablage übernimmt.
    proz = subprocess.Popen(["xclip", "-selection", "clipboard", "-i"],
                            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    proz.communicate(daten, timeout=5)


def fenster_klasse():
    try:
        erg = _lauf(["xdotool", "getactivewindow", "getwindowclassname"], zeit=3)
        return erg.stdout.decode("utf-8", "replace").strip().lower()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def tastenkombi(klasse, terminals):
    return "ctrl+shift+v" if any(t in klasse for t in terminals) else "ctrl+v"


class Vorbereitung:
    """Liest schon WÄHREND der Aufnahme die alte Zwischenablage und das aktive
    Fenster. So bleibt nach dem Loslassen nur noch: Text setzen, Strg+V."""

    def __init__(self, cfg):
        self.alt = None
        self.klasse = None
        e = cfg["einfuegen"]
        self._faden = threading.Thread(target=self._lesen, args=(e,), daemon=True)
        self._faden.start()

    def _lesen(self, e):
        self.klasse = fenster_klasse()
        if e.get("zwischenablage_zurueck", True) and e.get("art") != "tippen":
            self.alt = zwischenablage_lesen()

    def fertig(self, warte_s=0.5):
        self._faden.join(timeout=warte_s)
        return not self._faden.is_alive()


def einfuegen(text, cfg, vorbereitet=None):
    e = cfg["einfuegen"]
    if not text:
        return "leer"
    if e.get("leerzeichen_davor"):
        text = " " + text
    if e.get("art") == "tippen":
        _lauf(["xdotool", "type", "--clearmodifiers", "--delay", "8", text], zeit=120)
        return "getippt"
    if vorbereitet is not None and vorbereitet.fertig():
        alt, klasse = vorbereitet.alt, vorbereitet.klasse
    else:
        alt = zwischenablage_lesen() if e.get("zwischenablage_zurueck", True) else None
        klasse = fenster_klasse()
    zwischenablage_setzen(text.encode("utf-8"))
    time.sleep(e.get("warte_ms", 30) / 1000)  # Zwischenablage muss beim X-Server angekommen sein
    kombi = tastenkombi(klasse or "", e.get("terminals", []))
    _lauf(["xdotool", "key", "--clearmodifiers", kombi])
    if alt is not None:
        def zurueck():
            time.sleep(1.0)  # dem Programm Zeit geben, das Einfügen abzuholen
            try:
                zwischenablage_setzen(alt)
            except (OSError, subprocess.TimeoutExpired):
                pass
        threading.Thread(target=zurueck, daemon=True).start()
    return "eingefügt mit " + kombi
