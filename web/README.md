# HufiVoice Web/PWA – lokale Testkopie

Die Browser-App nimmt Sprache als WAV mit 16 kHz auf. Standardmäßig sendet sie nur an
`/api/transcribe` auf demselben Rechner. Der Python-Server verwendet danach die bereits gewählte
HufiVoice-Erkennung (`lokal`, `server` oder `api`).

## Nur auf dem Linux-Tower testen

```bash
cd ~/hufivoice-test-wave
./HUFIVOICE_WEB_STARTEN.sh
```

Dann `http://127.0.0.1:8765` öffnen. Nichts wird veröffentlicht.

Vorher prüfen, ohne etwas zu starten:

```bash
python3 app/hufivoice_web.py --pruefen
```

## Android und anderer Rechner

Browser erlauben das Mikrofon außerhalb von `localhost` nur in einem sicheren Kontext. Für Android
ist deshalb vertrauenswürdiges HTTPS nötig. Ein eigener LAN-/Internet-Start braucht außerdem zwingend
einen Zugangscode:

```bash
python3 app/hufivoice_web.py --token-erzeugen
HUFIVOICE_WEB_TOKEN='einen-langen-zufälligen-code' \
python3 app/hufivoice_web.py --host 0.0.0.0 --cert server.pem --key server-key.pem
```

Zertifikate oder Server werden von dieser Testkopie nicht eingerichtet. Für eine spätere öffentliche
Version gehören HTTPS, Benutzerkonten, Nutzungsgrenzen, Datenschutz, AGB und Abrechnung vor den Endpunkt.

Die PWA-Dateien liegen fertig und ohne externe Bibliotheken in `web/dist/`. Über „Zum Startbildschirm
hinzufügen“ lässt sie sich unter Android wie eine App öffnen. Apple und Windows sind noch nicht getestet.
Ein abweichender Online-Endpunkt muss HTTPS und passende CORS-Header für die Web-Adresse erlauben.
