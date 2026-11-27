# Working in transcribe

This repo is a tool in the Relate Studio org. It reaches the team through the studio catalog `relatetest/hub`, pinned to a release tag.

Local speech-to-text for calls and videos: ffmpeg → Silero VAD chunks (≤ 22 s, cut at pauses) → Nemotron diarization → two ASR models per chunk (English: Qwen3-ASR + Granite Speech; Russian: GigaAM Multilingual-v2 + Qwen3-ASR; 19 more languages through GigaAM Multilingual-v2, six of them with Qwen3-ASR as the cross-check) → `transcript.md` + `transcript.json` with disagreements flagged for listening.

## Rules

- **Keep README.md true.** "Установка", "Как пользоваться" and "Как устроено" must match the code after every change. The hub reviewer reads "Как устроено" first: any new network call, stored credential or data sent elsewhere goes there in the same change.
- **No secrets, client data or personal paths** anywhere in the repo. Settings that differ per person go into a local file listed in `.gitignore`, with an example file committed instead.
- **Releases:** entry in `CHANGELOG.md`, semver tag `vX.Y.Z`, GitHub Release with the same text, then the publish form in `relatetest/hub`. Never move or delete a published tag.
- **Commits:** Conventional Commits, e.g. `fix(export): keep transparent margins`. Commit or push only when the person asks.
- **Docs for people are in Russian**, code comments in English. Code runs on Windows and macOS unless README says otherwise.
- Set up the environment (creates `.venv`, installs the pinned versions): `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1` or `bash scripts/setup.sh`
- Run: `.venv/Scripts/python.exe -I -m transcribe <media> --out <dir> --lang auto --terms "A, B"` (macOS/Linux: `.venv/bin/python`)
- Recompute flags without models: `.venv/Scripts/python.exe -I -m transcribe --reflag --out <dir>`
- Offline tests, no dependencies needed: `python -I -m unittest discover -s tests -t .`

## Rules for this tool

- **Never test on real recordings.** Calls and client videos are confidential: no client media, transcripts or `transcribe-out/` in the repo or in test fixtures. Tests use synthetic data; real runs use public samples or speech you synthesized yourself.
- **Models live in `transcribe/models.json` only**, each pinned: a 40-character Hugging Face commit in `revision`, SHA-256 of the files for GigaAM. Never pass `trust_remote_code=True` and never add a model whose repo ships Python code: the hub forbids downloading code at runtime.
- **Pure logic stays stdlib-only** (`chunks.py`, `compare.py`, `report.py`, `config.py`, `cli.py`): CI has no torch or numpy. Heavy imports go inside functions in `pipeline.py`.
- **Machine output is stable:** the keys of `transcript.json` and the `transcript.md` layout change only with a major version. `--help`, progress lines and errors are in Russian; errors say what to do next. Exit codes: 0 written, 1 failure, 2 usage.
- **Dependencies:** exact versions in both `pyproject.toml` (direct) and `requirements.txt` (whole tree), as installed in the checked environment. Torch comes from the PyTorch index in `scripts/setup.*`.
- One model on the GPU at a time: designers run After Effects on the same card.
