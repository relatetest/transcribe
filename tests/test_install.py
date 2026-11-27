"""The one-file installers: they install this release, and the README names the same tag."""
import os
import re
import unittest

from transcribe import __version__

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAG = "v" + __version__


def text(name):
    with open(os.path.join(ROOT, name), encoding="utf-8-sig") as f:
        return f.read()


class Installers(unittest.TestCase):
    def test_both_install_this_release(self):
        self.assertIn('$Tag = "%s"' % TAG, text("install.ps1"))
        self.assertIn('tag="%s"' % TAG, text("install.sh"))

    def test_readme_downloads_them_at_this_tag(self):
        readme = text("README.md")
        raw = "https://raw.githubusercontent.com/relatetest/transcribe/%s/" % TAG
        self.assertIn(raw + "install.ps1", readme)
        self.assertIn(raw + "install.sh", readme)
        tags = set(re.findall(r"raw\.githubusercontent\.com/relatetest/transcribe/([^/]+)/", readme))
        self.assertEqual(tags, {TAG})

    def test_powershell_file_has_a_byte_order_mark(self):
        # Windows PowerShell 5.1 reads a file without it as ANSI, and the Russian messages break the parser.
        with open(os.path.join(ROOT, "install.ps1"), "rb") as f:
            self.assertEqual(f.read(3), b"\xef\xbb\xbf")

    def test_they_only_fetch_this_repository(self):
        for name in ("install.ps1", "install.sh"):
            urls = set(re.findall(r"https?://[^\s\"')]+", text(name)))
            self.assertEqual(urls, {"https://github.com/relatetest/transcribe.git", "https://github.com/relatetest/transcribe"}, name)


if __name__ == "__main__":
    unittest.main()
