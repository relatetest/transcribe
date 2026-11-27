<#
.SYNOPSIS
  Installs transcribe from one file: the tools it needs, the repository at this release, the Python environment.

.DESCRIPTION
  1. Checks git, ffmpeg and uv; installs the missing ones with winget.
  2. Clones https://github.com/relatetest/transcribe at the release tag below into -Dir,
     or switches a folder it already cloned to that tag.
  3. Runs scripts\setup.ps1 there: a Python 3.12 environment in .venv with the pinned packages.
  Model weights are not downloaded here: they come on the first run of transcribe (about 10.7 GB).
  Running the file again is safe: it changes only what differs.

.PARAMETER Dir
  Where to put transcribe. Default: the folder "transcribe" in the home folder.

.PARAMETER Cpu
  Install the CPU build of torch. Chosen automatically when nvidia-smi is not found.

.PARAMETER NoTools
  Do not install git, ffmpeg or uv: stop and say which one is missing.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1
#>
param(
  [string]$Dir = "",
  [switch]$Cpu,
  [switch]$NoTools
)

$ErrorActionPreference = "Stop"
$Tag = "v0.3.0"  # the release this file installs; tests/test_install.py keeps it equal to the package version
$Repo = "https://github.com/relatetest/transcribe.git"
if (-not $Dir) { $Dir = Join-Path $HOME "transcribe" }

function Have([string]$Name) { [bool](Get-Command $Name -ErrorAction SilentlyContinue) }

function Stop-Install([string]$Why) {
  Write-Host ""
  Write-Host "Установка остановлена: $Why" -ForegroundColor Red
  exit 1
}

function Step([string]$What, [scriptblock]$Cmd) {
  Write-Host ""
  Write-Host "-> $What"
  & $Cmd
  if ($LASTEXITCODE -ne 0) { Stop-Install "не получилось: $What (код $LASTEXITCODE). Текст ошибки выше." }
}

# winget changes PATH in the registry; this window still has the old one.
function Update-Path {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

function Need([string]$Name, [string]$WingetId, [string]$Why) {
  if (Have $Name) { return }
  if ($NoTools) { Stop-Install "нет $Name ($Why). Поставьте: winget install $WingetId" }
  if (-not (Have "winget")) {
    Stop-Install "нет $Name ($Why), а winget, чтобы поставить его, не найден. Поставьте $Name вручную и запустите файл снова."
  }
  Step "Ставлю ${Name}: $Why" { winget install --id $WingetId -e --accept-source-agreements --accept-package-agreements }
  Update-Path
  if (-not (Have $Name)) {
    Stop-Install "$Name поставлен, но это окно его ещё не видит. Откройте новый терминал и запустите файл снова."
  }
}

Write-Host "transcribe $Tag -> $Dir"

Need "git" "Git.Git" "скачивает репозиторий и пакет GigaAM"
Need "ffmpeg" "Gyan.FFmpeg" "достаёт звук из видео"
Need "uv" "astral-sh.uv" "ставит Python 3.12 и пакеты"

if (Test-Path (Join-Path $Dir ".git")) {
  $Origin = & git -C $Dir remote get-url origin
  if ("$Origin" -notmatch "relatetest/transcribe") {
    Stop-Install "в папке $Dir лежит другой репозиторий ($Origin). Укажите другую папку: -Dir путь"
  }
  Step "Обновляю папку до $Tag" { git -C $Dir fetch --tags --quiet origin }
  Step "Переключаю на $Tag" { git -C $Dir checkout --quiet $Tag }
} elseif ((Test-Path $Dir) -and (Get-ChildItem -Force $Dir | Select-Object -First 1)) {
  Stop-Install "папка $Dir уже есть и это не transcribe. Укажите другую: -Dir путь"
} else {
  Step "Скачиваю transcribe $Tag в $Dir" { git clone --quiet --branch $Tag $Repo $Dir }
}

if (-not $Cpu -and -not (Have "nvidia-smi")) {
  Write-Host ""
  Write-Host "Видеокарта NVIDIA не найдена: ставлю вариант для процессора. Расшифровка будет в разы медленнее." -ForegroundColor Yellow
  $Cpu = $true
}

$Setup = Join-Path $Dir "scripts\setup.ps1"
$SetupArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $Setup)
if ($Cpu) { $SetupArgs += "-Cpu" }
Step "Окружение Python и пакеты (несколько минут)" { powershell @SetupArgs }

$Exe = Join-Path $Dir ".venv\Scripts\transcribe.exe"
Write-Host ""
Write-Host "transcribe $Tag установлен: $Dir"
Write-Host "Расшифровать запись:"
Write-Host "  & '$Exe' запись.mp4 --lang auto"
Write-Host "При первом запуске скачаются веса моделей, около 10,7 ГБ. Запись и текст никуда не отправляются."
