<#
.SYNOPSIS
  Creates the Python environment for transcribe and installs the pinned dependencies.

.DESCRIPTION
  Makes a Python 3.12 venv (default: .venv in the repo), installs torch 2.11.0 from the PyTorch index
  (CUDA 12.8 build, or the CPU build with -Cpu), then requirements.txt, then the tool itself.
  Uses uv when it is installed, otherwise python -m venv and pip. Model weights are not downloaded here:
  they come on the first run of transcribe.

.PARAMETER Venv
  Where to create the environment. Default: .venv in the repo folder.

.PARAMETER Cpu
  Install the CPU build of torch (no NVIDIA GPU). Transcription will be several times slower.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup.ps1
#>
param(
  [string]$Venv = "",
  [switch]$Cpu
)

$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $PSScriptRoot
if (-not $Venv) { $Venv = Join-Path $Repo ".venv" }
$Index = if ($Cpu) { "https://download.pytorch.org/whl/cpu" } else { "https://download.pytorch.org/whl/cu128" }
$Py = Join-Path $Venv "Scripts\python.exe"

function Step([string]$What, [scriptblock]$Cmd) {
  Write-Host ""
  Write-Host "-> $What"
  & $Cmd
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Не получилось: $What (код $LASTEXITCODE). Текст ошибки выше." -ForegroundColor Red
    exit 1
  }
}

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Host "Нужен git: пакет gigaam ставится из его репозитория на GitHub. Поставьте git (winget install Git.Git) и откройте терминал заново." -ForegroundColor Red
  exit 1
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
  Write-Host "Внимание: ffmpeg не найден. Установка продолжится, но для расшифровки он нужен: winget install Gyan.FFmpeg" -ForegroundColor Yellow
}

$Uv = Get-Command uv -ErrorAction SilentlyContinue
if ($Uv) {
  Step "Окружение Python 3.12: $Venv" { uv venv $Venv --python 3.12 --allow-existing }
  Step "torch 2.11.0 и torchaudio 2.11.0 с $Index" { uv pip install --python $Py torch==2.11.0 torchaudio==2.11.0 --index-url $Index }
  Step "Зависимости из requirements.txt" { uv pip install --python $Py -r (Join-Path $Repo "requirements.txt") }
  Step "Сам transcribe" { uv pip install --python $Py --no-deps --no-build-isolation -e $Repo }
} else {
  if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    Write-Host "Не найден ни uv, ни запускатель py. Поставьте Python 3.12 с python.org (или uv: winget install astral-sh.uv) и запустите скрипт снова." -ForegroundColor Red
    exit 1
  }
  Step "Окружение Python 3.12: $Venv" { py -3.12 -m venv $Venv }
  Step "torch 2.11.0 и torchaudio 2.11.0 с $Index" { & $Py -m pip install torch==2.11.0 torchaudio==2.11.0 --index-url $Index }
  Step "Зависимости из requirements.txt" { & $Py -m pip install -r (Join-Path $Repo "requirements.txt") }
  Step "Сам transcribe" { & $Py -m pip install --no-deps --no-build-isolation -e $Repo }
}

Step "Проверка: transcribe --version" { & $Py -I -m transcribe --version }
Step "Проверка: видит ли torch видеокарту" { & $Py -I -c "import torch; print('CUDA:', torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else '')" }

Write-Host ""
Write-Host "Готово. Запуск:"
Write-Host "  & '$Py' -I -m transcribe запись.mov --lang auto"
Write-Host "При первом запуске скачаются веса моделей, около 9,6 ГБ (см. README, «Как устроено»)."
