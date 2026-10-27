#!/bin/bash
# HufiVoice entfernen und die Super-Taste an XFCE zurückgeben.
set -u
ZIEL="$HOME/.hufi/voice"
pkill -f "$ZIEL/app/hufivoice.py" 2>/dev/null
rm -f "$HOME/.config/autostart/hufivoice.desktop" "$HOME/.local/share/applications/hufivoice-einstellungen.desktop"
# Die Schrift Outfit in ~/.local/share/fonts bleibt (kann auch andere Programme nutzen).
if [ -f "$ZIEL/xfce-super-sicherung.txt" ] && command -v xfconf-query >/dev/null; then
  xfconf-query -c xfce4-keyboard-shortcuts -p /commands/custom/Super_L -n -t string \
    -s "$(cat "$ZIEL/xfce-super-sicherung.txt")" 2>/dev/null || \
  xfconf-query -c xfce4-keyboard-shortcuts -p /commands/custom/Super_L \
    -s "$(cat "$ZIEL/xfce-super-sicherung.txt")"
  echo "Super-Taste öffnet wieder das XFCE-Menü."
fi
read -r -p "Auch Modelle und Einstellungen in $ZIEL löschen? (j/n) " JA
[ "$JA" = "j" ] && rm -rf "$ZIEL"
echo "HufiVoice entfernt. ~/.hufi/geheim bleibt unangetastet."
