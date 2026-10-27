# HufiVoice Web auf dem M83 automatisch starten

Das ist nur vorbereitet. Auf dem M83 ist noch nichts eingerichtet.
Der Dienst heißt hufivoice-web.service. Dein vorhandenes hufivoice.service bleibt so, wie es ist.

1. Lege die HufiVoice-Testkopie in den Ordner `~/hufivoice-test-wave`.
2. Öffne ein Terminal und prüfe: `python3 ~/hufivoice-test-wave/app/hufivoice_web.py --pruefen`
   Steht bei der Erkennung FEHLT, fehlt dem M83 das Whisper-Programm oder das Modell.
3. Geh in den Ordner `deploy/autostart` und tippe: `bash install.sh`
4. Antworte mit `j`, wenn du gefragt wirst. Ohne `j` wird nichts geändert.
5. Öffne im Menü das Symbol „HufiVoice“. Chrome zeigt die App in einem eigenen Fenster.
6. Wieder weg damit: `bash uninstall.sh` im selben Ordner.

Wichtig: Die Erkennung auf dem Rechner selbst (Modus „lokal“) braucht das vorhandene
Whisper-Programm und Modell auf dem M83. Auf dem XXL gab es das nicht. Ob es auf dem M83
passt, zeigt nur Schritt 2. Das wurde noch nicht geprüft.
