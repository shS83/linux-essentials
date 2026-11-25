"""Qt adapter for the four music-reactive attractors."""
from datetime import datetime
import math
from pathlib import Path
import time

import moderngl

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage, QPainter

from .attractor_pack import AttractorPackScene
from .attractor_pack_renderer import AttractorPackRenderer
from .settings import EFFECTS
from .visualizer import Visualizer


class AttractorPackVisualizer(Visualizer):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.effect = EFFECTS.index("AttractorPack")
        self.scene = AttractorPackScene(gpu=True)
        self._renderer = None
        self.energy = 0.
        self.energy_at = -100.
        self._want_shot = False
        self.setMouseTracking(True)
        self.setWindowTitle("μSIK · AttractorPack · H help · T auto switch · F11 fullscreen")

    def initializeGL(self):
        try:
            self.ctx = moderngl.create_context(require=330)
            self._renderer = AttractorPackRenderer(self.ctx, self.scene.count)
            self.context().aboutToBeDestroyed.connect(self.cleanup)
        except Exception as exc:
            self.error = f'AttractorPack GPU initialization failed: {exc}'
            self.timer.stop()
            self.failed.emit(self.error)

    def on_energy(self, energy):
        self.energy = max(0., min(1., float(energy)))
        self.energy_at = time.monotonic()

    def on_beat(self, strength):
        super().on_beat(strength)
        self.scene.beat(strength)

    def showEvent(self, event):
        # Hidden time does not consume the current attractor's 15 second slot.
        self.last_frame = time.monotonic()
        super().showEvent(event)

    def reset(self):
        super().reset()
        self.energy = 0.
        self.energy_at = -100.
        self.scene.reset()

    def paintGL(self):
        now = time.monotonic()
        dt, self.last_frame = now - self.last_frame, now
        fade = math.exp(-max(0., now - self.band_time - .12) * 6)
        energy = self.energy * math.exp(-max(0., now - self.energy_at - .12) * 6)
        if self.error or self._renderer is None:
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor('black'))
            painter.setPen(QColor('white'))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                             self.error or 'AttractorPack GPU renderer unavailable')
            painter.end()
            return
        ratio = self.devicePixelRatioF()
        size = (max(1, round(self.width()*ratio)), max(1, round(self.height()*ratio)))
        try:
            target = self.ctx.detect_framebuffer(self.defaultFramebufferObject())
            self._renderer.draw(target, size, self.scene, dt, energy,
                                self.band_levels[0]*fade, self.band_levels[1]*fade)
            if self._want_shot:
                self._want_shot = False
                # The only normal runtime readback: an explicitly requested screenshot.
                data = target.read(components=4, alignment=1)
                raw = QImage(data, *size, size[0]*4, QImage.Format.Format_RGBA8888)
                shot = raw.flipped(Qt.Orientation.Vertical) if hasattr(raw, 'flipped') else raw.mirrored()
                filename = Path.cwd() / f'attractorpack_{datetime.now():%Y%m%d_%H%M%S_%f}.png'
                if not shot.save(str(filename)):
                    self.setWindowTitle(f'AttractorPack · Screenshot save failed: {filename}')
        except Exception as exc:
            self.error = f'AttractorPack GPU rendering failed: {exc}'
            self.timer.stop()
            self.failed.emit(self.error)
            return
        if self.scene.hud_visible:
            painter = QPainter(self)
            painter.fillRect(12, 12, 610, 122, QColor(0, 0, 0, 190))
            painter.setPen(QColor('#c8f4ff'))
            timer = f'{15-self.scene.switch_elapsed:.1f}s' if self.scene.auto_switch else 'off'
            sound = 'on' if self.scene.audio_enabled else 'off'
            for i, line in enumerate((
                f'ATTRACTORPACK · {self.scene.name} [{self.scene.current+1}/4] · Auto {timer} · Audio {sound}',
                'N next · T auto switch · 1–4 select · A audio · H HUD',
                'SPACE drift on/off · R new shape/angle · C palette · S screenshot',
                'Mouse: shape · Click: burst · F / F11 fullscreen · ESC close',
                'Parameters: ' + '  '.join(f'{v:+.2f}' for v in self.scene.parameters),
            )):
                painter.drawText(24, 34 + i*22, line)
            painter.end()

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_H:
            self.scene.hud_visible = not self.scene.hud_visible
        elif key == Qt.Key.Key_N:
            self.scene.select(self.scene.current+1)
        elif key == Qt.Key.Key_T:
            self.scene.toggle_auto()
        elif Qt.Key.Key_1 <= key <= Qt.Key.Key_4:
            self.scene.select(key-Qt.Key.Key_1)
        elif key == Qt.Key.Key_A:
            self.scene.toggle_audio()
        elif key == Qt.Key.Key_S:
            self._want_shot = True
        elif key == Qt.Key.Key_Space:
            self.scene.paused = not self.scene.paused
        elif key == Qt.Key.Key_C:
            self.scene.palette = (self.scene.palette + 1) % 4
        elif key == Qt.Key.Key_R:
            self.scene.randomize()
        elif key == Qt.Key.Key_F:
            self.borderless.toggle()
        else:
            super().keyPressEvent(event)
            return
        self.update()
        event.accept()

    def mouseMoveEvent(self, event):
        self.scene.pointer = (event.position().x() / max(1, self.width()) - .5,
                              event.position().y() / max(1, self.height()) - .5)
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        self.scene.pointer = (0., 0.)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.scene.burst()
        super().mousePressEvent(event)

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
