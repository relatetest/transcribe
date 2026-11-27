"""Two readings of one chunk → what differs, which terms are missing, whether a model echoed its context list.

Pure Python: tested in CI without models.
"""
import difflib
import re

FILLER = {"uh", "um", "ah", "oh", "hmm", "like", "yeah", "so", "okay", "ok", "the", "a", "an", "ну", "вот", "э", "эм", "типа"}
NUMBER = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
          "eight": "8", "nine": "9", "ten": "10"}
CONTRACTION = [("n't", " not"), ("'re", " are"), ("'ll", " will"), ("'ve", " have"), ("'m", " am"), ("'d", " would"),
               ("'s", " is")]
ECHO_SHARE = 0.6  # a reading made of this share of the context list's words is the list, not speech


def parse_terms(text):
    """«Figma, After Effects,» → ["Figma", "After Effects"]"""
    return [t.strip() for t in (text or "").split(",") if t.strip()]


def words(text):
    """Comparable words: lower case, ё = е, contractions spelled out, letters spelled with «and» joined
    («p and l» = pnl), a word or phrase said twice in a row («it's it's») counted once."""
    t = text.lower().replace("ё", "е").replace("’", "'")
    for short, full in CONTRACTION:
        t = t.replace(short, full)
    t = re.sub(r"\b([a-z]) and ([a-z])\b", r"\1n\2", t)
    out = re.findall(r"[\w']+", t)
    for n in (3, 2, 1):  # «it's it's» is «it is it is» once spelled out
        i = 0
        while i + 2 * n <= len(out):
            if out[i:i + n] == out[i + n:i + 2 * n]:
                del out[i + n:i + 2 * n]
            else:
                i += 1
    return out


def _squash(s):
    return re.sub(r"[^0-9a-zа-я]", "", "".join(NUMBER.get(w, w) for w in s.split() if w not in FILLER))


def trivial(x, y):
    """A difference that changes nothing: fillers only, or the same letters and digits once spelled-out numbers
    are digits («v three» / «v3»)."""
    return _squash(x) == _squash(y)


def compare(a, b, terms):
    """Share of words the two readings do not share, every difference that is not trivial, and the terms only b heard."""
    wa, wb = words(a), words(b)
    sm = difflib.SequenceMatcher(a=wa, b=wb, autojunk=False)
    same = sum(m.size for m in sm.get_matching_blocks())
    rate = 1 - same / max(len(wa), len(wb), 1)
    spans = [(" ".join(wa[i1:i2]), " ".join(wb[j1:j2])) for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"]
    spans = [s for s in spans if not trivial(*s)]
    lost = [t for t in terms if t.lower() in b.lower() and t.lower() not in a.lower()]
    return round(rate, 3), spans, lost


def echo(text, terms):
    """The model wrote its own context list instead of speech (seen on a music-only chunk): mostly the terms' words."""
    w, tw = words(text), set(words(" ".join(terms)))
    return len(w) >= 3 and sum(x in tw for x in w) / len(w) >= ECHO_SHARE


def flag(rows, terms, checked):
    """Fill each row's differences and flag from its two readings; return how many rows are flagged.

    A row is flagged where the two models wrote different words, where a term only the cross-check heard is
    missing from the primary reading, or where only the cross-check heard anything. Echoed context lists are
    moved to row["echo"] and do not count as speech.
    """
    n = 0
    for r in rows:
        if echo(r["text"], terms):
            r["echo"], r["text"] = r["text"], ""
        if not checked:
            continue
        if echo(r.get("check") or "", terms):
            r["check"] = ""
        rate, spans, lost = compare(r["text"], r.get("check") or "", terms)
        r.update({"differs": rate, "spans": spans, "terms_missing": lost})
        r["flag"] = bool(spans) or bool(lost) or (not r["text"] and bool(r.get("check")))
        n += r["flag"]
    return n


def unflag(rows):
    """Undo flag()'s echo moves, so the flags can be computed again from the stored readings (--reflag)."""
    for r in rows:
        if r.get("echo") and not r["text"]:
            r["text"] = r.pop("echo")


def pick_language(detected, languages, default):
    """The language most chunks were detected in, when it is more than half of them; otherwise the default.

    detected: language names as the detector wrote them («English», «Russian»); languages: {code: {"name": ...}}.
    A language without «name» is one the detector cannot name: it is never picked, and its two-letter code is
    not searched for inside other names («ka» is inside «kazakh»).
    """
    best, best_n = default, 0
    for code, spec in languages.items():
        name = (spec.get("name") or "").lower()
        if not name:
            continue
        n = sum(name in (d or "").lower() for d in detected)
        if n > best_n:
            best, best_n = code, n
    return best if best_n > len(detected) / 2 else default
