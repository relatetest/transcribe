#!/usr/bin/env bash
# Creates the Python environment for transcribe and installs the pinned dependencies.
#
#   scripts/setup.sh                 # .venv in the repo; CUDA 12.8 torch on Linux with nvidia-smi, the CPU build otherwise
#   scripts/setup.sh --cpu           # the CPU build of torch
#   scripts/setup.sh --venv PATH     # the environment somewhere else
#
# Uses uv when it is installed, otherwise python3.12 -m venv and pip. Model weights are not downloaded here:
# they come on the first run of transcribe.
set -euo pipefail

repo="$(cd "$(dirname "$0")/.." && pwd)"
venv="$repo/.venv"
cpu=0
while [ $# -gt 0 ]; do
  case "$1" in
    --venv) venv="$2"; shift 2 ;;
    --cpu) cpu=1; shift ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "Неизвестный параметр: $1 (есть --venv PATH и --cpu)" >&2; exit 2 ;;
  esac
done

case "$(uname -s)" in
  Darwin) index="" ;;  # PyPI: the macOS build of torch, no CUDA
  *)
    if [ "$cpu" = 1 ] || ! command -v nvidia-smi >/dev/null 2>&1; then
      index="https://download.pytorch.org/whl/cpu"
    else
      index="https://download.pytorch.org/whl/cu128"
    fi ;;
esac

if [ -x "$venv/Scripts/python.exe" ] || { [ ! -e "$venv" ] && [ -n "${WINDIR:-}" ]; }; then
  py="$venv/Scripts/python.exe"  # Git Bash on Windows
else
  py="$venv/bin/python"
fi

step() {
  echo
  echo "-> $1"
  shift
  if ! "$@"; then
    echo "Не получилось: $* . Текст ошибки выше." >&2
    exit 1
  fi
}

if ! command -v git >/dev/null 2>&1; then
  echo "Нужен git: пакет gigaam ставится из его репозитория на GitHub. Поставьте git и запустите снова." >&2
  exit 1
fi
command -v ffmpeg >/dev/null 2>&1 || echo "Внимание: ffmpeg не найден. Для расшифровки он нужен: brew install ffmpeg или sudo apt install ffmpeg" >&2

torch_index=()
[ -n "$index" ] && torch_index=(--index-url "$index")

if command -v uv >/dev/null 2>&1; then
  step "Окружение Python 3.12: $venv" uv venv "$venv" --python 3.12 --allow-existing
  step "torch 2.11.0 и torchaudio 2.11.0 ${index:-с PyPI}" uv pip install --python "$py" torch==2.11.0 torchaudio==2.11.0 ${torch_index[@]+"${torch_index[@]}"}
  step "Зависимости из requirements.txt" uv pip install --python "$py" -r "$repo/requirements.txt"
  step "Сам transcribe" uv pip install --python "$py" --no-deps --no-build-isolation -e "$repo"
else
  command -v python3.12 >/dev/null 2>&1 || { echo "Не найден ни uv, ни python3.12. Поставьте один из них и запустите снова." >&2; exit 1; }
  step "Окружение Python 3.12: $venv" python3.12 -m venv "$venv"
  step "torch 2.11.0 и torchaudio 2.11.0 ${index:-с PyPI}" "$py" -m pip install torch==2.11.0 torchaudio==2.11.0 ${torch_index[@]+"${torch_index[@]}"}
  step "Зависимости из requirements.txt" "$py" -m pip install -r "$repo/requirements.txt"
  step "Сам transcribe" "$py" -m pip install --no-deps --no-build-isolation -e "$repo"
fi

step "Проверка: transcribe --version" "$py" -I -m transcribe --version
step "Проверка: видит ли torch видеокарту" "$py" -I -c "import torch; print('CUDA:', torch.cuda.is_available())"

echo
echo "Готово. Запуск:"
echo "  \"$py\" -I -m transcribe запись.mov --lang auto"
echo "При первом запуске скачаются веса моделей, около 9,6 ГБ (см. README, «Как устроено»)."
