# HufiVoice für Linux (Testversion 0.2)

Standard am Linux-Tower: linke Windows-Taste (`Super_L`) halten = zuhören.
Loslassen = Text steht im aktiven Fenster. Kurz tippen = Startmenü wie immer.
Die Logitech C920 wird bei „Mikrofon: Automatisch“ bevorzugt.

## Dateien
- `hufivoice.py` startet alles. `--pruefen` zeigt, ob alles da ist. `--datei a.wav` testet ohne Mikrofon. `--einstellungen` öffnet das Einstellungsfenster. `--start` und `--stopp` steuern eine laufende Instanz.
- `config.json` Standard-Einstellungen. Eigene Werte gehören nach `~/.hufi/voice/config.json`.
- `hufivoice/` Bausteine: `taste.py` (Super-Taste), `aufnahme.py` (Mikrofon), `erkennung.py` (Vosk, Whisper, Server, API), `einfuegen.py` (xclip und xdotool), `fenster.py` (Live-Fenster: dunkle runde Pille, orange Pegel, weiches Ein- und Ausblenden), `einstellungen_fenster.py` (Einstellungsfenster), `einrichtung.py` (Einstellungen speichern, Autostart, Mikrofone).
- `schrift/` Outfit (OFL-Lizenz) für die Fenster. `hufivoice-einstellungen.desktop` Menüeintrag.
- `install.sh`, `build-whisper.sh`, `uninstall.sh`.
- `tests/` Tests ohne Mikrofon.

## Modus umschalten
In `~/.hufi/voice/config.json`:
- `"modus": "lokal"` Box zu. Whisper läuft auf dem Rechner (ohne AVX gebaut).
- `"modus": "server"` eigener Whisper-Server. `server.url` und `server.feldname` passend setzen
  (HufiBeta-Server: Feld `audio`, Hufi Desktop: Feld `file`). Antwort `{"text": ...}` oder `{"transcript": ...}`.
- `"modus": "api"` OpenAI-kompatible API. Schlüssel NUR in der Umgebungsvariable `HUFIVOICE_API_KEY`
  oder in der Datei `~/.hufi/geheim/hufivoice_api_key` (Rechte 600). Nie in config.json.
  Neue Konfigurationen nutzen `gpt-transcribe`; alte `whisper-1`-Konfigurationen werden weiterhin gelesen.

Langsamer Rechner? `"lokal": {"endtext": "vosk"}` nimmt sofort den Vorschau-Text (schnell, ungenauer).
Genauer? `HUFIVOICE_MODELL=small-q5_1 bash build-whisper.sh` und `whisper_modell` anpassen.

## Welle, Taste und Position (Testkopie)
- `taste.art: "halten"` nutzt `taste.name`, standardmäßig `Super_L`. Vorschläge: `Super_R`, `Control_R`, `Alt_R`, `F9`, `Menu`.
- `taste.abbruch: "Escape"` verwirft die laufende Aufnahme. Alte Werte `super` und `super+space` bleiben gültig.
- Im Einstellungsfenster nimmt „Taste aufnehmen“ den nächsten Tastendruck auf.
- `fenster.stil` ist `welle` (Standard) oder `pille`. Die Welle hat neun orange, runde Balken und reagiert auf den echten Mikrofonpegel.
- `fenster.position`: `unten_mitte`, `oben_mitte`, `unten_rechts` oder `unten_links`.
- `fenster.bildschirm`: `maus` wählt den Monitor mit dem Mauszeiger, `haupt` den Hauptmonitor.
- `fenster.animation` (true/false) schaltet das Gleiten und Blenden ab. `fenster.deckkraft` (0.86) steuert den Hintergrund.
- Ohne Compositor bekommt das Fenster runde Ecken über eine Form-Maske (kein Glas, aber rund).
- Fensterklasse und alte Zwischenablage werden schon während der Aufnahme gelesen. Nach dem Loslassen
  bleiben nur Text setzen, Strg+V, kurze Pause (`einfuegen.warte_ms`, Standard 30). Gemessen: 60 bis 70 ms
  ohne Erkennung. Jede Aufnahme schreibt die Zeiten ins Log.
- `taste.aktiv: false` schaltet die globale X11-Taste ab. Die lokale Steuerung mit `--start` und `--stopp` bleibt verfügbar.

## Wayland vorbereiten
Wenn `WAYLAND_DISPLAY` gesetzt ist und `gtk-layer-shell` über GI verfügbar ist, nutzt das Overlay die
Overlay-Ebene und nimmt keine Tastatureingaben an. Fehlt die Bibliothek, meldet HufiVoice den Rückfall
auf XWayland im Log. Für ein Desktop-Tastenkürzel zwei Befehle eintragen:
`python3 /pfad/zu/hufivoice.py --start` beim Drücken und `python3 /pfad/zu/hufivoice.py --stopp`
beim Loslassen. Diese Testkopie richtet keine Tastenkürzel selbst ein.

## Lokal im Browser und auf Android vorbereiten
`../HUFIVOICE_WEB_STARTEN.sh` startet die Web-App ausschließlich auf `http://127.0.0.1:8765`.
Sie nimmt im Browser 16-kHz-WAV auf und nutzt dieselbe HufiVoice-Erkennung wie die Desktop-App.
Die installierbaren PWA-Dateien stehen in `../web/dist`; die genaue Anleitung und die zwingenden
HTTPS-/Token-Regeln für Android stehen in `../web/README.md`. Es wird nichts automatisch veröffentlicht.

## Tests
```
python3 -m unittest discover -s tests -v          # Logik, Fenster, Tempo und Einstellungen
HUFIVOICE_TEST_WAV=tests/beispiel_de.wav python3 -m unittest discover -s tests   # mit echtem Whisper
bash tests/e2e_xvfb.sh tests/beispiel_de.wav                                       # ganzer Ablauf in Xvfb
```
`tests/beispiel_de.wav` ist eine Computerstimme (espeak-ng), keine echte Aufnahme.

## Grenzen
Die globale frei wählbare Taste wird direkt nur unter X11/XWayland beobachtet. Unter reinem Wayland
ist der beschriebene `--start`/`--stopp`-Weg vorgesehen. Android, Apple und Windows sind noch nicht
Teil dieser Linux-Testkopie.
