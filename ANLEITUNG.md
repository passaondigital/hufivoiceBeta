# HufiVoice auf Linux installieren (z. B. Rechner M83)

Du brauchst: Linux mit XFCE (X11), Internet für die Installation, ein Mikrofon (z. B. Logitech C920 per USB).

1. **Laden und entpacken.** ZIP herunterladen und mit Rechtsklick "Hier entpacken".
2. **Terminal öffnen.** Im entpackten Ordner `app` Rechtsklick, "Terminal hier öffnen".
3. **Installieren.** Eingeben: `bash install.sh` und Enter. Einmal dein Passwort eingeben. Das dauert 5 bis 15 Minuten.
4. **Super-Taste.** Frage "Super-Taste an HufiVoice geben?" mit `j` beantworten. Dann öffnet kurzes Tippen weiter dein Menü, und Halten startet das Zuhören.
5. **Neu anmelden.** Abmelden und wieder anmelden. Super halten, sprechen, loslassen. Fertig.

## Oder mit dem .deb (Debian, Ubuntu, Mint)
1. `hufivoice_0.2.0_all.deb` laden.
2. Terminal: `sudo apt install ./hufivoice_0.2.0_all.deb` (Passwort eingeben).
3. Dann als normaler Benutzer, ohne sudo: `hufivoice-einrichten`. Weiter wie oben ab Schritt 4.

## Einstellungen
Im Menü „HufiVoice Einstellungen“ öffnen (oder `hufivoice --einstellungen`). Dort: Taste an oder aus,
Super halten oder Super + Leertaste, Mikrofon, Lokal / Eigener Server / API, Schneller Modus, Autostart.
Nach dem Speichern HufiVoice neu starten (abmelden und anmelden reicht).

## Gut zu wissen
- Prüfen: `~/.hufi/voice/venv/bin/python ~/.hufi/voice/app/hufivoice.py --pruefen`
- Einstellungen als Datei: `~/.hufi/voice/config.json` (das Einstellungsfenster schreibt nur geänderte Werte hinein).
- API-Schlüssel nie in die config.json. Nur so: Datei `~/.hufi/geheim/hufivoice_api_key` anlegen, Schlüssel hinein, dann `chmod 600 ~/.hufi/geheim/hufivoice_api_key`.
- Entfernen: `bash ~/.hufi/voice/app/uninstall.sh`. Die Super-Taste öffnet dann wieder wie vorher das Menü.
