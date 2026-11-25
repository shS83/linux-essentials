"""MusiK's audio-reactive Circler Tetra OpenGL visualization."""
from __future__ import annotations

import time

import moderngl
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter

from .circler_reactive import CirclerScene, CirclerRenderer
from .visualizer import Visualizer


class CirclerVisualizer(Visualizer):
    """Reuse MusiK's existing beat, Qt window, FPS and borderless API."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.effect = 9  # Circler Tetra appended to EFFECTS; older IDs are stable.
        self.scene = CirclerScene()
        self._renderer = None

    def initializeGL(self):
        try:
            self.ctx = moderngl.create_context(require=330)
            self._renderer = CirclerRenderer(self.ctx)
            self.context().aboutToBeDestroyed.connect(self.cleanup)
        except Exception as exc:
            self.error = f"Circler OpenGL initialization failed: {exc}"
            self.timer.stop()
            self.failed.emit(self.error)

    def paintGL(self):
        if self.error or self._renderer is None:
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor("#141428"))
            painter.setPen(QColor("white"))
            painter.drawText(self.rect().adjusted(30, 30, -30, -30),
                             Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                             self.error or "Circler renderer unavailable")
            painter.end()
            return
        now = time.monotonic()
        dt = min(max(0.0, now - self.last_frame), .10)
        self.last_frame = now
        scale = self.devicePixelRatioF()
        w = max(1, round(self.width() * scale))
        h = max(1, round(self.height() * scale))
        try:
            # The default Qt framebuffer is NOT GL framebuffer 0.
            target = self.ctx.detect_framebuffer(self.defaultFramebufferObject())
            target.use()
            self.scene.update(dt, w, h)
            self._renderer.draw(self.scene, w, h)
        except Exception as exc:
            self.timer.stop()
            self.error = f"Circler rendering failed: {exc}"
            self.failed.emit(self.error)

    def on_beat(self, strength):
        super().on_beat(strength)
        self.scene.beat()

    def reset(self):
        super().reset()
        self.scene.flash = 0.0
        for tetra in self.scene.tetrahedra:
            tetra.kick = 0.0

    def cleanup(self):
        """Release GL resources on Qt context destruction, not window close.

        Closing just hides the widget; the player can reopen the same instance.
        """
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
