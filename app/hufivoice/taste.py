"""Globale Taste beobachten (X11, XFCE). Nutzt die RECORD-Erweiterung: wir
lauschen nur mit und nehmen der Super-Taste nichts weg.

art "super":        Super halten = zuhören, loslassen = einfügen.
                    Kurz tippen = Menü (macht HufiVoice dann selbst).
                    Super plus andere Taste (z. B. Super+E) = nichts tun.
art "super+space":  Super gedrückt halten und Leertaste halten = zuhören.
                    Eine von beiden loslassen = einfügen. Die Kombi wird
                    abgefangen, damit kein Leerzeichen im Fenster landet.
art "halten":       Die in taste.name gewählte X11-Taste halten. Kurz tippen
                    öffnet nur bei Super_L/Super_R das Menü. Eine zusätzliche
                    Taste macht daraus eine normale Tastenkombination.

Ereignisse gehen als Wörter in eine Warteschlange:
vorbereiten, start, ende, abbruch, tippen."""
import threading
import time

try:
    from Xlib import X, XK, display
    from Xlib.ext import record
    from Xlib.protocol import rq
except ImportError:  # Reine Logiktests laufen auch auf Rechnern ohne python3-xlib.
    X = XK = display = record = rq = None

ENTPRELLEN_S = 0.06  # automatische Tastenwiederholung herausfiltern


class TastenWaechter:
    def __init__(self, art, halten_ms, schlange, name="Super_L", abbruch="Escape"):
        if display is None:
            raise RuntimeError("python3-xlib fehlt")
        self.art = art
        self.halten_s = halten_ms / 1000.0
        self.q = schlange
        self._lesen = display.Display()
        self._steuer = display.Display()
        self.super_codes = {self._lesen.keysym_to_keycode(XK.string_to_keysym(n))
                            for n in ("Super_L", "Super_R")} - {0}
        self.space_code = self._lesen.keysym_to_keycode(XK.XK_space)
        self.tasten_name = name or "Super_L"
        self.tasten_code = self._code(self.tasten_name)
        self.abbruch_code = self._code(abbruch) if abbruch else 0
        if self.art == "halten" and not self.tasten_code:
            raise ValueError(f"Unbekannte X11-Taste: {self.tasten_name}")
        self.unten = set()
        self.andere = False
        self.aktiv = False
        self.vorbereitet = False
        self._halten_uhr = None
        self._los_uhren = {}
        self._sperre = threading.Lock()
        self._kontext = None

    def _code(self, name):
        return self._lesen.keysym_to_keycode(XK.string_to_keysym(name)) if name else 0

    # ---------- Zustand ----------
    def _melde(self, wort):
        self.q.put(wort)

    def _super_unten(self):
        return bool(self.unten & self.super_codes)

    def _ausloeser_codes(self):
        return self.super_codes if self.art in ("super", "super+space") else {self.tasten_code}

    def _ausloeser_unten(self):
        return bool(self.unten & self._ausloeser_codes())

    def _vorbereiten_halten(self):
        self.andere = False
        self.vorbereitet = True
        self._melde("vorbereiten")
        self._halten_uhr = threading.Timer(self.halten_s, self._lang_gehalten)
        self._halten_uhr.start()

    def _gedrueckt(self, code):
        uhr = self._los_uhren.pop(code, None)
        if uhr:            # war nur Wiederholung: Loslassen vergessen
            uhr.cancel()
            return
        if code in self.unten:
            return
        self.unten.add(code)
        if code in self._ausloeser_codes():
            if self.art == "halten":
                if len(self.unten & self._ausloeser_codes()) == 1 and len(self.unten) == 1:
                    self._vorbereiten_halten()
                return
            if len(self.unten & self.super_codes) == 1 and len(self.unten) == 1:
                self.andere = False
                if self.art == "super":
                    self._vorbereiten_halten()  # Mikrofon schon an, damit kein Wort fehlt
            return
        if self.art == "halten":
            if not self._ausloeser_unten():
                return
            # Escape verwirft ausdrücklich; jede andere zweite Taste bleibt eine normale Kombi.
            self.andere = True
            self._abbrechen()
            return
        if not self._super_unten():
            return
        if self.art == "super+space" and code == self.space_code and not self.aktiv:
            self.aktiv = True
            self._melde("vorbereiten")
            self._melde("start")
            return
        # andere Taste zusammen mit Super: das ist eine normale Tastenkombi
        self.andere = True
        self._abbrechen()

    def _lang_gehalten(self):
        with self._sperre:
            if self._ausloeser_unten() and not self.andere and not self.aktiv:
                self.aktiv = True
                self._melde("start")

    def _abbrechen(self):
        if self._halten_uhr:
            self._halten_uhr.cancel()
        if self.aktiv or self.vorbereitet:
            self._melde("abbruch")
        self.aktiv = False
        self.vorbereitet = False

    def _losgelassen(self, code):
        if code not in self.unten:
            return
        uhr = threading.Timer(ENTPRELLEN_S, self._wirklich_los, args=(code, time.monotonic()))
        self._los_uhren[code] = uhr
        uhr.start()

    def _ende_melden(self, los_zeit):
        try:
            self.q.zeit_ende = los_zeit  # echter Zeitpunkt des Loslassens, für die Zeitmessung
        except AttributeError:
            pass
        self._melde("ende")

    def _wirklich_los(self, code, los_zeit=None):
        with self._sperre:
            self._los_uhren.pop(code, None)
            self.unten.discard(code)
            ist_super = code in self.super_codes
            ist_ausloeser = code in self._ausloeser_codes()
            if self.art == "halten" and ist_ausloeser and not self._ausloeser_unten():
                if self._halten_uhr:
                    self._halten_uhr.cancel()
                if self.aktiv:
                    self._ende_melden(los_zeit)
                elif not self.andere:
                    if self.vorbereitet:
                        self._melde("abbruch")
                    if self.tasten_name in ("Super_L", "Super_R"):
                        self._melde("tippen")
                self.aktiv = self.vorbereitet = False
                return
            if self.art == "super" and ist_super and not self._super_unten():
                if self._halten_uhr:
                    self._halten_uhr.cancel()
                if self.aktiv:
                    self._ende_melden(los_zeit)
                elif not self.andere:
                    if self.vorbereitet:
                        self._melde("abbruch")
                    self._melde("tippen")
                self.aktiv = self.vorbereitet = False
            elif self.art == "super+space" and self.aktiv and (ist_super or code == self.space_code):
                self._ende_melden(los_zeit)
                self.aktiv = False

    # ---------- X11 ----------
    def _rueckruf(self, antwort):
        if antwort.category != record.FromServer or antwort.client_swapped:
            return
        daten = antwort.data
        while daten:
            ereignis, daten = rq.EventField(None).parse_binary_value(
                daten, self._lesen.display, None, None)
            with self._sperre:
                if ereignis.type == X.KeyPress:
                    self._gedrueckt(ereignis.detail)
                elif ereignis.type == X.KeyRelease:
                    self._losgelassen(ereignis.detail)

    def _kombi_abfangen(self):
        """Super+Leertaste festhalten, damit kein Leerzeichen getippt wird."""
        abfang = display.Display()
        wurzel = abfang.screen().root
        for zusatz in (0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask):
            wurzel.grab_key(self.space_code, X.Mod4Mask | zusatz, True,
                            X.GrabModeAsync, X.GrabModeAsync)
        abfang.sync()
        while True:
            abfang.next_event()  # Ereignisse wegwerfen, RECORD sieht sie trotzdem

    def laufen(self):
        if not self._lesen.has_extension("RECORD"):
            raise RuntimeError("X-Server ohne RECORD-Erweiterung")
        if self.art == "super+space":
            threading.Thread(target=self._kombi_abfangen, daemon=True).start()
        self._kontext = self._steuer.record_create_context(0, [record.AllClients], [{
            "core_requests": (0, 0), "core_replies": (0, 0),
            "ext_requests": (0, 0, 0, 0), "ext_replies": (0, 0, 0, 0),
            "delivered_events": (0, 0), "device_events": (X.KeyPress, X.KeyRelease),
            "errors": (0, 0), "client_started": False, "client_died": False}])
        self._steuer.sync()  # Kontext muss beim X-Server angekommen sein
        try:
            self._lesen.record_enable_context(self._kontext, self._rueckruf)
        finally:
            self._lesen.record_free_context(self._kontext)
