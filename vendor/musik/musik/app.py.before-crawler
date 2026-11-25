import os
import random
from pathlib import Path
import sys
from time import perf_counter

# AudioBufferOutput requires Qt's FFmpeg backend.
os.environ.setdefault("QT_MEDIA_BACKEND", "ffmpeg")

import numpy as np
from PySide6.QtCore import Qt, QRectF, QTimer, QUrl, QSize, QStandardPaths, QEvent, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QKeySequence, QPainter, QPainterPath, QPixmap, QPen, QShortcut, QSurfaceFormat
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QMenu, QLineEdit, QStyledItemDelegate, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton,
    QSlider, QVBoxLayout, QWidget,
)
from .audio_output import PlaybackOutput
from .audio import AudioAnalysis
from .library import AUDIO_FILE_FILTER, FolderScanner
from .playlist import load_playlist, save_playlist
from .visualizer import Visualizer
from .effects import EffectVisualizer
from .circler_qt import CirclerVisualizer
from .fog_qt import FogShSVisualizer
from .folders import choose_folders
from .settings import SettingsDialog, THEMES, EFFECTS, GRADIENTS, default_store, load_settings
from .gl_backend import apply_backend
from .seek_slider import SeekSlider
from .metadata import MetadataPlaylist, MetadataDialog
import ctypes

STYLE = """
QMainWindow { background: #24132c; }
QWidget#canvas {
 background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
 stop:0 #381754, stop:0.46 #632b60, stop:1 #cf713e);
}
QWidget { color: #fff4ed; font-family: 'Noto Sans', sans-serif; font-size: 13px; }
QLabel { background: transparent; }
QLabel#brand { font-size: 42px; font-weight: 800; letter-spacing: -2px; }
QLabel#eyebrow { color: #e8c1d6; font-size: 11px; letter-spacing: 2px; }
QLabel#track { font-size: 22px; font-weight: 600; }
QLabel#muted { color: #e4c7d6; }
QFrame#panel { background: rgba(23, 13, 35, 190); border: 1px solid rgba(255,255,255,28); border-radius: 18px; }
QPushButton#transport { padding: 5px; background: rgba(32,17,46,155); border-radius: 8px; }
QPushButton#transport:hover { background: #75426b; }
QPushButton { background: rgba(255,255,255,17); border: 1px solid rgba(255,255,255,35); border-radius: 9px; padding: 10px 14px; }
QPushButton:hover { background: rgba(255,255,255,38); border-color: #f7ae89; }
QPushButton:pressed { background: #7d436f; }
QPushButton:disabled { color: #947f92; background: rgba(255,255,255,6); border-color: transparent; }
QPushButton#primary { background: #f7ac81; color: #28152e; font-weight: 700; }
QPushButton#visualize { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #9a5de0,stop:1 #ef9a65); color: white; font-weight: 700; padding: 13px 22px; }
QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { padding: 13px 10px; border-bottom: 1px solid rgba(255,255,255,12); border-radius: 5px; }
QListWidget::item:selected { background: rgba(196,131,224,70); }
QListWidget::item:hover { background: rgba(255,255,255,18); }
QSlider::groove:horizontal { height: 4px; border-radius: 2px; background: rgba(255,255,255,35); }
QSlider::sub-page:horizontal { background: #f4ad88; border-radius: 2px; }
QSlider::handle:horizontal { background: #ffe1cc; width: 12px; margin: -4px 0; border-radius: 6px; }
QStatusBar { background: #25162e; color: #d9bcd1; font-size: 11px; }
QToolTip { color: #fff4ed; background: #38213e; border: 1px solid #8e5e91; }
"""


def make_transport_icons():
    # Use the same 34-unit outlines as the C++ player.
    triangles = {
        "Previous": ((24, 7), (11, 17), (24, 27)),
        "Play": ((10, 7), (26, 17), (10, 27)),
        "Next": ((10, 7), (23, 17), (10, 27)),
    }
    bars = {
        "Previous": [(6, 7, 3, 20)], "Next": [(25, 7, 3, 20)],
        "Pause": [(10, 7, 5, 20), (19, 7, 5, 20)], "Stop": [(9, 9, 16, 16)],
    }
    icons = {}
    for name in ("Previous", "Play", "Pause", "Stop", "Next"):
        pixmap = QPixmap(102, 102)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.scale(3, 3)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        if name in triangles:
            first, second, third = triangles[name]
            path.moveTo(*first)
            path.lineTo(*second)
            path.lineTo(*third)
            path.closeSubpath()
        for rect in bars.get(name, ()):
            path.addRect(*rect)
        painter.fillPath(path, Qt.GlobalColor.white)
        painter.end()
        icons[name] = QIcon(pixmap)
    return icons


def timestamp(ms):
    seconds = max(0, ms // 1000)
    return f"{seconds // 60}:{seconds % 60:02d}"


class Oscilloscope(QWidget):
    mode_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(115)
        self.scope_points = 512
        self.accent = "#ffc3a3"
        self.scope_background = "#20152e"
        self.display_mode = 0
        self.spectrum = np.zeros(48)
        self.spectrum_max = 20000.0
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Click to switch between oscilloscope and spectrum analyzer")
        self.samples = np.zeros(512)
        self.pending = self.samples
        self.timer = QTimer(self)
        self.timer.setInterval(33)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    def set_samples(self, samples):
        self.pending = samples

    def set_spectrum(self, levels, maximum):
        self.spectrum = levels
        self.spectrum_max = maximum

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.display_mode = (self.display_mode + 1) % 3
            self.mode_changed.emit(self.display_mode)
            self.update()
            event.accept()
        else:
            super().mousePressEvent(event)

    def tick(self):
        self.samples = self.pending
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(self.scope_background))
        painter.setPen(QPen(QColor(255, 220, 240, 14), 1))
        for x in range(0, self.width(), 36):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), 28):
            painter.drawLine(0, y, self.width(), y)
        painter.setPen(QColor("#e4c7d6"))
        labels = ("OSCILLOSCOPE · click for spectrum", "SPECTRUM · click for combo", "COMBO · click for oscilloscope")
        painter.drawText(10, 16, labels[self.display_mode])
        area_width = self.width() // 2 if self.display_mode == 2 else self.width()
        if self.display_mode != 1:
            self.draw_wave(painter, area_width)
        if self.display_mode != 0:
            if self.display_mode == 2:
                painter.translate(area_width, 0)
                area_width = self.width() - area_width
            left, top, bottom = 10.0, 26.0, self.height() - 22.0
            width = max(1.0, area_width - 20.0)
            count = min(len(self.spectrum), max(1, int(width)))
            starts = np.arange(count) * len(self.spectrum) // count
            levels = np.maximum.reduceat(self.spectrum, starts)
            step = width / count
            for i, level in enumerate(levels):
                height = float(np.clip(level, 0, 1)) * max(1, bottom - top)
                painter.fillRect(QRectF(left + i * step, bottom - height,
                                        max(1, step - .1), height), QColor(self.accent))
            painter.setPen(QColor("#e4c7d6"))
            for frequency in (30, 100, 1000, 10000):
                if frequency >= self.spectrum_max:
                    continue
                x = left + width * np.log(frequency / 30) / np.log(self.spectrum_max / 30)
                label = f"{frequency // 1000}k" if frequency >= 1000 else str(frequency)
                painter.drawText(int(x), self.height() - 5, label)
            painter.drawText(area_width - 62, 16, "−72–0 dB")
        painter.end()

    def draw_wave(self, painter, area_width):
        count = min(len(self.samples), self.scope_points, max(2, round(area_width * self.devicePixelRatioF())))
        points = np.interp(np.linspace(0, len(self.samples) - 1, count), np.arange(len(self.samples)), self.samples)
        path = QPainterPath()
        for i, sample in enumerate(points):
            x = i * area_width / max(1, count - 1)
            y = self.height() / 2 - float(np.clip(sample, -1, 1)) * self.height() * 0.43
            path.moveTo(x, y) if i == 0 else path.lineTo(x, y)
        glow = QColor(self.accent)
        glow.setAlpha(40)
        painter.setPen(QPen(glow, 7))
        painter.drawPath(path)
        painter.setPen(QPen(QColor(self.accent), 1.6))
        painter.drawPath(path)



class TrackDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        playing = "▶" if index.data(Qt.UserRole + 3) else " "
        option.text = f"{index.row()+1:3}    {playing}  {option.text}"


class MainWindow(QMainWindow):
    def __init__(self, settings_store=None):
        super().__init__()
        self.settings_store = settings_store if settings_store is not None else default_store()
        self.preferences = load_settings(self.settings_store)
        self.import_counter = 0
        self.shuffle_key = None
        self.shuffle_cycle = []
        self.shuffle_pool = []
        self.shuffle_pool_key = None
        self.play_history = []
        self.history_index = -1
        self.history_navigation = False
        self.setWindowTitle("μSIK")
        self.resize(1130, 870)
        self.setMinimumSize(930, 720)
        self.setStyleSheet(STYLE)
        self.current_item = None
        self.visualizer = None
        self.visualizer_effect = None
        self.metadata_dialog = None
        self.party_active = False
        self.party_index = self.preferences["effect"]
        self.party_timer = QTimer(self)
        self.party_timer.setInterval(12000)
        self.party_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.party_timer.timeout.connect(self.advance_party)
        self.folder_scanner = None
        self.closing = False
        self.player = QMediaPlayer(self)
        self.output = QAudioOutput(self)
        self.output.setVolume(0.7)
        self.analysis = AudioAnalysis(self)
        self.playback_output = PlaybackOutput(self.player, self.output, self.analysis, self)
        self.playback_output.warning.connect(self.statusBar().showMessage)
        self.build_ui()
        self.analysis.waveform.connect(self.scope.set_samples)
        self.analysis.spectrum.connect(self.scope.set_spectrum)
        self.apply_settings(self.preferences, persist=False)
        self.scope.mode_changed.connect(self.save_display_mode)
        self.player.positionChanged.connect(self.position_changed)
        self.player.durationChanged.connect(self.duration_changed)
        self.player.seekableChanged.connect(self.update_controls)
        self.player.playbackStateChanged.connect(self.state_changed)
        self.player.mediaStatusChanged.connect(self.media_status_changed)
        self.player.errorOccurred.connect(self.player_error)
        self.playlist.itemDoubleClicked.connect(self.play_item)
        self.playlist.itemSelectionChanged.connect(self.update_controls)
        self.seek.sliderReleased.connect(self.seek_to)
        self.seek.track_clicked.connect(lambda _value: self.seek_to())
        QShortcut(QKeySequence("Space"), self, activated=self.toggle_play)
        QShortcut(QKeySequence("Delete"), self.playlist, activated=self.remove_files)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.add_files)
        self.statusBar().showMessage("Add your music to begin · Space: play / pause · Ctrl+O: add files")
        self.update_controls()

    def autosave_playlist(self):
        """Save current playlist before application exits."""

        directory = Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppDataLocation
            )
        )

        filename = directory / "autosave.m3u8"

        try:
            directory.mkdir(parents=True, exist_ok=True)

            tracks = [
                self.playlist.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.playlist.count())
            ]

            save_playlist(str(filename), tracks)

            print(f"[MusiK] Autosaved {len(tracks)} tracks to {filename}")

        except (OSError, ValueError) as exc:
            print(f"[MusiK] Autosave failed: {exc}")

    def autoload_playlist(self):
        """Restore playlist from previous session."""

        directory = Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppDataLocation
            )
        )

        filename = directory / "autosave.m3u8"

        if not filename.is_file():
            print("[MusiK] No previous playlist found")
            return

        try:
            start = perf_counter()

            tracks, missing = load_playlist(str(filename))

            parsed = perf_counter()

            self.add_paths(tracks, report_missing=False)

            loaded = perf_counter()

            print(f"[MusiK] Playlist parsing: {parsed - start:.3f}s")
            print(f"[MusiK] Qt population:    {loaded - parsed:.3f}s")
            print(f"[MusiK] Total:            {loaded - start:.3f}s")
            print(f"[MusiK] Tracks:           {len(tracks)}")

            if missing:
                print(f"[MusiK] {len(missing)} missing files skipped")

        except (OSError, UnicodeError, ValueError) as exc:
            print(f"[MusiK] Autoload failed: {exc}")

    def build_ui(self):
        canvas = QWidget(objectName="canvas")
        self.setCentralWidget(canvas)
        layout = QVBoxLayout(canvas)
        layout.setContentsMargins(30, 22, 30, 24)
        layout.setSpacing(18)
        header = QHBoxLayout()
        title = QVBoxLayout()
        title.setSpacing(0)
        self.brand = QLabel("μSIK", objectName="brand")
        title.addWidget(self.brand)
        self.hue = 0
        self.rainbow_timer = QTimer(self)
        self.rainbow_timer.setInterval(45)
        self.rainbow_timer.timeout.connect(self.animate_brand)
        title.addWidget(QLabel("SOUND INTO COLOUR", objectName="eyebrow"))
        header.addLayout(title)
        header.addStretch()
        self.settings_button = QPushButton("Settings")
        self.settings_button.clicked.connect(self.show_settings)

        self.party_button = QPushButton("Party Mode")
        self.party_button.setCheckable(True)
        self.party_button.setToolTip("Cycle all visualizations every 12 seconds; click again to stop")
        self.party_button.toggled.connect(self.set_party_mode)

        self.visualize_button = QPushButton("✦  Start visualization", objectName="visualize")
        self.visualize_button.clicked.connect(self.show_visualizer)

        layout.addLayout(header)

        panel = QFrame(objectName="panel")
        box = QVBoxLayout(panel)
        box.setContentsMargins(22, 18, 22, 18)
        box.setSpacing(12)
        row = QHBoxLayout()
        row.addWidget(QLabel("NOW PLAYING", objectName="eyebrow"))
        row.addStretch()
        self.state_label = QLabel("STOPPED", objectName="eyebrow")
        row.addWidget(self.state_label)
        box.addLayout(row)
        self.track_label = QLabel("Your next favourite sound", objectName="track")
        self.track_label.setWordWrap(True)
        box.addWidget(self.track_label)
        self.scope = Oscilloscope()
        box.addWidget(self.scope)
        timeline = QHBoxLayout()
        self.elapsed = QLabel("0:00", objectName="muted")
        self.duration = QLabel("0:00", objectName="muted")
        self.seek = SeekSlider(Qt.Orientation.Horizontal)
        self.seek.setRange(0, 0)
        self.seek.setAccessibleName("Playback position")
        timeline.addWidget(self.elapsed)
        timeline.addWidget(self.seek, 1)
        timeline.addWidget(self.duration)
        box.addLayout(timeline)
        controls = QHBoxLayout()
        self.transport_icons = make_transport_icons()
        self.previous_button = self.transport_button("Previous", self.previous)
        self.play_button = self.transport_button("Play", self.toggle_play)
        self.next_button = self.transport_button("Next", self.next)
        self.stop_button = self.transport_button("Stop", self.stop)
        for button in (self.previous_button, self.play_button, self.stop_button, self.next_button):
            header.addWidget(button)
        header.addWidget(self.visualize_button)
        header.addWidget(self.party_button)
        header.addWidget(self.settings_button)
        controls.addStretch()
        self.mute = QPushButton()
        self.mute.setCheckable(True)
        self.mute.setIconSize(QSize(28, 28))
        self.mute.toggled.connect(self.output.setMuted)
        self.output.mutedChanged.connect(self.update_mute_button)
        self.update_mute_button(self.output.isMuted())
        controls.addWidget(self.mute)
        controls.addWidget(QLabel("Volume", objectName="muted"))
        volume = QSlider(Qt.Orientation.Horizontal)
        volume.setRange(0, 100)
        volume.setValue(70)
        volume.setFixedWidth(85)
        volume.setAccessibleName("Volume")
        volume.valueChanged.connect(lambda value: self.output.setVolume(value / 100))
        controls.addWidget(volume)
        layout.addWidget(panel)

        playlist_panel = QFrame(objectName="panel")
        box = QVBoxLayout(playlist_panel)
        box.setContentsMargins(20, 18, 20, 16)
        row = QHBoxLayout()
        row.addWidget(QLabel("PLAYLIST", objectName="eyebrow"))
        row.addStretch()
        self.count_label = QLabel("0 tracks", objectName="muted")
        row.addWidget(self.count_label)
        box.addLayout(row)
        self.playlist = MetadataPlaylist()
        self.playlist.setItemDelegate(TrackDelegate(self.playlist))
        self.playlist.setContextMenuPolicy(Qt.CustomContextMenu)
        self.playlist.customContextMenuRequested.connect(self.track_menu)
        self.playlist.metadata_requested.connect(self.show_track_metadata)
        self.playlist.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.playlist.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.playlist.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.playlist.setAccessibleName("Playlist — double-click a track to play")
        self.playlist.setMinimumHeight(130)
        box.addWidget(self.playlist, 1)
        self.empty_label = QLabel("A little silence before the music.\nAdd audio files with + to build your playlist.", objectName="muted")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(self.empty_label)
        row = QHBoxLayout()
        for text, callback in (("+  Add files", self.add_files), ("Add folders", self.add_folder),
                               ("−  Remove files", self.remove_files),
                               ("Load playlist", self.load), ("Save playlist", self.save)):
            button = QPushButton(text)
            button.clicked.connect(callback)
            row.addWidget(button)
            if text == "Add folders":
                self.add_folder_button = button
                button.setToolTip("Select several folders, including their subfolders")
            if text.startswith("−"):
                self.remove_button = button
            if text.startswith("Save"):
                self.save_button = button
        box.addLayout(row)
        search_row = QHBoxLayout()
        prompt = QLabel(">")
        prompt.setStyleSheet("color:white; font-size:24px; font-weight:900;")
        self.search = QLineEdit(objectName="fzfSearch")
        self.search.setPlaceholderText("Search playlist by filename or folder (Esc clears)")
        self.search.setClearButtonEnabled(True)
        self.search.setStyleSheet("color:white; background:#211829; border:1px solid #79508e;"
                                  "border-radius:8px; padding:8px;")
        self.search_terms = []
        self.search.textChanged.connect(self.filter_playlist)
        self.search.returnPressed.connect(self.play_first_match)
        clear_search = QShortcut(QKeySequence(Qt.Key_Escape), self.search)
        clear_search.setContext(Qt.WidgetShortcut)
        clear_search.activated.connect(self.search.clear)
        search_row.addWidget(prompt)
        search_row.addWidget(self.search, 1)
        box.addLayout(search_row)
        layout.addWidget(playlist_panel, 1)
        layout.addLayout(controls)

    def filter_playlist(self, text):
        self.search_terms = text.casefold().split()
        for row in range(self.playlist.count()):
            self.filter_track(self.playlist.item(row))

    def filter_track(self, item):
        path = item.data(Qt.UserRole).casefold()
        item.setHidden(not all(term in path for term in self.search_terms))

    def play_first_match(self):
        for row in range(self.playlist.count()):
            item = self.playlist.item(row)
            if not item.isHidden():
                self.play_item(item)
                return

    def track_menu(self, pos):
        item = self.playlist.itemAt(pos)
        if item is not None:
            menu = QMenu(self.playlist)
            details = menu.addAction("Track information")
            if menu.exec(self.playlist.viewport().mapToGlobal(pos)) == details:
                self.show_track_metadata(item.data(Qt.UserRole))

    def animate_brand(self):
        self.hue = (self.hue + 3) % 360
        self.brand.setStyleSheet(f"color: hsl({self.hue}, 100%, 65%);")

    def save_display_mode(self, mode):
        self.preferences["display"] = mode
        self.settings_store.setValue("display", mode)

    def show_settings(self):
        dialog = SettingsDialog(self.preferences, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.apply_settings(dialog.values())

    def apply_settings(self, values, persist=True):
        old = self.preferences
        values = dict(values)
        values.setdefault("gl_backend", old.get("gl_backend", "auto"))
        if values["order"] == 4:
            values["order"] = 0
        self.preferences = values
        self.playback_output.configure(values)
        if old["playback"] != values["playback"]:
            self.shuffle_pool = []
            self.shuffle_pool_key = None
            self.play_history = []
            self.history_index = -1
        self.scope.display_mode = values["display"]
        self.scope.scope_points = values["scope_points"]
        self.analysis.set_spectrum_bands(values["spectrum_bands"])
        self.analysis.set_phrase_bars(values["laser_bars"])
        colors = THEMES[values["theme"]][1]
        style = STYLE
        for before, after in zip(("#381754", "#632b60", "#cf713e", "#f7ac81", "#f7ae89", "#f4ad88", "#9a5de0", "#ef9a65"),
                                 (*colors[:3], colors[3], colors[3], colors[3], colors[1], colors[2])):
            style = style.replace(before, after)
        for before, after in (("#24132c", QColor(colors[0]).darker(130).name()),
                              ("#25162e", QColor(colors[0]).darker(140).name()),
                              ("#7d436f", colors[1]), ("#38213e", colors[0]),
                              ("#8e5e91", colors[2])):
            style = style.replace(before, after)
        style += "QDialog { background: " + colors[0] + "; } QComboBox, QSpinBox { background: #201b29; color: white; padding: 6px; }"
        stops = GRADIENTS[values["gradient"]][1]
        if values["gradient"] == 8:
            stops = (values["custom_start"],values["custom_end"])
        if stops is not None or values["reverse"]:
            left, right = stops or (colors[0],colors[2])
            if values["reverse"]:
                left,right = right,left
            style += f"QWidget#canvas {{ background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {left},stop:1 {right}); }}"
        self.setStyleSheet(style)
        self.scope.accent = colors[3]
        self.scope.scope_background = QColor(colors[0]).darker(160).name()
        self.scope.update()
        self.sort_playlist(restore_manual=old["order"] != values["order"])
        if old["effect"] != values["effect"]:
            self.set_party_mode(False)
        if old["effect"] != values["effect"] and self.visualizer is not None:
            visible = self.visualizer.isVisible()
            fullscreen = self.visualizer.borderless.active
            geometry = self.visualizer.borderless.geometry if fullscreen else self.visualizer.geometry()
            self.dispose_visualizer()
            if visible:
                self.show_visualizer()
                self.visualizer.setGeometry(geometry)
                if fullscreen:
                    self.visualizer.borderless.set_active(True)
        if persist:
            self.settings_store.setValue("effectListVersion",2)
            for key, value in values.items():
                self.settings_store.setValue(key, value)
            self.settings_store.sync()
            if old.get("gl_backend", "auto") != values["gl_backend"]:
                self.statusBar().showMessage("OpenGL backend saved. Restart MusiK to use it.")

    def sort_playlist(self, restore_manual=False):
        order = self.preferences["order"]
        self.playlist.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove if order == 0
                                      else QAbstractItemView.DragDropMode.NoDragDrop)
        if not order and not restore_manual:
            return
        current = self.playlist.currentItem()
        selected = self.playlist.selectedItems()
        items = [self.playlist.item(i) for i in range(self.playlist.count())]
        keys = {
            0: lambda item: item.data(Qt.ItemDataRole.UserRole + 1),
            1: lambda item: (item.text().casefold(), item.data(Qt.ItemDataRole.UserRole).casefold()),
            2: lambda item: (item.text().casefold(), item.data(Qt.ItemDataRole.UserRole).casefold()),
            3: lambda item: item.data(Qt.ItemDataRole.UserRole).casefold(),
        }
        items.sort(key=keys[order], reverse=order == 2)
        self.playlist.blockSignals(True)
        try:
            while self.playlist.count():
                self.playlist.takeItem(0)
            for item in items:
                self.playlist.addItem(item)
                self.filter_track(item)
            if current is not None:
                self.playlist.setCurrentItem(current)
            self.playlist.clearSelection()
            for item in selected:
                item.setSelected(True)
        finally:
            self.playlist.blockSignals(False)

    def dispose_visualizer(self):
        visual = self.visualizer
        self.analysis.beat.disconnect(visual.on_beat)
        self.analysis.bands.disconnect(visual.on_bands)
        if isinstance(visual, EffectVisualizer):
            self.analysis.energy.disconnect(visual.on_energy)
            self.analysis.phrase.disconnect(visual.on_phrase)
        elif isinstance(visual, FogShSVisualizer):
            self.analysis.energy.disconnect(visual.on_energy)
            self.analysis.waveform.disconnect(visual.on_waveform)
        visual.removeEventFilter(self)
        visual.close()
        visual.deleteLater()
        self.visualizer = None
        self.scope.setVisible(True)
        self.scope.timer.start()

    def update_mute_button(self, muted):
        pixmap = QPixmap(108, 108)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.scale(3, 3)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(Qt.GlobalColor.white, 3, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawArc(QRectF(7, 5, 22, 25), 0, 180 * 16)
        painter.drawRoundedRect(QRectF(5, 18, 6, 12), 2, 2)
        painter.drawRoundedRect(QRectF(25, 18, 6, 12), 2, 2)
        if muted:
            painter.setPen(QPen(QColor("#ff354c"), 3))
            painter.drawLine(5, 31, 31, 5)
        painter.end()
        self.mute.setChecked(muted)
        self.mute.setIcon(QIcon(pixmap))
        action = "Unmute" if muted else "Mute"
        self.mute.setToolTip(action)
        self.mute.setAccessibleName(action)

    def transport_button(self, name, callback):
        button = QPushButton()
        button.setObjectName("transport")
        button.setIcon(self.transport_icons[name])
        button.setIconSize(QSize(26, 26))
        button.setFixedWidth(42)
        button.setToolTip(name)
        button.setAccessibleName(name)
        button.clicked.connect(callback)
        return button

    def add_paths(self, paths, report_missing=True):
        missing = []
        added = 0
        known = {os.path.normcase(self.playlist.item(i).data(Qt.UserRole)) for i in range(self.playlist.count())}
        for value in paths:
            path = Path(value).expanduser().resolve()
            if not path.is_file():
                missing.append(str(value))
                continue
            key = os.path.normcase(str(path))
            if key in known:
                continue
            known.add(key)
            item = QListWidgetItem(path.stem)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            item.setToolTip("")
            item.setData(Qt.ItemDataRole.UserRole + 1, self.import_counter)
            item.setData(Qt.ItemDataRole.UserRole + 2, random.random())
            self.import_counter += 1
            self.playlist.addItem(item)
            self.filter_track(item)
            added += 1
        self.sort_playlist()
        if self.playlist.currentRow() < 0 and self.playlist.count():
            self.playlist.setCurrentRow(0)
        self.update_controls()
        if missing and report_missing:
            QMessageBox.warning(self, "Files unavailable", "Could not find:\n" + "\n".join(missing[:10]))
        return added

    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Add music", "", AUDIO_FILE_FILTER)
        self.add_paths(paths)

    def add_folder(self):
        if self.folder_scanner is not None:
            self.folder_scanner.requestInterruption()
            self.add_folder_button.setEnabled(False)
            return
        folders = choose_folders(self)
        if not folders:
            return
        self.folder_added = 0
        self.folder_errors = 0
        self.folder_scanner = FolderScanner(folders, self)
        self.folder_scanner.files_found.connect(self.folder_files_found)
        self.folder_scanner.scan_error.connect(self.folder_scan_error)
        self.folder_scanner.finished.connect(self.folder_scan_finished)
        self.add_folder_button.setText("Cancel scan")
        self.statusBar().showMessage("Scanning music folder and subfolders…")
        self.folder_scanner.start()

    def folder_files_found(self, paths):
        if self.closing:
            return
        self.folder_added += self.add_paths(paths, report_missing=False)
        self.statusBar().showMessage(f"Scanning music folder… {self.folder_added} tracks added")

    def folder_scan_error(self, message):
        self.folder_errors += 1

    def folder_scan_finished(self):
        cancelled = self.folder_scanner.isInterruptionRequested()
        self.folder_scanner.deleteLater()
        self.folder_scanner = None
        self.add_folder_button.setText("Add folders")
        self.add_folder_button.setEnabled(True)
        result = "Scan cancelled" if cancelled else "Folder scan complete"
        detail = f" · {self.folder_errors} unreadable folders/files skipped" if self.folder_errors else ""
        self.statusBar().showMessage(f"{result} · {self.folder_added} tracks added{detail}")
        if self.closing:
            self.close()

    def remove_files(self):
        selected = self.playlist.selectedItems()
        if self.current_item in selected:
            self.stop()
            self.player.setSource(QUrl())
            self.current_item = None
            self.track_label.setText("Your next favourite sound")
        for item in selected:
            self.playlist.takeItem(self.playlist.row(item))
        self.update_controls()

    def load(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Load playlist", "", "Playlists (*.m3u8 *.m3u)")
        if not filename:
            return
        try:
            tracks, missing = load_playlist(filename)
        except (OSError, UnicodeError) as exc:
            QMessageBox.warning(self, "Cannot load playlist", str(exc))
            return
        self.stop()
        self.player.setSource(QUrl())
        self.current_item = None
        self.playlist.clear()
        self.track_label.setText("Your next favourite sound")
        self.add_paths(tracks)
        if missing:
            QMessageBox.warning(self, "Skipped playlist entries", "Missing files or unsupported network URLs:\n" + "\n".join(missing[:10]))

    def save(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save playlist", "MusiK.m3u8", "UTF-8 playlist (*.m3u8);;M3U playlist (*.m3u)")
        if filename:
            if Path(filename).suffix.lower() not in (".m3u8", ".m3u"):
                filename += ".m3u8"
            try:
                save_playlist(filename, [self.playlist.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.playlist.count())])
            except (OSError, ValueError) as exc:
                QMessageBox.warning(self, "Cannot save playlist", str(exc))

    def play_item(self, item):
        if item is None:
            return
        if item is not self.current_item:
            if self.current_item is not None:
                self.current_item.setFont(QFont())
                self.current_item.setData(Qt.UserRole + 3, False)
            self.player.stop()
            self.analysis.reset()
            self.current_item = item
            item.setData(Qt.UserRole + 3, True)
            font = QFont()
            font.setBold(True)
            item.setFont(font)
            self.player.setSource(QUrl.fromLocalFile(item.data(Qt.ItemDataRole.UserRole)))
            self.track_label.setText(item.text())
            self.track_label.setToolTip(item.data(Qt.ItemDataRole.UserRole))
        self.playlist.setCurrentItem(item)
        if self.preferences["playback"] in (2, 4) and not self.history_navigation:
            path = item.data(Qt.ItemDataRole.UserRole)
            if self.history_index < 0 or self.play_history[self.history_index] != path:
                self.play_history = self.play_history[:self.history_index + 1]
                self.play_history.append(path)
                self.history_index = len(self.play_history) - 1
        self.player.play()

    def play(self):
        selected = self.playlist.currentItem()
        self.play_item(selected if selected is not None else self.current_item)

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        elif self.player.playbackState() == QMediaPlayer.PlaybackState.PausedState:
            self.player.play()
        else:
            self.play()

    def stop(self):
        self.player.stop()
        self.player.setPosition(0)
        self.analysis.reset()
        if self.visualizer:
            self.visualizer.reset()

    def play_adjacent(self, direction):
        count = self.playlist.count()
        if not count:
            return
        mode = self.preferences["playback"]
        row = self.playlist.row(self.current_item) if self.current_item is not None else -1
        if mode in (2, 4):
            paths = tuple(self.playlist.item(i).data(Qt.UserRole) for i in range(count))
            if self.shuffle_pool_key != (mode, paths):
                self.shuffle_pool_key = (mode, paths)
                self.shuffle_pool = []
                # Preserve only history entries that still exist in the playlist.
                self.play_history = [path for path in self.play_history if path in paths]
                current_path = paths[row] if row >= 0 else None
                if current_path in self.play_history:
                    self.history_index = len(self.play_history) - 1 - self.play_history[::-1].index(current_path)
                else:
                    self.play_history = [current_path] if current_path else []
                    self.history_index = len(self.play_history) - 1
            target = None
            if direction < 0:
                if self.history_index > 0:
                    self.history_index -= 1
                    target = self.play_history[self.history_index]
                else:
                    return
            elif self.history_index + 1 < len(self.play_history):
                self.history_index += 1
                target = self.play_history[self.history_index]
            else:
                current_path = paths[row] if row >= 0 else None
                choices = [p for p in paths if p != current_path]
                if not choices:
                    target = paths[0]
                elif mode == 4:
                    target = random.choice(choices)
                else:
                    # A shuffled bag: play each track before starting a new cycle.
                    self.shuffle_pool = [p for p in self.shuffle_pool if p in choices]
                    if not self.shuffle_pool:
                        self.shuffle_pool = choices.copy()
                        random.shuffle(self.shuffle_pool)
                    target = self.shuffle_pool.pop()
                self.play_history = self.play_history[:self.history_index + 1]
                self.play_history.append(target)
                self.history_index = len(self.play_history) - 1
            self.history_navigation = True
            try:
                self.play_item(self.playlist.item(paths.index(target)))
            finally:
                self.history_navigation = False
            return
        if mode == 3:
            paths = tuple(self.playlist.item(i).data(Qt.UserRole) for i in range(count))
            if self.shuffle_key != (mode, paths):
                self.shuffle_key = (mode, paths)
                groups = {}
                for i, path in enumerate(paths):
                    groups.setdefault(str(Path(path).parent), []).append(i)
                blocks = list(groups.values())
                random.shuffle(blocks)
                self.shuffle_cycle = [i for block in blocks for i in block]
            position = self.shuffle_cycle.index(row) if row >= 0 else -1
            row = self.shuffle_cycle[(position + direction) % count]
        else:
            row = (row + direction * (-1 if mode == 1 else 1)) % count
        self.play_item(self.playlist.item(row))

    def next(self):
        self.play_adjacent(1)

    def previous(self):
        self.play_adjacent(-1)

    def media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.next()
        self.update_controls()

    def player_error(self, error, message):
        if error != QMediaPlayer.Error.NoError:
            self.statusBar().showMessage(f"Playback error: {message}")
            self.analysis.reset()

    def state_changed(self, state):
        self.analysis.active = state == QMediaPlayer.PlaybackState.PlayingState
        self.state_label.setText({QMediaPlayer.PlaybackState.PlayingState: "PLAYING",
                                  QMediaPlayer.PlaybackState.PausedState: "PAUSED",
                                  QMediaPlayer.PlaybackState.StoppedState: "STOPPED"}[state])
        if not self.analysis.active:
            self.analysis.reset()
            if self.visualizer:
                self.visualizer.reset()
        self.update_controls()

    def update_controls(self):
        count = self.playlist.count()
        self.count_label.setText(f"{count} track{'s' if count != 1 else ''}")
        self.empty_label.setVisible(count == 0)
        self.playlist.setVisible(count > 0)
        self.play_button.setEnabled(count > 0)
        self.previous_button.setEnabled(count > 0)
        self.next_button.setEnabled(count > 0)
        self.save_button.setEnabled(count > 0)
        self.remove_button.setEnabled(bool(self.playlist.selectedItems()))
        playing = self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        action = "Pause" if playing else "Play"
        self.play_button.setIcon(self.transport_icons[action])
        self.play_button.setToolTip(action)
        self.play_button.setAccessibleName(action)
        self.stop_button.setEnabled(self.player.playbackState() != QMediaPlayer.PlaybackState.StoppedState)
        self.seek.setEnabled(self.player.isSeekable())

    def position_changed(self, position):
        self.elapsed.setText(timestamp(position))
        if not self.seek.isSliderDown():
            self.seek.setValue(position)

    def duration_changed(self, duration):
        self.seek.setRange(0, duration)
        self.duration.setText(timestamp(duration))

    def seek_to(self):
        self.playback_output.flush()
        self.analysis.reset()
        if self.visualizer:
            self.visualizer.reset()
        self.player.setPosition(self.seek.value())

    def show_track_metadata(self, path):
        if self.metadata_dialog is not None:
            return
        self.playlist.metadata_open = True
        self.metadata_dialog = MetadataDialog(path, self)
        self.metadata_dialog.finished.connect(self.metadata_finished)
        self.metadata_dialog.open()

    def metadata_finished(self, result):
        self.metadata_dialog = None
        self.playlist.metadata_open = False
        self.playlist.cancel_hover()

    def set_party_mode(self, enabled):
        self.party_active = bool(enabled)
        self.party_button.blockSignals(True)
        self.party_button.setChecked(self.party_active)
        self.party_button.setText("Party Mode · On" if self.party_active else "Party Mode")
        self.party_button.blockSignals(False)
        if enabled:
            self.rainbow_timer.start()
            self.party_index = (self.visualizer_effect if self.visualizer is not None
                                else self.preferences["effect"])
            self.show_visualizer()
            if self.party_active:
                self.party_timer.start()
        else:
            self.rainbow_timer.stop()
            self.brand.setStyleSheet("")
            self.party_timer.stop()

    def advance_party(self):
        if not self.party_active:
            return
        if self.visualizer is None or not self.visualizer.isVisible():
            self.set_party_mode(False)
            return
        # Do not steal focus or replace a window while the user is in a dialog.
        if QApplication.activeModalWidget() is not None:
            return
        self.party_index = (self.party_index + 1) % len(EFFECTS)
        self.show_visualizer()

    def visualizer_failed(self, message):
        self.set_party_mode(False)
        self.statusBar().showMessage(message)

    def eventFilter(self, watched, event):
        if watched is self.visualizer:
            if event.type() == QEvent.Type.Show:
                self.scope.timer.stop()
                self.scope.setVisible(False)
            elif event.type() in (QEvent.Type.Hide, QEvent.Type.Close):
                self.scope.setVisible(True)
                self.scope.timer.start()
        if watched is self.visualizer and event.type() == QEvent.Type.Close:
            self.set_party_mode(False)
        return super().eventFilter(watched, event)

    def show_visualizer(self):
        effect = self.party_index if self.party_active else self.preferences["effect"]
        fullscreen = False
        geometry = None
        if self.visualizer is not None and self.visualizer_effect != effect:
            fullscreen = self.visualizer.borderless.active
            geometry = self.visualizer.borderless.geometry if fullscreen else self.visualizer.geometry()
            self.dispose_visualizer()
        if self.visualizer is None:
            self.visualizer = (CirclerVisualizer(self) if effect == EFFECTS.index("Circler Tetra")
                               else FogShSVisualizer(self) if effect == EFFECTS.index("fog_shS")
                               else Visualizer(self) if effect == 0
                               else EffectVisualizer(effect, self))
            self.visualizer_effect = effect
            self.visualizer.installEventFilter(self)
            if isinstance(self.visualizer, EffectVisualizer):
                self.analysis.energy.connect(self.visualizer.on_energy)
                self.analysis.phrase.connect(self.visualizer.on_phrase)
            elif isinstance(self.visualizer, FogShSVisualizer):
                self.analysis.energy.connect(self.visualizer.on_energy)
                self.analysis.waveform.connect(self.visualizer.on_waveform)
            self.analysis.beat.connect(self.visualizer.on_beat)
            self.analysis.bands.connect(self.visualizer.on_bands)
            self.visualizer.failed.connect(self.visualizer_failed)
            if geometry is not None:
                self.visualizer.setGeometry(geometry)
        self.visualizer.show()
        if fullscreen:
            self.visualizer.borderless.set_active(True)
        self.visualizer.raise_()
        self.visualizer.activateWindow()
        if not self.visualizer.error:
            prefix = "Party Mode · " if self.party_active else "Visualization · "
            self.statusBar().showMessage(prefix + EFFECTS[effect] + " · F11: fullscreen · Esc: back / close")

    def closeEvent(self, event):
        self.player.stop()

        if self.visualizer:
            self.visualizer.close()

        if self.folder_scanner is not None:
            self.closing = True
            self.folder_scanner.requestInterruption()
            self.hide()
            event.ignore()
            return

        try:
            self.autosave_playlist()
        except (OSError, ValueError) as exc:
            QMessageBox.warning(
                self,
                "Playlist autosave failed",
                str(exc)
            )

        self.playback_output.close()
        super().closeEvent(event)

        self.set_party_mode(False)
        self.playlist.cancel_hover()
        if self.metadata_dialog is not None:
            self.metadata_dialog.reject()
        self.player.stop()
        if self.visualizer:
            self.visualizer.close()
        if self.folder_scanner is not None:
            self.closing = True
            self.folder_scanner.requestInterruption()
            self.hide()
            event.ignore()
            return




def main():
    apply_backend(str(default_store().value("gl_backend", "auto")))
    fmt = QSurfaceFormat()
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setSwapInterval(1)
    QSurfaceFormat.setDefaultFormat(fmt)
    BASE_DIR = Path(__file__).resolve().parent

    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "Prometheus.MusiK.Player.1"
        )

    app = QApplication(sys.argv)

    icon = QIcon()

    for size in (16, 24, 32, 48, 64):
        icon.addFile(
            str(BASE_DIR.parent / f"MusiK-{size}.ico"),
            QSize(size, size)
        )

    icon.addFile(str(BASE_DIR.parent / "MusiK-logo.png"), QSize(256, 256))

    app.setWindowIcon(icon)

    app.setApplicationName("MusiK")
    app.setApplicationDisplayName("μSIK")
    app.setOrganizationName("MusiK")
    window = MainWindow()
    window.autoload_playlist()
    window.add_paths(sys.argv[1:])
    app.aboutToQuit.connect(window.autosave_playlist)
    window.show()
    # Save playlist

    sys.exit(app.exec())
