"""Persistent player preferences and a fixed, seeded set of gradient themes."""
from .audio_output import OutputControls, WIDTHS
from .gl_backend import BACKEND_LABELS, available_backends

import colorsys
import random

from PySide6.QtCore import QSettings, QSize
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import (
    QApplication, QTabWidget, QWidget, QCheckBox, QColorDialog, QPushButton, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QSpinBox, QVBoxLayout,
)


def make_themes():
    rng = random.Random(20261030)
    themes = [("μSIK", ("#381754", "#632b60", "#cf713e", "#ffc3a3"))]
    names = ("Aurora", "Ember", "Lagoon", "Velvet", "Neon", "Dusk", "Ocean",
             "Orchid", "Copper", "Forest", "Midnight", "Rose", "Glacier",
             "Solar", "Plum", "Jade", "Cosmic", "Amber", "Electric")
    for name in names:
        hue = rng.random()
        shift = rng.uniform(0.08, 0.30)
        def color(h, s, v):
            return "#" + "".join(f"{round(c * 255):02x}" for c in colorsys.hsv_to_rgb(h % 1, s, v))
        themes.append((name, (color(hue, .72, .25), color(hue + shift, .68, .42),
                              color(hue + shift * 2, .65, .64), color(hue + shift, .30, 1))))
    return tuple(themes)


THEMES = make_themes()
ORDERS = ("Manual / import order", "Title A–Z", "Title Z–A", "Folder / filename")
EFFECTS = ("Chrome sphere", "PsyTunnel", "Hiss", "Matrixia",
           "Orbit Streams", "Glyph Spin", "Glyph Trails", "Biolume", "Fireworks", "Circler Tetra", "fog_shS")
PLAYBACK = ("Normal", "Reversed", "Shuffle tracks", "Shuffle albums (folders)", "Random")
DISPLAY = ("Oscilloscope", "Spectrum analyzer", "Combo (half + half)")
GRADIENTS = (("Player theme", None), ("Black → White", ("#000000","#ffffff")),
             ("Bright yellow → Deep green", ("#ffff00","#004116")), ("Electric cyan → Deep blue", ("#00ffff","#0a0c55")),
             ("Coral → Midnight violet", ("#ff6e55","#230850")), ("Lime → Deep teal", ("#beff14","#032830")),
             ("Electric pink → Midnight blue", ("#ff28b4","#061246")), ("Golden orange → Deep burgundy", ("#ffa01e","#460823")),
             ("Custom colors", None))
DEFAULTS = {"output_device": "", "output_width": "auto", "output_rate": 0, "playback": 0, "display": 0, "gradient": 0, "reverse": 0, "custom_start": "#ff00ff", "custom_end": "#ff9600","scope_points": 512, "spectrum_bands": 48, "order": 0, "theme": 0, "effect": 0, "laser_bars": 4, "gl_backend": "auto"}
LIMITS = {"playback": (0, 4), "display": (0, 2), "gradient": (0, 8), "reverse": (0,1), "scope_points": (64, 4096), "spectrum_bands": (8, 2048), "order": (0, 3),
          "theme": (0, 19), "effect": (0, len(EFFECTS) - 1), "laser_bars": (2, 8)}


def load_settings(store):
    values = {}
    for key, default in DEFAULTS.items():
        if key == "gl_backend":
            value = str(store.value(key, default))
            values[key] = value if value in BACKEND_LABELS else default
            continue
        if key in ("output_device", "output_width"):
            value = str(store.value(key, default))
            values[key] = value if key == "output_device" or value in WIDTHS else default
            continue
        if key in ("custom_start", "custom_end"):
            color = QColor(str(store.value(key, default)))
            values[key] = color.name() if color.isValid() else default
            continue
        try:
            value = int(store.value(key, default))
        except (ValueError, TypeError):
            value = default
        if key == "output_rate":
            values[key] = value if 0 <= value <= 768000 else 0
            continue
        if key == "order" and value == 4:
            value = 0  # Migrate old playlist-shuffle setting to manual order.
        low, high = LIMITS[key]
        values[key] = max(low, min(high, value))
    if values["laser_bars"] not in (2,4,8):
        values["laser_bars"] = 4
    if store.contains("effect") and str(store.value("effectListVersion", 1)) == "1":
        values["effect"] = (0,1,2,3,0,4,0,5,6)[values["effect"]]
    return values


def default_store():
    return QSettings("MusiK", "MusiK")


class SettingsDialog(QDialog):
    def __init__(self, values, parent=None):
        super().__init__(parent)
        self.setWindowTitle("μSIK · Settings")
        self.setMinimumWidth(470)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.scope_points = QSpinBox()
        self.scope_points.setRange(*LIMITS["scope_points"])
        self.scope_points.setSingleStep(64)
        self.scope_points.setValue(values["scope_points"])
        self.scope_points.setSuffix(" points")
        self.scope_points.setToolTip("Number of samples drawn across the oscilloscope")
        form.addRow("Oscilloscope density", self.scope_points)
        self.spectrum_bands = QSpinBox()
        self.spectrum_bands.setRange(*LIMITS["spectrum_bands"])
        self.spectrum_bands.setSingleStep(8)
        self.spectrum_bands.setValue(values["spectrum_bands"])
        self.spectrum_bands.setSuffix(" bands")
        form.addRow("Spectrum density", self.spectrum_bands)
        self.order = QComboBox()
        self.order.addItems(ORDERS)
        self.order.setCurrentIndex(values["order"])
        form.addRow("Playlist order", self.order)
        self.theme = QComboBox()
        self.theme.setIconSize(QSize(100, 22))
        for name, colors in THEMES:
            preview = QPixmap(100, 22)
            painter = QPainter(preview)
            gradient = QLinearGradient(0, 0, 100, 22)
            for stop, color in zip((0, .46, 1), colors):
                gradient.setColorAt(stop, QColor(color))
            painter.fillRect(preview.rect(), gradient)
            painter.end()
            self.theme.addItem(QIcon(preview), name)
        self.theme.setCurrentIndex(values["theme"])
        form.addRow("Player theme", self.theme)
        self.effect = QComboBox()
        self.effect.addItems(EFFECTS)
        self.effect.setCurrentIndex(values["effect"])
        form.addRow("Visualization", self.effect)
        self.gl_backend = QComboBox()
        for key, label in available_backends():
            self.gl_backend.addItem(label, key)
        if self.gl_backend.findData(values["gl_backend"]) < 0:
            self.gl_backend.addItem(BACKEND_LABELS[values["gl_backend"]] + " (unavailable here)", values["gl_backend"])
        self.gl_backend.setCurrentIndex(self.gl_backend.findData(values["gl_backend"]))
        form.addRow("OpenGL backend", self.gl_backend)
        active_platform = QApplication.platformName() if QApplication.instance() else "not started"
        gl_hint = QLabel(f"Current Qt platform: {active_platform}. Changing the OpenGL backend takes effect after restarting MusiK.")
        gl_hint.setWordWrap(True)
        form.addRow("", gl_hint)
        self.laser_bars = QComboBox()
        self.laser_bars.addItem("Every 2 bars", 2)
        self.laser_bars.addItem("Every 4 bars", 4)
        self.laser_bars.addItem("Every 8 bars", 8)
        self.laser_bars.setCurrentIndex(self.laser_bars.findData(values["laser_bars"]))
        self.laser_bars.setToolTip("Estimated 4/4 phrases from bass onsets; timing depends on the music")
        form.addRow("Laser pattern changes", self.laser_bars)
        for key, label, choices in (("playback","Playback order",PLAYBACK), ("display","Audio display",DISPLAY),
                                    ("gradient","Background gradient",[name for name, _ in GRADIENTS])):
            combo = QComboBox()
            combo.addItems(choices)
            combo.setCurrentIndex(values[key])
            setattr(self, key, combo)
            form.addRow(label, combo)
        self.reverse = QCheckBox("Reverse gradient direction")
        self.reverse.setChecked(bool(values["reverse"]))
        form.addRow("", self.reverse)
        self.custom = {key: values[key] for key in ("custom_start","custom_end")}
        for key, label in (("custom_start","Gradient start"), ("custom_end","Gradient end")):
            button = QPushButton(self.custom[key])
            button.clicked.connect(lambda checked=False,k=key,b=button: self.choose_color(k,b))
            form.addRow(label, button)
        tabs = QTabWidget()
        general = QWidget()
        general.setLayout(form)
        tabs.addTab(general, "Player")
        audio = QWidget()
        self.audio_controls = OutputControls(QFormLayout(audio), values)
        tabs.addTab(audio, "Audio")
        layout.addWidget(tabs)
        hint = QLabel("Settings are remembered. In Matrixia, click the visualization to change colour.\n"
                      "PsyTunnel: bass flashes white, quiet passages can reverse the motion.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def choose_color(self, key, button):
        color = QColorDialog.getColor(QColor(self.custom[key]), self)
        if color.isValid():
            self.custom[key] = color.name()
            self.gradient.setCurrentIndex(len(GRADIENTS)-1)
            button.setText(color.name())

    def values(self):
        return {**self.audio_controls.values(), **self.custom, "playback":self.playback.currentIndex(), "display":self.display.currentIndex(),
                "gradient":self.gradient.currentIndex(), "reverse":int(self.reverse.isChecked()), "scope_points": self.scope_points.value(), "spectrum_bands": self.spectrum_bands.value(),
                "order": self.order.currentIndex(), "theme": self.theme.currentIndex(),
                "effect": self.effect.currentIndex(), "laser_bars": self.laser_bars.currentData(),
                "gl_backend": self.gl_backend.currentData()}
