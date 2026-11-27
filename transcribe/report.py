"""transcript.json (machine-readable, English keys) and transcript.md (for people, in Russian)."""
import json
import os

from . import __version__


def ts(t):
    """65.25 → «01:05.2»"""
    m, s = divmod(t, 60)
    return "%02d:%04.1f" % (int(m), s)


def markdown(meta, rows):
    md = ["# Расшифровка: %s" % os.path.basename(meta["media"]), "",
          "Распознавание `%s` · спикеры `%s` · %s (transcribe %s)." %
          (meta["asr"], meta["diarization"], meta["made"], meta.get("tool_version", __version__)),
          "",
          "Спикеры подписаны S1, S2… в порядке появления: имён модель не знает. Текст сделала одна модель, на слух "
          "его никто не проверял: перед тем как цитировать, переслушайте это место.", ""]
    cur = None
    for r in rows:
        head = "**[%s] %s:** " % (ts(r["start"]), r["speaker"]) if r["speaker"] != cur else "[%s] " % ts(r["start"])
        cur = r["speaker"]
        md += [head + (r["text"] or "…"), ""]
    return "\n".join(md)


def write(out, meta, rows):
    """Write both files into the folder out; return the path of transcript.md."""
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "transcript.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "chunks": rows}, f, ensure_ascii=False, indent=1)
    path = os.path.join(out, "transcript.md")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(markdown(meta, rows))
    return path
