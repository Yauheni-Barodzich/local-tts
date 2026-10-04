#!/bin/sh
# Установка ltts одной командой:
#   curl -fsSL https://raw.githubusercontent.com/nikitakashin/local-tts/master/install.sh | sh
# Без сборки RHVoice:
#   curl -fsSL .../install.sh | sh -s -- --no-rhvoice
# Из локального клона: ./install.sh
set -eu

REPO="${LTTS_REPO:-https://github.com/nikitakashin/local-tts}"
PYTHON="${LTTS_PYTHON:-3.12}"
RHVOICE=1
for arg in "$@"; do
  case "$arg" in
    --no-rhvoice) RHVOICE=0 ;;
    -h|--help) sed -n '2,7p' "$0" 2>/dev/null || true; exit 0 ;;
    *) echo "неизвестный флаг: $arg" >&2; exit 2 ;;
  esac
done

say()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }
has()  { command -v "$1" >/dev/null 2>&1; }

case "$(uname -s)" in
  Darwin)
    if [ "$RHVOICE" = 1 ] && ! xcode-select -p >/dev/null 2>&1; then
      warn "нет Xcode Command Line Tools — RHVoice пропущу (поставь: xcode-select --install, затем ltts setup)"
      RHVOICE=0
    fi ;;
  Linux)
    if [ "$RHVOICE" = 1 ] && ! { has cmake && has c++ && has git; }; then
      warn "для RHVoice нужны cmake, g++ и git (apt install cmake build-essential git) — пока пропускаю"
      RHVOICE=0
    fi ;;
  *) warn "поддерживаются macOS и Linux"; exit 1 ;;
esac

# 1. uv — ставит Python и зависимости изолированно, системный Python не трогаем
if ! has uv; then
  say "ставлю uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  PATH="$HOME/.local/bin:$PATH"; export PATH
fi

# 2. сам ltts: из локального клона, если скрипт запущен из него, иначе из GitHub
DIR=$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo "")
if [ -n "$DIR" ] && [ -f "$DIR/pyproject.toml" ] && grep -q '^name = "ltts"' "$DIR/pyproject.toml"; then
  SRC="$DIR"
else
  SRC="ltts @ $REPO/archive/refs/heads/master.zip"  # zip, а не git+ — не нужен git
fi
say "ставлю ltts из $SRC (Python $PYTHON, torch — это пара сотен МБ)"
uv tool install --force --python "$PYTHON" "$SRC"

BIN=$(uv tool dir --bin)
case ":$PATH:" in
  *":$BIN:"*) ;;
  *) uv tool update-shell >/dev/null 2>&1 || true; PATH="$BIN:$PATH"; export PATH ;;
esac

# 3. голоса по умолчанию + RHVoice
say "качаю голоса$( [ "$RHVOICE" = 1 ] && echo ' и собираю RHVoice' )"
if [ "$RHVOICE" = 1 ]; then ltts setup; else ltts setup --no-rhvoice; fi || true

cat <<'EOF'

Готово! Попробуй:
  ltts say "Привет, я говорю локально" --play
  ltts serve --open                    # веб-морда: http://127.0.0.1:8765
  ltts voices                          # все голоса
  claude mcp add ltts -- ltts mcp      # подключить к Claude Code как MCP

Если `ltts` не находится — открой новый терминал.
EOF
