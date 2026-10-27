"""Tests für den lokalen Web-/PWA-Zugang."""
import http.client
import importlib.util
import io
import json
import os
import re
import sys
import tempfile
import threading
import unittest
import wave
from unittest import mock

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)
SPEC = importlib.util.spec_from_file_location("hufivoice_web", os.path.join(APP, "hufivoice_web.py"))
WEB = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WEB)
WEB_DIST = os.path.join(os.path.dirname(APP), "web", "dist")
ROOT = os.path.dirname(APP)


def test_wav(sekunden=0.5):
    aus = io.BytesIO()
    with wave.open(aus, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\0\0" * int(16000 * sekunden))
    return aus.getvalue()


class WebAudio(unittest.TestCase):
    def test_wav_wird_als_pcm_gelesen(self):
        self.assertEqual(len(WEB.wav_pcm(test_wav())), 16000)

    def test_falsches_audio_wird_abgelehnt(self):
        with self.assertRaisesRegex(ValueError, "Ungültige WAV"):
            WEB.wav_pcm(b"kein audio")

    def test_lan_braucht_token(self):
        with self.assertRaisesRegex(ValueError, "token"):
            WEB.zugang_pruefen("0.0.0.0", "")
        WEB.zugang_pruefen("0.0.0.0", "geheim")
        WEB.zugang_pruefen("127.0.0.1", "")

    def test_ratenlimit(self):
        limit = WEB.RatenLimit(2, 60)
        self.assertTrue(limit.erlaubt("eins", jetzt=100))
        self.assertTrue(limit.erlaubt("eins", jetzt=101))
        self.assertFalse(limit.erlaubt("eins", jetzt=102))
        self.assertTrue(limit.erlaubt("eins", jetzt=161))

    def test_zugangscode_hat_genug_zufall(self):
        eins, zwei = WEB.token_erzeugen(), WEB.token_erzeugen()
        self.assertNotEqual(eins, zwei)
        self.assertGreaterEqual(len(eins), 40)
        self.assertRegex(eins, r"^[A-Za-z0-9_-]+$")


class WebDateien(unittest.TestCase):
    def test_javascript_verweist_nur_auf_vorhandene_elemente(self):
        with open(os.path.join(WEB_DIST, "index.html"), encoding="utf-8") as fh:
            html = fh.read()
        with open(os.path.join(WEB_DIST, "app.js"), encoding="utf-8") as fh:
            javascript = fh.read()
        vorhandene_ids = set(re.findall(r'\bid="([^"]+)"', html))
        verwendete_ids = set(re.findall(r'\$\("([^"]+)"\)', javascript))
        self.assertEqual(verwendete_ids - vorhandene_ids, set())
        self.assertEqual(html.count("<i></i>"), 9)

    def test_pwa_manifest_verweist_auf_vorhandene_dateien(self):
        with open(os.path.join(WEB_DIST, "manifest.webmanifest"), encoding="utf-8") as fh:
            manifest = json.load(fh)
        self.assertEqual(manifest["display"], "standalone")
        for icon in manifest["icons"]:
            self.assertTrue(os.path.isfile(os.path.join(WEB_DIST, icon["src"])))

    def test_private_online_konfiguration(self):
        from hufivoice import einstellungen
        cfg = einstellungen.laden(os.path.join(ROOT, "deploy", "config-online.json"))
        self.assertEqual(cfg["modus"], "api")
        self.assertEqual(cfg["api"]["modell"], "gpt-transcribe")
        self.assertFalse(cfg["api"]["bei_fehler_lokal"])
        with open(os.path.join(ROOT, ".dockerignore"), encoding="utf-8") as fh:
            ignoriert = fh.read()
        self.assertIn("original/", ignoriert)
        self.assertIn("deploy/.env", ignoriert)

    def test_web_diagnose_erkennt_api_schluessel(self):
        from hufivoice import einstellungen
        cfg = einstellungen.laden(os.path.join(ROOT, "deploy", "config-online.json"))
        with mock.patch.dict(os.environ, {"HUFIVOICE_API_KEY": "test-nur-attrappe"}):
            ergebnis = WEB.web_pruefen(cfg, token="", web_ordner=WEB_DIST)
        self.assertFalse([zeile for zeile in ergebnis if zeile[0] == "FEHLT"])
        self.assertIn(("OK", "API-Modell", "gpt-transcribe"), ergebnis)


class WebApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.web_ordner = tempfile.TemporaryDirectory()
        cls.server = WEB.server_bauen({}, "127.0.0.1", 0, "geheim", cls.web_ordner.name)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.web_ordner.cleanup()

    def anfrage(self, token=None):
        verbindung = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        headers = {"Content-Type": "audio/wav"}
        if token:
            headers["Authorization"] = "Bearer " + token
        verbindung.request("POST", "/api/transcribe", body=test_wav(), headers=headers)
        antwort = verbindung.getresponse()
        inhalt = json.loads(antwort.read())
        headers = dict(antwort.getheaders())
        verbindung.close()
        return antwort.status, inhalt, headers

    def test_healthcheck_ohne_token(self):
        verbindung = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        verbindung.request("GET", "/api/health")
        antwort = verbindung.getresponse()
        inhalt = json.loads(antwort.read())
        verbindung.close()
        self.assertEqual(antwort.status, 200)
        self.assertEqual(inhalt["status"], "ok")

    def test_token_schuetzt_api(self):
        status, inhalt, _headers = self.anfrage()
        self.assertEqual(status, 401)
        self.assertIn("Zugangscode", inhalt["fehler"])

    def test_wav_wird_transkribiert(self):
        with mock.patch.object(WEB.erkennung, "transkribieren", return_value=("Hallo vom Web", "lokal")):
            status, inhalt, headers = self.anfrage("geheim")
        self.assertEqual(status, 200)
        self.assertEqual(inhalt, {"text": "Hallo vom Web", "quelle": "lokal"})
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(headers["Permissions-Policy"], "microphone=(self)")


if __name__ == "__main__":
    unittest.main()
