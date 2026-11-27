import unittest

from transcribe.compare import compare, echo, flag, parse_terms, pick_language, trivial, unflag, words

LANGS = {"en": {"name": "English"}, "ru": {"name": "Russian"}}


class Words(unittest.TestCase):
    def test_normalised_for_comparison(self):
        self.assertEqual(words("It's it's FINE"), ["it", "is", "fine"])
        self.assertEqual(words("we don’t ship"), ["we", "do", "not", "ship"])
        self.assertEqual(words("the P and L is up"), ["the", "pnl", "is", "up"])
        self.assertEqual(words("Ёлка, ёж"), ["елка", "еж"])

    def test_repeated_phrase_counted_once(self):
        self.assertEqual(words("go to the go to the shop"), ["go", "to", "the", "shop"])


class Trivial(unittest.TestCase):
    def test_fillers_and_spelled_numbers_change_nothing(self):
        self.assertTrue(trivial("uh the", ""))
        self.assertTrue(trivial("v three", "v3"))
        self.assertTrue(trivial("ну вот", ""))

    def test_a_real_word_is_not_trivial(self):
        self.assertFalse(trivial("friday", "monday"))


class Compare(unittest.TestCase):
    def test_same_reading(self):
        self.assertEqual(compare("We ship on Friday.", "we ship on friday", []), (0.0, [], []))

    def test_differences_are_listed(self):
        rate, spans, lost = compare("We ship on Friday", "We ship on Monday", [])
        self.assertEqual(spans, [("friday", "monday")])
        self.assertEqual(rate, 0.25)
        self.assertEqual(lost, [])

    def test_trivial_differences_are_not_listed(self):
        self.assertEqual(compare("so we start at five", "we start at 5", [])[1], [])

    def test_term_only_the_crosscheck_heard(self):
        _, _, lost = compare("open the figure file", "open the Figma file", ["Figma", "Relate"])
        self.assertEqual(lost, ["Figma"])


class Echo(unittest.TestCase):
    terms = ["Figma", "After Effects", "Relate"]

    def test_context_list_written_back(self):
        self.assertTrue(echo("Figma, After Effects, Relate.", self.terms))

    def test_speech_with_terms_is_speech(self):
        self.assertFalse(echo("Let's open the Figma file and export it for After Effects", self.terms))

    def test_too_short_to_judge(self):
        self.assertFalse(echo("Figma Relate", self.terms))
        self.assertFalse(echo("anything at all", []))


class Flag(unittest.TestCase):
    def rows(self):
        return [
            {"start": 0.0, "end": 4.0, "speaker": "S1", "text": "Hello everyone.", "check": "Hello, everyone"},
            {"start": 4.0, "end": 9.5, "speaker": "S2", "text": "We ship on Friday", "check": "We ship on Monday"},
            {"start": 10.0, "end": 12.0, "speaker": "S2", "text": "Figma, After Effects, Relate", "check": "la la la"},
            {"start": 12.0, "end": 14.0, "speaker": "S1", "text": "open the figure file", "check": "open the Figma file"},
        ]

    def test_flags(self):
        rows = self.rows()
        n = flag(rows, ["Figma", "After Effects", "Relate"], True)
        self.assertEqual([r["flag"] for r in rows], [False, True, True, True])
        self.assertEqual(n, 3)
        self.assertEqual(rows[2]["text"], "")
        self.assertEqual(rows[2]["echo"], "Figma, After Effects, Relate")
        self.assertEqual(rows[3]["terms_missing"], ["Figma"])
        self.assertEqual(rows[1]["spans"], [("friday", "monday")])

    def test_draft_has_no_flags(self):
        rows = self.rows()
        self.assertEqual(flag(rows, [], False), 0)
        self.assertNotIn("flag", rows[1])

    def test_reflag_gives_the_same_result(self):
        rows = self.rows()
        terms = ["Figma", "After Effects", "Relate"]
        first = flag(rows, terms, True)
        snapshot = [dict(r) for r in rows]
        unflag(rows)
        self.assertEqual(rows[2]["text"], "Figma, After Effects, Relate")
        self.assertEqual(flag(rows, terms, True), first)
        self.assertEqual(rows, snapshot)


class Language(unittest.TestCase):
    def test_majority_wins(self):
        self.assertEqual(pick_language(["Russian"] * 4 + ["English"] * 2, LANGS, "en"), "ru")
        self.assertEqual(pick_language(["English"] * 6, LANGS, "en"), "en")

    def test_no_majority_falls_back(self):
        self.assertEqual(pick_language(["Russian"] * 3 + ["English"] * 3, LANGS, "en"), "en")
        self.assertEqual(pick_language(["", "", "Russian"], LANGS, "en"), "en")
        self.assertEqual(pick_language([], LANGS, "en"), "en")

    def test_a_language_without_a_name_is_never_detected(self):
        langs = dict(LANGS, ka={"primary": "x"}, de={"name": "German"})
        self.assertEqual(pick_language(["Kazakh"] * 6, langs, "en"), "en")  # «ka» is inside «kazakh»
        self.assertEqual(pick_language(["German"] * 5 + ["English"], langs, "en"), "de")


class Terms(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_terms(" Figma, After Effects ,, Relate,"), ["Figma", "After Effects", "Relate"])
        self.assertEqual(parse_terms(""), [])


if __name__ == "__main__":
    unittest.main()
