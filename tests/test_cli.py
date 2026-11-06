import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

from transcribe import __version__
from transcribe.cli import main

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_main(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(list(argv))
        except SystemExit as e:
            code = e.code
    return code, out.getvalue(), err.getvalue()


def module(*args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, "-m", "transcribe", *args], cwd=ROOT, capture_output=True,
                          text=True, encoding="utf-8", env=env)


class Help(unittest.TestCase):
    def test_help_is_russian_and_needs_no_models(self):
        r = module("--help")
        self.assertEqual(r.returncode, 0, r.stderr)
        for text in ("использование: transcribe", "аргументы", "параметры", "--lang", "--terms", "--reflag",
                     "--config", "--out", "--no-check", "примеры:"):
            self.assertIn(text, r.stdout)

    def test_version(self):
        r = module("--version")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "transcribe " + __version__)

    def test_cli_does_not_import_the_models(self):
        code = "import sys, transcribe.cli, transcribe.pipeline; transcribe.cli.build_parser(); " \
               "print(sorted(m for m in ('torch', 'numpy', 'transformers', 'gigaam') if m in sys.modules))"
        r = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "[]")


class UsageErrors(unittest.TestCase):
    def test_no_media(self):
        code, _, err = run_main()
        self.assertEqual(code, 2)
        self.assertIn("укажите запись", err)

    def test_reflag_without_a_folder(self):
        code, _, err = run_main("--reflag")
        self.assertEqual(code, 2)
        self.assertIn("--reflag --out", err)

    def test_missing_file(self):
        code, _, err = run_main(os.path.join(ROOT, "no-such-recording.mov"))
        self.assertEqual(code, 2)
        self.assertIn("файл не найден", err)

    def test_unknown_language(self):
        code, _, err = run_main("call.mov", "--lang", "de")
        self.assertEqual(code, 2)
        self.assertIn("en, ru", err)

    def test_unknown_option(self):
        code, _, err = run_main("--frobnicate")
        self.assertEqual(code, 2)
        self.assertIn("ошибка в аргументах", err)

    def test_bad_config(self):
        code, _, err = run_main("call.mov", "--config", os.path.join(ROOT, "missing.json"))
        self.assertEqual(code, 2)
        self.assertIn("--config", err)

    def test_reflag_without_a_transcript(self):
        with tempfile.TemporaryDirectory() as d:
            code, _, err = run_main("--reflag", "--out", d)
        self.assertEqual(code, 2)
        self.assertIn("transcript.json", err)


class Reflag(unittest.TestCase):
    def test_recomputes_flags_and_rewrites_both_files(self):
        meta = {"media": "demo.wav", "language": "en", "primary": "Qwen/Qwen3-ASR-1.7B-hf",
                "crosscheck": "ibm-granite/granite-speech-5.0-2b", "diarization": "nvidia/Nemotron-3-Diarization",
                "terms": ["Figma", "After Effects", "Relate"], "made": "2026-11-06T10:00:00", "chunks": 2, "flagged": 0}
        chunks = [{"start": 0.0, "end": 3.0, "speaker": "S1", "text": "open the figure file", "check": "open the Figma file",
                   "flag": False},
                  {"start": 3.0, "end": 5.0, "speaker": "S2", "text": "", "echo": "Figma, After Effects, Relate",
                   "check": "", "flag": True}]
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "transcript.json"), "w", encoding="utf-8") as f:
                json.dump({"meta": meta, "chunks": chunks}, f)
            code, out, err = run_main("--reflag", "--out", d)
            self.assertEqual(code, 0, err)
            self.assertIn("отмечено 1 из 2", out)
            with open(os.path.join(d, "transcript.json"), encoding="utf-8") as f:
                d2 = json.load(f)
            self.assertEqual(d2["meta"]["flagged"], 1)
            self.assertIn("reflagged", d2["meta"])
            self.assertEqual([c["flag"] for c in d2["chunks"]], [True, False])
            self.assertEqual(d2["chunks"][1]["echo"], "Figma, After Effects, Relate")
            with open(os.path.join(d, "transcript.md"), encoding="utf-8") as f:
                self.assertIn("термины услышала только проверочная: Figma", f.read())


if __name__ == "__main__":
    unittest.main()
