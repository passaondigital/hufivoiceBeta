"""Tests für Version 0.2: Live-Fenster, Pegel, Einstellungsfenster-Logik, Tempo.
Start: python3 -m unittest discover -s tests (im Ordner app).
Tests mit Bildschirm laufen nur, wenn DISPLAY gesetzt ist (z. B. Xvfb)."""
import array
import json
import math
import os
import queue
import shutil
import sys
import tempfile
import threading
import time
import unittest
from collections import namedtuple
from unittest import mock

APP = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, APP)

from hufivoice import aufnahme, einfuegen, einrichtung, einstellungen  # noqa: E402
from hufivoice.fenster_logik import position_koordinaten  # noqa: E402

MIT_BILDSCHIRM = bool(os.environ.get("DISPLAY"))


def ton(lautstaerke, sekunden=0.1):
    n = int(16000 * sekunden)
    return array.array("h", (int(lautstaerke * 32767 * math.sin(2 * math.pi * 220 * i / 16000))
                             for i in range(n))).tobytes()


class Pegel(unittest.TestCase):
    def test_stille_ist_null(self):
        self.assertEqual(aufnahme.pegel(b"\0\0" * 1600), 0.0)
        self.assertEqual(aufnahme.pegel(b""), 0.0)

    def test_laut_ist_hoch_leise_ist_mittel(self):
        laut, leise = aufnahme.pegel(ton(0.8)), aufnahme.pegel(ton(0.02))
        self.assertGreater(laut, 0.9)
        self.assertTrue(0.05 < leise < laut, (leise, laut))

    def test_pegel_ist_schnell(self):
        block = ton(0.3)
        beginn = time.perf_counter()
        for _ in range(100):
            aufnahme.pegel(block)
        self.assertLess((time.perf_counter() - beginn) / 100, 0.005)  # unter 5 ms pro Block


class Einstellungen(unittest.TestCase):
    def setUp(self):
        self.ordner = tempfile.mkdtemp()
        self.datei = os.path.join(self.ordner, "config.json")

    def tearDown(self):
        shutil.rmtree(self.ordner, ignore_errors=True)

    def test_speichern_nur_aenderungen(self):
        with open(self.datei, "w") as fh:
            json.dump({"woerter": "Eigene Wörter"}, fh)
        einrichtung.speichern({"modus": "api", "taste": {"aktiv": False}}, self.datei)
        with open(self.datei) as fh:
            gespeichert = json.load(fh)
        self.assertEqual(gespeichert, {"woerter": "Eigene Wörter", "modus": "api",
                                       "taste": {"aktiv": False}})
        cfg = einstellungen.laden(self.datei)
        self.assertFalse(cfg["taste"]["aktiv"])
        self.assertEqual(cfg["taste"]["art"], "halten")  # Standard bleibt

    def test_falsche_werte_werden_nicht_gespeichert(self):
        with self.assertRaises(ValueError):
            einrichtung.speichern({"modus": "cloud"}, self.datei)
        with self.assertRaises(ValueError):
            einrichtung.speichern({"taste": {"aktiv": "ja"}}, self.datei)
        with self.assertRaises(ValueError):
            einrichtung.speichern({"lokal": {"endtext": "schnell"}}, self.datei)
        self.assertFalse(os.path.exists(self.datei))

    def test_kein_schluessel_in_config(self):
        with self.assertRaises(ValueError):
            einrichtung.speichern({"api": {"schluessel": "test-nur-attrappe"}}, self.datei)

    def test_autostart_an_und_aus(self):
        pfad = os.path.join(self.ordner, "autostart", "hufivoice.desktop")
        self.assertTrue(einrichtung.autostart_setzen(True, pfad))
        with open(pfad) as fh:
            inhalt = fh.read()
        self.assertIn("hufivoice.py", inhalt)
        self.assertIn("Exec=", inhalt)
        self.assertFalse(einrichtung.autostart_setzen(False, pfad))

    def test_mikrofone_lesen(self):
        text = ("Source #1\n\tName: alsa_output.pci.monitor\n\tDescription: Monitor of Speakers\n"
                "Source #2\n\tName: alsa_input.usb-046d_HD_Pro_Webcam_C920\n"
                "\tDescription: HD Pro Webcam C920 Analog Stereo\n")
        self.assertEqual(einrichtung.mikrofone_aus_text(text),
                         [("alsa_input.usb-046d_HD_Pro_Webcam_C920", "HD Pro Webcam C920 Analog Stereo")])


class FensterLogik(unittest.TestCase):
    """Reine Rechenteile des Fensters, ohne Bildschirm."""

    @classmethod
    def setUpClass(cls):
        try:
            from hufivoice import fenster
        except (ImportError, ValueError) as fehler:
            raise unittest.SkipTest(f"GTK fehlt: {fehler}")
        cls.f = fenster

    def test_status_arten(self):
        f = self.f
        self.assertEqual(f.status_art("Ich höre zu"), f.HOEREN)
        self.assertEqual(f.status_art("Schreibe …"), f.SCHREIBEN)
        self.assertEqual(f.status_art("Fertig"), f.FERTIG)
        self.assertEqual(f.status_art("Nichts verstanden"), f.FEHLER)

    def test_sanfte_kurve(self):
        self.assertEqual(self.f.sanft(0), 0)
        self.assertEqual(self.f.sanft(1), 1)
        self.assertGreater(self.f.sanft(0.5), 0.5)  # schnell los, weich ankommen

    def test_langer_text_wird_vorne_gekuerzt(self):
        lang = " ".join(["Wort"] * 100) + " Ende"
        k = self.f.kuerzen(lang, 60)
        self.assertTrue(k.startswith("… "))
        self.assertTrue(k.endswith("Ende"))
        self.assertLessEqual(len(k), 62)

    def test_runde_ecken(self):
        try:
            import cairo  # noqa: F401
        except ImportError:
            self.skipTest("python3-gi-cairo fehlt")
        r = self.f.runde_ecken_region(200, 80, 20)
        self.assertFalse(r.contains_point(0, 0))      # Ecke ist weg
        self.assertTrue(r.contains_point(100, 40))    # Mitte ist da
        self.assertTrue(r.contains_point(0, 40))



class PositionenOhneBildschirm(unittest.TestCase):
    def test_alle_positionen_bleiben_im_monitor(self):
        r = namedtuple("Rechteck", "x y width height")(100, 50, 1280, 720)
        for position in ("unten_mitte", "oben_mitte", "unten_rechts", "unten_links"):
            x, y = position_koordinaten(r, 360, 112, position, 40)
            self.assertGreaterEqual(x, r.x)
            self.assertGreaterEqual(y, r.y)
            self.assertLessEqual(x + 360, r.x + r.width)
            self.assertLessEqual(y + 112, r.y + r.height)


class SchnellesEinfuegen(unittest.TestCase):
    def cfg(self):
        with mock.patch.dict(os.environ, {"HUFIVOICE_CONFIG": "/gibt/es/nicht"}):
            return einstellungen.laden()

    def test_nach_loslassen_kein_xclip_lesen_mehr(self):
        """Alte Zwischenablage und Fenster werden schon während der Aufnahme gelesen."""
        aufrufe = []

        def lauf(befehl, eingabe=None, zeit=10):
            aufrufe.append(befehl[:2])
            return mock.Mock(returncode=0, stdout=b"xfce4-terminal" if "getactivewindow" in befehl else b"alt")
        with mock.patch.object(einfuegen, "_lauf", lauf), \
                mock.patch.object(einfuegen, "zwischenablage_setzen"):
            v = einfuegen.Vorbereitung(self.cfg())
            self.assertTrue(v.fertig())
            aufrufe.clear()
            art = einfuegen.einfuegen("Hallo", self.cfg(), v)
        self.assertEqual(art, "eingefügt mit ctrl+shift+v")  # Terminal erkannt
        self.assertEqual(aufrufe, [["xdotool", "key"]])        # nur noch die Tastenkombi


class TasteAbschaltbar(unittest.TestCase):
    def test_taste_aus_startet_keinen_waechter(self):
        import hufivoice as hv_paket  # noqa: F401
        sys.path.insert(0, APP)
        import importlib.util
        spec = importlib.util.spec_from_file_location("hv_haupt", os.path.join(APP, "hufivoice.py"))
        haupt = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(haupt)
        with mock.patch.dict(os.environ, {"HUFIVOICE_CONFIG": "/gibt/es/nicht"}):
            cfg = einstellungen.laden()
        cfg["taste"]["aktiv"] = False
        cfg["fenster"]["zeigen"] = False
        cfg["vorschau"] = False
        app = haupt.App(cfg)
        with mock.patch.dict(sys.modules, {"hufivoice.taste": None}), \
                mock.patch("hufivoice.steuerung.server_starten"), \
                mock.patch.object(threading.Event, "wait", return_value=None):
            app.laufen()  # würde beim Import von taste scheitern, wenn es weiterliefe


@unittest.skipUnless(MIT_BILDSCHIRM, "kein Bildschirm (DISPLAY)")
class FensterMitBildschirm(unittest.TestCase):
    def test_zeigen_pegel_und_ausblenden(self):
        from gi.repository import GLib, Gtk
        from hufivoice import fenster
        f = fenster.Fenster({"fenster": {"breite": 520}})
        f.zeigen("Ich höre zu", "Hallo Welt")
        for i in range(20):
            f.pegel(i / 20)
        sichtbar, pegel = [], []
        GLib.timeout_add(150, lambda: pegel.append(max(f._verlauf)) and False)
        GLib.timeout_add(400, lambda: sichtbar.append(f.w.get_visible()) or f.zeigen("Fertig", "Hallo Welt.", 0.2))
        GLib.timeout_add(1200, lambda: sichtbar.append(f.w.get_visible()) or Gtk.main_quit())
        Gtk.main()
        self.assertEqual(sichtbar, [True, False])   # erst da, dann sanft weg
        self.assertGreater(pegel[0], 0.1)            # Pegel kam an


@unittest.skipUnless(MIT_BILDSCHIRM and shutil.which("xclip") and shutil.which("xdotool"),
                     "kein Bildschirm oder xclip/xdotool fehlt")
class TempoMitBildschirm(unittest.TestCase):
    def test_einfuegen_unter_300_ms(self):
        with mock.patch.dict(os.environ, {"HUFIVOICE_CONFIG": "/gibt/es/nicht"}):
            cfg = einstellungen.laden()
        cfg["einfuegen"]["zwischenablage_zurueck"] = True
        v = einfuegen.Vorbereitung(cfg)
        v.fertig(3)
        beginn = time.monotonic()
        einfuegen.einfuegen("Tempotest", cfg, v)
        dauer = (time.monotonic() - beginn) * 1000
        print(f"\nEinfügen dauerte {dauer:.0f} ms")
        self.assertLess(dauer, 300)

    def test_ganzer_weg_ohne_erkennung_unter_300_ms(self):
        """Loslassen bis eingefügt, ohne die Zeit der Spracherkennung selbst."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("hv_haupt2", os.path.join(APP, "hufivoice.py"))
        haupt = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(haupt)
        with mock.patch.dict(os.environ, {"HUFIVOICE_CONFIG": "/gibt/es/nicht"}):
            cfg = einstellungen.laden()
        cfg["fenster"]["zeigen"], cfg["vorschau"] = False, False
        app = haupt.App(cfg)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fh:
            aufnahme.als_wav(ton(0.2, 1.0), fh.name)
        with mock.patch.dict(os.environ, {"HUFIVOICE_TESTDATEI": fh.name}), \
                mock.patch.object(haupt.erkennung, "transkribieren", return_value=("Hallo", "lokal")):
            app._vorbereiten()
            app._start()
            time.sleep(1.2)
            app._ende(time.monotonic())
        os.unlink(fh.name)
        print(f"\nZeiten: {app.zeiten}")
        self.assertLess(app.zeiten["rest_ms"], 300)


if __name__ == "__main__":
    unittest.main()
