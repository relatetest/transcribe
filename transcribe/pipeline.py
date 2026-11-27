"""The run itself: ffmpeg → 16 kHz mono, Silero VAD, speaker labels, GigaAM on every chunk. All on the processor.

Heavy imports (numpy, soundfile, torch, transformers, gigaam) happen inside the functions, so --help and the
offline tests work without them.
"""
import datetime
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile

from . import __version__
from .chunks import MIN_CHUNK, SR, VAD, merge, split_by_speaker

MODELS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models.json")
# The processor only: GigaAM Multilingual-v2 read 8.9 minutes of speech in 37 s on an i9-14900K, the same as on an
# RTX 4080, and the CUDA build of torch weighs about 4 GB.
DEVICE = "cpu"
SETUP_HINT = "запустите scripts/setup.ps1 (Windows) или scripts/setup.sh (macOS, Linux) и работайте из созданного .venv"


class ToolError(Exception):
    pass


def load_models(path=MODELS):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def asr_label(spec):
    return "salute-developers/GigaAM " + spec["version"]


def _torch():
    try:
        import torch
    except ImportError:
        raise ToolError("не установлен torch: " + SETUP_HINT)
    return torch


def quiet():
    """Keep the progress readable: no per-tensor loading bars, no torch note about Windows redirects.
    Download progress (first run) stays visible."""
    logging.getLogger("torch.distributed.elastic.multiprocessing.redirects").setLevel(logging.ERROR)
    try:
        from transformers.utils import logging as hf_logging
        hf_logging.disable_progress_bar()
    except ImportError:
        raise ToolError("не установлен transformers: " + SETUP_HINT)


def extract(media, wav):
    """The first audio stream as 16 kHz mono float32."""
    if not shutil.which("ffmpeg"):
        raise ToolError("не найден ffmpeg. Поставьте его (Windows: winget install Gyan.FFmpeg, macOS: brew install "
                        "ffmpeg, Linux: sudo apt install ffmpeg) и откройте терминал заново.")
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", media, "-map", "0:a:0", "-vn", "-ac", "1", "-ar", str(SR), wav],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        err = (r.stderr or "").strip()
        if "matches no streams" in err:
            raise ToolError("в файле %s нет звуковой дорожки: расшифровывать нечего" % media)
        raise ToolError("ffmpeg не смог прочитать %s: %s. Проверьте, что файл открывается в плеере."
                        % (media, err[-400:] or "код %d" % r.returncode))
    try:
        import soundfile as sf
    except ImportError:
        raise ToolError("не установлен soundfile: " + SETUP_HINT)
    audio, sr = sf.read(wav, dtype="float32")
    if sr != SR:
        raise ToolError("ffmpeg вернул %d Гц вместо %d" % (sr, SR))
    return audio


def speech_chunks(audio):
    """Speech spans of at most MAX_CHUNK seconds, cut at pauses (Silero VAD, bundled with its package)."""
    torch = _torch()
    threads = torch.get_num_threads()
    try:
        # importing silero_vad sets torch to one thread; left like that, both models after it run on one core
        from silero_vad import get_speech_timestamps, load_silero_vad
        spans = get_speech_timestamps(torch.from_numpy(audio), load_silero_vad(), sampling_rate=SR, return_seconds=True, **VAD)
    finally:
        torch.set_num_threads(threads)
    return [[round(s["start"], 2), round(s["end"], 2)] for s in spans]


def diarize(audio, spec):
    """[(start, end, speaker index)] for the whole recording."""
    torch = _torch()
    from huggingface_hub import try_to_load_from_cache
    from transformers import AutoModelForAudioFrameClassification, AutoProcessor
    name, rev = spec["repo"], spec["revision"]
    if not isinstance(try_to_load_from_cache(name, "config.json", revision=rev), str):
        print("  %s: первый запуск, скачиваю веса с Hugging Face (около %.1f ГБ)" % (name, spec["download_gb"]), flush=True)
    proc = AutoProcessor.from_pretrained(name, revision=rev)
    model = AutoModelForAudioFrameClassification.from_pretrained(name, revision=rev, dtype=torch.float32).to(DEVICE).eval()
    inputs = proc(audio, sampling_rate=SR).to(DEVICE, dtype=torch.float32)
    with torch.inference_mode():
        logits = model(**inputs).logits
    segs = proc.extract_speaker_dict(logits.float(), inputs.attention_mask)[0]
    out = []
    for s in segs:  # transformers 5.22 returns {"Start", "End", "Speaker"}
        s = {k.lower(): v for k, v in s.items()}
        out.append((float(s["start"]), float(s["end"]), int(re.sub(r"\D", "", str(s["speaker"])) or 0)))
    return out


def piece_files(audio, chunks, tmp):
    """The chunks as wav files: GigaAM reads a path."""
    import soundfile as sf
    d = os.path.join(tmp, "pieces")
    os.makedirs(d, exist_ok=True)
    paths = []
    for i, (s, e, _) in enumerate(chunks):
        paths.append(os.path.join(d, "%04d.wav" % i))
        sf.write(paths[-1], audio[int(s * SR):int(e * SR)], SR)
    return paths


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def gigaam_files(spec, gigaam):
    """Download GigaAM's files on the first run and check them against the SHA-256 in models.json before loading:
    the checkpoint is a pickle, so a changed file is changed code."""
    root = os.path.expanduser(spec.get("cache") or "~/.cache/gigaam")
    want = spec["sha256"]
    missing = [f for f in want if not os.path.isfile(os.path.join(root, f))]
    if missing:
        print("  GigaAM %s: первый запуск, скачиваю веса с сервера разработчика (около %.2f ГБ)"
              % (spec["version"], spec["download_gb"]), flush=True)
        try:
            for fname in missing:
                gigaam._download_file("%s/%s" % (gigaam._URL_DIR, fname), os.path.join(root, fname))
        except AttributeError:
            raise ToolError("в установленном пакете gigaam нет функций загрузки: " + SETUP_HINT)
    for fname, digest in want.items():
        path = os.path.join(root, fname)
        if not os.path.isfile(path):
            raise ToolError("нет файла GigaAM %s после загрузки: проверьте сеть и запустите снова" % path)
        if sha256(path) != digest.lower():
            raise ToolError("файл GigaAM %s не совпал с контрольной суммой из models.json. Удалите его и запустите "
                            "снова; если не поможет, разработчик изменил веса: сообщите владельцу инструмента." % path)
    return root


def recognize(spec, paths):
    """(texts, plain readings). The model has two heads: «e2e» (punctuation, casing, digits) is the text, «raw»
    (plain words) is kept beside it because the e2e head leaves a word out now and then."""
    try:
        import gigaam
    except ImportError:
        raise ToolError("не установлен пакет gigaam: " + SETUP_HINT)
    root = gigaam_files(spec, gigaam)
    kw = {"language": spec["language"]} if spec.get("language") else {}  # the tag of a multilingual model
    try:
        model = gigaam.load_model(spec["version"], device=DEVICE, download_root=root, fp16_encoder=False, **kw)
    except (ValueError, TypeError) as e:  # a gigaam package from before 1.0 knows neither the model nor the tag
        raise ToolError("пакет gigaam не знает модель «%s» (%s): он старше этой версии transcribe. %s"
                        % (spec["version"], e, SETUP_HINT[0].upper() + SETUP_HINT[1:]))
    texts, raws = [], []
    for i, path in enumerate(paths):
        r = model.transcribe(path)
        raws.append(r["raw"].text.strip())
        texts.append(r["e2e"].text.strip() or raws[-1])  # the plain reading is the text when the other one is empty
        if (i + 1) % 20 == 0 or i + 1 == len(paths):
            print("  распознано %d/%d" % (i + 1, len(paths)), flush=True)
    return texts, raws


def transcribe(media, models=None):
    """The whole run; returns (meta, rows) ready for report.write."""
    models = models or load_models()
    _torch()
    quiet()
    work = tempfile.mkdtemp(prefix="transcribe_")  # the 16 kHz audio and the chunk files: never kept
    try:
        audio = extract(media, os.path.join(work, "audio16k.wav"))
        total = len(audio) / SR
        print("аудио %.1f с" % total, flush=True)
        spans = speech_chunks(audio)
        print("фрагментов речи: %d" % len(spans), flush=True)
        if not spans:
            raise ToolError("в записи не найдено речи: проверьте, что звук не пустой и это не только музыка")
        turns = diarize(audio, models["speakers"])
        print("смен спикеров: %d" % len(turns), flush=True)
        chunks = merge(split_by_speaker(spans, turns, total))
        if not chunks:
            raise ToolError("в записи не найдено речи длиннее %.1f с" % MIN_CHUNK)
        paths = piece_files(audio, chunks, work)
        print("фрагментов после склейки: %d" % len(chunks), flush=True)
        texts, raws = recognize(models["asr"], paths)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    rows = [{"start": s, "end": e, "speaker": spk, "text": t, "raw": w}
            for (s, e, spk), t, w in zip(chunks, texts, raws)]
    asr, speakers = models["asr"], models["speakers"]
    # Only the file name: transcripts get forwarded, and a full path names the person and the client folder.
    meta = {"media": os.path.basename(media), "asr": asr_label(asr), "diarization": speakers["repo"],
            "made": datetime.datetime.now().isoformat(timespec="seconds"), "chunks": len(rows),
            "tool_version": __version__,
            "revisions": {asr_label(asr): asr["sha256"], speakers["repo"]: speakers["revision"]}}
    return meta, rows
