"""Live-Fenster im ruhigen Apple-Stil: abgerundet, halbtransparent dunkel,
orange Pegelanzeige, weiche Ein- und Ausblendung, klare Statuszeile.

Nimmt nie den Fokus weg, damit der Text im richtigen Fenster landet.
Läuft auch ohne Compositor (dann ohne Transparenz, aber mit runden Ecken).
Unter Wayland wird gtk-layer-shell benutzt, falls es vorhanden ist. Sonst fällt
das Fenster mit einem klaren Hinweis auf XWayland zurück."""
import math
import os
import threading
import time

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("PangoCairo", "1.0")
LAYER_SHELL_VERFUEGBAR = False
if os.environ.get("WAYLAND_DISPLAY"):
    try:
        gi.require_version("GtkLayerShell", "0.1")
        LAYER_SHELL_VERFUEGBAR = True
    except (ValueError, ImportError):
        os.environ["GDK_BACKEND"] = "x11"
        print("Wayland erkannt, aber gtk-layer-shell fehlt; nutze XWayland (GDK_BACKEND=x11).",
              flush=True)
else:
    os.environ.setdefault("GDK_BACKEND", "x11")
from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo  # noqa: E402
if LAYER_SHELL_VERFUEGBAR:
    from gi.repository import GtkLayerShell  # noqa: E402
from .fenster_logik import position_koordinaten  # noqa: E402

ORANGE = (0xF9 / 255, 0x73 / 255, 0x16 / 255)
HOEHE_KOPF = 34
RADIUS = 22
ROHR = 18          # Innenabstand
BALKEN = 14        # Anzahl Pegel-Balken
WELLEN_BALKEN = 9
WELLEN_FORM = (0.3, 0.7, 1.0, 0.85, 0.5, 0.9, 0.4, 0.7, 0.3)
SCHRIFT = "Outfit, Inter, Cantarell, sans-serif"

# Statusarten: steuert Farbe, Punkt und Bewegung
HOEREN, SCHREIBEN, FERTIG, FEHLER = "hoeren", "schreiben", "fertig", "fehler"


def status_art(status):
    s = status.lower()
    if s.startswith("ich höre"):
        return HOEREN
    if s.startswith("schreibe") or s.startswith("denke"):
        return SCHREIBEN
    if s.startswith("fertig"):
        return FERTIG
    return FEHLER


def sanft(t):
    """Weiche Kurve (ease-out cubic) für Bewegungen, t von 0 bis 1."""
    t = min(1.0, max(0.0, t))
    return 1 - (1 - t) ** 3


def kuerzen(text, max_zeichen=180):
    """Nur das Ende langer Texte zeigen, damit das Fenster ruhig bleibt."""
    text = " ".join((text or "").split())
    if len(text) <= max_zeichen:
        return text
    rest = text[-max_zeichen:]
    leer = rest.find(" ")
    return "… " + (rest[leer + 1:] if 0 <= leer < 30 else rest)


def runde_ecken_region(breite, hoehe, radius):
    """Rechtecke, die zusammen ein Rechteck mit runden Ecken ergeben.
    Für Bildschirme ohne Compositor (dort gibt es keine Transparenz)."""
    import cairo
    teile = []
    for y in range(radius):
        dy = radius - y - 0.5
        einzug = int(round(radius - math.sqrt(max(0.0, radius * radius - dy * dy))))
        teile.append(cairo.RectangleInt(einzug, y, breite - 2 * einzug, 1))
        teile.append(cairo.RectangleInt(einzug, hoehe - 1 - y, breite - 2 * einzug, 1))
    teile.append(cairo.RectangleInt(0, radius, breite, max(0, hoehe - 2 * radius)))
    return cairo.Region(teile)


class Fenster:
    def __init__(self, cfg):
        f = cfg.get("fenster", {})
        self.breite = int(f.get("breite", 520))
        self.stil = f.get("stil", "welle")
        if self.stil == "welle" and "breite" not in f:
            self.breite = 360
        self.position = f.get("position", "unten_mitte")
        self.bildschirm = f.get("bildschirm", "maus")
        self.abstand = int(f.get("abstand_unten", 90))
        self.bewegung = bool(f.get("animation", True))
        self.deckkraft = float(f.get("deckkraft", 0.86))
        self._status, self._text, self._art = "HufiVoice", "", HOEREN
        self._pegel_ziel = 0.0
        self._verlauf = [0.0] * BALKEN
        self._welle = [0.0] * WELLEN_BALKEN
        self._sperre = threading.Lock()
        self._weg_uhr = None
        self._takt = None
        self._blende = 0.0       # 0 = unsichtbar, 1 = ganz da
        self._blende_ziel = 0.0
        self._start = time.monotonic()

        self.w = Gtk.Window(type=Gtk.WindowType.POPUP)
        self.w.set_name("hufivoice")
        self.w.set_title("HufiVoice")
        self.w.set_accept_focus(False)
        self.w.set_focus_on_map(False)
        self.w.set_keep_above(True)
        self.w.set_skip_taskbar_hint(True)
        self.w.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
        self.w.set_app_paintable(True)
        self.w.connect("realize", self._realisiert)
        self.layer_shell = bool(LAYER_SHELL_VERFUEGBAR and os.environ.get("WAYLAND_DISPLAY"))
        if self.layer_shell:
            GtkLayerShell.init_for_window(self.w)
            GtkLayerShell.set_layer(self.w, GtkLayerShell.Layer.OVERLAY)
            GtkLayerShell.set_keyboard_mode(self.w, GtkLayerShell.KeyboardMode.NONE)
        bild = self.w.get_screen()
        self.durchsichtig = bild.is_composited() and bild.get_rgba_visual() is not None
        if self.durchsichtig:
            self.w.set_visual(bild.get_rgba_visual())
        self.flaeche = Gtk.DrawingArea()
        self.flaeche.connect("draw", self._malen)
        self.w.add(self.flaeche)
        self.hoehe = 112 if self.stil == "welle" else self._hoehe_fuer("")
        self.w.set_default_size(self.breite, self.hoehe)

    # ---------- Größe und Platz ----------
    def _layout(self, cr_oder_widget, text, groesse=13.5):
        if hasattr(cr_oder_widget, "create_pango_layout"):
            lay = cr_oder_widget.create_pango_layout(text)
        else:
            lay = PangoCairo.create_layout(cr_oder_widget)
            lay.set_text(text, -1)
        lay.set_font_description(Pango.FontDescription(f"{SCHRIFT} {groesse}"))
        lay.set_width((self.breite - 2 * ROHR) * Pango.SCALE)
        lay.set_wrap(Pango.WrapMode.WORD_CHAR)
        return lay

    def _hoehe_fuer(self, text):
        if self.stil == "welle":
            return 112
        lay = self._layout(self.flaeche, kuerzen(text) or " ")
        lay.set_height(-3)  # höchstens 3 Zeilen
        lay.set_ellipsize(Pango.EllipsizeMode.START)
        _, log = lay.get_pixel_extents()
        return ROHR + HOEHE_KOPF + max(log.height, 22) + ROHR

    def _platz(self, versatz=0):
        anzeige = Gdk.Display.get_default()
        monitor = None
        if self.bildschirm == "maus":
            try:
                _bild, x, y = anzeige.get_default_seat().get_pointer().get_position()
                monitor = anzeige.get_monitor_at_point(x, y)
            except (AttributeError, TypeError):
                pass
        monitor = monitor or anzeige.get_primary_monitor() or anzeige.get_monitor(0)
        r = monitor.get_workarea() if hasattr(monitor, "get_workarea") else monitor.get_geometry()
        x, y = position_koordinaten(r, self.breite, self.hoehe, self.position, self.abstand)
        if self.layer_shell:
            GtkLayerShell.set_monitor(self.w, monitor)
            oben = self.position == "oben_mitte"
            GtkLayerShell.set_anchor(self.w, GtkLayerShell.Edge.TOP, oben)
            GtkLayerShell.set_anchor(self.w, GtkLayerShell.Edge.BOTTOM, not oben)
            GtkLayerShell.set_anchor(self.w, GtkLayerShell.Edge.LEFT,
                                     self.position in ("unten_links",))
            GtkLayerShell.set_anchor(self.w, GtkLayerShell.Edge.RIGHT,
                                     self.position in ("unten_rechts",))
            GtkLayerShell.set_margin(self.w,
                                     GtkLayerShell.Edge.TOP if oben else GtkLayerShell.Edge.BOTTOM,
                                     self.abstand + int(versatz))
        else:
            self.w.move(x, y + int(versatz))

    def _realisiert(self, *_):
        """Leere Eingaberegion: Mausklicks gehen an das Fenster darunter."""
        try:
            import cairo
            self.w.input_shape_combine_region(cairo.Region())
        except (ImportError, AttributeError, TypeError):
            if self.w.get_window():
                try:
                    import cairo
                    self.w.get_window().input_shape_combine_region(cairo.Region(), 0, 0)
                except (ImportError, AttributeError, TypeError):
                    pass

    def _form(self):
        if not self.durchsichtig and self.w.get_window():
            self.w.get_window().shape_combine_region(
                runde_ecken_region(self.breite, self.hoehe, RADIUS), 0, 0)

    # ---------- Malen ----------
    def _malen(self, _w, cr):
        b, h = self.breite, self.hoehe
        cr.set_operator(0)  # CLEAR
        cr.paint()
        cr.set_operator(2)  # OVER
        cr.new_sub_path()
        for wx, wy, a in ((b - RADIUS, RADIUS, -90), (b - RADIUS, h - RADIUS, 0),
                          (RADIUS, h - RADIUS, 90), (RADIUS, RADIUS, 180)):
            cr.arc(wx, wy, RADIUS, math.radians(a), math.radians(a + 90))
        cr.close_path()
        cr.set_source_rgba(0.04, 0.04, 0.04, self.deckkraft if self.durchsichtig else 1.0)
        cr.fill_preserve()
        cr.set_source_rgba(1, 1, 1, 0.09)
        cr.set_line_width(1)
        cr.stroke()

        with self._sperre:
            status, text, art = self._status, self._text, self._art
            verlauf = list(self._verlauf)
        jetzt = time.monotonic() - self._start
        if self.stil == "welle":
            self._welle_malen(cr, art, jetzt)
            return False
        # Punkt oder Haken
        px, py = ROHR + 6, ROHR + 9
        if art == FERTIG:
            cr.set_source_rgb(*ORANGE)
            cr.set_line_width(2.6)
            cr.set_line_cap(1)
            cr.move_to(px - 6, py)
            cr.line_to(px - 1.5, py + 4.5)
            cr.line_to(px + 6, py - 5)
            cr.stroke()
        else:
            puls = 0.5 + 0.5 * math.sin(jetzt * 5.2) if art == HOEREN and self.bewegung else 1.0
            if art == SCHREIBEN and self.bewegung:  # drehender Bogen
                cr.set_source_rgb(*ORANGE)
                cr.set_line_width(2.4)
                cr.arc(px, py, 6, jetzt * 6, jetzt * 6 + 4.2)
                cr.stroke()
            else:
                cr.set_source_rgba(*(ORANGE if art != FEHLER else (1, 1, 1)), 0.55 + 0.45 * puls)
                cr.arc(px, py, 4 + 1.5 * puls, 0, 2 * math.pi)
                cr.fill()
        # Statuszeile
        lay = self._layout(cr, status, 11)
        lay.set_width(-1)
        attr = Pango.FontDescription(f"{SCHRIFT} Semi-Bold 11")
        lay.set_font_description(attr)
        cr.set_source_rgb(*(ORANGE if art != FEHLER else (1, 1, 1)))
        cr.move_to(ROHR + 20, ROHR - 1)
        PangoCairo.show_layout(cr, lay)
        # Pegel: orange Balken rechts oben, nur beim Zuhören
        if art == HOEREN:
            bx = b - ROHR - BALKEN * 6
            for i, wert in enumerate(verlauf):
                hoehe = 4 + 16 * wert
                cr.set_source_rgba(*ORANGE, 0.5 + 0.5 * min(1.0, wert * 1.4))
                x, y = bx + i * 6, ROHR + 9 - hoehe / 2
                cr.rectangle(x, y, 3, hoehe)
                cr.fill()
        # Text
        lay = self._layout(cr, kuerzen(text) or ("…" if art == HOEREN else ""), 13.5)
        lay.set_height(-3)
        lay.set_ellipsize(Pango.EllipsizeMode.START)
        cr.set_source_rgba(1, 1, 1, 0.96)
        cr.move_to(ROHR, ROHR + HOEHE_KOPF - 4)
        PangoCairo.show_layout(cr, lay)
        return False

    def _welle_malen(self, cr, art, jetzt):
        """Große mittige Neun-Balken-Welle für Aufnahme und Verarbeitung."""
        with self._sperre:
            werte = list(self._welle)
        mitte_x, mitte_y = self.breite / 2, self.hoehe / 2
        if art == FERTIG:
            cr.set_source_rgb(*ORANGE)
            cr.set_line_width(7)
            cr.set_line_cap(1)
            cr.move_to(mitte_x - 18, mitte_y)
            cr.line_to(mitte_x - 5, mitte_y + 14)
            cr.line_to(mitte_x + 24, mitte_y - 18)
            cr.stroke()
            return
        for i, form in enumerate(WELLEN_FORM):
            if art == SCHREIBEN:
                wert = 0.28 + 0.72 * (0.5 + 0.5 * math.sin(jetzt * 2.8 - i * 0.75))
            else:
                wert = max(0.12, werte[i])
            hoehe = 12 + 58 * form * wert
            x = mitte_x + (i - 4) * 25
            if art == FEHLER:
                cr.set_source_rgba(0.72, 0.2, 0.18, 0.72)
            else:
                cr.set_source_rgba(*ORANGE, 0.92)
            cr.set_line_width(12)
            cr.set_line_cap(1)
            cr.move_to(x, mitte_y - hoehe / 2)
            cr.line_to(x, mitte_y + hoehe / 2)
            cr.stroke()

    # ---------- Takt: Pegel glätten, Ein- und Ausblenden ----------
    def _tick(self):
        with self._sperre:
            ziel = self._pegel_ziel
            letzter = self._verlauf[-1]
            neu = letzter + (ziel - letzter) * 0.5
            self._verlauf = self._verlauf[1:] + [neu]
            self._welle = [alt + (ziel * form - alt) * 0.42
                           for alt, form in zip(self._welle, WELLEN_FORM)]
            self._pegel_ziel *= 0.85
        schritt = 1 / 9 if self._blende_ziel > self._blende else 1 / 12   # ~150 ms rein, ~200 ms raus
        if self._blende != self._blende_ziel:
            self._blende = min(1.0, self._blende + schritt) if self._blende_ziel > self._blende \
                else max(0.0, self._blende - schritt)
            k = sanft(self._blende)
            if self.durchsichtig:
                self.w.set_opacity(k)
            self._platz(versatz=(1 - k) * 10)
            if self._blende <= 0.0:
                self.w.hide()
                self._takt = None
                return False
        self.flaeche.queue_draw()
        return True

    def _takt_an(self):
        if self._takt is None:
            self._takt = GLib.timeout_add(16 if self.bewegung else 100, self._tick)

    # ---------- von außen (aus jedem Thread) ----------
    def pegel(self, wert):
        with self._sperre:
            self._pegel_ziel = max(self._pegel_ziel, min(1.0, max(0.0, wert)))

    def zeigen(self, status, text="", weg_nach_s=None):
        def tun():
            if self._weg_uhr:
                GLib.source_remove(self._weg_uhr)
                self._weg_uhr = None
            with self._sperre:
                self._status, self._text, self._art = status, text or "", status_art(status)
            hoehe = self._hoehe_fuer(text)
            if hoehe != self.hoehe or not self.w.get_visible():
                self.hoehe = hoehe
                self.w.resize(self.breite, self.hoehe)
                self.flaeche.set_size_request(self.breite, self.hoehe)
            if not self.w.get_visible():
                self._blende = 0.0 if self.bewegung else 1.0
                if self.durchsichtig:
                    self.w.set_opacity(sanft(self._blende))
                self._platz(versatz=(1 - sanft(self._blende)) * 10)
                self.w.show_all()
            else:
                self._platz(versatz=(1 - sanft(self._blende)) * 10)
            self._form()
            self._blende_ziel = 1.0
            self._takt_an()
            if weg_nach_s:
                self._weg_uhr = GLib.timeout_add(int(weg_nach_s * 1000), self._weg)
            return False
        GLib.idle_add(tun)

    def _weg(self):
        self._weg_uhr = None
        if not self.bewegung:
            self.w.hide()
            return False
        self._blende_ziel = 0.0
        self._takt_an()
        return False

    def verstecken(self):
        GLib.idle_add(self._weg)


def hauptschleife():
    Gtk.main()


def beenden():
    GLib.idle_add(Gtk.main_quit)
