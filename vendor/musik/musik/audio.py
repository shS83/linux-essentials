"""Fixed-hop bass onsets and continuous mid/treble energy envelopes."""
import numpy as np
from PySide6.QtCore import QObject, Signal
from PySide6.QtMultimedia import QAudioFormat

from .rhythm import PhraseClock


class BassDetector:
    window_size = 2048
    hop = 512

    def __init__(self):
        self.spectrum_count = 48
        self.phrase_bars = 4
        self.reset()

    def reset(self):
        self.pending = np.empty((0, 1), dtype=np.float32)
        self.rate = 0
        self.channels = 0
        self.clock = 0.0
        self.phrase_clock = PhraseClock(self.phrase_bars)
        self.phrase_events = []
        self.last_beat = -1.0
        self.average = 0.0
        self.previous = 0.0
        self.levels = np.zeros(2, dtype=np.float64)
        self.spectrum_levels = np.zeros(self.spectrum_count, dtype=np.float64)
        self.window = np.hanning(self.window_size)

    def feed(self, samples, rate):
        samples = np.asarray(samples, dtype=np.float32)
        if samples.ndim == 1:
            samples = samples[:, None]
        if rate != self.rate or samples.shape[1] != self.channels:
            self.reset()
            self.rate, self.channels = rate, samples.shape[1]
            self.pending = np.empty((0, self.channels), dtype=np.float32)
            frequencies = np.fft.rfftfreq(self.window_size, 1 / rate)
            self.spectrum_edges = np.geomspace(30, min(20000, rate / 2), self.spectrum_count + 1)
            self.spectrum_centers = np.sqrt(self.spectrum_edges[:-1]*self.spectrum_edges[1:])
            self.spectrum_mask = (frequencies >= self.spectrum_edges[0]) & (frequencies < self.spectrum_edges[-1])
            self.spectrum_indices = np.searchsorted(self.spectrum_edges, frequencies[self.spectrum_mask], side="right")-1
            self.spectrum_frequencies = frequencies
            self.band = (frequencies >= 35) & (frequencies <= 180)
            self.motion_bands = ((frequencies > 180) & (frequencies < 2500),
                                 (frequencies >= 2500) & (frequencies <= 16000))
        self.pending = np.concatenate((self.pending, samples))
        beats = []
        self.phrase_events = []
        while len(self.pending) >= self.window_size:
            # Channel power avoids cancellation of opposite-phase stereo bass.
            spectrum = np.fft.rfft(self.pending[:self.window_size] * self.window[:, None], axis=0)
            power = np.mean(np.abs(spectrum) ** 2, axis=1)
            amplitudes = 2 * np.sqrt(power) / self.window.sum()
            magnitudes = np.zeros(self.spectrum_count)
            np.maximum.at(magnitudes, self.spectrum_indices, amplitudes[self.spectrum_mask])
            empty = magnitudes == 0
            magnitudes[empty] = np.interp(self.spectrum_centers[empty], self.spectrum_frequencies, amplitudes)
            target_spectrum = np.clip((20 * np.log10(np.maximum(magnitudes, 1e-6)) + 72) / 72, 0, 1)
            response_spectrum = np.where(target_spectrum > self.spectrum_levels, 0.025, 0.18)
            self.spectrum_levels += (target_spectrum - self.spectrum_levels) * (1 - np.exp(-self.hop / rate / response_spectrum))
            energy = float(np.sqrt(np.sum(power[self.band])) / self.window.sum())
            band_energy = np.array([np.sqrt(np.sum(power[band])) / self.window.sum()
                                    for band in self.motion_bands])
            # Compress the dynamic range so vocals and acoustic instruments also move
            # the surface. A small noise floor keeps silence from becoming jitter.
            target = np.clip(np.log1p(np.maximum(0, band_energy - 0.001) * 28)
                             / np.log1p(0.30 * 28), 0, 1)
            response = np.where(target > self.levels, 0.025, 0.16)
            self.levels += (target - self.levels) * (1 - np.exp(-self.hop / rate / response))
            threshold = max(0.012, self.average * 1.55)
            onset = (energy > threshold and energy > self.previous * 1.13 + 0.003
                     and self.clock - self.last_beat >= 0.22)
            if onset:
                beats.append(min(1.0, max(0.35, energy * 5)))
                self.last_beat = self.clock
            audible = np.sqrt(np.sum(power)) / self.window.sum() > .003
            if self.phrase_clock.advance(self.hop / rate, onset, audible):
                self.phrase_events.append(self.phrase_clock.phrases)
            self.average += (energy - self.average) * (1 - np.exp(-self.hop / rate / 0.45))
            self.previous = energy
            self.clock += self.hop / rate
            self.pending = self.pending[self.hop:]
        return beats


class AudioAnalysis(QObject):
    beat = Signal(float)
    bands = Signal(float, float)
    waveform = Signal(object)
    spectrum = Signal(object, float)
    energy = Signal(float)
    phrase = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.detector = BassDetector()
        self.active = False

    def reset(self):
        self.detector.reset()
        self.bands.emit(0.0, 0.0)
        self.spectrum.emit(np.zeros(self.detector.spectrum_count), 20000.0)
        self.energy.emit(0.0)
        self.waveform.emit(np.zeros(512, dtype=np.float32))

    def set_spectrum_bands(self, count):
        count = max(8, min(2048, int(count)))
        if count != self.detector.spectrum_count:
            self.detector.spectrum_count = count
            self.reset()

    def set_phrase_bars(self, bars):
        bars = bars if bars in (2,4,8) else 4
        if bars != self.detector.phrase_bars:
            self.detector.phrase_bars = bars
            self.detector.phrase_clock.set_bars(bars)

    def receive(self, buffer):
        if not self.active or not buffer.isValid() or not buffer.frameCount():
            return
        fmt = buffer.format()
        formats = {
            QAudioFormat.SampleFormat.UInt8: (np.uint8, 128.0, 128.0),
            QAudioFormat.SampleFormat.Int16: (np.int16, 32768.0, 0.0),
            QAudioFormat.SampleFormat.Int32: (np.int32, 2147483648.0, 0.0),
            QAudioFormat.SampleFormat.Float: (np.float32, 1.0, 0.0),
        }
        if fmt.sampleFormat() not in formats:
            return
        dtype, scale, offset = formats[fmt.sampleFormat()]
        samples = np.frombuffer(buffer.constData(), dtype=dtype, count=buffer.sampleCount())
        samples = (samples.astype(np.float32) - offset) / scale
        samples = np.nan_to_num(samples.reshape(-1, fmt.channelCount()))
        self.energy.emit(float(np.clip(np.log1p(np.sqrt(np.mean(samples ** 2)) * 18) / np.log1p(0.4 * 18), 0, 1)))
        channel = int(np.argmax(np.mean(samples ** 2, axis=0)))
        self.waveform.emit(samples[-4096:, channel].copy())
        for strength in self.detector.feed(samples, fmt.sampleRate()):
            self.beat.emit(strength)
        for number in self.detector.phrase_events:
            self.phrase.emit(number)
        self.bands.emit(*self.detector.levels)
        self.spectrum.emit(self.detector.spectrum_levels.copy(), min(20000.0, fmt.sampleRate() / 2))
