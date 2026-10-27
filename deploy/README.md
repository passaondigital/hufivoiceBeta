# Private Online-Vorlage – nicht gestartet, nicht veröffentlicht

Diese Vorlage ist für Pascals ersten privaten Online-Test gedacht. Sie läuft als unprivilegierter,
schreibgeschützter Container und bindet den Dienst auf dem Host nur an `127.0.0.1:8765`. Erst ein
separater HTTPS-Reverse-Proxy darf ihn nach außen reichen.

## Voraussetzungen

- Eigene Domain mit vertrauenswürdigem HTTPS-Zertifikat
- Docker/Compose auf dem späteren Server
- Eigener API-Schlüssel und langer, zufälliger HufiVoice-Zugangscode

Einen Zugangscode erzeugt die Testkopie, ohne ihn zu speichern:

```bash
python3 app/hufivoice_web.py --token-erzeugen
```

## Erst später auf einem freigegebenen Testserver

```bash
cd deploy
cp .env.example .env
# .env nur lokal bearbeiten und mit chmod 600 schützen
HUFIVOICE_WEB_TOKEN=test HUFIVOICE_API_KEY=test docker compose config --quiet
docker compose build
docker compose up -d
```

Danach kann ein geprüfter Nginx-VHost anhand von `nginx-hufivoice-web.example.conf` auf den lokalen
Port zeigen. In der PWA wird derselbe `HUFIVOICE_WEB_TOKEN` einmal als Zugangscode eingetragen.

## Sicherheitsgrenzen dieser Privatversion

- Ein gemeinsamer Token ist noch kein Mehrbenutzerkonto.
- Pro IP sind standardmäßig 30 Transkriptionen pro Minute und zwei gleichzeitig erlaubt.
- Audio ist auf 20 MB und 3 Minuten begrenzt und wird nach der Transkription gelöscht.
- Der Container enthält kein lokales Whisper-Modell; online nutzt er den in `config-online.json`
  gewählten API-Dienst. Für einen eigenen Whisper-Server stattdessen `modus: server` konfigurieren.
- Die Vorlage nutzt `gpt-transcribe`. Laut offizieller OpenAI-Dokumentation ist das der empfohlene
  Start für abgeschlossene Audiodateien; das alte `whisper-1` wird am 26.02.2027 abgeschaltet:
  https://developers.openai.com/api/docs/guides/speech-to-text
- Vor Verkauf fehlen weiterhin Benutzerverwaltung, Quoten je Konto, Abrechnung, Audit und Rechtstexte.

Diese Befehle wurden im Rahmen der Testkopie nicht ausgeführt. Es wurde kein Image gebaut und kein
Server verändert.
