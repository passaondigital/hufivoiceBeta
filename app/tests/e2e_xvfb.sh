#!/bin/bash
# Ende-zu-Ende-Test in einem unsichtbaren Bildschirm (Xvfb), ohne Mikrofon.
set -u
WAV="${1:?Bitte Pfad zu einer WAV angeben (16 kHz, mono), z. B. tests/beispiel_de.wav}"
export DISPLAY=:97
Xvfb :97 -screen 0 1280x800x24 >/dev/null 2>&1 & XV=$!
sleep 1.5
xfwm4 --compositor=off >/dev/null 2>&1 & WM=$!
sleep 1.5
rm -f /tmp/ziel.txt
python3 "$(dirname "$0")/ziel_fenster.py" & ZI=$!
sleep 2
xdotool search --name Zielfenster windowactivate --sync 2>/dev/null
echo "alter Inhalt" | xclip -selection clipboard -i
HUFIVOICE_TESTDATEI="$WAV" python3 "$(dirname "$0")/../hufivoice.py" > /tmp/hv-e2e.log 2>&1 & HV=$!
sleep 4
echo "1) Super kurz tippen (Menü-Befehl), dann Super 8 s halten"
xdotool keydown Super_L; sleep 0.1; xdotool keyup Super_L; sleep 1
xdotool keydown Super_L; sleep 4
ffmpeg -loglevel error -y -f x11grab -video_size 1280x800 -i :97 -frames:v 1 /tmp/fenster-live.png
sleep 4.5; xdotool keyup Super_L
sleep 1.2; ffmpeg -loglevel error -y -f x11grab -video_size 1280x800 -i :97 -frames:v 1 /tmp/fenster-schreibe.png
sleep 14
echo "Zielfenster enthält: $(cat /tmp/ziel.txt)"
sleep 1.5; echo "Zwischenablage danach: $(xclip -selection clipboard -o)"
echo "2) Super+E (Kombi) darf nichts einfügen"
xdotool key super+e; sleep 2
echo "Log:"; cat /tmp/hv-e2e.log
kill $HV $ZI $WM $XV 2>/dev/null
