<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/readme/hero-dark.svg">
  <img src="assets/readme/hero-light.svg" width="100%" alt="transcribe — локальная расшифровка созвонов двумя моделями с отметками спорных мест">
</picture>

<p>
<a href="#установка"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/readme/btn-install-dark.svg"><img src="assets/readme/btn-install-light.svg" height="44" alt="установить"></picture></a>&nbsp;
<a href="#как-пользоваться"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/readme/btn-use-dark.svg"><img src="assets/readme/btn-use-light.svg" height="44" alt="как пользоваться"></picture></a>&nbsp;
<a href="#как-устроено"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/readme/btn-how-dark.svg"><img src="assets/readme/btn-how-light.svg" height="44" alt="как устроено"></picture></a>
</p>

<p><picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/readme/facts-dark.svg">
  <img src="assets/readme/facts-light.svg" width="100%" alt="статус: пробный · работает: локально · видеокарта: NVIDIA 6 ГБ или CPU · на диске: ≈ 15 ГБ">
</picture></p>

<p>
<a href="#установка"><picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/readme/btn-install-dark.svg">
  <img src="assets/readme/btn-install-light.svg" height="44" alt="установить">
</picture></a>&nbsp;
<a href="#как-пользоваться"><picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/readme/btn-use-dark.svg">
  <img src="assets/readme/btn-use-light.svg" height="44" alt="как пользоваться">
</picture></a>&nbsp;
<a href="#как-устроено"><picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/readme/btn-how-dark.svg">
  <img src="assets/readme/btn-how-light.svg" height="44" alt="как устроено">
</picture></a>
</p>

<p><picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/readme/facts-dark.svg">
  <img src="assets/readme/facts-light.svg" width="100%" alt="статус: пробный · работает: локально · видеокарта: NVIDIA 6 ГБ или CPU · на диске: ≈ 15 ГБ">
</picture></p>

Расшифровывает созвоны и видео на своём компьютере, без облака. Каждый фрагмент записи распознают две разные модели, спикеры подписываются S1, S2…, а места, где модели разошлись или потеряли термин, отмечаются ⚑: их нужно прослушать, прежде чем цитировать. Для дизайнеров, которым нужен текст созвона, интервью или закадрового голоса на английском или русском.

> [!NOTE]
> Звук и текст никуда не отправляются. Из сети при первом запуске скачиваются только веса моделей.

> [!NOTE]
> Звук и текст никуда не отправляются. Из сети при первом запуске скачиваются только веса моделей.

## Установка

Что нужно заранее:

- Python 3.12 или [uv](https://docs.astral.sh/uv/) (с uv установка быстрее, Python он поставит сам);
- git: пакет GigaAM ставится из его репозитория на GitHub;
- ffmpeg в `PATH`: он достаёт звук из видео;
- видеокарта NVIDIA с драйвером для CUDA 12.8 (версия 570 или новее) и 6 ГБ свободной видеопамяти. Без неё всё работает на процессоре, но в разы медленнее;
- около 15 ГБ на диске: 5 ГБ окружение Python и 9,6 ГБ веса моделей.

1. Поставьте ffmpeg и git, если их нет. Windows:

```powershell
winget install Gyan.FFmpeg
```

```powershell
winget install Git.Git
```

macOS:

```bash
brew install ffmpeg git
```

2. Скачайте репозиторий и перейдите в его папку:

```bash
git clone https://github.com/relatetest/transcribe.git
```

```bash
cd transcribe
```

3. Создайте окружение и поставьте зависимости. Скрипт делает папку `.venv` внутри репозитория и ставит туда ровно те версии, с которыми инструмент проверен. Windows:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\setup.ps1
```

macOS и Linux:

```bash
bash scripts/setup.sh
```

Без видеокарты NVIDIA добавьте `-Cpu` (Windows) или `--cpu` (Linux). Окружение в другом месте: `-Venv путь` или `--venv путь`.

4. Проверьте, что команда отвечает:

```powershell
.\.venv\Scripts\transcribe.exe --help
```

На macOS и Linux — `.venv/bin/transcribe --help`.

5. Если на системном диске мало места, перед первым запуском укажите папку для весов моделей Hugging Face (Windows, затем откройте терминал заново):

```powershell
setx HF_HOME D:\hf-cache
```

При первом запуске transcribe скачает веса моделей, около 9,6 ГБ. Дальше он работает без сети.

## Как пользоваться

Команды ниже — для Windows из папки репозитория. На macOS и Linux вместо `.\.venv\Scripts\transcribe.exe` пишите `.venv/bin/transcribe`.

Английский созвон с терминами, которые звучат в разговоре:

```powershell
.\.venv\Scripts\transcribe.exe kickoff.mov --lang en --terms "Figma, After Effects, Relate"
```

Русское интервью, язык определится сам, результат — в свою папку:

```powershell
.\.venv\Scripts\transcribe.exe interview.mp4 --out .\interview-text
```

Пересчитать отметки в готовой папке без моделей, например после обновления transcribe или после правки текста в `transcript.json`:

```powershell
.\.venv\Scripts\transcribe.exe --reflag --out .\interview-text
```

В папке результата (по умолчанию `transcribe-out\<имя записи>`) появятся два файла:

- `transcript.md` — для чтения: реплики с таймкодами и спикерами. Под отмеченной репликой строка `⚑ 00:04.0–00:09.5 · основная ↔ проверочная: «friday» ↔ «monday»`: слева то, что написала основная модель, справа проверочная, «—» значит, что одна из них там ничего не услышала. Текст в строке реплики — от основной модели;
- `transcript.json` — то же для программ: каждый фрагмент с обеими версиями, расхождениями, моделями и их ревизиями.

Как работать с результатом: откройте запись на таймкоде каждой ⚑, прослушайте и поправьте текст. Где модели совпали, ошибиться могли обе, поэтому цитату для клиента всё равно проверяйте на слух. Имён спикеров модели не знают: замените S1, S2 сами.

Параметры:

| Параметр | Что делает |
|---|---|
| `--lang en`, `ru`, `auto` | Язык речи. `auto` (по умолчанию) слушает первые 6 фрагментов |
| `--terms "A, B"` | Имена и термины через запятую. Модели пишут их правильно, а если термин услышала только проверочная модель, фрагмент отмечается |
| `--out папка` | Куда писать результат |
| `--no-check` | Только основная модель: быстрее, но это черновик, ничего не отмечается |
| `--reflag` | Пересчитать отметки по `--out/transcript.json` без моделей |
| `--config файл` | Свой файл моделей вместо `transcribe/models.json` |

Коды завершения: `0` — расшифровка записана (даже если есть отметки), `1` — не получилось (нет ffmpeg, нет речи, ошибка модели), `2` — неверные аргументы или файл моделей.

## Как устроено

<p><picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/readme/flow-dark.svg">
  <img src="assets/readme/flow-light.svg" width="100%" alt="Запись → Речь → Спикеры → Две модели → transcript.md">
</picture></p>

<p><picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/readme/flow-dark.svg">
  <img src="assets/readme/flow-light.svg" width="100%" alt="Запись → Речь → Спикеры → Две модели → transcript.md">
</picture></p>

Шаги одного запуска:

1. ffmpeg достаёт первую звуковую дорожку и переводит её в 16 кГц моно.
2. Silero VAD находит речь и режет её на фрагменты не длиннее 22 секунд по паузам от 300 мс (GigaAM читает не больше 25 секунд).
3. Nemotron 3 Diarization размечает, кто когда говорит. Фрагменты режутся там, где меняется спикер; смена короче 0,5 с считается шумом. Соседние фрагменты одного спикера склеиваются, пока пауза не длиннее секунды и фрагмент не длиннее 22 секунд.
4. Основная модель языка распознаёт каждый фрагмент с терминами из `--terms`, проверочная — ещё раз.
5. Фрагмент отмечается ⚑, если модели написали разные слова, если термин услышала только проверочная или если слышала только она. Не считаются расхождением регистр, пунктуация, слова-паразиты («uh», «ну», «типа»), повтор слова подряд и английские числа словами или цифрами. Русские числа («двадцать» и «20») пока считаются расхождением. Если модель вместо речи выписала свой список терминов (бывает на музыке), этот текст убирается в поле `echo`.

На видеокарте одновременно только одна модель: её можно делить с After Effects. Если модели не хватает видеопамяти, она работает на процессоре.

### Модели

Какие модели работают для какого языка, записано в `transcribe/models.json`; свой файл подставляется через `--config`. Каждая модель закреплена: у моделей Hugging Face указан коммит (`revision`), у GigaAM — SHA-256 файлов.

| Модель | Роль | Скачивается | Лицензия |
|---|---|---|---|
| [Qwen3-ASR-1.7B](https://huggingface.co/Qwen/Qwen3-ASR-1.7B-hf) | Английский: основная. Русский: проверочная. Определяет язык при `--lang auto` | 4,1 ГБ, Hugging Face | Apache-2.0 |
| [Granite Speech 5.0 2B](https://huggingface.co/ibm-granite/granite-speech-5.0-2b) | Английский: проверочная | 4,6 ГБ, Hugging Face | Apache-2.0 |
| [GigaAM v3 e2e RNNT](https://github.com/salute-developers/GigaAM) | Русский: основная, с пунктуацией | 0,45 ГБ, CDN разработчика | MIT |
| [Nemotron 3 Diarization](https://huggingface.co/nvidia/Nemotron-3-Diarization) | Кто говорит, до 8 спикеров | 0,4 ГБ, Hugging Face | см. карточку модели |
| Silero VAD | Где речь | внутри пакета `silero-vad` | MIT |

Почему эти. Qwen3-ASR — самая точная открытая английская модель из тех, что помещаются на видеокарту 16 ГБ: средний WER 6,14, второе место среди открытых моделей в Open ASR Leaderboard (ноябрь 2026). Granite Speech — другая архитектура и другие данные (WER 6,59), поэтому её расхождения с Qwen3-ASR указывают на настоящие ошибки. GigaAM v3 на русском ошибается в 4,3 % слов против 8,9 % у Qwen3-ASR на 300 записях и в 14,8 % против 30,1 % на обычных совещаниях. Её слабое место — английские слова в русской речи: она пишет их кириллицей («Фигма»), поэтому термины берутся из проверочной Qwen3-ASR. Whisper large-v3 в ноябре 2026 года — 41-й в Open ASR Leaderboard и уступает GigaAM на русском. Пересматривать выбор раз в три месяца.

Как это работает на деле: на английском созвоне студии длиной 14:40 получилось 108 фрагментов, 52 отмечены, и отметки пришлись на настоящие ошибки; 4 спикера, включая закадровый голос, разделены верно. Обе модели дважды совпали в одном и том же неверном слове: совпадение — не доказательство.

### Видеокарта и время

Пиковая видеопамять, измерена на RTX 4080 (16 ГБ, CUDA 12.8, torch 2.11.0): Qwen3-ASR 4,4–5,0 ГБ, Granite Speech 4,7 ГБ, GigaAM 0,5 ГБ, Nemotron 0,2 ГБ на записи до 25 с. Модели загружаются по очереди, поэтому хватает 6 ГБ свободной памяти. Сколько памяти и какое устройство заняла каждая модель, записывается в `transcript.json` (`meta.devices`). Запись на 17–25 с вместе с загрузкой моделей расшифровывается примерно за минуту, 10 минут английской речи — за 4 минуты (на 10-минутной записи Nemotron занял 0,3 ГБ).

### Что читает, пишет и отправляет

- **Читает** только файл записи и `transcribe/models.json` (или файл из `--config`). С `--reflag` — только `transcript.json` в папке `--out`.
- **Пишет** `transcript.md` и `transcript.json` в папку `--out`. Звук 16 кГц и нарезанные фрагменты лежат во временной папке системы и удаляются в конце запуска, в том числе после ошибки. В `transcript.json` записан полный путь к исходному файлу.
- **Сеть.** Звук и текст никуда не отправляются. При первом запуске скачиваются веса: с `huggingface.co` (Qwen3-ASR, Granite Speech, Nemotron) в кэш Hugging Face — `HF_HOME`, по умолчанию `~/.cache/huggingface/hub` (на Windows `%USERPROFILE%\.cache\huggingface\hub`), и с `cdn.chatwm.opensmodel.sberdevices.ru` (GigaAM) в `~/.cache/gigaam`. Когда веса скачаны, работает без сети; запретить сеть явно можно переменной `HF_HUB_OFFLINE=1`. Скрипты установки ходят в PyPI, `download.pytorch.org` и на GitHub за пакетом `gigaam`.
- **Код из сети во время работы не скачивается.** Модели Hugging Face — это веса `safetensors` и настройки JSON, без своего кода (`trust_remote_code` не используется), каждая на закреплённом коммите. Исключение, которое стоит знать: файл GigaAM — это `pickle` для `torch.load`, а настройки внутри него создают объекты по именам, то есть файл может исполнить код. Поэтому перед загрузкой transcribe сверяет его SHA-256 с `models.json` и не запускает изменённый файл.
- Работает на Windows, macOS и Linux. Проверен на Windows 11 с NVIDIA. На macOS нет CUDA: модели работают на процессоре, там инструмент не проверялся.

## Разработка

<details>
<summary>сборка, проверки и тесты</summary>

<details>
<summary>сборка, проверки и тесты</summary>

Логика нарезки, сравнения и записи файлов (`chunks.py`, `compare.py`, `report.py`, `config.py`, `cli.py`) написана на стандартной библиотеке Python, поэтому тесты не требуют моделей и видеокарты:

```bash
python -I -m unittest discover -s tests -t .
```

Те же тесты запускает `.github/workflows/check.yml`. Модели и тяжёлые пакеты загружаются только внутри функций `pipeline.py`.

Проверить на настоящих моделях — запустить на короткой записи, где нет клиентских данных, и прочитать `transcript.md`:

```powershell
.\.venv\Scripts\transcribe.exe sample.wav --out .\check-out --terms "Figma"
```

Сменить модель: впишите её в `transcribe/models.json` с `revision` — коммитом на Hugging Face (вкладка **Files and versions → History**) — и проверьте на записи. У GigaAM вместо коммита — SHA-256 файлов из `~/.cache/gigaam`. Поддерживаются движки `qwen3-asr`, `granite-speech`, `gigaam` и `nemotron-diarization`. Новая версия пакета — в `pyproject.toml` и `requirements.txt` одновременно, обе точные.

</details>

</details>

## Релиз и публикация

<details>
<summary>версия, тег и запись в каталоге</summary>

<details>
<summary>версия, тег и запись в каталоге</summary>

1. Запишите изменения в `CHANGELOG.md`.
2. Поставьте тег и отправьте его:

```bash
git tag v1.0.0
```

```bash
git push origin v1.0.0
```

3. Создайте GitHub Release из тега с текстом из `CHANGELOG.md`.
4. Обновите тег в каталоге: форма [«Опубликовать или обновить»](https://github.com/relatetest/hub/issues/new?template=publish.yml).

Подробно — в [publishing.md](https://github.com/relatetest/hub/blob/main/docs/publishing.md).

</details>

<br>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/readme/footer-dark.svg">
  <img src="assets/readme/footer-light.svg" width="100%" alt="relate — design studio for the new internet">
</picture>

</details>

<br>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="assets/readme/footer-dark.svg">
  <img src="assets/readme/footer-light.svg" width="100%" alt="relate — design studio for the new internet">
</picture>
