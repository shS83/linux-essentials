"""Crawler visualization integrated into the existing MusiK Qt visualizer API."""
from __future__ import annotations

import math
import time

import moderngl
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QFont

from .crawler_renderer import CrawlerRenderer
from .settings import EFFECTS
from .visualizer import Visualizer


class CrawlerVisualizer(Visualizer):
	"""Audio-reactive neon geometry with HUD hidden by default."""

	def __init__(self, parent=None):
		super().__init__(parent)
		self.effect = EFFECTS.index('Crawler')
		self._renderer = None
		self._energy = 0.0
		self._energy_at = -100.0
		self._elapsed = 0.0
		self._paused = False
		self._clear_next = False
		self._hud_visible = False
		self.ball_count = 94
		self.trail_alpha = 14
		self.plasma = True
		self.bloom = True
		self.scanlines = True
		self.vignette = True

	def on_energy(self, energy):
		self._energy = max(0., min(1., float(energy)))
		self._energy_at = time.monotonic()

	def reset(self):
		super().reset()
		self._energy = 0.0
		self._energy_at = -100.0
		self._clear_next = True

	def initializeGL(self):
		try:
			self.ctx = moderngl.create_context(require=330)
			self._renderer = CrawlerRenderer(self.ctx, render_scale=0.5)
			self.context().aboutToBeDestroyed.connect(self.cleanup)
		except Exception as exc:
			self.error = f'Crawler OpenGL initialization failed: {exc}'
			self.timer.stop()
			self.failed.emit(self.error)

	def paintGL(self):
		if self.error or self._renderer is None:
			painter = QPainter(self)
			painter.fillRect(self.rect(), QColor('#080414'))
			painter.setPen(Qt.GlobalColor.white)
			painter.drawText(self.rect().adjusted(25,25,-25,-25),
			                 Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
			                 self.error or 'Crawler renderer unavailable')
			painter.end()
			return
		now = time.monotonic()
		dt = min(0.1, max(0.0, now-self.last_frame))
		self.last_frame = now
		if not self._paused:
			self._elapsed += dt
		fade = math.exp(-max(0.,now-self.band_time-0.12)*6.)
		mid, treble = (max(0.,min(1.,float(x)*fade)) for x in self.band_levels)
		energy = self._energy*math.exp(-max(0.,now-self._energy_at-0.12)*6.)
		bass = min(1., self.strength*math.exp(-max(0.,now-self.beat_time)*5.5))
		ratio = self.devicePixelRatioF()
		size = (max(1,round(self.width()*ratio)), max(1,round(self.height()*ratio)))
		try:
			target = self.ctx.detect_framebuffer(self.defaultFramebufferObject())
			self._renderer.draw(target, size, self._elapsed, dt,
			                   self.ball_count, self.trail_alpha, energy, mid, treble, bass,
			                   paused=self._paused, clear=self._clear_next,
			                   plasma=self.plasma, bloom=self.bloom,
			                   scanlines=self.scanlines, vignette=self.vignette)
			self._clear_next = False
		except Exception as exc:
			self.error = f'Crawler rendering failed: {exc}'
			self.timer.stop()
			self.failed.emit(self.error)
			return
		if self._hud_visible:
			self._paint_hud()

	def _paint_hud(self):
		painter = QPainter(self)
		painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
		painter.fillRect(12, 12, 350, 132, QColor(5, 5, 20, 180))
		painter.setPen(QColor('#a6fcff'))
		font = QFont('Monospace', 10)
		font.setStyleHint(QFont.StyleHint.TypeWriter)
		painter.setFont(font)
		lines = (
			f'CRAWLER  |  {self.ball_count} balls  |  trail {self.trail_alpha}',
			f'H HUD  SPACE pause  C clear  R reset',
			f'UP/DOWN balls  LEFT/RIGHT trail',
			f'B plasma  L bloom  S scanlines  V vignette',
			f'F11 fullscreen  ESC close',
		)
		for i,line in enumerate(lines):
			painter.drawText(24, 35+i*22, line)
		painter.end()

	def keyPressEvent(self, event):
		key = event.key()
		if key == Qt.Key.Key_H:
			self._hud_visible = not self._hud_visible
		elif key == Qt.Key.Key_Space:
			self._paused = not self._paused
		elif key == Qt.Key.Key_C:
			self._clear_next = True
		elif key == Qt.Key.Key_R:
			self.ball_count, self.trail_alpha = 94, 14
			self._clear_next = True
		elif key == Qt.Key.Key_Up:
			self.ball_count = min(200, self.ball_count+1)
		elif key == Qt.Key.Key_Down:
			self.ball_count = max(2, self.ball_count-1)
		elif key == Qt.Key.Key_Left:
			self.trail_alpha = max(1, self.trail_alpha-1)
		elif key == Qt.Key.Key_Right:
			self.trail_alpha = min(64, self.trail_alpha+1)
		elif key == Qt.Key.Key_B:
			self.plasma = not self.plasma
		elif key == Qt.Key.Key_L:
			self.bloom = not self.bloom
		elif key == Qt.Key.Key_S:
			self.scanlines = not self.scanlines
		elif key == Qt.Key.Key_V:
			self.vignette = not self.vignette
		else:
			# Use MusiK's existing F11/Esc handling and borderless window.
			super().keyPressEvent(event)
			return
		self.update()
		event.accept()

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
