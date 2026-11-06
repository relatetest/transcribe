"""Speech spans → chunks: cut where the speaker changes, joined back while one speaker keeps talking.

Pure Python on purpose: the chunk rules are tested in CI, where there is no torch or numpy.
"""

SR = 16000
MAX_CHUNK = 22.0  # s; GigaAM reads 25 s at most, Silero pads each span on both sides
STEP = 0.01       # the speaker timeline's resolution, s
MIN_TURN = 0.5    # a speaker change shorter than this inside a speech span is noise, not a turn
MAX_PAUSE = 1.0   # s; a longer pause between two spans of one speaker starts a new chunk
MIN_CHUNK = 0.2   # s; shorter pieces are dropped: no model reads them

# Silero VAD settings: speech spans of at most MAX_CHUNK seconds, cut at pauses of 300 ms or more.
VAD = {"max_speech_duration_s": MAX_CHUNK, "min_silence_duration_ms": 300, "speech_pad_ms": 150}


def split_by_speaker(chunks, turns, total):
    """Speech spans cut where the speaker changes, so a quick exchange is not given to one person.

    chunks: [[start, end]] in seconds; turns: [(start, end, speaker index)] from diarization; total: length in seconds.
    Returns [[start, end, label]], S1 being whoever speaks first, S? where nobody was detected.
    Overlapping turns: the one that started first keeps the frame.
    """
    line = [-1] * (int(total / STEP) + 1)
    size = len(line)
    for s, e, spk in sorted(turns):
        for i in range(max(int(s / STEP), 0), min(int(e / STEP), size)):
            if line[i] < 0:
                line[i] = spk
    out = []
    for a, b in chunks:
        i_a = int(a / STEP)
        lab = line[i_a:max(int(b / STEP), i_a + 1)]
        runs, start = [], 0
        for i in range(1, len(lab) + 1):
            if i == len(lab) or lab[i] != lab[start]:
                runs.append([start, i, int(lab[start])])
                start = i
        smooth = []
        for r in runs:  # short runs and silence-labelled runs join their neighbour
            if smooth and ((r[1] - r[0]) * STEP < MIN_TURN or r[2] < 0 or smooth[-1][2] == r[2]):
                smooth[-1][1] = r[1]
            elif smooth and smooth[-1][2] < 0:
                smooth[-1][1:] = [r[1], r[2]]
            else:
                smooth.append(list(r))
        if len(smooth) > 1 and (smooth[0][1] - smooth[0][0]) * STEP < MIN_TURN:  # a short first run belongs to the next turn
            smooth[1][0] = smooth[0][0]
            smooth.pop(0)
        for i0, i1, spk in smooth:
            out.append([round(a + i0 * STEP, 2), round(a + i1 * STEP, 2), spk])
    order = []
    for _, _, spk in out:
        if spk >= 0 and spk not in order:
            order.append(spk)
    return [[s, e, "S%d" % (order.index(spk) + 1) if spk >= 0 else "S?"] for s, e, spk in out]


def merge(spans):
    """Neighbouring spans of one speaker joined while they stay under MAX_CHUNK and the pause is short:
    more context for the models, fewer cuts mid-sentence. Pieces under MIN_CHUNK are dropped."""
    out = []
    for a, b, lab in spans:
        if out and out[-1][2] == lab and b - out[-1][0] <= MAX_CHUNK and a - out[-1][1] <= MAX_PAUSE:
            out[-1][1] = b
        else:
            out.append([a, b, lab])
    return [c for c in out if c[1] - c[0] >= MIN_CHUNK]
