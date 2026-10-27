#!/usr/bin/env bash
# Nimmt den HufiVoice-Web-Autostart und das Chrome-App-Symbol wieder weg.
# Fasst das andere hufivoice.service NICHT an. Die App-Dateien in ~/hufivoice-test-wave bleiben.
set -eu

UNIT_ZIEL="$HOME/.config/systemd/user/hufivoice-web.service"
DESKTOP_ZIEL="$HOME/.local/share/applications/hufivoice-web.desktop"

read -r -p "HufiVoice-Web-Autostart und Symbol entfernen? [j/N] " antwort || antwort=""
if [ "$antwort" != "j" ] && [ "$antwort" != "J" ]; then
  echo "Abgebrochen. Nichts geaendert."
  exit 0
fi

systemctl --user disable --now hufivoice-web.service 2>/dev/null || true
for datei in "$UNIT_ZIEL" "$DESKTOP_ZIEL"; do
  if [ -e "$datei" ]; then rm -f "$datei"; echo "Entfernt: $datei"; fi
  if [ -e "$datei.bak" ]; then
    mv "$datei.bak" "$datei"; echo "Alte Fassung zurueckgeholt: $datei"
  fi
done
systemctl --user daemon-reload || true
echo "Fertig. hufivoice.service wurde nicht veraendert."
