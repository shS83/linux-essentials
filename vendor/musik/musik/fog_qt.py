"""Qt integration for the original fog_shS + live waveform outline."""
from __future__ import annotations

import math
import time

import numpy as np
import moderngl
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter

from .fog_renderer import FogRenderer, AUDIO_SAMPLES, resample_waveform
from .visualizer import Visualizer


class FogShSVisualizer(Visualizer):
    """Fixed-memory renderer; shares MusiK's existing FPS and window controls."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.effect = 10  # appended after Circler, keeping previous IDs stable
        self._renderer = None
        self._waveform = np.zeros(AUDIO_SAMPLES, dtype=np.float32)
        self._energy = 0.0
        self._energy_at = -100.

    def on_waveform(self, samples):
        self._waveform = resample_waveform(samples)

    def on_energy(self, energy):
        self._energy = float(np.clip(energy, 0., 1.))
        self._energy_at = time.monotonic()

    def reset(self):
        super().reset()
        self._waveform.fill(0.)
        self._energy = 0.
        if self._renderer is not None:
            self._renderer.updated_audio.fill(0.)

    def initializeGL(self):
        try:
            self.ctx = moderngl.create_context(require=330)
            self._renderer = FogRenderer(self.ctx)
            self.context().aboutToBeDestroyed.connect(self.cleanup)
        except Exception as exc:
            self.error = f"fog_shS OpenGL initialization failed: {exc}"
            self.timer.stop()
            self.failed.emit(self.error)

    def paintGL(self):
        if self.error or self._renderer is None:
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor('#071122'))
            painter.setPen(Qt.GlobalColor.white)
            painter.drawText(self.rect().adjusted(25, 25, -25, -25),
                             Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                             self.error or 'fog_shS renderer not initialized')
            painter.end()
            return
        now = time.monotonic()
        dt = min(.1, max(0., now - self.last_frame))
        self.last_frame = now
        ratio = self.devicePixelRatioF()
        size = (max(1, round(self.width() * ratio)), max(1, round(self.height() * ratio)))
        pulse = self.strength * math.exp(-max(0., now - self.beat_time) * 6.0)
        energy = self._energy * math.exp(-max(0., now - self._energy_at - .12) * 6.)
        mids = [float(x) * math.exp(-max(0., now - self.band_time - .12) * 6.) for x in self.band_levels]
        try:
            target = self.ctx.detect_framebuffer(self.defaultFramebufferObject())
            self._renderer.draw(target, size, now - self.started,
                                self._waveform, energy, pulse, *mids, dt)
        except Exception as exc:
            self.timer.stop()
            self.error = f"fog_shS rendering failed: {exc}"
            self.failed.emit(self.error)

    def cleanup(self):
        if self._renderer is None:
            self.ctx = None
            return
        self.makeCurrent()
        try:
            self._renderer.release()
            self._renderer = None
            self.ctx = None
        finally:
            self.doneCurrent()
