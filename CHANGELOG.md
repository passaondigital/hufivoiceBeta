### 27.10.2026, 22:56

- Wer: MrEqui im Auftrag von Pascal
- Wie: Testkopie per scp vom XXL geholt (nur gelesen), Geheimnis-Suche mit grep, Autostart-Dateien neu geschrieben und mit `bash -n`, `systemd-analyze verify` und `desktop-file-validate` geprüft, Git-Commit auf Branch `test-wave-2026-10-27`.
- Wo: Repo `passaondigital/hufivoiceBeta`, Branch `test-wave-2026-10-27` (nicht `main`); neu: ganze Testkopie plus `deploy/autostart/`.
- Was: Inhalt der HufiVoice-Testkopie hochgeladen (ohne `original/`, `__pycache__`, `.env`); neu `deploy/autostart/` mit `hufivoice-web.service`, `hufivoice-web.desktop`, `install.sh`, `uninstall.sh`, `ANLEITUNG.md`. Kein Schlüssel, Passwort oder Token gefunden; `deploy/.env.example` enthält nur Platzhalter.
- Warum: Codex-Stand vom 27.10.2026 sichern und den Autostart für den M83 vorbereiten, ohne den M83 oder `main` zu verändern.
- Rückweg: Branch `test-wave-2026-10-27` löschen; `main` ist unverändert (Stand 2a092e1).
- Tests: Auf der Box lief die `unittest`-Suite mit 51 Tests OK, 1 übersprungen (andere Umgebung als der XXL). `install.sh` mit Antwort „n“ in einem Test-Ordner: nichts geändert. Auf dem M83 NICHT GETESTET. Lokales Whisper meldete in der Box-Prüfung FEHLT.

### 27.10.2026, 22:50

- Wer: Codex auf dem XXL für Pascal
- Wie: Bedienhilfen mit Patch-Werkzeug ergänzt; Launcher mit `bash -n`, Tokenformat und Web-Diagnose direkt geprüft; vollständige `unittest`-Suite ausgeführt.
- Wo: `HUFIVOICE_WEB_STARTEN.sh`, `app/hufivoice_web.py`, `app/tests/test_web.py`, `app/README.md`, `web/README.md`, `deploy/README.md`, `CHANGELOG.md`.
- Was: Ein-Befehl-Start für die lokale Web-App; `--pruefen` kontrolliert Web-Dateien, Bindung, Token, TLS-Paar und Erkennungsmodus, ohne etwas zu starten; `--token-erzeugen` gibt einen zufälligen Zugangscode mit etwa 256 Bit aus und speichert ihn nicht.
- Warum: Pascal soll die private Linux-Webversion ohne Docker-Wissen starten und einen Online-Zugang sicher vorbereiten können.
- Rückweg: Die genannten Änderungen entfernen oder vollständig `rm -rf ~/hufivoice-test-wave`.
- Tests: 47 Tests PASS, 5 echte Desktop-/Mikrofontests übersprungen. Launcher ist ausführbar und syntaktisch gültig. Online-Diagnose mit reinem Testschlüssel PASS.
- Aktueller lokaler Befund: Web-App und Zugangsschutz PASS; lokale Transkription auf dem XXL noch FEHLT, weil Whisper-Programm oder Modell nicht in der Testumgebung vorhanden ist. Gemäß Auftrag wurde nichts installiert.

### 27.10.2026, 22:49

- Wer: Codex auf dem XXL für Pascal
- Wie: Offizielle OpenAI-Dokumentation geprüft; Code mit Patch-Werkzeug geändert; `docker compose config`, JSON-, Python- und JavaScript-Syntax geprüft; vollständige `unittest`-Suite ausgeführt. Kein Container gebaut oder gestartet.
- Wo: `.dockerignore`, `deploy/Dockerfile`, `deploy/compose.yaml`, `deploy/config-online.json`, `deploy/.env.example`, `deploy/nginx-hufivoice-web.example.conf`, `deploy/README.md`, `app/config.json`, `app/README.md`, `app/hufivoice/erkennung.py`, `app/hufivoice_web.py`, `app/tests/test_hufivoice.py`, `app/tests/test_web.py`, `CHANGELOG.md`.
- Was: Private Online-Verpackung vorbereitet; Container läuft unprivilegiert und schreibgeschützt; Port bleibt am Host lokal; HTTPS-Vorlage; Token-Pflicht; Healthcheck; 30 Anfragen pro Minute; höchstens zwei Transkriptionen gleichzeitig. Neue API-Konfiguration auf `gpt-transcribe` umgestellt, `languages[]` und `keywords[]` ergänzt; altes `whisper-1`-Format bleibt kompatibel.
- Warum: Pascal möchte HufiVoice zunächst selbst lokal und online auf Linux und Android nutzen, später aber sauber verkaufen können.
- Rückweg: Neue Dateien unter `deploy/` und `.dockerignore` entfernen; API-Änderungen anhand des unveränderten Ordners `original/` zurücksetzen oder vollständig `rm -rf ~/hufivoice-test-wave`.
- Tests: 45 Tests PASS, 5 echte Desktop-/Mikrofontests mangels GTK/Xlib übersprungen. Compose- und zusammengeführte Online-Konfiguration mit Platzhalter-Geheimnissen gültig. Container-Image absichtlich NOT TESTED/NOT BUILT.
- Quelle: https://developers.openai.com/api/docs/guides/speech-to-text – `gpt-transcribe` ist für abgeschlossene Aufnahmen empfohlen; `whisper-1` ist veraltet und wird laut Dokumentation am 26.02.2027 abgeschaltet.

### 27.10.2026, 22:46

- Wer: Codex auf dem XXL für Pascal
- Wie: Lokale Sites-Arbeitsweise ohne Veröffentlichung; Bearbeitung mit Patch-Werkzeug; Prüfung mit `unittest`, `py_compile`, `node --check`, `json.tool` und lokalem HTTP-Abruf.
- Wo: `app/hufivoice_web.py`, `app/README.md`, `app/tests/test_web.py`, `app/tests/test_design.py`, `app/tests/test_hufivoice.py`, `web/README.md`, `web/dist/index.html`, `web/dist/styles.css`, `web/dist/app.js`, `web/dist/sw.js`, `web/dist/manifest.webmanifest`, `web/dist/icon.svg`, `PRODUKTPLAN.md`, `CHANGELOG.md`.
- Was: Lokale Web-App/PWA für Linux und Android vorbereitet; Browseraufnahme als WAV; neun Live-Wellenbalken; Maus- und Tastaturbedienung; lokaler Transkriptions-Endpunkt; nur wählbare HTTPS-Online-Endpunkte; kurzlebiger Zugangscode; LAN ohne Token gesperrt; maximal 3 Minuten und 20 MB; CSP und weitere Sicherheitsheader; Service Worker für die Oberfläche; Produktweg für Verkauf sowie Apple/Windows dokumentiert.
- Warum: Pascal möchte HufiVoice zuerst selbst lokal und im Web auf Linux und Android nutzen und später verkaufbar machen.
- Rückweg: Nur die genannten Web-Dateien entfernen oder vollständig `rm -rf ~/hufivoice-test-wave`; Original und laufendes System bleiben unberührt.
- Tests: 41 Tests PASS, 5 Desktop-/Mikrofontests mangels GTK/Xlib übersprungen. JavaScript, alle verwendeten HTML-Elemente und Manifest-Dateien geprüft. Lokale Startseite und PWA-Manifest lieferten HTTP 200. Der Prüfserver wurde danach beendet.
- Noch offen: echter Browser-Mikrofontest, Android-Test über vertrauenswürdiges HTTPS, echte lokale Whisper-Erkennung, Benutzerkonten/Abrechnung/Rechtstexte und Veröffentlichung.

### 27.10.2026, 22:41

- Wer: Codex auf dem XXL für Pascal
- Wie: Download mit `curl`, Entpacken mit `unzip`, Bearbeitung mit Patch-Werkzeug, Prüfung mit `unittest`, `py_compile`, `diff`, `rg` und `sha256sum`.
- Wo: `app/config.json`, `app/README.md`, `app/hufivoice.py`, `app/hufivoice/einstellungen.py`, `app/hufivoice/einstellungen_fenster.py`, `app/hufivoice/fenster.py`, `app/hufivoice/fenster_logik.py`, `app/hufivoice/steuerung.py`, `app/hufivoice/taste.py`, `app/tests/test_design.py`, `app/tests/test_hufivoice.py`, `PASCAL_PRUEFLISTE.md`, `THIRD_PARTY.md`, `CHANGELOG.md`.
- Was: Neun orange Wellenbalken mit echtem Mikrofonpegel; vier Overlay-Positionen; Monitor an Maus oder Hauptmonitor; klick-durchlässiges, fokusfreies Overlay; vorbereiteter Layer-Shell-Weg; frei wählbare Halte-Taste mit Aufnahme-Knopf; `Super_L` als Standard; Escape-Abbruch; alte Tastenwerte bleiben gültig; lokale Befehle `--start` und `--stopp` für Wayland.
- Warum: Pascal möchte die Wave beim Halten der Taste als Overlay sehen und die Taste frei wählen. Am Linux-Tower soll die linke Windows-Taste der Logitech K120 zusammen mit dem Mikrofon der Logitech C920 benutzt werden.
- Rückweg: `rm -rf ~/hufivoice-test-wave` (das installierte Original bleibt unberührt).
- Tests:

| Test | Ergebnis | Begründung |
|---|---|---|
| T1 Bisherige Tests | PASS | Gesamtlauf: 34 Tests erfolgreich, 5 umgebungsbedingt übersprungen. |
| T2 Neue Tastenlogik | PASS | Super_L, Control_R, F9, Halten, kurzes Tippen, Kombination und Escape-Abbruch simuliert. |
| T3 Alte Konfiguration | PASS | `super` und `super+space` werden in eigenen Tests geladen. |
| T4 Overlay unter Xvfb | NOT TESTED | Xvfb ist da, aber GTK ist auf dem XXL nicht über GI verfügbar; kein Bildschirmfoto möglich. |
| T5 Klick-durchlässig | NOT TESTED | GTK und python3-gi-cairo fehlen; nichts nachinstalliert. |
| T6 Fokus bleibt im Ziel | NOT TESTED | GTK fehlt; deshalb kein echter Fenstertest. |
| T7 Vier Positionen | PASS | Alle vier Koordinaten liegen im simulierten sichtbaren Monitorbereich. |
| T8 Wayland-Rückfall | NOT TESTED | GtkLayerShell und GTK fehlen auf dem XXL; Rückfallcode und Loghinweis sind eingebaut, Start nicht möglich. |
| T9 Echtes Mikrofon und Taste | NOT TESTED | Nur mit Pascal am Linux-Tower/M83 prüfbar; fünf Schritte stehen in `PASCAL_PRUEFLISTE.md`. |
