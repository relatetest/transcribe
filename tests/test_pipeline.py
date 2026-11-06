"""The parts of the run that need no models: the GigaAM file check and the ffmpeg check."""
import hashlib
import os
import tempfile
import unittest
from unittest import mock

from transcribe import pipeline


class FakeGigaam:
    def __init__(self, content):
        self.content = content
        self.calls = []

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
            self.assertEqual(fake.calls, ["model", "tokenizer"])
            fake.calls.clear()
            self.assertEqual(pipeline.gigaam_files(spec, fake), d)
            self.assertEqual(fake.calls, [])

    def test_changed_file_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            spec = self.spec(d, hashlib.sha256(b"weights").hexdigest())
            with mock.patch("builtins.print"), self.assertRaises(pipeline.ToolError) as e:
                pipeline.gigaam_files(spec, FakeGigaam(b"something else"))
            self.assertIn("контрольной суммой", str(e.exception))


class Ffmpeg(unittest.TestCase):
    def test_missing_ffmpeg_says_how_to_install(self):
        with mock.patch("shutil.which", return_value=None), self.assertRaises(pipeline.ToolError) as e:
            pipeline.extract("call.mov", "out.wav")
        self.assertIn("winget install Gyan.FFmpeg", str(e.exception))


if __name__ == "__main__":
    unittest.main()
