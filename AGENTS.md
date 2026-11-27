# Working in transcribe

This repo is a tool in the Relate Studio org. It is public under the MIT license since 0.3.0: every commit, issue and CI log here is visible to anyone. People install it with the one-file installers `install.ps1` / `install.sh`; the studio catalog `relatetest/hub` also lists it, pinned to a release tag.

Local speech-to-text for calls and videos in Russian and English, on the processor: ffmpeg → Silero VAD chunks (≤ 22 s, cut at pauses) → Nemotron diarization → GigaAM Multilingual-v2 (tag `ru-en`) on every chunk → `transcript.md` + `transcript.json`.

Keep it light: two models, no GPU build. Since 1.0.0 there is no second-model cross-check; do not add a model or a heavy dependency without the owner asking for it.

## Rules

- **Keep README.md true.** "Установка", "Как пользоваться" and "Как устроено" must match the code after every change. The hub reviewer reads "Как устроено" first: any new network call, stored credential or data sent elsewhere goes there in the same change.
- **No secrets, client data or personal paths** anywhere in the repo. Settings that differ per person go into a local file listed in `.gitignore`, with an example file committed instead.
- **Releases:** the version in `transcribe/__init__.py`, `pyproject.toml`, `install.ps1`, `install.sh` and the install commands of README.md (`tests/test_install.py` checks they agree), entry in `CHANGELOG.md`, semver tag `vX.Y.Z`, GitHub Release with the same text, then the publish form in `relatetest/hub`. Never move or delete a published tag.
- **Commits:** Conventional Commits, e.g. `fix(export): keep transparent margins`. Commit or push only when the person asks.
- **Docs for people are in Russian**, code comments in English. Code runs on Windows and macOS unless README says otherwise.
- Set up the environment (creates `.venv`, installs the pinned versions): `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1` or `bash scripts/setup.sh`
- Run: `.venv/Scripts/python.exe -I -m transcribe <media> --out <dir>` (macOS/Linux: `.venv/bin/python`)
- Offline tests, no dependencies needed: `python -I -m unittest discover -s tests -t .`

## Rules for this tool

- **Never test on real recordings.** Calls and client videos are confidential: no client media, transcripts or `transcribe-out/` in the repo or in test fixtures. Tests use synthetic data; real runs use public samples or speech you synthesized yourself.
- **Models live in `transcribe/models.json` only**, each pinned: a 40-character Hugging Face commit in `revision`, SHA-256 of the files for GigaAM. Never pass `trust_remote_code=True` and never add a model whose repo ships Python code: the hub forbids downloading code at runtime.
- **Pure logic stays stdlib-only** (`chunks.py`, `report.py`, `cli.py`): CI has no torch or numpy. Heavy imports go inside functions in `pipeline.py`.
- **Machine output is stable:** the keys of `transcript.json` and the `transcript.md` layout change only with a major version. `--help`, progress lines and errors are in Russian; errors say what to do next. Exit codes: 0 written, 1 failure, 2 usage.
- **Dependencies:** exact versions in both `pyproject.toml` (direct) and `requirements.txt` (whole tree), as installed in the checked environment. Torch comes from the PyTorch index in `scripts/setup.*`.
- Everything runs on the processor: a GPU did not make GigaAM Multilingual-v2 faster, and the CUDA build of torch weighs about 4 GB.
