#!/usr/bin/env bash
# Собирает RHVoice (ядро + RHVoice-test) и кладёт русский язык и голоса в $LTTS_HOME/rhvoice.
# Использование: scripts/build-rhvoice.sh [голос ...]   (по умолчанию: anna aleksandr elena irina)
set -euo pipefail

RHVOICE_TAG="${RHVOICE_TAG:-1.18.4}"
LTTS_HOME="${LTTS_HOME:-$HOME/.local/share/ltts}"
PREFIX="$LTTS_HOME/rhvoice"
DATA="$PREFIX/data"
SRC="${TMPDIR:-/tmp}/ltts-rhvoice-src-$RHVOICE_TAG"
VOICES=("$@")
[ ${#VOICES[@]} -eq 0 ] && VOICES=(anna aleksandr elena irina)

log() { printf '\033[1;36m[rhvoice]\033[0m %s\n' "$*" >&2; }

need() { command -v "$1" >/dev/null 2>&1; }
if ! need cmake; then
  if need brew; then log "ставлю cmake через brew"; brew install cmake >/dev/null
  else echo "нужен cmake (apt install cmake / brew install cmake)" >&2; exit 1; fi
fi
need git || { echo "нужен git" >&2; exit 1; }
need c++ || { echo "нужен компилятор C++ (xcode-select --install / apt install build-essential)" >&2; exit 1; }

if [ ! -x "$PREFIX/bin/RHVoice-test" ]; then
  if [ ! -d "$SRC/.git" ]; then
    log "клонирую RHVoice $RHVOICE_TAG"
    rm -rf "$SRC"
    git -c advice.detachedHead=false clone -q --depth 1 --branch "$RHVOICE_TAG" https://github.com/RHVoice/RHVoice.git "$SRC"
  fi
  log "подтягиваю зависимости (boost, cmake-модули)"
  # .gitmodules местами с CRLF — чистим пути от \r
  git -C "$SRC" config -f .gitmodules --get-regexp 'submodule\..*\.path' \
    | awk '{print $2}' | tr -d '\r' | grep -E '^(external|cmake/thirdParty)' \
    | xargs git -C "$SRC" submodule update -q --init --depth 1 --jobs 16 --

  # RHVoice использует std::unary_function/not1, которых нет в C++20 у свежего libc++ — собираем в C++17
  sed -i.bak 's/set(CMAKE_CXX_STANDARD 20)/set(CMAKE_CXX_STANDARD 17)/' "$SRC/CMakeLists.txt"
  # GNU-флаги линкера (--sort-common, --as-needed) ломают ld от Apple
  sed -i.bak -e '/"-Wl,--sort-common"/d' -e '/"-Wl,--as-needed"/d' "$SRC/cmake/Hardening.cmake"

  # CMake-сборка ждёт системный boost; подключаем вендоренные заголовки из external/
  BOOST_INC=""
  for d in "$SRC"/external/libs/boost/libs/*/include; do BOOST_INC="$BOOST_INC -I$d"; done
  LINK_FLAGS=""
  [ "$(uname)" = Darwin ] && LINK_FLAGS="-undefined dynamic_lookup"

  log "собираю (пара минут, лог: $PREFIX/build.log)"
  mkdir -p "$PREFIX"
  BUILD_LOG="$PREFIX/build.log"
  : > "$BUILD_LOG"
  trap 'echo "сборка упала, хвост лога:" >&2; tail -30 "$BUILD_LOG" >&2' ERR
  cmake -S "$SRC" -B "$SRC/build" -Wno-dev -DCMAKE_POLICY_VERSION_MINIMUM=3.5 -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CXX_FLAGS="-D_LIBCPP_ENABLE_CXX17_REMOVED_UNARY_BINARY_FUNCTION -Wno-deprecated-declarations$BOOST_INC" \
    -DCMAKE_SHARED_LINKER_FLAGS="$LINK_FLAGS" -DHARDENING_PIC=OFF \
    -DCMAKE_INSTALL_RPATH="$PREFIX/lib" -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON \
    -DWITH_DATA=OFF -DBUILD_UTILS=OFF -DBUILD_CLIENT=OFF -DBUILD_SERVICE=OFF \
    -DBUILD_SPEECHDISPATCHER_MODULE=OFF -DCMAKE_INSTALL_PREFIX="$PREFIX" >>"$BUILD_LOG" 2>&1
  cmake --build "$SRC/build" -j "$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)" >>"$BUILD_LOG" 2>&1
  cmake --install "$SRC/build" >>"$BUILD_LOG" 2>&1
  trap - ERR
fi

if [ "${LTTS_RHVOICE_BIN_ONLY:-}" = 1 ]; then
  log "собран: $PREFIX/bin/RHVoice-test"
  exit 0
fi

fetch() { # repo dest
  if [ ! -d "$2" ]; then
    git clone -q --depth 1 "https://github.com/RHVoice/$1.git" "$2.tmp" && rm -rf "$2.tmp/.git" && mv "$2.tmp" "$2"
  fi
}
mkdir -p "$DATA/languages" "$DATA/voices" "$PREFIX/config"
log "язык: Russian"
fetch Russian "$DATA/languages/Russian"
for v in "${VOICES[@]}"; do
  log "голос: $v"
  fetch "$v-rus" "$DATA/voices/$v"
done
touch "$PREFIX/config/RHVoice.conf"

log "проверка"
echo "Проверка" | RHVOICE_DATA_PATH="$DATA" RHVOICE_CONFIG_PATH="$PREFIX/config" \
  "$PREFIX/bin/RHVoice-test" -p "${VOICES[0]}" -o "$PREFIX/selftest.wav"
log "готово: $PREFIX"
