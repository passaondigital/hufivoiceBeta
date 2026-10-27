"""Einstellungen speichern, Autostart an und aus, Mikrofone finden.
Ohne GTK, damit es sich leicht testen lässt."""
import json
import os
import subprocess
import sys
import tempfile

from . import einstellungen

APP_DIR = einstellungen.APP_DIR
AUTOSTART = os.path.expanduser("~/.config/autostart/hufivoice.desktop")


def _eigene_datei(datei=None):
    return datei or os.environ.get("HUFIVOICE_CONFIG") or os.path.expanduser("~/.hufi/voice/config.json")


def eigene_laden(datei=None):
    pfad = _eigene_datei(datei)
    if os.path.isfile(pfad):
        with open(pfad, encoding="utf-8") as fh:
            return json.load(fh)
    return {}


def speichern(aenderungen, datei=None):
    """Schreibt nur die geänderten Werte in die eigene Datei. Alles andere
    bleibt, wie es ist. Prüft vorher, ob die Werte gültig sind. Schreibt
    erst in eine Hilfsdatei und tauscht dann, damit nie eine halbe Datei bleibt."""
    pfad = _eigene_datei(datei)
    eigene = eigene_laden(pfad)
    einstellungen._mischen(eigene, aenderungen)
    with open(einstellungen.STANDARD, encoding="utf-8") as fh:
        gesamt = json.load(fh)
    einstellungen._mischen(gesamt, json.loads(json.dumps(eigene)))
    einstellungen.pruefen(gesamt)
    for teil in ("api",):  # Schlüssel nie in die Datei
        for k in list(eigene.get(teil, {})):
            if k in ("schluessel", "key", "api_key"):
                raise ValueError("API-Schlüssel gehören nicht in config.json, nur nach ~/.hufi/geheim/")
    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(pfad), prefix=".config-", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(eigene, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, pfad)
    return gesamt


def autostart_eintrag(python=None, skript=None):
    python = python or sys.executable
    skript = skript or os.path.join(APP_DIR, "hufivoice.py")
    return ("[Desktop Entry]\nType=Application\nName=HufiVoice\n"
            "Comment=Taste halten, sprechen, loslassen\n"
            f"Exec={python} {skript}\nIcon=audio-input-microphone\n"
            "X-GNOME-Autostart-enabled=true\nTerminal=false\n")


def autostart_ist_an(pfad=None):
    return os.path.isfile(pfad or AUTOSTART)


def autostart_setzen(an, pfad=None):
    pfad = pfad or AUTOSTART
    if an:
        os.makedirs(os.path.dirname(pfad), exist_ok=True)
        with open(pfad, "w", encoding="utf-8") as fh:
            fh.write(autostart_eintrag())
    elif os.path.isfile(pfad):
        os.unlink(pfad)
    return autostart_ist_an(pfad)


def mikrofone():
    """Liste von (name, beschreibung). Leer, wenn pactl fehlt."""
    try:
        aus = subprocess.run(["pactl", "list", "sources"], capture_output=True, text=True,
                             timeout=5, env={**os.environ, "LC_ALL": "C"}).stdout
    except (OSError, subprocess.TimeoutExpired):
        return []
    return mikrofone_aus_text(aus)


def mikrofone_aus_text(aus):
    liste, name = [], None
    for zeile in aus.splitlines():
        z = zeile.strip()
        if z.startswith("Name:"):
            name = z.split(":", 1)[1].strip()
        elif z.startswith("Description:") and name:
            if not name.endswith(".monitor"):  # Lautsprecher-Mitschnitt ist kein Mikrofon
                liste.append((name, z.split(":", 1)[1].strip()))
            name = None
    return liste
