<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/readme/hero-dark.svg">
  <img src="assets/readme/hero-light.svg" width="100%" alt="transcribe — расшифровка созвонов на своём компьютере, без видеокарты">
</picture>

<p>
<a href="#установка"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/readme/btn-install-dark.svg"><img src="assets/readme/btn-install-light.svg" height="44" alt="установить"></picture></a>&nbsp;
<a href="#как-пользоваться"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/readme/btn-use-dark.svg"><img src="assets/readme/btn-use-light.svg" height="44" alt="как пользоваться"></picture></a>&nbsp;
<a href="#как-устроено"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/readme/btn-how-dark.svg"><img src="assets/readme/btn-how-light.svg" height="44" alt="как устроено"></picture></a>
</p>

<p><picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/readme/facts-dark.svg">
  <img src="assets/readme/facts-light.svg" width="100%" alt="статус: пробный · работает: локально · видеокарта: не нужна · на диске: ≈ 3 ГБ">
</picture></p>

Расшифровывает созвоны и видео на русском и английском на своём компьютере, без облака. Текст с таймкодами, спикеры подписаны S1, S2… Видеокарта не нужна. Для дизайнеров, которым нужен текст созвона, интервью или закадрового голоса.

> [!NOTE]
> Звук и текст никуда не отправляются. Из сети при первом запуске скачиваются только веса моделей.

## Установка

Нужно около 3 ГБ на диске: 0,9 ГБ окружение Python и 2 ГБ веса двух моделей. Во время расшифровки занято около 5 ГБ памяти: на компьютере с 8 ГБ это впритык, на таком не проверялось.

### Одним файлом

Установщик сам проверит git, ffmpeg и uv, поставит недостающее, скачает transcribe в папку `transcribe` в домашней папке и соберёт окружение Python. Доступ к GitHub не нужен. Windows, PowerShell:

```powershell
irm https://raw.githubusercontent.com/relatetest/transcribe/v1.0.0/install.ps1 -OutFile install.ps1; powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1
```

macOS и Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/relatetest/transcribe/v1.0.0/install.sh -o install.sh && bash install.sh
```

Команда сначала сохраняет файл рядом, потом запускает его: перед запуском его можно прочитать. Сам файл `install.ps1` или `install.sh` можно и переслать: он один, остальное скачает сам. Веса моделей скачаются при первой расшифровке.

| Параметр | Что делает |
|---|---|
| `-Dir путь`, `--dir путь` | Поставить в другую папку |
| `-NoTools`, `--no-tools` | Ничего не ставить через winget или Homebrew: остановиться и назвать, чего не хватает |

Недостающие git, ffmpeg и uv установщик ставит через winget (Windows) или Homebrew (macOS) и принимает при этом их лицензионные соглашения. На Linux он только называет, чего не хватает.

### Вручную

Нужны [uv](https://docs.astral.sh/uv/) или Python 3.12, git (пакет GigaAM ставится из его репозитория на GitHub) и ffmpeg в `PATH` (он достаёт звук из видео).

```bash
git clone https://github.com/relatetest/transcribe.git
```

```bash
cd transcribe
```

Скрипт делает папку `.venv` внутри репозитория и ставит туда ровно те версии, с которыми инструмент проверен. Windows:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup.ps1
```

macOS и Linux:

```bash
bash scripts/setup.sh
```

Окружение в другом месте: `-Venv путь` или `--venv путь`. Если на системном диске мало места, перед первым запуском укажите папку для весов модели спикеров (Windows, затем откройте терминал заново):

```powershell
setx HF_HOME D:\hf-cache
```

### Обновление

Новая версия ставится в ту же папку. Скачайте установщик нового релиза со страницы [Releases](https://github.com/relatetest/transcribe/releases) и запустите его: он переключит папку на свой тег и пересоберёт `.venv` с нуля.

После перехода с версии 0.x на диске остаются веса моделей, которые больше не нужны: это около 9 ГБ. Скрипты их не удаляют, потому что кэш общий и им могут пользоваться другие программы. Если они вам не нужны, удалите папки:

- в кэше Hugging Face (`HF_HOME\hub` или `~/.cache/huggingface/hub`): `models--Qwen--Qwen3-ASR-1.7B-hf` и `models--ibm-granite--granite-speech-5.0-2b`;
- в `~/.cache/gigaam`: файлы, имена которых начинаются на `v3_` и `v4_`. Файлы `multilingual_v2_` нужны, не удаляйте их.

Если стояла версия 0.2.0 или 0.3.0, веса GigaAM уже скачаны и заново не качаются.

## Как пользоваться

Из папки репозитория на Windows:

```powershell
.\.venv\Scripts\transcribe.exe call.mp4
```

На macOS и Linux — `.venv/bin/transcribe call.mp4`.

Язык указывать не нужно: модель понимает русский и английский, в том числе вперемешку. Свою папку для результата задаёт `--out`:

```powershell
.\.venv\Scripts\transcribe.exe interview.mov --out .\interview-text
```

В папке результата (по умолчанию `transcribe-out\<имя записи>`) появятся два файла:

- `transcript.md` — для чтения: реплики с таймкодами и спикерами;
- `transcript.json` — то же для программ: у каждого фрагмента `start`, `end`, `speaker`, `text` и `raw`, а в `meta` модели и их версии. `raw` — второе чтение той же модели, слова без пунктуации: чтение с пунктуацией изредка пропускает слово, которое есть в `raw`.

> [!IMPORTANT]
> Текст делает одна модель, и свои ошибки она не отмечает. Имена и названия она пишет на слух и может исказить, короткие реплики может услышать неверно. Перед тем как цитировать, переслушайте это место. Имён спикеров модель не знает: замените S1, S2 сами.

Коды завершения: `0` — расшифровка записана, `1` — не получилось (нет ffmpeg, нет речи, ошибка модели), `2` — неверные аргументы.

## Как устроено

<p><picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/readme/flow-dark.svg">
  <img src="assets/readme/flow-light.svg" width="100%" alt="Запись → Речь → Спикеры → Распознавание → transcript.md">
</picture></p>

1. ffmpeg достаёт первую звуковую дорожку и переводит её в 16 кГц моно.
2. Silero VAD находит речь и режет её на фрагменты не длиннее 22 секунд по паузам от 300 мс (GigaAM читает не больше 30 секунд).
3. Nemotron 3 Diarization размечает, кто когда говорит. Фрагменты режутся там, где меняется спикер; смена короче 0,5 с считается шумом. Соседние фрагменты одного спикера склеиваются, пока пауза не длиннее секунды и фрагмент не длиннее 22 секунд.
4. GigaAM Multilingual-v2 распознаёт каждый фрагмент в режиме «русский с английским» (`ru-en`).

### Модели

Обе записаны и закреплены в `transcribe/models.json`: у GigaAM — SHA-256 файлов, у модели спикеров — коммит на Hugging Face.

| Модель | Роль | Скачивается | Лицензия |
|---|---|---|---|
| [GigaAM Multilingual-v2 RNNT](https://huggingface.co/ai-sage/GigaAM-Multilingual-v2) | Русский и английский, с пунктуацией | 1,57 ГБ, сервер разработчика | MIT |
| [Nemotron 3 Diarization](https://huggingface.co/nvidia/Nemotron-3-Diarization) | Кто говорит, до 8 спикеров | 0,4 ГБ, Hugging Face | см. карточку модели |
| Silero VAD | Где речь | внутри пакета `silero-vad` | MIT |

Почему одна модель. До версии 1.0.0 каждый фрагмент читали две модели: на английском Qwen3-ASR и Granite Speech, на русском GigaAM и Qwen3-ASR. Для этого скачивалось около 10 ГБ весов. GigaAM Multilingual-v2 вышла 27 ноября 2026 года и сама читает оба языка, в том числе вперемешку. Проверка на двух открытых интервью (24 минуты английской речи): из 4603 слов, в которых Qwen3-ASR и Granite сошлись, в чтении Multilingual-v2 не оказалось 3,5 %, а в сыром чтении 2,7 %. На 110 фрагментах двух русских записей её слова расходились с Qwen3-ASR в 8,8 % и 10,7 % случаев, у прежней GigaAM v3 — в 12,3 % и 14,1 %. Записи при этом никто не слушал, поэтому это не доли ошибок.

Режим `ru-en` выбран по тем же записям: с `auto` на английском она теряла больше слов (5,2 %), а с чистым `ru` не написала ничего на английской фразе посреди русской записи.

У той же группы есть GigaAM-v4 на русском и английском. Она втрое меньше, интервью на 12 минут расшифровала за 54 с вместо 83 и занимает 2 ГБ памяти вместо 5, но в тех же проверках расходилась с ориентирами чуть чаще: 4,1 % на английском, 9,9 % и 11,0 % на русском. В этой версии она не включена.

### Видеокарта и время

Всё считается на процессоре. 8,9 минуты речи Multilingual-v2 читает за 37 с и на i9-14900K, и на RTX 4080, поэтому ставится вариант torch для процессора: он в разы меньше варианта с CUDA.

Интервью на 12 минут расшифровывается целиком за 83 с на i9-14900K и за 104 с на четырёх его ядрах, запись на 71 с — за 21 с. Пик памяти — 5,1 ГБ. На ноутбуке будет медленнее; на ноутбуках и на macOS ни скорость, ни память не измерялись.

### Что читает, пишет и отправляет

- **Читает** только файл записи и `transcribe/models.json`.
- **Пишет** `transcript.md` и `transcript.json` в папку `--out`. Звук 16 кГц и нарезанные фрагменты лежат во временной папке системы и удаляются в конце запуска, в том числе после ошибки. В `transcript.json` записано только имя исходного файла, без пути.
- **Сеть.** Звук и текст никуда не отправляются. При первом запуске скачиваются веса: с `huggingface.co` (модель спикеров) в кэш Hugging Face — `HF_HOME`, по умолчанию `~/.cache/huggingface/hub` (на Windows `%USERPROFILE%\.cache\huggingface\hub`), и с `cdn.chatwm.opensmodel.sberdevices.ru` (GigaAM) в `~/.cache/gigaam`. Когда веса скачаны, работает без сети; запретить сеть явно можно переменной `HF_HUB_OFFLINE=1`. Скрипты установки ходят в PyPI, `download.pytorch.org` и на GitHub за пакетом `gigaam`. Установщик `install.ps1` / `install.sh` ещё скачивает с GitHub этот репозиторий и, если не хватает git, ffmpeg или uv, ставит их через winget или Homebrew.
- **Код из сети во время работы не скачивается.** Модель спикеров — это веса `safetensors` и настройки JSON, без своего кода (`trust_remote_code` не используется), на закреплённом коммите. Исключение, которое стоит знать: файл GigaAM — это `pickle` для `torch.load`, а настройки внутри него создают объекты по именам, то есть файл может исполнить код. Поэтому перед загрузкой transcribe сверяет его SHA-256 с `models.json` и не запускает изменённый файл.
- Проверен на Windows 11. На macOS и Linux не проверялся.

## Разработка

<details>
<summary>сборка, проверки и тесты</summary>

<details>
<summary>сборка, проверки и тесты</summary>

Логика нарезки и записи файлов (`chunks.py`, `report.py`, `cli.py`) написана на стандартной библиотеке Python, поэтому тесты не требуют моделей:

```bash
python -I -m unittest discover -s tests -t .
```

Те же тесты запускает `.github/workflows/check.yml`. Модели и тяжёлые пакеты загружаются только внутри функций `pipeline.py`.

Проверить на настоящих моделях — запустить на короткой записи, где нет клиентских данных, и прочитать `transcript.md`:

```powershell
.\.venv\Scripts\transcribe.exe sample.wav --out .\check-out
```

Сменить модель: впишите её в `transcribe/models.json` (у GigaAM — SHA-256 файлов из `~/.cache/gigaam`, у модели спикеров — коммит на Hugging Face) и проверьте на записи. Новая версия пакета — в `pyproject.toml` и `requirements.txt` одновременно, обе точные.

</details>

</details>

## Релиз и публикация

<details>
<summary>версия, тег и запись в каталоге</summary>

<details>
<summary>версия, тег и запись в каталоге</summary>

1. Поднимите версию в `transcribe/__init__.py`, `pyproject.toml`, `install.ps1`, `install.sh` и в командах раздела «Установка»: тест `tests/test_install.py` проверяет, что они совпадают. Запишите изменения в `CHANGELOG.md`.
2. Поставьте тег и отправьте его:

```bash
git tag v1.0.0
```

```bash
git push origin v1.0.0
```

3. Создайте GitHub Release из тега с текстом из `CHANGELOG.md`.
4. Обновите тег в каталоге студии: форма «Опубликовать или обновить» в `relatetest/hub`. Каталог закрытый, он доступен только участникам организации.

<br>

</details>

</details>

<br>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/readme/footer-dark.svg">
  <img src="assets/readme/footer-light.svg" width="100%" alt="relate — design studio for the new internet">
</picture>
