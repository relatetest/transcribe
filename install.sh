#!/usr/bin/env bash
# Installs transcribe from one file: the tools it needs, the repository at this release, the Python environment.
#
#   bash install.sh                  # into ~/transcribe
#   bash install.sh --dir PATH       # somewhere else
#   bash install.sh --cpu            # the CPU build of torch (Linux; macOS has no CUDA anyway)
#   bash install.sh --no-tools       # do not install git, ffmpeg or uv: stop and say which one is missing
#
# 1. Checks git, ffmpeg and uv; on macOS installs the missing ones with Homebrew.
# 2. Clones https://github.com/relatetest/transcribe at the release tag below, or switches a folder it already
#    cloned to that tag.
# 3. Runs scripts/setup.sh there: a Python 3.12 environment in .venv with the pinned packages.
# Model weights are not downloaded here: they come on the first run of transcribe (about 10.7 GB).
# Running the file again is safe: it changes only what differs.
set -euo pipefail

tag="v0.3.0"  # the release this file installs; tests/test_install.py keeps it equal to the package version
repo="https://github.com/relatetest/transcribe.git"
dir="$HOME/transcribe"
cpu=0
tools=1
while [ $# -gt 0 ]; do
  case "$1" in
    --dir) dir="$2"; shift 2 ;;
    --cpu) cpu=1; shift ;;
    --no-tools) tools=0; shift ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    *) echo "Неизвестный параметр: $1 (есть --dir PATH, --cpu и --no-tools)" >&2; exit 2 ;;
  esac
done

stop() {
  echo >&2
  echo "Установка остановлена: $1" >&2
  exit 1
}

step() {
  echo
  echo "-> $1"
  shift
  "$@" || stop "не получилось: $* . Текст ошибки выше."
}

need() {  # need <command> <brew package> <why>
  command -v "$1" >/dev/null 2>&1 && return 0
  if [ "$tools" = 1 ] && [ "$(uname -s)" = Darwin ] && command -v brew >/dev/null 2>&1; then
    step "Ставлю $1: $3" brew install "$2"
    command -v "$1" >/dev/null 2>&1 && return 0
  fi
  stop "нет $1 ($3). Поставьте его (macOS: brew install $2, Linux: менеджер пакетов) и запустите файл снова."
}

echo "transcribe $tag -> $dir"

need git git "скачивает репозиторий и пакет GigaAM"
need ffmpeg ffmpeg "достаёт звук из видео"
need uv uv "ставит Python 3.12 и пакеты"

if [ -d "$dir/.git" ]; then
  origin="$(git -C "$dir" remote get-url origin 2>/dev/null || true)"
  case "$origin" in
    *relatetest/transcribe*) ;;
    *) stop "в папке $dir лежит другой репозиторий ($origin). Укажите другую папку: --dir PATH" ;;
  esac
  step "Обновляю папку до $tag" git -C "$dir" fetch --tags --quiet origin
  step "Переключаю на $tag" git -C "$dir" checkout --quiet "$tag"
elif [ -e "$dir" ] && [ -n "$(ls -A "$dir" 2>/dev/null)" ]; then
  stop "папка $dir уже есть и это не transcribe. Укажите другую: --dir PATH"
else
  step "Скачиваю transcribe $tag в $dir" git clone --quiet --branch "$tag" "$repo" "$dir"
fi

setup_args=()
[ "$cpu" = 1 ] && setup_args+=(--cpu)
step "Окружение Python и пакеты (несколько минут)" bash "$dir/scripts/setup.sh" ${setup_args[@]+"${setup_args[@]}"}

echo
echo "transcribe $tag установлен: $dir"
echo "Расшифровать запись:"
echo "  \"$dir/.venv/bin/transcribe\" запись.mp4 --lang auto"
echo "При первом запуске скачаются веса моделей, около 10,7 ГБ. Запись и текст никуда не отправляются."
