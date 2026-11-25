"""A sample-clock phrase estimate: four quarter notes per bar, anchored by bass onsets."""
from collections import deque
from statistics import median


class PhraseClock:
    def __init__(self, bars=4):
        self.bars = bars if bars in (2,4,8) else 4
        self.period = 0.5
        self.intervals = deque(maxlen=9)
        self.time = 0.0
        self.last_onset = None
        self.position = 0.0
        self.next_boundary = self.bars * 4
        self.phrases = 0
        self.silence = 0.0

    def set_bars(self, bars):
        self.bars = bars if bars in (2,4,8) else 4
        length = self.bars * 4
        self.next_boundary = (int(self.position / length) + 1) * length

    def advance(self, dt, onset=False, active=True):
        self.time += dt
        self.silence = 0.0 if active else self.silence + dt
        if self.silence > 2.0:
            self.last_onset = None
            self.intervals.clear()
            self.position = 0.0
            self.next_boundary = self.bars * 4
            return False
        if onset:
            if self.last_onset is not None:
                interval = self.time - self.last_onset
                # Missing kicks can span multiple quarters. Fold long gaps to
                # the established tempo, but never count every kick as a bar.
                if self.intervals and interval > self.period * 1.6:
                    interval /= max(1, round(interval / self.period))
                if .25 <= interval <= 1.0:
                    if not self.intervals:
                        self.position = 1.0 - dt / interval
                    self.intervals.append(interval)
                    self.period = median(self.intervals)
            self.last_onset = self.time
        if self.last_onset is None or not self.intervals:
            return False
        self.position += dt / self.period
        if self.position + 1e-8 >= self.next_boundary:
            self.next_boundary += self.bars * 4
            self.phrases += 1
            return True
        return False
