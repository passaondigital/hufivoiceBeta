"""Einstellungsfenster: einfach und ruhig. Taste, Mikrofon, lokal oder API,
schneller Modus, Autostart. Speichert nur in ~/.hufi/voice/config.json."""
import os

os.environ.setdefault("GDK_BACKEND", "x11")

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk  # noqa: E402

from . import VERSION, einrichtung, einstellungen  # noqa: E402

CSS = b"""
window.hv { background-color: #0A0A0A; }
.hv * { font-family: Outfit, Inter, Cantarell, sans-serif; }
.hv label { color: #FFFFFF; }
.hv .titel { font-size: 26px; font-weight: 700; }
.hv .titel-orange { color: #E97824; }
.hv .unter { color: #A3A3A3; font-size: 14px; }
.hv .gruppe-titel { color: #A3A3A3; font-size: 13px; font-weight: 600; margin: 18px 6px 6px 6px; }
.hv .karte { background-color: #161616; border-radius: 16px; border: 1px solid rgba(255,255,255,0.08); }
.hv .zeile { padding: 12px 16px; }
.hv .trenner { background-color: rgba(255,255,255,0.08); min-height: 1px; margin: 0 16px; }
.hv .hilfe { color: #A3A3A3; font-size: 13px; }
.hv entry, .hv combobox button { background: #0A0A0A; color: #FFFFFF; border-radius: 10px; border: 1px solid rgba(255,255,255,0.15); padding: 6px 10px; box-shadow: none; }
.hv switch { background: #2A2A2A; border-radius: 999px; border: none; }
.hv switch:checked { background: #E97824; }
.hv switch slider { background: #FFFFFF; border-radius: 999px; min-width: 22px; min-height: 22px; border: none; }
.hv .segment button { background: #161616; color: #FFFFFF; border: 1px solid rgba(255,255,255,0.12); padding: 7px 16px; box-shadow: none; }
.hv .segment button:checked { background: #FFFFFF; color: #000000; }
.hv .segment button:checked label { color: #000000; }
.hv .segment button:first-child { border-radius: 999px 0 0 999px; }
.hv .segment button:last-child { border-radius: 0 999px 999px 0; }
.hv .knopf-orange { background: #E97824; color: #000000; border-radius: 999px; padding: 8px 22px; border: none; font-weight: 600; box-shadow: none; }
.hv .knopf-orange label { color: #000000; }
.hv .knopf-orange:hover { background: #D96D1D; }
.hv .knopf-leer { background: transparent; border-radius: 999px; padding: 8px 18px; border: 1px solid rgba(255,255,255,0.3); box-shadow: none; }
.hv .meldung { color: #E97824; font-size: 14px; }
.hv *:focus { outline-color: #E97824; }
"""

MODI = (("lokal", "Lokal"), ("server", "Eigener Server"), ("api", "API"))
MODUS_HILFE = {
    "lokal": "Nur auf diesem Rechner. Kein Internet nötig, nichts verlässt dein Gerät.",
    "server": "Die Aufnahme geht nur an deinen eigenen Whisper-Server. Fällt er aus, geht es lokal weiter.",
    "api": "Dienst mit eigenem Schlüssel. Der Schlüssel gehört in ~/.hufi/geheim/hufivoice_api_key "
           "(Rechte 600), nie in dieses Fenster.",
}


class EinstellungsFenster(Gtk.Window):
    def __init__(self, datei=None):
        super().__init__(title="HufiVoice Einstellungen")
        self.datei = datei
        self.cfg = einstellungen.laden(datei)
        self.get_style_context().add_class("hv")
        self.set_default_size(520, -1)
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_border_width(24)

        haupt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(haupt)
        kopf = Gtk.Label(xalign=0)
        kopf.set_markup('Hufi<span foreground="#E97824">Voice</span>')
        kopf.get_style_context().add_class("titel")
        haupt.pack_start(kopf, False, False, 0)
        unter = Gtk.Label(label=f"Einstellungen · Testversion {VERSION}", xalign=0)
        unter.get_style_context().add_class("unter")
        haupt.pack_start(unter, False, False, 4)

        # Taste
        t = self.cfg["taste"]
        self.taste_an = Gtk.Switch(active=t.get("aktiv", True), valign=Gtk.Align.CENTER)
        self.taste_art = self._segment((("halten", "Eine Taste"), ("super", "Super alt"),
                                        ("super+space", "Super + Leertaste")),
                                       t.get("art", "super"))
        self.taste_name = Gtk.ComboBoxText.new_with_entry()
        for name in ("Super_L", "Super_R", "Control_R", "Alt_R", "F9", "Menu"):
            self.taste_name.append(name, name)
        name = t.get("name", "Super_L")
        if not self.taste_name.set_active_id(name):
            self.taste_name.get_child().set_text(name)
        aufnehmen = Gtk.Button(label="Taste aufnehmen")
        aufnehmen.get_style_context().add_class("knopf-leer")
        aufnehmen.connect("clicked", self._taste_aufnehmen)
        self._taste_aufnahme = False
        self.connect("key-press-event", self._taste_empfangen)
        self._gruppe(haupt, "TASTE", [
            self._zeile("Taste aktiv", self.taste_an, "Aus: HufiVoice reagiert auf keine Taste."),
            self._zeile("Tasten-Art", self.taste_art),
            self._zeile("Welche Taste", self.taste_name, "Vorschlag wählen oder X11-Namen eingeben."),
            self._zeile("Neue Taste", aufnehmen, "Klicken und danach die gewünschte Taste drücken."),
        ])

        # Mikrofon
        self.mikro = Gtk.ComboBoxText()
        self.mikro.append("auto", "Automatisch (Webcam C920 zuerst)")
        for name, beschr in einrichtung.mikrofone():
            self.mikro.append(name, beschr)
        if not self.mikro.set_active_id(self.cfg.get("mikrofon", "auto")):
            self.mikro.append(self.cfg.get("mikrofon"), self.cfg.get("mikrofon"))
            self.mikro.set_active_id(self.cfg.get("mikrofon"))
        self._gruppe(haupt, "MIKROFON", [self._zeile("Mikrofon", self.mikro)])

        # Erkennung
        self.modus = self._segment(MODI, self.cfg["modus"])
        self.modus_hilfe = Gtk.Label(xalign=0, wrap=True, max_width_chars=52)
        self.modus_hilfe.get_style_context().add_class("hilfe")
        self.server_url = Gtk.Entry(text=self.cfg["server"].get("url", ""), hexpand=True)
        self.server_zeile = self._zeile("Server-Adresse", self.server_url)
        self.schnell = Gtk.Switch(active=self.cfg["lokal"].get("endtext") == "vosk",
                                  valign=Gtk.Align.CENTER)
        modus_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        modus_box.get_style_context().add_class("zeile")
        modus_box.pack_start(self.modus, False, False, 0)
        modus_box.pack_start(self.modus_hilfe, False, False, 0)
        self._gruppe(haupt, "ERKENNUNG", [
            modus_box, self.server_zeile,
            self._zeile("Schneller Modus", self.schnell,
                        "Für langsame Rechner: Text sofort, dafür etwas ungenauer."),
        ])

        # Start
        self.auto = Gtk.Switch(active=einrichtung.autostart_ist_an(), valign=Gtk.Align.CENTER)
        self._gruppe(haupt, "START", [self._zeile("Beim Anmelden starten", self.auto)])

        # Knöpfe
        unten = Gtk.Box(spacing=10, margin_top=22)
        self.meldung = Gtk.Label(xalign=0, hexpand=True, wrap=True, max_width_chars=30)
        self.meldung.get_style_context().add_class("meldung")
        zu = Gtk.Button(label="Schließen")
        zu.get_style_context().add_class("knopf-leer")
        zu.connect("clicked", lambda *_: self.close())
        sichern = Gtk.Button(label="Speichern")
        sichern.get_style_context().add_class("knopf-orange")
        sichern.connect("clicked", self._speichern)
        unten.pack_start(self.meldung, True, True, 0)
        unten.pack_end(sichern, False, False, 0)
        unten.pack_end(zu, False, False, 0)
        haupt.pack_start(unten, False, False, 0)
        self._modus_geaendert()

    # ---------- Bausteine ----------
    def _segment(self, wahl, aktiv):
        box = Gtk.Box(spacing=0, halign=Gtk.Align.START)
        box.get_style_context().add_class("segment")
        box.knoepfe = {}
        erster = None
        for wert, text in wahl:
            k = Gtk.RadioButton.new_with_label_from_widget(erster, text)
            k.set_mode(False)  # sieht aus wie ein Knopf
            erster = erster or k
            k.set_active(wert == aktiv)
            k.connect("toggled", lambda *_: self._modus_geaendert())
            box.knoepfe[wert] = k
            box.pack_start(k, False, False, 0)
        return box

    @staticmethod
    def _wert(segment):
        return next(w for w, k in segment.knoepfe.items() if k.get_active())

    def _zeile(self, titel, widget, hilfe=None):
        zeile = Gtk.Box(spacing=16)
        zeile.get_style_context().add_class("zeile")
        links = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, valign=Gtk.Align.CENTER)
        links.pack_start(Gtk.Label(label=titel, xalign=0), False, False, 0)
        if hilfe:
            h = Gtk.Label(label=hilfe, xalign=0, wrap=True, max_width_chars=34)
            h.get_style_context().add_class("hilfe")
            links.pack_start(h, False, False, 0)
        zeile.pack_start(links, True, True, 0)
        zeile.pack_end(widget, False, False, 0)
        return zeile

    def _gruppe(self, haupt, titel, zeilen):
        t = Gtk.Label(label=titel, xalign=0)
        t.get_style_context().add_class("gruppe-titel")
        haupt.pack_start(t, False, False, 0)
        karte = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        karte.get_style_context().add_class("karte")
        for i, z in enumerate(zeilen):
            if i:
                trenner = Gtk.Box()
                trenner.get_style_context().add_class("trenner")
                karte.pack_start(trenner, False, False, 0)
            karte.pack_start(z, False, False, 0)
        haupt.pack_start(karte, False, False, 0)

    # ---------- Verhalten ----------
    def _modus_geaendert(self):
        if not hasattr(self, "modus_hilfe"):
            return
        m = self._wert(self.modus)
        self.modus_hilfe.set_text(MODUS_HILFE[m])
        if hasattr(self, "server_zeile"):
            self.server_zeile.set_visible(m == "server")
            self.server_zeile.set_no_show_all(m != "server")

    def _taste_aufnehmen(self, *_):
        self._taste_aufnahme = True
        self.meldung.set_text("Jetzt eine Taste drücken …")
        self.present()

    def _taste_empfangen(self, _fenster, ereignis):
        if not self._taste_aufnahme:
            return False
        name = Gdk.keyval_name(ereignis.keyval)
        if name:
            if not self.taste_name.set_active_id(name):
                self.taste_name.get_child().set_text(name)
            self.taste_art.knoepfe["halten"].set_active(True)
            self.meldung.set_text(f"Taste aufgenommen: {name}")
        self._taste_aufnahme = False
        return True

    def werte(self):
        return {
            "modus": self._wert(self.modus),
            "mikrofon": self.mikro.get_active_id() or "auto",
            "taste": {"aktiv": self.taste_an.get_active(), "art": self._wert(self.taste_art),
                      "name": self.taste_name.get_child().get_text().strip() or "Super_L",
                      "abbruch": self.cfg["taste"].get("abbruch", "Escape")},
            "lokal": {"endtext": "vosk" if self.schnell.get_active() else "whisper"},
            "server": {"url": self.server_url.get_text().strip()},
        }

    def _speichern(self, *_):
        try:
            einrichtung.speichern(self.werte(), self.datei)
            einrichtung.autostart_setzen(self.auto.get_active())
            self.meldung.set_text("Gespeichert. Gilt nach dem nächsten Start von HufiVoice.")
        except (ValueError, OSError) as fehler:
            self.meldung.set_text(f"Nicht gespeichert: {fehler}")


def css_laden():
    anbieter = Gtk.CssProvider()
    anbieter.load_from_data(CSS)
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), anbieter,
                                             Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    Gtk.Settings.get_default().set_property("gtk-application-prefer-dark-theme", True)


def starten(datei=None):
    css_laden()
    f = EinstellungsFenster(datei)
    f.connect("destroy", Gtk.main_quit)
    f.show_all()
    f._modus_geaendert()
    Gtk.main()
    return 0
