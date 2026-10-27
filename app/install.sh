#!/bin/bash
# HufiVoice installieren (Linux, X11, XFCE). Ändert nur Dinge in deinem
# Benutzerordner, ausser den Paketen aus Schritt 1 (fragt nach Passwort).
set -euo pipefail
HIER="$(cd "$(dirname "$0")" && pwd)"
ZIEL="$HOME/.hufi/voice"
VOSK_ZIP="vosk-model-small-de-0.15.zip"
VOSK_SHA="b7e53c90b1f0a38456f4cd62b366ecd58803cd97cd42b06438e2c131713d5e43"

echo "== 1/7 Pakete"
if [ "${HUFIVOICE_OHNE_APT:-0}" = "1" ]; then
  echo "Übersprungen (Pakete kommen schon mit dem .deb)."
else
  sudo apt-get install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0 python3-xlib python3-venv \
    xdotool xclip pulseaudio-utils build-essential cmake git curl unzip binutils
fi

echo "== 2/7 Programm nach $ZIEL/app"
mkdir -p "$ZIEL/modelle" "$HOME/.hufi/geheim"
chmod 700 "$HOME/.hufi/geheim"
rm -rf "$ZIEL/app.alt"; [ -d "$ZIEL/app" ] && mv "$ZIEL/app" "$ZIEL/app.alt"
cp -r "$HIER" "$ZIEL/app"
python3 -m venv --system-site-packages "$ZIEL/venv"
"$ZIEL/venv/bin/pip" install -q vosk
[ -f "$ZIEL/config.json" ] || cp "$HIER/config.json" "$ZIEL/config.json"

echo "== 3/7 Whisper ohne AVX bauen (dauert 5 bis 15 Minuten)"
bash "$HIER/build-whisper.sh"

echo "== 4/7 Vosk-Modell für die Live-Vorschau (45 MB)"
if [ ! -d "$ZIEL/modelle/vosk-model-small-de-0.15" ]; then
  curl -L -o "/tmp/$VOSK_ZIP" "https://alphacephei.com/vosk/models/$VOSK_ZIP"
  echo "$VOSK_SHA  /tmp/$VOSK_ZIP" | sha256sum -c -
  unzip -q "/tmp/$VOSK_ZIP" -d "$ZIEL/modelle" && rm "/tmp/$VOSK_ZIP"
fi

echo "== 5/7 Schrift Outfit und Menü-Eintrag"
mkdir -p "$HOME/.local/share/fonts" "$HOME/.local/share/applications"
if ! fc-list 2>/dev/null | grep -qi "Outfit"; then
  cp "$HIER/schrift/Outfit-VariableFont_wght.ttf" "$HOME/.local/share/fonts/" && fc-cache -f >/dev/null 2>&1 || true
fi
sed "s#@ZIEL@#$ZIEL#g" "$HIER/hufivoice-einstellungen.desktop" > "$HOME/.local/share/applications/hufivoice-einstellungen.desktop"

echo "== 6/7 Autostart"
mkdir -p "$HOME/.config/autostart"
sed "s#@ZIEL@#$ZIEL#g" "$HIER/hufivoice.desktop" > "$HOME/.config/autostart/hufivoice.desktop"

echo "== 7/7 Super-Taste und Menü"
if command -v xfconf-query >/dev/null; then
  ALT="$(xfconf-query -c xfce4-keyboard-shortcuts -p /commands/custom/Super_L 2>/dev/null || true)"
  if [ -n "$ALT" ]; then
    echo "XFCE öffnet beim Druck auf Super: $ALT"
    echo "Damit Halten nicht auch das Menü öffnet, übernimmt HufiVoice das kurze Tippen."
    read -r -p "Super-Taste an HufiVoice geben? (j/n) " JA
    if [ "$JA" = "j" ]; then
      echo "$ALT" > "$ZIEL/xfce-super-sicherung.txt"
      "$ZIEL/venv/bin/python" - "$ZIEL/config.json" "$ALT" <<'PY'
import json, sys
p, befehl = sys.argv[1], sys.argv[2]
c = json.load(open(p)); c.setdefault("taste", {})["menue_befehl"] = befehl
json.dump(c, open(p, "w"), indent=2, ensure_ascii=False)
PY
      xfconf-query -c xfce4-keyboard-shortcuts -p /commands/custom/Super_L -r
      echo "Erledigt. Rückweg: uninstall.sh stellt es wieder her."
    else
      echo "Dann bitte in $ZIEL/config.json \"art\": \"super+space\" setzen."
    fi
  fi
fi

"$ZIEL/venv/bin/python" "$ZIEL/app/hufivoice.py" --pruefen || true
echo "Fertig. Starten: $ZIEL/venv/bin/python $ZIEL/app/hufivoice.py  (oder neu anmelden)"
echo "Einstellungen: im Menü \"HufiVoice Einstellungen\" oder $ZIEL/venv/bin/python $ZIEL/app/hufivoice.py --einstellungen"
