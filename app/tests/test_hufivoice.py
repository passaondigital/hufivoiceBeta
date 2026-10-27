"""Tests ohne Mikrofon. Start: python3 -m unittest discover -s tests (im Ordner app)."""
import http.server
import json
import os
import queue
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)

from hufivoice import einfuegen, einstellungen, erkennung  # noqa: E402

TEST_SCHLUESSEL = "test-nur-attrappe"  # kein echter Schlüssel


class Attrappe(http.server.BaseHTTPRequestHandler):
    zuletzt = {}

    def do_POST(self):
        laenge = int(self.headers["Content-Length"])
        koerper = self.rfile.read(laenge)
        Attrappe.zuletzt = {"pfad": self.path, "auth": self.headers.get("Authorization"),
                            "koerper": koerper}
        antwort = {"text": "Hallo vom Server"} if "audio/transcriptions" in self.path \
            else {"transcript": "Hallo vom Server"}
        daten = json.dumps(antwort).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(daten)))
        self.end_headers()
        self.wfile.write(daten)

    def log_message(self, *a):
        pass


class Grundlagen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = http.server.HTTPServer(("127.0.0.1", 0), Attrappe)
        cls.url = f"http://127.0.0.1:{cls.srv.server_port}"
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def cfg(self, **mehr):
        with mock.patch.dict(os.environ, {"HUFIVOICE_CONFIG": "/gibt/es/nicht"}):
            c = einstellungen.laden()
        c.update(mehr)
        c["lokal"]["whisper_programm"] = "/gibt/es/nicht"
        return c

    def test_standard_einstellungen(self):
        c = self.cfg()
        self.assertEqual(c["modus"], "lokal")
        self.assertEqual(c["taste"]["art"], "halten")
        self.assertEqual(c["taste"]["name"], "Super_L")

    def test_alte_tasten_einstellungen_bleiben_gueltig(self):
        for art in ("super", "super+space"):
            with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
                json.dump({"taste": {"art": art}}, fh)
                pfad = fh.name
            try:
                self.assertEqual(einstellungen.laden(pfad)["taste"]["art"], art)
            finally:
                os.unlink(pfad)

    def test_falscher_modus(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"modus": "cloud"}, fh)
        with self.assertRaises(ValueError):
            einstellungen.laden(fh.name)
        os.unlink(fh.name)

    def test_server_modus(self):
        c = self.cfg(modus="server")
        c["server"]["url"] = self.url + "/transcribe"
        c["server"]["feldname"] = "file"
        text, quelle = erkennung.transkribieren(c, b"\0\0" * 16000)
        self.assertEqual((text, quelle), ("Hallo vom Server", "server"))
        self.assertIn(b'name="file"; filename="aufnahme.wav"', Attrappe.zuletzt["koerper"])
        self.assertIsNone(Attrappe.zuletzt["auth"])

    def test_api_modus_schluessel_aus_umgebung(self):
        c = self.cfg(modus="api")
        c["api"]["url"] = self.url + "/v1/audio/transcriptions"
        with mock.patch.dict(os.environ, {"HUFIVOICE_API_KEY": TEST_SCHLUESSEL}):
            text, quelle = erkennung.transkribieren(c, b"\0\0" * 16000)
        self.assertEqual((text, quelle), ("Hallo vom Server", "api"))
        self.assertEqual(Attrappe.zuletzt["auth"], "Bearer " + TEST_SCHLUESSEL)
        self.assertIn(b'name="model"\r\n\r\ngpt-transcribe', Attrappe.zuletzt["koerper"])
        self.assertIn(b'name="languages[]"\r\n\r\nde', Attrappe.zuletzt["koerper"])
        self.assertIn(b'name="keywords[]"\r\n\r\nHuf', Attrappe.zuletzt["koerper"])
        self.assertNotIn(b'name="language"', Attrappe.zuletzt["koerper"])

    def test_altes_whisper_api_format_bleibt_moeglich(self):
        c = self.cfg(modus="api")
        c["api"]["url"] = self.url + "/v1/audio/transcriptions"
        c["api"]["modell"] = "whisper-1"
        with mock.patch.dict(os.environ, {"HUFIVOICE_API_KEY": TEST_SCHLUESSEL}):
            text, quelle = erkennung.transkribieren(c, b"\0\0" * 16000)
        self.assertEqual((text, quelle), ("Hallo vom Server", "api"))
        self.assertIn(b'name="language"\r\n\r\nde', Attrappe.zuletzt["koerper"])
        self.assertNotIn(b'name="languages[]"', Attrappe.zuletzt["koerper"])

    def test_api_ohne_schluessel_faellt_auf_vosk_text(self):
        c = self.cfg(modus="api")
        c["api"]["url"] = self.url + "/v1/audio/transcriptions"
        with mock.patch.dict(os.environ, {"HUFIVOICE_API_KEY": "", "HOME": tempfile.mkdtemp()}):
            text, quelle = erkennung.transkribieren(c, b"\0\0" * 16000, "vosk text")
        self.assertEqual(quelle, "vosk")

    def test_schluessel_datei_nur_in_geheim(self):
        with self.assertRaises(ValueError):
            einstellungen.lade_schluessel({"schluessel_umgebung": "GIBTS_NICHT_123",
                                           "schluessel_datei": "/tmp/schluessel"})

    def test_schluessel_datei(self):
        heim = tempfile.mkdtemp()
        os.makedirs(os.path.join(heim, ".hufi", "geheim"))
        datei = os.path.join(heim, ".hufi", "geheim", "hufivoice_api_key")
        with open(datei, "w") as fh:
            fh.write(TEST_SCHLUESSEL + "\n")
        os.chmod(datei, 0o600)
        with mock.patch.dict(os.environ, {"HOME": heim, "GIBTS_NICHT_123": ""}):
            wert = einstellungen.lade_schluessel({"schluessel_umgebung": "GIBTS_NICHT_123",
                                                  "schluessel_datei": "~/.hufi/geheim/hufivoice_api_key"})
        self.assertEqual(wert, TEST_SCHLUESSEL)

    def test_kein_schluessel_im_code(self):
        import re
        for wurzel, _, dateien in os.walk(APP):
            for d in dateien:
                if d.endswith((".py", ".json", ".sh")):
                    with open(os.path.join(wurzel, d), encoding="utf-8") as fh:
                        inhalt = fh.read()
                    self.assertIsNone(re.search(r"sk-[A-Za-z0-9_-]{20,}", inhalt), d)

    def test_erfindungen_raus(self):
        self.assertEqual(erkennung.aufraeumen("Untertitel im Auftrag des ZDF, 2021"), "")
        self.assertEqual(erkennung.aufraeumen(" [Musik] Hallo  Welt "), "Hallo Welt")

    def test_terminal_kombi(self):
        t = ["xfce4-terminal", "xterm"]
        self.assertEqual(einfuegen.tastenkombi("xfce4-terminal", t), "ctrl+shift+v")
        self.assertEqual(einfuegen.tastenkombi("firefox", t), "ctrl+v")


class TastenLogik(unittest.TestCase):
    """Zustände der Taste ohne X-Server durchspielen."""

    def waechter(self, art="super"):
        from hufivoice import taste
        w = object.__new__(taste.TastenWaechter)
        w.art, w.halten_s, w.q = art, 0.1, queue.Queue()
        w.super_codes, w.space_code = {133}, 65
        w.tasten_name, w.tasten_code, w.abbruch_code = "Super_L", 133, 9
        w.unten, w.andere, w.aktiv, w.vorbereitet = set(), False, False, False
        w._halten_uhr, w._los_uhren, w._sperre = None, {}, threading.Lock()
        return w

    def woerter(self, w):
        time.sleep(0.15)
        aus = []
        while not w.q.empty():
            aus.append(w.q.get())
        return aus

    def test_kurz_tippen_oeffnet_menue(self):
        w = self.waechter()
        w._gedrueckt(133)
        w._losgelassen(133)
        self.assertEqual(self.woerter(w), ["vorbereiten", "abbruch", "tippen"])

    def test_halten_und_loslassen(self):
        w = self.waechter()
        w._gedrueckt(133)
        time.sleep(0.2)
        for _ in range(3):           # automatische Wiederholung
            w._losgelassen(133)
            w._gedrueckt(133)
        w._losgelassen(133)
        self.assertEqual(self.woerter(w), ["vorbereiten", "start", "ende"])

    def test_super_plus_e_ist_kombi(self):
        w = self.waechter()
        w._gedrueckt(133)
        w._gedrueckt(26)
        w._losgelassen(26)
        w._losgelassen(133)
        self.assertEqual(self.woerter(w), ["vorbereiten", "abbruch"])

    def test_super_leertaste(self):
        w = self.waechter("super+space")
        w._gedrueckt(133)
        w._gedrueckt(65)
        w._losgelassen(65)
        w._losgelassen(133)
        self.assertEqual(self.woerter(w), ["vorbereiten", "start", "ende"])

    def test_halten_control_r(self):
        w = self.waechter("halten")
        w.tasten_name, w.tasten_code = "Control_R", 105
        w._gedrueckt(105)
        time.sleep(0.2)
        w._losgelassen(105)
        self.assertEqual(self.woerter(w), ["vorbereiten", "start", "ende"])

    def test_halten_f9_kurz_macht_nichts(self):
        w = self.waechter("halten")
        w.tasten_name, w.tasten_code = "F9", 75
        w._gedrueckt(75)
        w._losgelassen(75)
        self.assertEqual(self.woerter(w), ["vorbereiten", "abbruch"])

    def test_halten_zweite_taste_ist_kombi(self):
        w = self.waechter("halten")
        w.tasten_name, w.tasten_code = "Control_R", 105
        w._gedrueckt(105)
        w._gedrueckt(38)
        w._losgelassen(38)
        w._losgelassen(105)
        self.assertEqual(self.woerter(w), ["vorbereiten", "abbruch"])

    def test_halten_escape_bricht_aktive_aufnahme_ab(self):
        w = self.waechter("halten")
        w.tasten_name, w.tasten_code = "F9", 75
        w._gedrueckt(75)
        time.sleep(0.2)
        w._gedrueckt(9)
        w._losgelassen(9)
        w._losgelassen(75)
        self.assertEqual(self.woerter(w), ["vorbereiten", "start", "abbruch"])


@unittest.skipUnless(os.environ.get("HUFIVOICE_TEST_WAV"), "HUFIVOICE_TEST_WAV nicht gesetzt")
class EchtesWhisper(unittest.TestCase):
    def test_wav_lokal(self):
        import wave
        with wave.open(os.environ["HUFIVOICE_TEST_WAV"]) as w:
            pcm = w.readframes(w.getnframes())
        c = einstellungen.laden()
        text, quelle = erkennung.transkribieren(c, pcm)
        print("\nWhisper lokal:", text)
        self.assertEqual(quelle, "lokal")
        self.assertIn("freitag", text.lower())


if __name__ == "__main__":
    unittest.main()
