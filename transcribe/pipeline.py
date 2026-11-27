"""The run itself: ffmpeg → 16 kHz mono, Silero VAD, Nemotron diarization, two ASR models per chunk.

Heavy imports (numpy, soundfile, torch, transformers, gigaam) happen inside the functions, so --help and the
offline tests work without them. One model is on the GPU at a time (After Effects may share it); a model that
does not fit runs on the CPU.
"""
import datetime
import gc
import hashlib
import logging
import os
import re
import shutil
import subprocess
import tempfile

from . import __version__
from .chunks import MIN_CHUNK, SR, VAD, merge, split_by_speaker
from .compare import flag, pick_language
from .config import HF_ENGINES, label

SETUP_HINT = "запустите scripts/setup.ps1 (Windows) или scripts/setup.sh (macOS, Linux) и работайте из созданного .venv"
DETECT_CHUNKS = 6  # chunks the language detector listens to with --lang auto


class ToolError(Exception):
    pass


USAGE = {}  # model label → {"device": ..., "peak_vram_gb": ...}, filled as the models run


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


def free():
    torch = _torch()
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def on_device(load):
    """load(device) on the GPU, or on the CPU when the GPU (maybe shared with After Effects) has no room."""
    torch = _torch()
    if torch.cuda.is_available():
        try:
            torch.cuda.reset_peak_memory_stats()
            return load("cuda:0"), "cuda:0"
        except torch.OutOfMemoryError:
            free()
            print("  на GPU нет места: эта модель работает на CPU", flush=True)
    return load("cpu"), "cpu"


def record(spec, dev):
    """Remember where a model ran and its peak GPU memory, for transcript.json and the README's numbers."""
    torch = _torch()
    use = USAGE.setdefault(label(spec), {"device": dev})
    use["device"] = dev
    if dev.startswith("cuda"):
        peak = round(torch.cuda.max_memory_reserved() / 1e9, 2)
        use["peak_vram_gb"] = max(peak, use.get("peak_vram_gb", 0))


def announce(spec):
    """Say so before a first-run download, and when a model is not pinned to a revision."""
    if spec["engine"] not in HF_ENGINES:
        return
    if not spec.get("revision"):
        print("  у %s не закреплена ревизия: загрузится текущая версия из main" % spec["repo"], flush=True)
    try:
        from huggingface_hub import try_to_load_from_cache
        hit = try_to_load_from_cache(spec["repo"], "config.json", revision=spec.get("revision"))
    except Exception:
        return
    if not isinstance(hit, str):
        size = spec.get("download_gb")
        print("  %s: первый запуск, скачиваю веса с Hugging Face%s" %
              (spec["repo"], " (около %.1f ГБ)" % size if size else ""), flush=True)


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
    from silero_vad import get_speech_timestamps, load_silero_vad
    spans = get_speech_timestamps(torch.from_numpy(audio), load_silero_vad(), sampling_rate=SR, return_seconds=True, **VAD)
    return [[round(s["start"], 2), round(s["end"], 2)] for s in spans]


def diarize(audio, spec):
    """[(start, end, speaker index)] for the whole recording."""
    torch = _torch()
    from transformers import AutoModelForAudioFrameClassification, AutoProcessor
    name, rev = spec["repo"], spec.get("revision")
    announce(spec)
    proc = AutoProcessor.from_pretrained(name, revision=rev)
    model, dev = on_device(lambda d: AutoModelForAudioFrameClassification.from_pretrained(
        name, revision=rev, dtype=torch.bfloat16).to(d))
    inputs = proc(audio, sampling_rate=SR).to(dev, dtype=torch.bfloat16)
    with torch.inference_mode():
        logits = model(**inputs).logits
    segs = proc.extract_speaker_dict(logits.float(), inputs.attention_mask)[0]
    record(spec, dev)
    del model
    free()
    out = []
    for s in segs:  # transformers 5.22 returns {"Start", "End", "Speaker"}
        s = {k.lower(): v for k, v in s.items()}
        out.append((float(s["start"]), float(s["end"]), int(re.sub(r"\D", "", str(s["speaker"])) or 0)))
    return out


def piece_files(audio, chunks, tmp):
    """The chunks as wav files: every model reads a path the same way."""
    import soundfile as sf
    d = os.path.join(tmp, "pieces")
    os.makedirs(d, exist_ok=True)
    paths = []
    for i, (s, e, _) in enumerate(chunks):
        paths.append(os.path.join(d, "%04d.wav" % i))
        sf.write(paths[-1], audio[int(s * SR):int(e * SR)], SR)
    return paths


def run_qwen(spec, paths, language, terms, batch=4):
    """Qwen3-ASR through transformers' own support (the -hf checkpoint); the terms go in as its context prompt.
    language: «English», «Russian» or None to let the model detect it. Returns (texts, detected languages)."""
    torch = _torch()
    from transformers import AutoModelForMultimodalLM, AutoProcessor
    name, rev = spec["repo"], spec.get("revision")
    announce(spec)
    proc = AutoProcessor.from_pretrained(name, revision=rev)
    model, dev = on_device(lambda d: AutoModelForMultimodalLM.from_pretrained(
        name, revision=rev, dtype=torch.bfloat16).to(d).eval())
    texts, detected = [], []
    for i in range(0, len(paths), batch):
        part = paths[i:i + batch]
        kw = {"language": [language] * len(part)} if language else {}
        if terms:
            kw["prompt"] = "Vocabulary: %s." % terms
        inputs = proc.apply_transcription_request(part, **kw).to(dev, torch.bfloat16)
        with torch.inference_mode():
            out = model.generate(**inputs, max_new_tokens=400, do_sample=False)
        parsed = proc.decode(out[:, inputs["input_ids"].shape[1]:], return_format="parsed")
        texts += [(p.get("transcription") or "").strip() for p in parsed]
        detected += [p.get("language") or "" for p in parsed]
        print("  %s %d/%d" % (name.split("/")[-1], min(i + batch, len(paths)), len(paths)), flush=True)
    record(spec, dev)
    del model
    free()
    return texts, detected


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def gigaam_files(spec, gigaam):
    """Download GigaAM's files on the first run and check them against the SHA-256 in the config before loading:
    the checkpoint is a pickle, so a changed file is changed code."""
    root = os.path.expanduser(spec.get("cache") or "~/.cache/gigaam")
    version = spec["version"]
    want = spec.get("sha256") or {}
    missing = [f for f in want if not os.path.isfile(os.path.join(root, f))]
    if missing or not want:
        print("  GigaAM %s: первый запуск, скачиваю веса с CDN разработчика (около %.2f ГБ)"
              % (version, spec.get("download_gb", 0.45)), flush=True)
        try:
            if want:  # exactly the files the config pins: a v3 model has one tokenizer, a two-head model has two
                for fname in missing:
                    gigaam._download_file("%s/%s" % (gigaam._URL_DIR, fname), os.path.join(root, fname))
            else:
                gigaam._download_model(version, root)
                gigaam._download_tokenizer(version, root)
        except AttributeError:
            raise ToolError("в установленном пакете gigaam нет функций загрузки: " + SETUP_HINT)
    if not want:
        print("  у GigaAM не закреплены контрольные суммы: файлы не проверены", flush=True)
    for fname, digest in want.items():
        path = os.path.join(root, fname)
        if not os.path.isfile(path):
            raise ToolError("нет файла GigaAM %s после загрузки: проверьте сеть и запустите снова" % path)
        if sha256(path) != digest.lower():
            raise ToolError("файл GigaAM %s не совпал с контрольной суммой из файла моделей. Удалите его и запустите "
                            "снова; если не поможет, разработчик изменил веса: сообщите владельцу инструмента." % path)
    return root


def run_gigaam(spec, paths, tag=None):
    """GigaAM through its own package. Returns (texts, plain readings or None).

    The v4 and multilingual_v2 models have two heads: «e2e» (punctuation, casing, digits) is the reading, «raw»
    (plain words) is returned beside it because the e2e head leaves a word out now and then. tag is the language
    tag of a multilingual model: «ru», «de», or a mix such as «ru-en»."""
    try:
        import gigaam
    except ImportError:
        raise ToolError("не установлен пакет gigaam: " + SETUP_HINT)
    root = gigaam_files(spec, gigaam)
    kw = {"language": tag} if tag and spec.get("multilingual") else {}
    try:
        model, dev = on_device(lambda d: gigaam.load_model(spec["version"], device=d, download_root=root, **kw))
    except (ValueError, TypeError) as e:  # a gigaam package from before 1.0 knows neither the model nor the tag
        raise ToolError("пакет gigaam не знает модель «%s» (%s): он старше этой версии transcribe. %s"
                        % (spec["version"], e, SETUP_HINT[0].upper() + SETUP_HINT[1:]))
    texts, raws = [], []
    for i, path in enumerate(paths):
        r = model.transcribe(path)
        if isinstance(r, dict):  # gigaam 1.0, a two-head model: {"e2e": result, "raw": result}
            texts.append(r["e2e"].text.strip())
            raws.append(r["raw"].text.strip())
        else:  # v3 and older: one reading
            texts.append((r if isinstance(r, str) else getattr(r, "text", str(r))).strip())
            raws.append("")
        if (i + 1) % 20 == 0 or i + 1 == len(paths):
            print("  GigaAM %d/%d" % (i + 1, len(paths)), flush=True)
    record(spec, dev)
    del model
    free()
    return texts, (raws if any(raws) else None)


def run_granite(spec, paths, terms):
    """Granite Speech by its model card's prompts: keyword biasing when there are terms."""
    torch = _torch()
    import soundfile as sf
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor
    name, rev = spec["repo"], spec.get("revision")
    announce(spec)
    proc = AutoProcessor.from_pretrained(name, revision=rev)
    model, dev = on_device(lambda d: AutoModelForSpeechSeq2Seq.from_pretrained(
        name, revision=rev, dtype=torch.bfloat16).to(d).eval())
    ask = "<|audio|>" + ("transcribe the speech to text. Keywords: " + terms if terms
                         else "transcribe the speech with proper punctuation and capitalization.")
    prompt = proc.tokenizer.apply_chat_template([{"role": "user", "content": ask}], tokenize=False, add_generation_prompt=True)
    texts = []
    for i, path in enumerate(paths):
        wav, _ = sf.read(path, dtype="float32")
        inputs = proc(prompt, torch.from_numpy(wav).unsqueeze(0), device=dev, return_tensors="pt").to(dev)
        with torch.inference_mode():
            out = model.generate(**inputs, max_new_tokens=400, do_sample=False, num_beams=1)
        texts.append(proc.tokenizer.decode(out[0, inputs["input_ids"].shape[-1]:], skip_special_tokens=True).strip())
        if (i + 1) % 20 == 0 or i + 1 == len(paths):
            print("  granite %d/%d" % (i + 1, len(paths)), flush=True)
    record(spec, dev)
    del model
    free()
    return texts


def run(spec, paths, language, terms, tag=None):
    """(texts, the model's second plain reading or None). language is the name Qwen3-ASR takes («Russian»),
    tag is the language tag a multilingual GigaAM takes («ru-en»)."""
    engine = spec["engine"]
    if engine == "qwen3-asr":
        return run_qwen(spec, paths, language, terms)[0], None
    if engine == "gigaam":
        return run_gigaam(spec, paths, tag)
    if engine == "granite-speech":
        return run_granite(spec, paths, terms), None
    raise ToolError("движок «%s» не распознаёт речь" % engine)


def transcribe(media, cfg, lang, terms, crosscheck=True):
    """The whole run; returns (meta, rows) ready for report.write."""
    models = cfg["models"]
    terms_text = ", ".join(terms)
    USAGE.clear()
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
        turns = diarize(audio, models[cfg["diarization"]])
        print("смен спикеров: %d" % len(turns), flush=True)
        chunks = merge(split_by_speaker(spans, turns, total))
        if not chunks:
            raise ToolError("в записи не найдено речи длиннее %.1f с" % MIN_CHUNK)
        paths = piece_files(audio, chunks, work)
        print("фрагментов после склейки: %d" % len(chunks), flush=True)

        if lang == "auto":
            _, det = run_qwen(models[cfg["language_detection"]], paths[:DETECT_CHUNKS], None, "")
            lang = pick_language(det, cfg["languages"], cfg["default_language"])
            print("язык: %s %s" % (lang, det), flush=True)
        route = cfg["languages"][lang]
        primary_spec = models[route["primary"]]
        check_spec = models[route["crosscheck"]] if crosscheck and route.get("crosscheck") else None
        name = route.get("name")
        tag = route.get("gigaam_language") or lang
        primary, raw = run(primary_spec, paths, name, terms_text, tag)
        check = run(check_spec, paths, name, terms_text, tag)[0] if check_spec else None
    finally:
        shutil.rmtree(work, ignore_errors=True)

    rows = [{"start": s, "end": e, "speaker": spk, "text": p} for (s, e, spk), p in zip(chunks, primary)]
    if raw is not None:  # the primary's own plain reading; it is the text when the formatted head wrote nothing
        for r, w in zip(rows, raw):
            r["raw"] = w
            r["text"] = r["text"] or w
    if check is not None:
        for r, c in zip(rows, check):
            r["check"] = c
    used = [primary_spec, models[cfg["diarization"]]] + ([check_spec] if check_spec else [])
    # Only the file name: transcripts get forwarded, and a full path names the person and the client folder.
    meta = {"media": os.path.basename(media), "language": lang, "primary": label(primary_spec),
            "crosscheck": label(check_spec) if check_spec else None, "diarization": label(models[cfg["diarization"]]),
            "terms": terms, "made": datetime.datetime.now().isoformat(timespec="seconds"), "chunks": len(rows),
            "tool_version": __version__,
            "revisions": {label(s): s.get("revision") or s.get("sha256") for s in used},
            "devices": dict(USAGE)}
    if primary_spec.get("multilingual"):
        meta["primary_language"] = tag
    meta["flagged"] = flag(rows, terms, check is not None)
    return meta, rows
