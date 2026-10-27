#!/usr/bin/env bash
# Richtet HufiVoice Web als Autostart (systemd-User-Dienst) und als Chrome-App-Symbol ein.
# Ueberschreibt nichts ohne Nachfrage. Kein sudo noetig. Rueckweg: bash uninstall.sh
set -eu

HIER="$(cd -- "$(dirname -- "$0")" && pwd)"
APP_ORDNER="$HOME/hufivoice-test-wave"
UNIT_ORDNER="$HOME/.config/systemd/user"
DESKTOP_ORDNER="$HOME/.local/share/applications"
UNIT_ZIEL="$UNIT_ORDNER/hufivoice-web.service"
DESKTOP_ZIEL="$DESKTOP_ORDNER/hufivoice-web.desktop"

frage() { # frage "Text" -> 0 bei j/J
  local antwort
  read -r -p "$1 [j/N] " antwort || antwort=""
  [ "$antwort" = "j" ] || [ "$antwort" = "J" ]
}

if [ ! -x "$APP_ORDNER/HUFIVOICE_WEB_STARTEN.sh" ]; then
  echo "Fehlt: $APP_ORDNER/HUFIVOICE_WEB_STARTEN.sh"
  echo "Bitte zuerst die HufiVoice-Testkopie nach $APP_ORDNER legen."
  exit 1
fi

echo "Pruefung (startet nichts):"
python3 "$APP_ORDNER/app/hufivoice_web.py" --pruefen || echo "Hinweis: Die Pruefung meldet etwas als FEHLT (siehe oben)."

if ! frage "HufiVoice Web jetzt als Autostart einrichten?"; then
  echo "Abgebrochen. Nichts geaendert."
  exit 0
fi

mkdir -p "$UNIT_ORDNER" "$DESKTOP_ORDNER"

kopieren() { # kopieren quelle ziel
  if [ -e "$2" ]; then
    if cmp -s "$1" "$2"; then echo "Schon aktuell: $2"; return 0; fi
    if ! frage "$2 gibt es schon. Ersetzen? (Sicherung: $2.bak)"; then
      echo "Uebersprungen: $2"; return 0
    fi
    cp -p "$2" "$2.bak"
  fi
  cp "$1" "$2"
  echo "Angelegt: $2"
}

kopieren "$HIER/hufivoice-web.service" "$UNIT_ZIEL"

TMP_DESKTOP="$(mktemp)"
sed "s|@ICON@|$APP_ORDNER/web/dist/icon.svg|" "$HIER/hufivoice-web.desktop" > "$TMP_DESKTOP"
kopieren "$TMP_DESKTOP" "$DESKTOP_ZIEL"
rm -f "$TMP_DESKTOP"

if ! command -v google-chrome >/dev/null 2>&1; then
  echo "Hinweis: google-chrome wurde nicht gefunden. Das Symbol startet erst, wenn Chrome da ist."
fi

systemctl --user daemon-reload
systemctl --user enable --now hufivoice-web.service
echo
echo "Fertig. HufiVoice Web laeuft auf http://127.0.0.1:8765"
echo "Status: systemctl --user status hufivoice-web.service"
echo "Rueckweg: bash $HIER/uninstall.sh"
