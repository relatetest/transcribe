import copy
import json
import os
import re
import tempfile
import unittest

from transcribe import config


class DefaultConfig(unittest.TestCase):
    def setUp(self):
        self.cfg = config.load()

    def test_languages_from_the_brief(self):
        langs = self.cfg["languages"]
        models = self.cfg["models"]
        self.assertEqual(len(langs), 21)
        self.assertEqual(list(langs)[:2], ["en", "ru"])
        self.assertEqual(models[langs["en"]["primary"]]["repo"], "Qwen/Qwen3-ASR-1.7B-hf")
        self.assertEqual(models[langs["en"]["crosscheck"]]["repo"], "ibm-granite/granite-speech-5.0-2b")
        self.assertEqual(models[langs["ru"]["primary"]]["version"], "multilingual_v2_rnnt")
        self.assertEqual(langs["ru"]["gigaam_language"], "ru-en")
        self.assertEqual(models[langs["ru"]["crosscheck"]]["repo"], "Qwen/Qwen3-ASR-1.7B-hf")
        self.assertEqual(models[self.cfg["diarization"]]["repo"], "nvidia/Nemotron-3-Diarization")

    def test_other_languages_go_through_the_multilingual_model(self):
        langs, models = self.cfg["languages"], self.cfg["models"]
        others = {code: spec for code, spec in langs.items() if code not in ("en", "ru")}
        self.assertEqual(len(others), 19)
        for code, spec in others.items():
            self.assertTrue(models[spec["primary"]].get("multilingual"), code)
            self.assertNotIn("gigaam_language", spec, code)  # the tag is the language code itself
        checked = {code for code, spec in others.items() if spec.get("crosscheck")}
        self.assertEqual(checked, {"de", "fr", "es", "it", "nl", "pt"})
        for code in checked:
            self.assertEqual(models[langs[code]["crosscheck"]]["repo"], "Qwen/Qwen3-ASR-1.7B-hf")

    def test_only_languages_the_detector_can_name_have_a_name(self):
        named = {code for code, spec in self.cfg["languages"].items() if spec.get("name")}
        self.assertEqual(named, {"en", "ru", "de", "fr", "es", "it", "nl", "pt", "pl", "ro"})

    def test_every_model_is_pinned(self):
        for key, spec in self.cfg["models"].items():
            if spec["engine"] in config.HF_ENGINES:
                self.assertRegex(spec.get("revision", ""), r"^[0-9a-f]{40}$", key)
            else:
                self.assertTrue(spec.get("sha256"), key)
                for digest in spec["sha256"].values():
                    self.assertRegex(digest, r"^[0-9a-f]{64}$", key)

    def test_no_personal_paths(self):
        with open(config.DEFAULT, encoding="utf-8") as f:
            text = f.read()
        self.assertIsNone(re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]|/Users/|/home/", text))

    def test_labels(self):
        models = self.cfg["models"]
        self.assertEqual(config.label(models["gigaam"]), "salute-developers/GigaAM v3_e2e_rnnt")
        self.assertEqual(config.label(models["gigaam-multilingual"]), "salute-developers/GigaAM multilingual_v2_rnnt")
        self.assertEqual(config.label(models["gigaam-v4"]), "salute-developers/GigaAM v4_rnnt")
        self.assertEqual(config.label(models["qwen3-asr"]), "Qwen/Qwen3-ASR-1.7B-hf")


class BrokenConfig(unittest.TestCase):
    def setUp(self):
        with open(config.DEFAULT, encoding="utf-8") as f:
            self.good = json.load(f)

    def broken(self, change):
        cfg = copy.deepcopy(self.good)
        change(cfg)
        with self.assertRaises(config.ConfigError) as e:
            config.check(cfg)
        return str(e.exception)

    def test_unknown_engine(self):
        msg = self.broken(lambda c: c["models"]["qwen3-asr"].update(engine="whisper"))
        self.assertIn("whisper", msg)

    def test_language_points_to_a_missing_model(self):
        msg = self.broken(lambda c: c["languages"]["ru"].update(crosscheck="nope"))
        self.assertIn("nope", msg)

    def test_diarization_model_in_an_asr_role(self):
        self.broken(lambda c: c["languages"]["en"].update(primary="nemotron-diarization"))

    def test_default_language_must_exist(self):
        self.broken(lambda c: c.update(default_language="ja"))

    def test_language_tag_needs_a_multilingual_model(self):
        msg = self.broken(lambda c: c["languages"]["ru"].update(primary="gigaam"))
        self.assertIn("gigaam_language", msg)
        self.broken(lambda c: c["languages"]["ru"].update(gigaam_language=["ru", "en"]))

    def test_a_config_from_0_1_0_still_loads(self):
        def old(c):
            c["languages"] = {"en": c["languages"]["en"],
                              "ru": {"name": "Russian", "primary": "gigaam", "crosscheck": "qwen3-asr"}}
            for key in ("gigaam-multilingual", "gigaam-v4"):
                del c["models"][key]
        cfg = copy.deepcopy(self.good)
        old(cfg)
        config.check(cfg)

    def test_missing_file_and_bad_json(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(config.ConfigError):
                config.load(os.path.join(d, "none.json"))
            bad = os.path.join(d, "bad.json")
            with open(bad, "w", encoding="utf-8") as f:
                f.write("{not json")
            with self.assertRaises(config.ConfigError):
                config.load(bad)

    def test_own_config_file(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mine.json")
            cfg = copy.deepcopy(self.good)
            cfg["languages"] = {"en": cfg["languages"]["en"]}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f)
            self.assertEqual(set(config.load(path)["languages"]), {"en"})


if __name__ == "__main__":
    unittest.main()
