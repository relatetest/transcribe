import random
import unittest

from transcribe.chunks import MAX_CHUNK, MAX_PAUSE, MIN_CHUNK, VAD, merge, split_by_speaker


class SplitBySpeaker(unittest.TestCase):
    def test_cut_where_the_speaker_changes(self):
        out = split_by_speaker([[0.0, 10.0]], [(0.0, 5.0, 0), (5.0, 10.0, 1)], 10.0)
        self.assertEqual(out, [[0.0, 5.0, "S1"], [5.0, 10.0, "S2"]])

    def test_a_blip_shorter_than_a_turn_is_noise(self):
        turns = [(0.0, 4.0, 0), (4.0, 4.3, 1), (4.3, 10.0, 0)]
        self.assertEqual(split_by_speaker([[0.0, 10.0]], turns, 10.0), [[0.0, 10.0, "S1"]])

    def test_labels_follow_first_arrival_not_the_model_index(self):
        turns = [(0.0, 3.0, 3), (3.0, 6.0, 0), (6.0, 9.0, 3)]
        out = split_by_speaker([[0.0, 3.0], [3.0, 6.0], [6.0, 9.0]], turns, 9.0)
        self.assertEqual([lab for _, _, lab in out], ["S1", "S2", "S1"])

    def test_no_speaker_detected(self):
        self.assertEqual(split_by_speaker([[1.0, 2.0]], [], 3.0), [[1.0, 2.0, "S?"]])

    def test_overlap_goes_to_whoever_started_first(self):
        out = split_by_speaker([[0.0, 10.0]], [(0.0, 6.0, 0), (5.0, 10.0, 1)], 10.0)
        self.assertEqual(out, [[0.0, 6.0, "S1"], [6.0, 10.0, "S2"]])

    def test_short_first_run_joins_the_next_turn(self):
        out = split_by_speaker([[0.0, 5.0]], [(0.0, 0.3, 0), (0.3, 5.0, 1)], 5.0)
        self.assertEqual(out, [[0.0, 5.0, "S1"]])

    def test_silence_before_speech_joins_the_speech(self):
        out = split_by_speaker([[0.0, 5.0]], [(1.0, 5.0, 7)], 5.0)
        self.assertEqual(out, [[0.0, 5.0, "S1"]])

    def test_spans_cover_the_chunk_without_gaps(self):
        rnd = random.Random(7)
        for _ in range(200):
            total = rnd.uniform(5, 120)
            turns, t = [], 0.0
            while t < total:
                d = rnd.uniform(0.1, 8)
                turns.append((t, min(t + d, total), rnd.randrange(4)))
                t += d + rnd.choice([0, 0, rnd.uniform(0, 1)])
            chunks, t = [], rnd.uniform(0, 1)
            while t < total - 0.5:
                e = min(t + rnd.uniform(0.3, MAX_CHUNK), total)
                chunks.append([round(t, 2), round(e, 2)])
                t = e + rnd.uniform(0.3, 2)
            out = split_by_speaker(chunks, turns, total)
            for a, b in chunks:
                inside = [s for s in out if a - 0.011 <= s[0] and s[1] <= b + 0.011]
                self.assertTrue(inside)
                self.assertAlmostEqual(inside[0][0], a, delta=0.011)
                self.assertAlmostEqual(inside[-1][1], b, delta=0.011)
                for x, y in zip(inside, inside[1:]):
                    self.assertAlmostEqual(x[1], y[0], delta=0.011)


class Merge(unittest.TestCase):
    def test_one_speaker_short_pause_is_joined(self):
        self.assertEqual(merge([[0.0, 5.0, "S1"], [5.5, 9.0, "S1"]]), [[0.0, 9.0, "S1"]])

    def test_long_pause_starts_a_new_chunk(self):
        spans = [[0.0, 5.0, "S1"], [5.0 + MAX_PAUSE + 0.5, 9.0, "S1"]]
        self.assertEqual(merge(spans), spans)

    def test_never_longer_than_the_limit(self):
        spans = [[0.0, 12.0, "S1"], [12.5, 23.0, "S1"]]
        self.assertEqual(merge(spans), spans)

    def test_speakers_are_never_joined(self):
        spans = [[0.0, 5.0, "S1"], [5.2, 9.0, "S2"]]
        self.assertEqual(merge(spans), spans)

    def test_pieces_too_short_to_read_are_dropped(self):
        self.assertEqual(merge([[0.0, 0.1, "S1"], [3.0, 6.0, "S2"]]), [[3.0, 6.0, "S2"]])

    def test_random_spans_stay_within_limits(self):
        rnd = random.Random(11)
        for _ in range(300):
            spans, t = [], 0.0
            for _ in range(rnd.randrange(1, 30)):
                d = rnd.uniform(0.05, MAX_CHUNK)
                spans.append([round(t, 2), round(t + d, 2), rnd.choice(["S1", "S2", "S?"])])
                t += d + rnd.uniform(0, 2.5)
            out = merge([list(s) for s in spans])
            for a, b, _ in out:
                self.assertLessEqual(b - a, MAX_CHUNK + 1e-9)
                self.assertGreaterEqual(b - a, MIN_CHUNK)
            for x, y in zip(out, out[1:]):
                self.assertLessEqual(x[1], y[0])


class VadSettings(unittest.TestCase):
    def test_chunks_fit_every_model(self):
        # GigaAM reads 25 s at most; Silero keeps the padded span under max_speech_duration_s
        self.assertLessEqual(VAD["max_speech_duration_s"], 25)
        self.assertEqual(VAD["max_speech_duration_s"], MAX_CHUNK)
        self.assertGreaterEqual(VAD["min_silence_duration_ms"], 100)


if __name__ == "__main__":
    unittest.main()
