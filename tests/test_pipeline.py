"""The parts of the run that need no models: the model pins, the GigaAM file check, its readings, the ffmpeg check."""
import hashlib
import os
import re
import sys
import tempfile
import types
import unittest
from unittest import mock

from transcribe import pipeline


class Models(unittest.TestCase):
    def setUp(self):
        self.models = pipeline.load_models()

    def test_two_models_both_pinned(self):
        self.assertEqual(self.models["asr"]["version"], "multilingual_v2_rnnt")
        self.assertEqual(self.models["asr"]["language"], "ru-en")  # plain «ru» wrote nothing for an English sentence
        self.assertEqual(len(self.models["asr"]["sha256"]), 3)
        self.assertTrue(all(name.startswith("multilingual_v2_rnnt") for name in self.models["asr"]["sha256"]))
        for digest in self.models["asr"]["sha256"].values():
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
        self.assertEqual(self.models["speakers"]["repo"], "nvidia/Nemotron-3-Diarization")
        self.assertRegex(self.models["speakers"]["revision"], r"^[0-9a-f]{40}$")

    def test_no_personal_paths(self):
        with open(pipeline.MODELS, encoding="utf-8") as f:
            self.assertIsNone(re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]|/Users/|/home/", f.read()))

    def test_label(self):
        self.assertEqual(pipeline.asr_label(self.models["asr"]), "salute-developers/GigaAM multilingual_v2_rnnt")


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


class GigaamFiles(unittest.TestCase):
    def spec(self, root, digest, names=("m.ckpt", "m_e2e.model", "m_raw.model")):
        return {"version": "v4_rnnt", "cache": root, "download_gb": 0.49, "sha256": dict.fromkeys(names, digest)}

    def test_first_run_downloads_then_checks(self):
        with tempfile.TemporaryDirectory() as d:
            fake = FakeGigaam(b"weights")
            spec = self.spec(d, hashlib.sha256(b"weights").hexdigest())
            with open(os.path.join(d, "m.ckpt"), "wb") as f:  # already there: only the two tokenizers are fetched
                f.write(b"weights")
            with mock.patch("builtins.print"):
                self.assertEqual(pipeline.gigaam_files(spec, fake), d)
            self.assertEqual(fake.calls, ["https://cdn.example/GigaAM/" + n for n in ("m_e2e.model", "m_raw.model")])
            fake.calls.clear()
            self.assertEqual(pipeline.gigaam_files(spec, fake), d)
            self.assertEqual(fake.calls, [])

    def test_changed_file_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            spec = self.spec(d, hashlib.sha256(b"weights").hexdigest())
            with mock.patch("builtins.print"), self.assertRaises(pipeline.ToolError) as e:
                pipeline.gigaam_files(spec, FakeGigaam(b"something else"))
            self.assertIn("контрольной суммой", str(e.exception))


def reading(text):
    return types.SimpleNamespace(text=text)


class Recognize(unittest.TestCase):
    """recognize with a stand-in package: how it loads the model and what it makes of the answers."""

    def run_with(self, answers, load_error=None, spec=None):
        spec = spec or {"version": "multilingual_v2_rnnt", "language": "ru-en"}
        loaded = {}
        fake = types.ModuleType("gigaam")

        def load_model(version, **kw):
            if load_error:
                raise load_error
            loaded.update(kw, version=version)
            return types.SimpleNamespace(transcribe=lambda path: answers[path])

        fake.load_model = load_model
        with mock.patch.dict(sys.modules, {"gigaam": fake}), \
                mock.patch.object(pipeline, "gigaam_files", return_value="cache"), mock.patch("builtins.print"):
            return pipeline.recognize(spec, list(answers)), loaded

    def test_text_and_plain_reading_on_the_processor(self):
        answers = {"a.wav": {"e2e": reading(" Привет, как дела? "), "raw": reading("привет как дела")},
                   "b.wav": {"e2e": reading(""), "raw": reading("да")}}
        (texts, raws), loaded = self.run_with(answers)
        self.assertEqual(texts, ["Привет, как дела?", "да"])  # an empty formatted reading falls back to the plain one
        self.assertEqual(raws, ["привет как дела", "да"])
        self.assertEqual(loaded["device"], "cpu")
        self.assertFalse(loaded["fp16_encoder"])
        self.assertEqual(loaded["language"], "ru-en")

    def test_a_model_without_a_language_tag_gets_none(self):
        answers = {"a.wav": {"e2e": reading("Да."), "raw": reading("да")}}
        _, loaded = self.run_with(answers, spec={"version": "v4_rnnt"})
        self.assertNotIn("language", loaded)

    def test_old_package_says_to_run_setup_again(self):
        with self.assertRaises(pipeline.ToolError) as e:
            self.run_with({}, load_error=ValueError("Model 'v4_rnnt' not found"))
        self.assertIn("scripts/setup.ps1", str(e.exception))


class SpeechChunks(unittest.TestCase):
    def test_torch_keeps_its_threads_after_the_vad(self):
        threads = [8]
        torch = types.ModuleType("torch")
        torch.get_num_threads = lambda: threads[-1]
        torch.set_num_threads = threads.append
        torch.from_numpy = lambda audio: audio
        vad = types.ModuleType("silero_vad")
        vad.load_silero_vad = lambda: torch.set_num_threads(1)  # what the real package does when it is imported
        vad.get_speech_timestamps = lambda *a, **kw: [{"start": 0.0, "end": 1.234}]
        with mock.patch.dict(sys.modules, {"torch": torch, "silero_vad": vad}):
            self.assertEqual(pipeline.speech_chunks([0.0]), [[0.0, 1.23]])
        self.assertEqual(threads[-1], 8)


class Ffmpeg(unittest.TestCase):
    def test_missing_ffmpeg_says_how_to_install(self):
        with mock.patch("shutil.which", return_value=None), self.assertRaises(pipeline.ToolError) as e:
            pipeline.extract("call.mov", "out.wav")
        self.assertIn("winget install Gyan.FFmpeg", str(e.exception))


if __name__ == "__main__":
    unittest.main()
