import contextlib
import io
import os
import subprocess
import sys
import unittest

from transcribe import __version__
from transcribe.cli import main, out_dir, build_parser

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
        for text in ("использование: transcribe", "аргументы", "параметры", "--out", "примеры:", "Видеокарта не нужна"):
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


class Arguments(unittest.TestCase):
    def test_no_media(self):
        code, _, err = run_main()
        self.assertEqual(code, 2)
        self.assertIn("укажите запись", err)

    def test_missing_file(self):
        code, _, err = run_main(os.path.join(ROOT, "no-such-recording.mov"))
        self.assertEqual(code, 2)
        self.assertIn("файл не найден", err)

    def test_unknown_option(self):
        code, _, err = run_main("call.mov", "--lang", "ru")  # an option of 0.x
        self.assertEqual(code, 2)
        self.assertIn("ошибка в аргументах", err)

    def test_default_output_folder(self):
        a = build_parser().parse_args([os.path.join("in", "call 1.mov")])
        self.assertEqual(out_dir(a), os.path.join("transcribe-out", "call 1"))


if __name__ == "__main__":
    unittest.main()
