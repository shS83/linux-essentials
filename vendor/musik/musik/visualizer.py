import colorsys
import math
from pathlib import Path
import random
import time

import moderngl
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from .borderless import BorderlessWindow
from .settings import EFFECTS


class Visualizer(QOpenGLWidget):
    failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowTitle("μSIK · Visualization — F11 fullscreen · Esc close")
        self.resize(1280, 720)
        self.borderless = BorderlessWindow(self)
        self.ctx = self.program = self.vao = None
        self.error = ""
        self.started = time.monotonic()
        self.beat_time = -100.0
        self.strength = 0.0
        self.kick = 0.0
        self.band_levels = (0.0, 0.0)
        self.band_time = -100.0
        self.motion = [0.0, 0.0]
        self.last_frame = self.started
        self.flash = (0.7, 0.2, 0.8)
        self.density = 1.4
        self.speed = 1.0
        self.frame_count = 0
        self.frame_clock = self.started
        self.frameSwapped.connect(self.report_fps)
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.update)

    def report_fps(self):
        self.frame_count += 1
        now = time.monotonic()
        elapsed = now - self.frame_clock
        if elapsed >= 1:
            effect = EFFECTS[getattr(self, "effect", 0)]
            self.setWindowTitle(f"μSIK · {effect} · {self.frame_count / elapsed:.0f} FPS · F11 / Esc")
            self.frame_clock = now
            self.frame_count = 0

    def on_beat(self, strength):
        self.beat_time = time.monotonic()
        self.strength = strength
        self.flash = colorsys.hsv_to_rgb(random.random(), 0.72, 1.0)

    def reset(self):
        self.beat_time = -100.0
        self.strength = 0.0
        self.kick = 0.0
        self.band_levels = (0.0, 0.0)
        self.motion = [0.0, 0.0]
        self.band_time = -100.0
        self.update()

    def on_bands(self, mid, treble):
        self.band_levels = (mid, treble)
        self.band_time = time.monotonic()

    def initializeGL(self):
        try:
            self.ctx = moderngl.create_context(require=330)
            folder = Path(__file__).resolve().parent.parent / "shaders"
            self.program = self.ctx.program(
                vertex_shader=(folder / "scene.vert").read_text(),
                fragment_shader=(folder / "scene.frag").read_text(),
            )
            self.vao = self.ctx.vertex_array(self.program, [])
            self.context().aboutToBeDestroyed.connect(self.cleanup)
        except Exception as exc:
            self.error = f"OpenGL 3.3 visualization unavailable: {exc}"
            self.failed.emit(self.error)

    def paintGL(self):
        if self.error or self.vao is None:
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor("#21132d"))
            painter.setPen(QColor("#ffffff"))
            painter.drawText(self.rect().adjusted(30, 30, -30, -30), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.error)
            painter.end()
            return
        # Qt owns an FBO which can change on resize / HiDPI / fullscreen.
        framebuffer = self.ctx.detect_framebuffer(self.defaultFramebufferObject())
        framebuffer.use()
        ratio = self.devicePixelRatioF()
        size = (round(self.width() * ratio), round(self.height() * ratio))
        self.ctx.viewport = (0, 0, *size)
        now = time.monotonic()
        dt = min(now - self.last_frame, 0.1)
        self.last_frame = now
        # Decay stale data if the decoder stops delivering buffers.
        decay = math.exp(-max(0.0, now - self.band_time - 0.10) * 12)
        blend = 1 - math.exp(-dt / 0.035)
        for i in range(2):
            self.motion[i] += (self.band_levels[i] * decay - self.motion[i]) * blend
        self.program["u_resolution"].value = size
        self.program["u_time"].value = now - self.started
        self.program["u_density"].value = self.density
        self.program["u_speed"].value = self.speed
        pulse = self.strength * math.exp(-(now - self.beat_time) * 7.0)
        self.kick += (pulse-self.kick)*(1-math.exp(-dt/(.020 if pulse>self.kick else .180)))
        self.program["u_kick"].value = self.kick
        self.program["u_pulse"].value = pulse
        self.program["u_flash"].value = self.flash
        self.program["u_mid"].value = self.motion[0]
        self.program["u_treble"].value = self.motion[1]
        self.vao.render(mode=moderngl.TRIANGLES, vertices=3)

    def showEvent(self, event):
        super().showEvent(event)
        self.frame_clock = time.monotonic()
        self.frame_count = 0
        self.timer.start()

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.borderless.set_active(False) if self.borderless.active else self.close()
        elif key == Qt.Key.Key_F11:
            self.borderless.toggle()
        elif key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            self.density = max(0, min(4, self.density + (0.1 if key == Qt.Key.Key_Up else -0.1)))
        elif key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self.speed = max(0, min(4, self.speed + (0.1 if key == Qt.Key.Key_Right else -0.1)))
        elif key == Qt.Key.Key_R:
            self.density, self.speed = 1.4, 1.0
        else:
            super().keyPressEvent(event)

    def cleanup(self):
        self.makeCurrent()
        for resource in (self.vao, self.program):
            if resource is not None:
                resource.release()
        self.vao = self.program = self.ctx = None
        self.doneCurrent()
