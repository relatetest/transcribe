import json
import os
import tempfile
import unittest

from transcribe.report import markdown, ts, write

META_KEYS = {"media", "asr", "diarization", "made", "chunks", "tool_version"}


def sample():
    rows = [
        {"start": 0.0, "end": 4.0, "speaker": "S1", "text": "Hello everyone.", "raw": "hello everyone"},
        {"start": 4.0, "end": 9.5, "speaker": "S1", "text": "We ship on Friday.", "raw": "we ship on friday"},
        {"start": 9.5, "end": 12.0, "speaker": "S2", "text": "", "raw": ""},
    ]
    meta = {"media": "/tmp/demo call.mov", "asr": "salute-developers/GigaAM multilingual_v2_rnnt",
            "diarization": "nvidia/Nemotron-3-Diarization", "made": "2026-11-27T10:00:00",
            "chunks": len(rows), "tool_version": "1.0.0"}
    return meta, rows


class Timecode(unittest.TestCase):
    def test_format(self):
        self.assertEqual(ts(0), "00:00.0")
        self.assertEqual(ts(61.5), "01:01.5")
        self.assertEqual(ts(3600), "60:00.0")


class Markdown(unittest.TestCase):
    def test_transcript(self):
        md = markdown(*sample())
        self.assertTrue(md.startswith("# Расшифровка: demo call.mov\n"))
        self.assertIn("**[00:00.0] S1:** Hello everyone.", md)
        self.assertIn("\n[00:04.0] We ship on Friday.\n", md)  # the same speaker: no second label
        self.assertIn("**[00:09.5] S2:** …", md)

    def test_it_says_nobody_checked_the_text(self):
        self.assertIn("переслушайте", markdown(*sample()))


class Files(unittest.TestCase):
    def test_write(self):
        meta, rows = sample()
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "nested", "out")
            path = write(out, meta, rows)
            self.assertEqual(path, os.path.join(out, "transcript.md"))
            with open(os.path.join(out, "transcript.json"), encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(set(data), {"meta", "chunks"})
            self.assertTrue(META_KEYS <= set(data["meta"]))
            self.assertEqual(set(data["chunks"][0]), {"start", "end", "speaker", "text", "raw"})
            with open(path, "rb") as f:
                self.assertNotIn(b"\r\n", f.read())


if __name__ == "__main__":
    unittest.main()
