"""transcript.json (machine-readable, English keys) and transcript.md (for people, in Russian)."""
import json
import os

from . import __version__

MAX_DIFFS = 8  # differences listed per flagged chunk in transcript.md; transcript.json keeps all


def ts(t):
    """65.25 → «01:05.2»"""
    m, s = divmod(t, 60)
    return "%02d:%04.1f" % (int(m), s)


def read(out):
    with open(os.path.join(out, "transcript.json"), encoding="utf-8") as f:
        d = json.load(f)
    return d["meta"], d["chunks"]


def markdown(meta, rows):
    md = ["# Расшифровка: %s" % os.path.basename(meta["media"]), "",
          "Язык **%s** · основная модель `%s` · проверочная `%s` · спикеры `%s` · %s (transcribe %s)." %
          (meta["language"], meta["primary"], meta["crosscheck"] or "—", meta["diarization"], meta["made"],
           meta.get("tool_version", __version__)),
          "",
          "Спикеры подписаны S1, S2… в порядке появления: имён модели не знают.", ""]
    if meta["crosscheck"] is None:
        md += ["**Черновик:** работала только основная модель, ничего не сверялось.", ""]
    else:
        md += ["**Отмечено ⚑: %d из %d фрагментов.** Там модели написали разные слова (каждое расхождение указано) "
               "или термин услышала только проверочная модель. Прослушайте эти секунды, прежде чем цитировать. "
               "Где модели совпали, ошибиться могли обе." % (meta["flagged"], len(rows)), ""]
    cur = None
    for r in rows:
        head = "**[%s] %s:** " % (ts(r["start"]), r["speaker"]) if r["speaker"] != cur else "[%s] " % ts(r["start"])
        cur = r["speaker"]
        line = head + (r["text"] or "…")
        if r.get("flag"):
            diffs = "; ".join("«%s» ↔ «%s»" % (x or "—", y or "—") for x, y in r["spans"][:MAX_DIFFS])
            line += "  \n  ⚑ %s–%s · основная ↔ проверочная: %s" % (ts(r["start"]), ts(r["end"]), diffs or "—")
            if r.get("terms_missing"):
                line += " · термины услышала только проверочная: " + ", ".join(r["terms_missing"])
        md += [line, ""]
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
