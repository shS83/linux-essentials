"""Audio-driven adaptations of PsyTunnel, Hiss and Matrixia (see licenses/)."""
import math
from pathlib import Path
import random
import time

import moderngl
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap

from .visualizer import Visualizer
from .settings import EFFECTS
from .lasers import LaserScene
from .biolume import Biolume
from .fireworks import Fireworks
from .fireworks_debug import FireworksDebug

class MusicMotion:
    """Integrate velocity so changes of loudness never jump animation time."""
    def __init__(self):
        self.energy = 0.0
        self.speed = 0.0
        self.travel = 0.0
        self.phase = 0.0
        self.reverse_left = 0.0
        self.armed = False

    def step(self, dt, energy, mid, treble, pulse):
        blend = 1 - math.exp(-dt / 0.22)
        self.energy += (energy - self.energy) * blend
        if self.energy > 0.55:
            self.armed = True
        if self.energy < 0.22 and self.armed:
            self.reverse_left = 1.6
            self.armed = False
        self.reverse_left = max(0, self.reverse_left - dt)
        target = 0.06 + 4.8 * self.energy + 1.2 * mid + 0.6 * treble + 2 * pulse
        if self.reverse_left > 0 and self.energy < 0.35:
            target = -0.8 - 0.8 * (1 - self.energy)
        self.speed += (target - self.speed) * (1 - math.exp(-dt / 0.25))
        self.travel += self.speed * dt
        self.phase += dt * (0.025 + 1.8 * self.energy + 0.5 * mid + 0.35 * treble)


class EffectVisualizer(Visualizer):
    def __init__(self, effect, parent=None):
        super().__init__(parent)
        self.effect = effect
        self.lasers = LaserScene((1,3,4)[effect-4]) if 4 <= effect <= 6 else None
        self.bio = self.fire = None
        self.setWindowTitle(f"μSIK · {EFFECTS[effect]} · F11 fullscreen · Esc close")
        self.dynamics = MusicMotion()
        self.energy_level = 0.0
        self.energy_time = -100.0
        self.resources = []
        self.source_fbo = self.source_texture = None
        self.source_size = None
        self.matrix_color = 1
        self.matrix_clock = 0.0
        self.glyphs = []
        self.streams = []
        self.fireworks_debug = None
        self.rng = random.Random(1731)
        if effect == 3:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def on_beat(self, strength):
        super().on_beat(strength)
        if self.lasers is not None:
            self.lasers.on_beat(self.parent().preferences["laser_bars"] if self.parent() else 4)

    def on_phrase(self, number):
        if self.lasers is not None and self.parent() and self.parent().party_active:
            self.lasers.change_phrase(number)

    def on_energy(self, level):
        self.energy_level = level
        self.energy_time = time.monotonic()

    def reset(self):
        super().reset()
        self.energy_level = 0.0
        self.energy_time = -100.0
        self.dynamics = MusicMotion()
        if self.lasers is not None:
            self.lasers.reset()

    def initializeGL(self):
        try:
            if self.effect in (1, 2, 7, 8):
                self.ctx = moderngl.create_context(require=330)
                folder = Path(__file__).resolve().parent.parent / "shaders"
                vertex = (folder / "scene.vert").read_text()
                def program(filename):
                    result = self.ctx.program(vertex_shader=vertex, fragment_shader=(folder / filename).read_text())
                    vao = self.ctx.vertex_array(result, [])
                    self.resources.extend((vao, result))
                    return result, vao
                if self.effect == 7:
                    self.program, self.vao = program("biolume.frag")
                elif self.effect == 8:
                    self.fire = Fireworks(self.ctx, folder)
                    self.fireworks_debug = FireworksDebug(self, self.fire)
                    self.resources.extend((self.fire.vao, self.fire.buffer, self.fire.program))
                elif self.effect == 1:
                    self.program, self.vao = program("tunnel.frag")
                else:
                    self.cube_program, self.cube_vao = program("hiss_scene.frag")
                    self.program, self.vao = program("hiss.frag")
            self.context().aboutToBeDestroyed.connect(self.cleanup)
        except Exception as exc:
            self.error = f"Visualization unavailable: {exc}"
            self.failed.emit(self.error)

    def paintGL(self):
        if self.error:
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor("#21132d"))
            painter.setPen(QColor("white"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.error)
            painter.end()
            return
        now = time.monotonic()
        dt = min(max(0, now - self.last_frame), 0.1)
        self.last_frame = now
        decay = math.exp(-max(0, now - self.band_time - 0.1) * 12)
        for i in range(2):
            self.motion[i] += (self.band_levels[i] * decay - self.motion[i]) * (1 - math.exp(-dt / .08))
        mid, treble = self.motion
        pulse = self.strength * math.exp(-max(0, now - self.beat_time) * 5.5)
        energy = self.energy_level * math.exp(-max(0, now - self.energy_time - .1) * 8)
        self.dynamics.step(dt, energy, mid, treble, pulse)
        if self.lasers is not None:
            self.lasers.paint(self, dt, self.dynamics.energy, mid, treble, pulse)
            return
        if self.effect == 3:
            self.paint_matrix(dt, mid, treble, pulse)
            return
        ratio = self.devicePixelRatioF()
        size = (max(1, round(self.width() * ratio)), max(1, round(self.height() * ratio)))
        framebuffer = self.ctx.detect_framebuffer(self.defaultFramebufferObject())
        framebuffer.use()
        self.ctx.viewport = (0, 0, *size)
        self.ctx.disable(moderngl.DEPTH_TEST | moderngl.BLEND)
        if self.effect == 8:
            self.fire.draw(dt, self.width(), self.height(), ratio, energy)
            return
        if self.effect == 7:
            aspect = size[0]/size[1]
            if self.bio is None:
                self.bio = Biolume(aspect)
            self.bio.step(dt, aspect, energy, treble, pulse)
            self.bio.upload(self.program)
            for name, value in (("u_resolution",size),("u_time",now-self.started),("u_bass",energy),
                                ("u_treble",treble),("u_pulse",self.bio.pulse)):
                if name in self.program:
                    self.program[name].value = value
            self.vao.render(moderngl.TRIANGLES, vertices=3)
            return
        if self.effect == 1:
            phase = self.dynamics.phase
            values = {
                "uResolution": size, "uTime": phase,
                "uCamera": (.18 * math.sin(phase * .23), .15 * math.cos(phase * .19), self.dynamics.travel),
                "uForward": (0., 0., 1.),
                "uRight": (math.cos(phase * .08), math.sin(phase * .08), 0.),
                "uUp": (-math.sin(phase * .08), math.cos(phase * .08), 0.),
                "uPaletteFrom": 1, "uPaletteTo": 1, "uPaletteMix": 0., "uFlash": min(.65, pulse * .65),
            }
            for name, value in values.items():
                self.program[name].value = value
            self.vao.render(mode=moderngl.TRIANGLES, vertices=3)
        else:
            if self.source_size != size:
                self.release_source()
                self.source_texture = self.ctx.texture(size, 4)
                self.source_texture.filter = (moderngl.LINEAR, moderngl.LINEAR)
                self.source_texture.repeat_x = self.source_texture.repeat_y = False
                self.source_fbo = self.ctx.framebuffer(color_attachments=[self.source_texture])
                self.source_size = size
            self.source_fbo.use()
            self.cube_program["resolution"].value = size
            self.cube_program["angle"].value = self.dynamics.phase * .65
            self.cube_vao.render(mode=moderngl.TRIANGLES, vertices=3)
            framebuffer.use()
            self.source_texture.use(0)
            values = {"source": 0, "resolution": size, "time": self.dynamics.phase,
                      "strength": .07 + .46 * self.dynamics.energy + .26 * mid + .22 * pulse,
                      "dispersion": .08 + .46 * treble + .24 * pulse,
                      "turbulence": .48 + 1.2 * treble}
            for name, value in values.items():
                self.program[name].value = value
            self.vao.render(mode=moderngl.TRIANGLES, vertices=3)

    def make_glyphs(self):
        # Matrixia's mixed Katakana/ASCII rain, without its instruction toast.
        characters = "アイウエオカキクケコサシスセソタチツテトナニヌネノ0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        palette = ("#38ff75", "#4414ff", "#ffb448", "#ff55bb", "#b394ff", "#fafafa", "#ff5757")
        font = QFont("Yu Gothic", 15)
        font.setPixelSize(20)
        self.glyphs = []
        ratio = self.devicePixelRatioF()
        for tint in (palette[self.matrix_color], "#edfff4"):
            images = []
            for char in characters:
                pixmap = QPixmap(round(24 * ratio), round(27 * ratio))
                pixmap.setDevicePixelRatio(ratio)
                pixmap.fill(Qt.GlobalColor.transparent)
                painter = QPainter(pixmap)
                painter.setFont(font)
                painter.setPen(QColor(tint))
                painter.drawText(0, 21, char)
                painter.end()
                images.append(pixmap)
            self.glyphs.append(images)
        self.glyph_ratio = ratio

    def paint_matrix(self, dt, mid, treble, pulse):
        if not self.glyphs or self.glyph_ratio != self.devicePixelRatioF():
            self.make_glyphs()

        cell_w = 24
        cell_h = 27
        trail_length = 22
        columns = max(1, self.width() // cell_w + 1)
        glyph_count = len(self.glyphs[0])

        # Each stream:
        # [head_y, speed_factor, glyphs, accumulator]
        # glyphs = [(row, glyph_index), ...]

        while len(self.streams) < columns:
            self.streams.append([
                self.rng.uniform(-self.height(), 0),
                self.rng.uniform(.6, 1.5),
                [],
                0.0
            ])

        self.streams = self.streams[:columns]

        rate = (
                8
                + 190 * self.dynamics.energy
                + 100 * mid
                + 100 * treble
                + 260 * pulse
        )

        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#020604"))

        for column, stream in enumerate(self.streams):
            head_y, speed, chars, accumulator = stream

            # Advance the stream.
            new_y = head_y + dt * rate * speed

            # Generate a new glyph each time the head crosses
            # a character cell boundary.
            old_row = int(head_y // cell_h)
            new_row = int(new_y // cell_h)

            for row in range(old_row + 1, new_row + 1):
                chars.insert(0, (
                    row,
                    self.rng.randrange(glyph_count)
                ))

            # Keep only the trailing characters.
            del chars[trail_length:]

            stream[0] = new_y

            # Draw already-born glyphs.
            for tail, (row, glyph_index) in enumerate(chars):
                y = row * cell_h

                if y < -cell_h or y > self.height():
                    continue

                # Head is white; the trail fades to green/black.
                is_head = tail == 0

                opacity = (1 - tail / trail_length) ** 1.6

                painter.setOpacity(opacity)

                painter.drawPixmap(
                    column * cell_w,
                    int(y),
                    self.glyphs[1 if is_head else 0][glyph_index]
                )

            # Restart the stream after it has exited the screen.
            if head_y > self.height() + trail_length * cell_h:
                stream[0] = -self.rng.uniform(
                    cell_h,
                    max(cell_h + 1, self.height() * .4)
                )
                chars.clear()

        painter.end()

    def mousePressEvent(self, event):
        if self.effect == 3 and event.button() == Qt.MouseButton.LeftButton:
            self.matrix_color = (self.matrix_color + 1) % 7
            self.glyphs = []
            self.update()
            event.accept()
        else:
            super().mousePressEvent(event)

    def release_source(self):
        for resource in (self.source_fbo, self.source_texture):
            if resource is not None:
                resource.release()
        self.source_fbo = self.source_texture = None
        self.source_size = None

    def cleanup(self):
        self.makeCurrent()
        self.release_source()
        for resource in self.resources:
            resource.release()
        self.resources = []
        self.ctx = self.program = self.vao = None
        self.doneCurrent()
