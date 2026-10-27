#!/usr/bin/env python3
"""Lokaler Web-/PWA-Zugang zu HufiVoice.

Standardmäßig nur auf 127.0.0.1. Für LAN-Zugriff ist ein Token Pflicht. Für
Mikrofonzugriff von Android muss die Seite über vertrauenswürdiges HTTPS laufen.
"""
import argparse
import hmac
import json
import os
import secrets
import ssl
import sys
import threading
import time
import wave
from collections import defaultdict, deque
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO

APP = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, APP)

from hufivoice import einstellungen, erkennung  # noqa: E402

MAX_AUDIO = 20 * 1024 * 1024
LOOPBACK = {"127.0.0.1", "::1", "localhost"}
WEB_DATEIEN = ("index.html", "styles.css", "app.js", "sw.js", "manifest.webmanifest", "icon.svg")


class RatenLimit:
    """Kleines Prozess-Limit gegen versehentliche oder einfache Überlastung."""

    def __init__(self, anzahl=30, fenster_s=60):
        self.anzahl = max(1, int(anzahl))
        self.fenster_s = max(1, int(fenster_s))
        self._aufrufe = defaultdict(deque)
        self._sperre = threading.Lock()

    def erlaubt(self, schluessel, jetzt=None):
        jetzt = time.monotonic() if jetzt is None else jetzt
        with self._sperre:
            aufrufe = self._aufrufe[schluessel]
            while aufrufe and aufrufe[0] <= jetzt - self.fenster_s:
                aufrufe.popleft()
            if len(aufrufe) >= self.anzahl:
                return False
            aufrufe.append(jetzt)
            return True


def wav_pcm(daten):
    """Liest das vom Browser erzeugte 16-kHz-Mono-WAV sicher ein."""
    try:
        with wave.open(BytesIO(daten), "rb") as wav:
            if (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) != (16000, 1, 2):
                raise ValueError("Audio muss WAV mit 16 kHz, mono und 16 Bit sein")
            sekunden = wav.getnframes() / wav.getframerate()
            if sekunden > 180:
                raise ValueError("Aufnahme ist länger als 3 Minuten")
            return wav.readframes(wav.getnframes())
    except (wave.Error, EOFError) as fehler:
        raise ValueError("Ungültige WAV-Datei") from fehler


def zugang_pruefen(host, token):
    if host not in LOOPBACK and not token:
        raise ValueError("Für LAN-/Internet-Zugriff ist --token Pflicht")


def token_erzeugen():
    """Erzeugt etwa 256 Bit Zufall für den privaten Web-Zugang."""
    return secrets.token_urlsafe(32)


def web_pruefen(cfg, host="127.0.0.1", token="", cert=None, key=None, web_ordner=None):
    """Prüft die Web-Konfiguration, ohne Server oder Aufnahme zu starten."""
    ergebnis = []

    def zeile(name, ok, info="", hinweis=False):
        ergebnis.append(("HINWEIS" if hinweis else ("OK" if ok else "FEHLT"), name, info))

    web_ordner = web_ordner or os.path.join(os.path.dirname(APP), "web", "dist")
    fehlend = [name for name in WEB_DATEIEN if not os.path.isfile(os.path.join(web_ordner, name))]
    zeile("Web-App", not fehlend, "vollständig" if not fehlend else ", ".join(fehlend))
    try:
        zugang_pruefen(host, token)
        zeile("Zugangsschutz", True, "nur lokal" if host in LOOPBACK else "Token gesetzt")
    except ValueError as fehler:
        zeile("Zugangsschutz", False, str(fehler))
    if bool(cert) != bool(key):
        zeile("HTTPS-Dateien", False, "Zertifikat und Schlüssel müssen zusammen angegeben werden")
    elif cert and key:
        cert, key = os.path.expanduser(cert), os.path.expanduser(key)
        ok = os.path.isfile(cert) and os.path.isfile(key)
        zeile("HTTPS-Dateien", ok, "vorhanden" if ok else "Zertifikat oder Schlüssel fehlt")
    elif host not in LOOPBACK:
        zeile("HTTPS", True, "muss vor diesem Dienst am Reverse-Proxy enden", hinweis=True)

    modus = cfg.get("modus")
    if modus == "lokal":
        programm = einstellungen.pfad(cfg["lokal"].get("whisper_programm"))
        modell = einstellungen.pfad(cfg["lokal"].get("whisper_modell"))
        lokal_ok = bool(programm and modell and os.path.isfile(programm) and os.path.isfile(modell))
        zeile("Lokales Whisper", lokal_ok,
              "Programm und Modell vorhanden" if lokal_ok
              else "Programm oder Modell fehlt")
    elif modus == "api":
        try:
            schluessel = bool(einstellungen.lade_schluessel(cfg["api"]))
        except ValueError as fehler:
            schluessel = False
            zeile("API-Konfiguration", False, str(fehler))
        else:
            zeile("API-Schlüssel", schluessel, "gesetzt" if schluessel else "fehlt")
        api_url = cfg["api"].get("url", "")
        zeile("API-Adresse", api_url.startswith(("https://", "http://127.0.0.1", "http://localhost")),
              api_url)
        zeile("API-Modell", bool(cfg["api"].get("modell")), cfg["api"].get("modell", "fehlt"))
    elif modus == "server":
        url = cfg["server"].get("url", "")
        zeile("Whisper-Server", url.startswith(("https://", "http://127.0.0.1", "http://localhost")), url)
    else:
        zeile("Erkennungsmodus", False, str(modus))
    return ergebnis


class Handler(SimpleHTTPRequestHandler):
    server_version = "HufiVoiceWeb/0.1"

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "microphone=(self)")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'self'; style-src 'self'; "
                         "img-src 'self' data:; connect-src 'self' https:; object-src 'none'; "
                         "base-uri 'none'; frame-ancestors 'none'")
        super().end_headers()

    def _json(self, status, inhalt):
        daten = json.dumps(inhalt, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(daten)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(daten)

    def _erlaubt(self):
        token = self.server.zugangs_token
        erhalten = self.headers.get("Authorization", "")
        return not token or hmac.compare_digest(erhalten, "Bearer " + token)

    def do_GET(self):
        if self.path == "/api/health":
            self._json(200, {"status": "ok", "dienst": "hufivoice-web"})
            return
        super().do_GET()

    def do_POST(self):
        if self.path != "/api/transcribe":
            self._json(404, {"fehler": "Nicht gefunden"})
            return
        if not self._erlaubt():
            self._json(401, {"fehler": "Zugangscode fehlt oder ist falsch"})
            return
        if not self.server.raten_limit.erlaubt(self.client_address[0]):
            self.send_response(429)
            self.send_header("Retry-After", "60")
            self.send_header("Content-Type", "application/json; charset=utf-8")
            daten = json.dumps({"fehler": "Zu viele Anfragen. Bitte kurz warten."}).encode("utf-8")
            self.send_header("Content-Length", str(len(daten)))
            self.end_headers()
            self.wfile.write(daten)
            return
        if not self.server.transkriptions_plaetze.acquire(blocking=False):
            self._json(503, {"fehler": "HufiVoice ist gerade beschäftigt. Bitte erneut versuchen."})
            return
        try:
            try:
                laenge = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                laenge = 0
            if laenge < 44 or laenge > MAX_AUDIO:
                self._json(413, {"fehler": "Audio fehlt oder ist zu groß"})
                return
            try:
                pcm = wav_pcm(self.rfile.read(laenge))
                text, quelle = erkennung.transkribieren(self.server.hufi_cfg, pcm)
                if not text:
                    self._json(422, {"fehler": "Nichts verstanden", "quelle": quelle})
                    return
                self._json(200, {"text": text, "quelle": quelle})
            except ValueError as fehler:
                self._json(400, {"fehler": str(fehler)})
            except Exception as fehler:  # noqa: BLE001 - Webserver darf nicht abstürzen
                print("Web-Transkription fehlgeschlagen:", fehler, flush=True)
                self._json(500, {"fehler": "Transkription fehlgeschlagen"})
        finally:
            self.server.transkriptions_plaetze.release()

    def log_message(self, format_, *args):
        print(f"Web {self.client_address[0]}: {format_ % args}", flush=True)


def server_bauen(cfg, host="127.0.0.1", port=8765, token="", web_ordner=None,
                  rate_limit=30, parallel=2):
    zugang_pruefen(host, token)
    web_ordner = web_ordner or os.path.join(os.path.dirname(APP), "web", "dist")

    class WebHandler(Handler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=web_ordner, **kwargs)

    server = ThreadingHTTPServer((host, port), WebHandler)
    server.hufi_cfg = cfg
    server.zugangs_token = token
    server.raten_limit = RatenLimit(rate_limit)
    server.transkriptions_plaetze = threading.BoundedSemaphore(max(1, int(parallel)))
    return server


def main():
    parser = argparse.ArgumentParser(description="HufiVoice lokal im Browser und als PWA")
    parser.add_argument("--host", default="127.0.0.1", help="Standard: nur dieser Rechner")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", default=os.environ.get("HUFIVOICE_WEB_TOKEN", ""),
                        help="Pflicht bei LAN-Zugriff; besser über HUFIVOICE_WEB_TOKEN setzen")
    parser.add_argument("--config", help="andere HufiVoice-Konfiguration")
    parser.add_argument("--cert", help="TLS-Zertifikat (PEM)")
    parser.add_argument("--key", help="privater TLS-Schlüssel (PEM)")
    parser.add_argument("--rate-limit", type=int, default=30, help="Transkriptionen pro Minute und IP")
    parser.add_argument("--parallel", type=int, default=2, help="gleichzeitige Transkriptionen")
    aktion = parser.add_mutually_exclusive_group()
    aktion.add_argument("--pruefen", action="store_true", help="Web-Einrichtung prüfen, nichts starten")
    aktion.add_argument("--token-erzeugen", action="store_true", help="sicheren Zugangscode ausgeben")
    args = parser.parse_args()
    if args.token_erzeugen:
        print(token_erzeugen())
        return 0
    cfg = einstellungen.laden(args.config)
    if args.pruefen:
        ergebnis = web_pruefen(cfg, args.host, args.token, args.cert, args.key)
        for status, name, info in ergebnis:
            print(f"  [{status:7}] {name}: {info}")
        return 0 if all(status != "FEHLT" for status, _name, _info in ergebnis) else 1
    try:
        server = server_bauen(cfg, args.host, args.port, args.token,
                              rate_limit=args.rate_limit, parallel=args.parallel)
    except ValueError as fehler:
        parser.error(str(fehler))
    schema = "http"
    if args.cert or args.key:
        if not (args.cert and args.key):
            parser.error("--cert und --key müssen zusammen angegeben werden")
        kontext = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        kontext.load_cert_chain(args.cert, args.key)
        server.socket = kontext.wrap_socket(server.socket, server_side=True)
        schema = "https"
    print(f"HufiVoice Web läuft auf {schema}://{args.host}:{args.port}", flush=True)
    if args.host not in LOOPBACK and schema != "https":
        print("Hinweis: Android erlaubt das Mikrofon im LAN nur über vertrauenswürdiges HTTPS.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
