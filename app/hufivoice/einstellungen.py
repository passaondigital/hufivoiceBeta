"""Einstellungen laden. Reihenfolge: Standard (app/config.json), dann eigene
Datei (~/.hufi/voice/config.json oder HUFIVOICE_CONFIG). Eigene Werte gewinnen."""
import copy
import json
import os
import stat

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STANDARD = os.path.join(APP_DIR, "config.json")
EIGENE = os.path.expanduser("~/.hufi/voice/config.json")
MODI = ("lokal", "server", "api")
TASTEN = ("super", "super+space", "halten")
FENSTER_STILE = ("pille", "welle")
FENSTER_POSITIONEN = ("unten_mitte", "oben_mitte", "unten_rechts", "unten_links")
FENSTER_BILDSCHIRME = ("maus", "haupt")


def _mischen(basis, neu):
    for k, v in neu.items():
        if isinstance(v, dict) and isinstance(basis.get(k), dict):
            _mischen(basis[k], v)
        else:
            basis[k] = v
    return basis


def pfad(wert):
    return os.path.expandvars(os.path.expanduser(wert)) if wert else wert


def laden(datei=None):
    with open(STANDARD, encoding="utf-8") as fh:
        cfg = json.load(fh)
    eigene = datei or os.environ.get("HUFIVOICE_CONFIG") or EIGENE
    if os.path.isfile(eigene) and os.path.abspath(eigene) != STANDARD:
        with open(eigene, encoding="utf-8") as fh:
            _mischen(cfg, json.load(fh))
    cfg = copy.deepcopy(cfg)
    pruefen(cfg)
    return cfg


def pruefen(cfg):
    """Wirft ValueError, wenn ein Wert nicht passt. Gibt cfg zurück."""
    if cfg.get("modus") not in MODI:
        raise ValueError(f"modus muss lokal, server oder api sein, nicht {cfg.get('modus')!r}")
    if cfg["taste"].get("art") not in TASTEN:
        raise ValueError("taste.art muss super, super+space oder halten sein")
    if cfg["taste"].get("art") == "halten" and not cfg["taste"].get("name"):
        raise ValueError("taste.name darf bei taste.art halten nicht leer sein")
    if cfg["taste"].get("abbruch") is not None and not isinstance(cfg["taste"].get("abbruch"), str):
        raise ValueError("taste.abbruch muss ein X11-Tastenname oder null sein")
    if not isinstance(cfg["taste"].get("aktiv", True), bool):
        raise ValueError("taste.aktiv muss true oder false sein")
    if cfg.get("lokal", {}).get("endtext", "whisper") not in ("whisper", "vosk"):
        raise ValueError("lokal.endtext muss whisper oder vosk sein")
    fenster = cfg.get("fenster", {})
    if fenster.get("stil", "welle") not in FENSTER_STILE:
        raise ValueError("fenster.stil muss pille oder welle sein")
    if fenster.get("position", "unten_mitte") not in FENSTER_POSITIONEN:
        raise ValueError("fenster.position ist ungültig")
    if fenster.get("bildschirm", "maus") not in FENSTER_BILDSCHIRME:
        raise ValueError("fenster.bildschirm muss maus oder haupt sein")
    return cfg


def lade_schluessel(api_cfg):
    """API-Schlüssel nur aus Umgebungsvariable oder ~/.hufi/geheim/. Gibt den
    Schlüssel zurück, druckt ihn aber nie. None, wenn keiner da ist."""
    name = api_cfg.get("schluessel_umgebung") or "HUFIVOICE_API_KEY"
    wert = os.environ.get(name, "").strip()
    if wert:
        return wert
    datei = pfad(api_cfg.get("schluessel_datei") or "~/.hufi/geheim/hufivoice_api_key")
    geheim = os.path.realpath(os.path.expanduser("~/.hufi/geheim"))
    if not os.path.realpath(datei).startswith(geheim + os.sep):
        raise ValueError("Schlüssel-Datei muss in ~/.hufi/geheim/ liegen")
    if not os.path.isfile(datei):
        return None
    rechte = stat.S_IMODE(os.stat(datei).st_mode)
    if rechte & 0o077:
        print("Warnung: Schlüssel-Datei ist für andere lesbar. Bitte: chmod 600", datei)
    with open(datei, encoding="utf-8") as fh:
        return fh.read().strip() or None
