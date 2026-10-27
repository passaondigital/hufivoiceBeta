#!/bin/bash
# Baut whisper.cpp OHNE AVX (für Pentium G3220 und andere ältere CPUs)
# und lädt das Modell base-q5_1 (60 MB). Ziel: ~/.hufi/voice/
set -euo pipefail
ZIEL="$HOME/.hufi/voice"
STAND="231638a0717b7822784297e5980965ffcec05810"   # getesteter Stand (19.10.2026)
MODELL="${HUFIVOICE_MODELL:-base-q5_1}"            # tiny-q5_1 = schneller, small-q5_1 = genauer
mkdir -p "$ZIEL/modelle"
cd "$ZIEL"
if [ ! -d whisper.cpp ]; then
  git clone https://github.com/ggml-org/whisper.cpp
fi
cd whisper.cpp
git fetch -q origin && git checkout -q "$STAND"
cmake -B build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF \
  -DGGML_NATIVE=OFF -DGGML_AVX=OFF -DGGML_AVX2=OFF -DGGML_AVX512=OFF \
  -DGGML_FMA=OFF -DGGML_F16C=OFF -DGGML_BMI2=OFF -DWHISPER_BUILD_TESTS=OFF
cmake --build build -j"$(nproc)" --target whisper-cli
# Kontrolle: keine AVX-Befehle im Programm
if objdump -d build/bin/whisper-cli | grep -qE "%ymm|%zmm"; then
  echo "FEHLER: Programm enthält AVX. Bitte melden."; exit 1
fi
echo "whisper.cpp ohne AVX gebaut."
if [ ! -f "$ZIEL/modelle/ggml-$MODELL.bin" ]; then
  sh models/download-ggml-model.sh "$MODELL" "$ZIEL/modelle"
fi
ls -la "$ZIEL/modelle/"
