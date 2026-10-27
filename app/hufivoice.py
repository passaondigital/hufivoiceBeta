#!/usr/bin/env python3
"""HufiVoice für Linux (XFCE).

Super-Taste halten = zuhören (kleines Fenster zeigt den Text live).
Loslassen = Text steht im aktiven Fenster. Kurz tippen = Menü wie immer.

Aufruf:
  hufivoice.py                 normal starten (läuft im Hintergrund)
  hufivoice.py --pruefen       zeigt, ob alles da ist
  hufivoice.py --datei a.wav   Test ohne Mikrofon: WAV in Text umwandeln
  hufivoice.py --modus server  Modus nur für diesen Start ändern
  hufivoice.py --einstellungen Einstellungsfenster öffnen
  hufivoice.py --start / --stopp Steuerbefehle für Wayland-Tastenkürzel
"""
import argparse
import os
import queue
import shutil
import subprocess
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hufivoice import VERSION, aufnahme, einstellungen, erkennung  # noqa: E402

MIN_SEKUNDEN = 0.4
START = time.monotonic()


def pruefen(cfg):
    ok = True

    def zeile(name, gut, info=""):
        nonlocal ok
        ok = ok and gut
        print(f"  [{'OK ' if gut else 'FEHLT'}] {name}{'  ' + info if info else ''}")

    print(f"HufiVoice {VERSION}  Modus: {cfg['modus']}")
    l = cfg["lokal"]
    zeile("whisper.cpp Programm", os.path.isfile(einstellungen.pfad(l["whisper_programm"])),
          einstellungen.pfad(l["whisper_programm"]))
    zeile("Whisper Modell", os.path.isfile(einstellungen.pfad(l["whisper_modell"])),
          einstellungen.pfad(l["whisper_modell"]))
    zeile("Vosk Modell (Vorschau)", os.path.isdir(einstellungen.pfad(l["vosk_modell"])),
          einstellungen.pfad(l["vosk_modell"]))
    try:
        import vosk  # noqa: F401
        zeile("Python-Paket vosk", True)
    except ImportError:
        zeile("Python-Paket vosk", False, "pip install vosk")
    for prog in ("xdotool", "xclip", "parecord"):
        zeile(prog, bool(shutil.which(prog)))
    try:
        import Xlib  # noqa: F401
        zeile("python3-xlib", True)
    except ImportError:
        zeile("python3-xlib", False)
    try:
        import gi  # noqa: F401
        zeile("GTK (python3-gi)", True)
    except ImportError:
        zeile("GTK (python3-gi)", False)
    if shutil.which("pactl"):
        mic = aufnahme.finde_mikrofon()
        zeile("Mikrofon", bool(mic), mic or "keins gefunden")
    if cfg["modus"] == "api":
        try:
            da = bool(einstellungen.lade_schluessel(cfg["api"]))
        except ValueError as fehler:
            da = False
            print("  ", fehler)
        zeile("API-Schlüssel", da, "vorhanden (wird nicht angezeigt)" if da else "")
    if cfg["modus"] == "server":
        print("  Server:", cfg["server"]["url"])
    return ok


def datei_test(cfg, pfad):
    import wave
    with wave.open(pfad, "rb") as w:
        pcm = w.readframes(w.getnframes())
    vorschau = erkennung.Vorschau(cfg["lokal"]["vosk_modell"])
    vtext = ""
    if vorschau.ok and cfg.get("vorschau", True):
        vorschau.neu()
        for i in range(0, len(pcm), aufnahme.BLOCK):
            vtext = vorschau.block(pcm[i:i + aufnahme.BLOCK])
        vtext = vorschau.ende()
        print("Vorschau (Vosk):", vtext)
    beginn = time.monotonic()
    text, quelle = erkennung.transkribieren(cfg, pcm, vtext)
    print(f"Ergebnis ({quelle}, {time.monotonic() - beginn:.1f} s für "
          f"{aufnahme.sekunden(pcm):.1f} s Ton):", text)
    return 0 if text else 1


class App:
    def __init__(self, cfg):
        self.cfg = cfg
        self.q = queue.Queue()
        self.fenster = None
        if cfg["fenster"].get("zeigen", True):
            try:
                from hufivoice import fenster
                self.fenster_mod = fenster
                self.fenster = fenster.Fenster(cfg)
            except (ImportError, ValueError, RuntimeError) as fehler:
                print("Ohne Fenster, weil:", fehler, flush=True)
        # Vosk-Modell im Hintergrund laden: HufiVoice ist sofort bereit,
        # die Live-Vorschau kommt dazu, sobald das Modell geladen ist.
        self.vorschau = None
        if cfg.get("vorschau", True):
            threading.Thread(target=self._vorschau_laden, daemon=True).start()
        self.aufn = None
        self.vorbereitet = None
        self.zeiten = {}
        self.vtext = ""
        self.zeigt = False
        self._vorschau_an = False
        self._letzte_anzeige = 0.0

    def _vorschau_laden(self):
        beginn = time.monotonic()
        v = erkennung.Vorschau(self.cfg["lokal"]["vosk_modell"])
        if v.ok:
            self.vorschau = v
            print(f"Live-Vorschau bereit ({time.monotonic() - beginn:.1f} s).", flush=True)
        else:
            print("Keine Live-Vorschau (Vosk oder Modell fehlt).", flush=True)

    def _zeige(self, status, text="", weg=None):
        if self.fenster:
            self.fenster.zeigen(status, text, weg)
        else:
            print(f"[{status}] {text}", flush=True)

    def _block(self, pcm):
        if self.fenster and self.zeigt:
            self.fenster.pegel(aufnahme.pegel(pcm))
        if self.vorschau and self.vorschau.ok and self._vorschau_an:
            self.vtext = self.vorschau.block(pcm)
            jetzt = time.monotonic()
            if self.zeigt and jetzt - self._letzte_anzeige > 0.2:
                self._letzte_anzeige = jetzt
                self._zeige("Ich höre zu", self.vtext)

    def arbeiter(self):
        while True:
            wort = self.q.get()
            try:
                if wort == "ende":
                    self._ende(getattr(self.q, "zeit_ende", None))
                else:
                    getattr(self, "_" + wort)()
            except Exception as fehler:  # noqa: BLE001  nie ganz abstürzen
                print("Fehler bei", wort, ":", fehler, flush=True)
                self._zeige("Fehler", str(fehler)[:160], weg=4)

    def _vorbereiten(self):
        if self.aufn:
            return
        self.vtext = ""
        self._vorschau_an = bool(self.vorschau and self.vorschau.ok)
        if self._vorschau_an:
            self.vorschau.neu()
        self.aufn = aufnahme.Aufnahme(self.cfg.get("mikrofon", "auto"), self._block)
        self.aufn.start()

    def _start(self):
        self.zeigt = True
        self._zeige("Ich höre zu", self.vtext)
        from hufivoice import einfuegen
        self.vorbereitet = einfuegen.Vorbereitung(self.cfg)  # schon jetzt, nicht erst nach dem Loslassen

    def _abbruch(self):
        self.zeigt = False
        if self.aufn:
            self.aufn.stopp()
            self.aufn = None
        if self.fenster:
            self.fenster.verstecken()

    def _tippen(self):
        t = self.cfg["taste"]
        if t.get("tippen_oeffnet_menue") and t.get("menue_befehl"):
            subprocess.Popen(t["menue_befehl"], shell=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _ende(self, los=None):
        los = los or time.monotonic()
        self.zeigt = False
        if self.fenster:
            self.fenster.verstecken()
        if not self.aufn:
            return
        pcm = self.aufn.stopp()
        self.aufn = None
        vtext = self.vorschau.ende() if self._vorschau_an else ""
        if aufnahme.sekunden(pcm) < MIN_SEKUNDEN:
            self._abbruch()
            return
        print("Schreibe …", flush=True)
        t1 = time.monotonic()
        text, quelle = erkennung.transkribieren(self.cfg, pcm, vtext)
        t2 = time.monotonic()
        if not text:
            print("Nichts verstanden", flush=True)
            return
        from hufivoice import einfuegen
        art = einfuegen.einfuegen(text, self.cfg, self.vorbereitet)
        t3 = time.monotonic()
        self.vorbereitet = None
        self.zeiten = {"erkennung_ms": round((t2 - t1) * 1000),
                       "rest_ms": round(((t1 - los) + (t3 - t2)) * 1000),
                       "gesamt_ms": round((t3 - los) * 1000)}
        print(f"Fertig: {len(text)} Zeichen, Quelle {quelle}, {art}. Zeit nach Loslassen: "
              f"{self.zeiten['gesamt_ms']} ms (Erkennung {self.zeiten['erkennung_ms']} ms, "
              f"alles andere {self.zeiten['rest_ms']} ms)", flush=True)

    def laufen(self):
        from hufivoice import steuerung
        self._steuer_server = steuerung.server_starten(self.q)
        if not os.environ.get("DISPLAY"):
            print("Wayland-Steuerung bereit: Aufnahme mit --start und --stopp.", flush=True)
            threading.Thread(target=self.arbeiter, daemon=True).start()
            if self.fenster:
                self.fenster_mod.hauptschleife()
            else:
                threading.Event().wait()
            return
        if not self.cfg["taste"].get("aktiv", True):
            print("Die globale Taste ist aus; --start/--stopp bleiben verfügbar.", flush=True)
            threading.Thread(target=self.arbeiter, daemon=True).start()
            if self.fenster:
                self.fenster_mod.hauptschleife()
            else:
                threading.Event().wait()
            return
        from hufivoice import taste
        tcfg = self.cfg["taste"]
        waechter = taste.TastenWaechter(tcfg["art"], tcfg.get("halten_ms", 350), self.q,
                                        tcfg.get("name", "Super_L"),
                                        tcfg.get("abbruch", "Escape"))
        threading.Thread(target=self.arbeiter, daemon=True).start()
        art = ({"super": "Super halten", "super+space": "Super+Leertaste halten"}
               .get(tcfg["art"], f"{tcfg.get('name', 'Super_L')} halten"))
        print(f"HufiVoice {VERSION} läuft. {art} zum Sprechen. Modus: {self.cfg['modus']}. "
              f"Start in {(time.monotonic() - START) * 1000:.0f} ms.", flush=True)
        if self.fenster:
            threading.Thread(target=self._waechter_lauf, args=(waechter,), daemon=True).start()
            self.fenster_mod.hauptschleife()
        else:
            waechter.laufen()

    def _waechter_lauf(self, waechter):
        try:
            waechter.laufen()
        except Exception as fehler:  # noqa: BLE001
            print("Tasten-Wächter gestoppt:", fehler, flush=True)
            self.fenster_mod.beenden()


def main():
    p = argparse.ArgumentParser(description="HufiVoice: Taste halten, sprechen, loslassen.")
    p.add_argument("--pruefen", action="store_true", help="Einrichtung prüfen")
    p.add_argument("--datei", help="WAV-Datei (16 kHz mono) umwandeln, ohne Mikrofon")
    p.add_argument("--modus", choices=einstellungen.MODI, help="Modus nur für diesen Start")
    p.add_argument("--config", help="andere Einstellungsdatei")
    p.add_argument("--einstellungen", action="store_true", help="Einstellungsfenster öffnen")
    steuer = p.add_mutually_exclusive_group()
    steuer.add_argument("--start", action="store_true", help="laufende Aufnahme starten")
    steuer.add_argument("--stopp", action="store_true", help="laufende Aufnahme beenden")
    a = p.parse_args()
    if a.start or a.stopp:
        from hufivoice import steuerung
        return 0 if steuerung.senden("start" if a.start else "stopp") else 1
    cfg = einstellungen.laden(a.config)
    if a.modus:
        cfg["modus"] = a.modus
    if a.pruefen:
        return 0 if pruefen(cfg) else 1
    if a.datei:
        return datei_test(cfg, a.datei)
    if a.einstellungen:
        from hufivoice import einstellungen_fenster
        return einstellungen_fenster.starten(a.config)
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        print("Keine grafische Sitzung gefunden (DISPLAY und WAYLAND_DISPLAY fehlen).")
        return 1
    App(cfg).laufen()
    return 0


if __name__ == "__main__":
    sys.exit(main())
