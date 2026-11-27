"""The parts of the run that need no models: the GigaAM file check, its two readings and the ffmpeg check."""
import hashlib
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

from transcribe import pipeline


class FakeGigaam:
    _URL_DIR = "https://cdn.example/GigaAM"

    def __init__(self, content):
        self.content = content
        self.calls = []

    def _download_file(self, url, path):
        self.calls.append(url)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(self.content)

    def _download_model(self, version, root):
        self.calls.append("model")
        path = os.path.join(root, version + ".ckpt")
        if not os.path.exists(path):
            os.makedirs(root, exist_ok=True)
            with open(path, "wb") as f:
                f.write(self.content)

    def _download_tokenizer(self, version, root):
        self.calls.append("tokenizer")


class GigaamFiles(unittest.TestCase):
    def spec(self, root, digest):
        return {"engine": "gigaam", "version": "v3_e2e_rnnt", "cache": root, "sha256": {"v3_e2e_rnnt.ckpt": digest}}

    def test_first_run_downloads_then_checks(self):
        with tempfile.TemporaryDirectory() as d:
            fake = FakeGigaam(b"weights")
            spec = self.spec(d, hashlib.sha256(b"weights").hexdigest())
            with mock.patch("builtins.print"):
                self.assertEqual(pipeline.gigaam_files(spec, fake), d)
            self.assertEqual(fake.calls, ["https://cdn.example/GigaAM/v3_e2e_rnnt.ckpt"])
            fake.calls.clear()
            self.assertEqual(pipeline.gigaam_files(spec, fake), d)
            self.assertEqual(fake.calls, [])

    def test_two_head_model_downloads_every_pinned_file(self):
        with tempfile.TemporaryDirectory() as d:
            fake = FakeGigaam(b"weights")
            digest = hashlib.sha256(b"weights").hexdigest()
            names = ["multilingual_v2_rnnt.ckpt", "multilingual_v2_rnnt_e2e_tokenizer.model",
                     "multilingual_v2_rnnt_raw_tokenizer.model"]
            spec = {"engine": "gigaam", "version": "multilingual_v2_rnnt", "cache": d, "sha256": dict.fromkeys(names, digest)}
            with open(os.path.join(d, names[0]), "wb") as f:  # already there: only the two tokenizers are fetched
                f.write(b"weights")
            with mock.patch("builtins.print"):
                pipeline.gigaam_files(spec, fake)
            self.assertEqual(fake.calls, ["https://cdn.example/GigaAM/" + n for n in names[1:]])

    def test_unpinned_model_uses_the_package_download(self):
        with tempfile.TemporaryDirectory() as d:
            fake = FakeGigaam(b"weights")
            with mock.patch("builtins.print"):
                pipeline.gigaam_files({"engine": "gigaam", "version": "v3_e2e_rnnt", "cache": d}, fake)
            self.assertEqual(fake.calls, ["model", "tokenizer"])

    def test_changed_file_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            spec = self.spec(d, hashlib.sha256(b"weights").hexdigest())
            with mock.patch("builtins.print"), self.assertRaises(pipeline.ToolError) as e:
                pipeline.gigaam_files(spec, FakeGigaam(b"something else"))
            self.assertIn("контрольной суммой", str(e.exception))


class Reading:
    def __init__(self, text):
        self.text = text


class GigaamReadings(unittest.TestCase):
    """run_gigaam with a stand-in package: what it passes to load_model and what it makes of the answer."""

    def run_with(self, answers, spec, tag, load_error=None):
        loaded = {}
        fake = types.ModuleType("gigaam")

        def load_model(version, device=None, download_root=None, **kw):
            if load_error:
                raise load_error
            loaded.update(version=version, kw=kw)
            return types.SimpleNamespace(transcribe=lambda path: answers[path])

        fake.load_model = load_model
        with mock.patch.dict(sys.modules, {"gigaam": fake}), \
                mock.patch.object(pipeline, "gigaam_files", return_value="cache"), \
                mock.patch.object(pipeline, "on_device", lambda load: (load("cpu"), "cpu")), \
                mock.patch.object(pipeline, "record"), mock.patch.object(pipeline, "free"), mock.patch("builtins.print"):
            return pipeline.run_gigaam(spec, list(answers), tag), loaded

    def test_two_heads_give_the_reading_and_the_plain_reading(self):
        answers = {"a.wav": {"e2e": Reading(" Привет, как дела? "), "raw": Reading("привет как дела")},
                   "b.wav": {"e2e": Reading(""), "raw": Reading("да")}}
        spec = {"engine": "gigaam", "version": "multilingual_v2_rnnt", "multilingual": True}
        (texts, raws), loaded = self.run_with(answers, spec, "ru-en")
        self.assertEqual(texts, ["Привет, как дела?", ""])
        self.assertEqual(raws, ["привет как дела", "да"])
        self.assertEqual(loaded["kw"], {"language": "ru-en"})

    def test_one_head_model_gets_no_language_and_gives_no_plain_reading(self):
        spec = {"engine": "gigaam", "version": "v3_e2e_rnnt"}
        (texts, raws), loaded = self.run_with({"a.wav": "Привет.", "b.wav": Reading("Да.")}, spec, "ru")
        self.assertEqual(texts, ["Привет.", "Да."])
        self.assertIsNone(raws)
        self.assertEqual(loaded["kw"], {})

    def test_two_head_model_without_the_flag_gets_no_language(self):
        spec = {"engine": "gigaam", "version": "v4_rnnt"}
        (_, raws), loaded = self.run_with({"a.wav": {"e2e": Reading("Да."), "raw": Reading("да")}}, spec, "ru")
        self.assertEqual(raws, ["да"])
        self.assertEqual(loaded["kw"], {})

    def test_old_package_says_to_run_setup_again(self):
        spec = {"engine": "gigaam", "version": "multilingual_v2_rnnt", "multilingual": True}
        with self.assertRaises(pipeline.ToolError) as e:
            self.run_with({}, spec, "ru-en", load_error=ValueError("Model 'multilingual_v2_rnnt' not found"))
        self.assertIn("scripts/setup.ps1", str(e.exception))


class Ffmpeg(unittest.TestCase):
    def test_missing_ffmpeg_says_how_to_install(self):
        with mock.patch("shutil.which", return_value=None), self.assertRaises(pipeline.ToolError) as e:
            pipeline.extract("call.mov", "out.wav")
        self.assertIn("winget install Gyan.FFmpeg", str(e.exception))


if __name__ == "__main__":
    unittest.main()
