import json
import os
import tempfile
import unittest

from transcribe.compare import flag
from transcribe.report import markdown, read, ts, write

SOURCE_META_KEYS = {"media", "language", "primary", "crosscheck", "diarization", "terms", "made", "chunks", "flagged"}


def sample(crosscheck=True):
    rows = [
        {"start": 0.0, "end": 4.0, "speaker": "S1", "text": "Hello everyone.", "check": "Hello, everyone"},
        {"start": 4.0, "end": 9.5, "speaker": "S1", "text": "We ship on Friday", "check": "We ship on Monday"},
        {"start": 9.5, "end": 12.0, "speaker": "S2", "text": "Okay.", "check": "Okay."},
    ]
    if not crosscheck:
        for r in rows:
            del r["check"]
    meta = {"media": "/tmp/demo call.mov", "language": "en", "primary": "Qwen/Qwen3-ASR-1.7B-hf",
            "crosscheck": "ibm-granite/granite-speech-5.0-2b" if crosscheck else None,
            "diarization": "nvidia/Nemotron-3-Diarization", "terms": [], "made": "2026-11-06T10:00:00",
            "chunks": len(rows), "tool_version": "0.1.0"}
    meta["flagged"] = flag(rows, [], crosscheck)
    return meta, rows


class Timecode(unittest.TestCase):
    def test_format(self):
        self.assertEqual(ts(0), "00:00.0")
        self.assertEqual(ts(61.5), "01:01.5")
        self.assertEqual(ts(3600), "60:00.0")


class Markdown(unittest.TestCase):
    def test_flagged_transcript(self):
        md = markdown(*sample())
        self.assertTrue(md.startswith("# Расшифровка: demo call.mov\n"))
        self.assertIn("**Отмечено ⚑: 1 из 3 фрагментов.**", md)
        self.assertIn("**[00:00.0] S1:** Hello everyone.", md)
        self.assertIn("\n[00:04.0] We ship on Friday  \n  ⚑ 00:04.0–00:09.5 · основная ↔ проверочная: «friday» ↔ «monday»", md)
        self.assertIn("**[00:09.5] S2:** Okay.", md)
        self.assertEqual(md.count("⚑"), 2)

    def test_draft(self):
        md = markdown(*sample(crosscheck=False))
        self.assertIn("**Черновик:**", md)
        self.assertNotIn("Отмечено", md)

    def test_echoed_chunk_shows_an_ellipsis(self):
        meta, rows = sample()
        rows[2]["text"] = ""
        self.assertIn("**[00:09.5] S2:** …", markdown(meta, rows))

    def test_terms_missing_are_named(self):
        meta, rows = sample()
        rows[0].update({"flag": True, "spans": [], "terms_missing": ["Figma"]})
        self.assertIn("термины услышала только проверочная: Figma", markdown(meta, rows))


class Files(unittest.TestCase):
    def test_write_and_read_back(self):
        meta, rows = sample()
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "nested", "out")
            path = write(out, meta, rows)
            self.assertEqual(path, os.path.join(out, "transcript.md"))
            with open(os.path.join(out, "transcript.json"), encoding="utf-8") as f:
                raw = json.load(f)
            self.assertEqual(set(raw), {"meta", "chunks"})
            self.assertTrue(SOURCE_META_KEYS <= set(raw["meta"]))
            m2, r2 = read(out)
            self.assertEqual(m2, meta)
            self.assertEqual([r["text"] for r in r2], [r["text"] for r in rows])
            self.assertEqual(r2[1]["spans"], [["friday", "monday"]])
            with open(path, "rb") as f:
                self.assertNotIn(b"\r\n", f.read())


if __name__ == "__main__":
    unittest.main()
