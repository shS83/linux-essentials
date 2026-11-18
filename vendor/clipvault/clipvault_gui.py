"""ClipVault – polished PySide6 clipboard manager.

Uses the existing project modules:
    security.py: is_secret(text) -> bool
    syntax.py: detect_syntax(text), sanitize_terminal(text)
    database.py: save_clipboard(text) -> int, get_history(limit) -> rows
    database_actions.py: delete_clipboard(entry_id) -> bool

Requires: PySide6, pygments, psycopg[binary]
Place clipvault.png next to this script.
"""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QRectF, QSize, QPointF, QTimer
from PySide6.QtGui import (
    QAction, QColor, QFont, QIcon, QLinearGradient, QPainter,
    QPainterPath, QPen, QPixmap, QRadialGradient, QShortcut, QKeySequence, QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication, QAbstractItemView, QComboBox, QDialog,
    QDialogButtonBox, QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QMainWindow,
    QMenu, QMessageBox, QPlainTextEdit, QPushButton, QSplitter,
    QStyledItemDelegate, QStyle, QSystemTrayIcon, QTextEdit,
    QVBoxLayout, QWidget,
)
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

from database import get_history, save_clipboard
from database_actions import delete_clipboard
from security import is_secret
from syntax import detect_syntax, sanitize_terminal


BASE = Path(__file__).resolve().parent
LOGO_PATH = BASE / "clipvault.png"
MAX_CONTENT_LENGTH = 100_000
MAX_VISIBLE_ENTRIES = 300
THEME = "material"

PURPLE = QColor("#c86aff")
GOLD = QColor("#f2bc62")
TEXT = QColor("#f3eefa")
MUTED = QColor("#9f96b6")


@dataclass
class ClipEntry:
    id: int
    content: str
    created_at: datetime | None

    @property
    def timestamp(self) -> str:
        return self.created_at.astimezone().strftime("%H:%M") if self.created_at else "--:--"

    @property
    def detail_time(self) -> str:
        return self.created_at.astimezone().strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "Unknown time"

    @property
    def summary(self) -> str:
        clean = sanitize_terminal(self.content.strip())
        return next(iter(clean.splitlines()), "(empty)").replace("\t", "    ")


def digest_for(text: str) -> bytes:
    return hashlib.sha256(text.encode("utf-8")).digest()


def fuzzy_score(needle: str, haystack: str) -> int | None:
    """fzf-like subsequence search, preferring contiguous/early matches.

    Every whitespace-separated search token must match, but its letters
    need not be adjacent. This is intentionally small and predictable,
    rather than a complete implementation of fzf's ranking algorithm.
    """
    if not needle.strip():
        return 0
    haystack = haystack.casefold()
    total = 0
    for token in needle.casefold().split():
        pos = -1
        prev = -2
        score = 0
        for char in token:
            pos = haystack.find(char, pos + 1)
            if pos < 0:
                return None
            score += 3
            if pos == prev + 1:
                score += 9
            if pos == 0 or not haystack[pos - 1].isalnum():
                score += 7
            prev = pos
        total += score - min(pos, 200) // 4
    return total


def make_tray_icon() -> QIcon:
    """Simple clipboard glyph, recognizable even at 22x22 pixels."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(GOLD, 4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    p.setBrush(QColor("#181120"))
    p.drawRoundedRect(QRectF(11, 12, 42, 46), 8, 8)
    p.setBrush(QColor("#321349"))
    p.setPen(QPen(PURPLE, 3))
    p.drawRoundedRect(QRectF(23, 7, 18, 12), 4, 4)
    p.setPen(QPen(QColor("#e1b5ff"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for y in (31, 39, 47):
        p.drawLine(21, y, 43, y)
    p.end()
    return QIcon(pixmap)


class LogoHeader(QFrame):
    """Full-width, custom-painted recessed dark header; panes start below."""

    def __init__(self, logo_path: Path, parent=None):
        super().__init__(parent)
        self.setFixedHeight(217)
        self.setMinimumWidth(0)
        self.logo = QPixmap(str(logo_path))
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 14)
        layout.addWidget(self.label)
        if self.logo.isNull():
            self.label.setText("ClipVault")
            self.label.setStyleSheet('color: #f5bf6b; font: italic bold 48px "Georgia";')
            self.label.setToolTip(f"Logo not found: {logo_path}")
        else:
            self.label.setToolTip("ClipVault")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.logo.isNull():
            self.label.setPixmap(self.logo.scaled(
                max(1, self.width() - 30), 205,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            ))

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = self.rect()
        bg = QLinearGradient(0, 0, 0, r.height())
        bg.setColorAt(0, QColor("#09090d"))
        bg.setColorAt(0.52, QColor("#1e1420"))
        bg.setColorAt(1, QColor("#0a090e"))
        p.fillRect(r, bg)
        glow = QRadialGradient(QPointF(r.center().x(), r.center().y() + 35), max(200, r.width() * .43))
        glow.setColorAt(0, QColor(135, 61, 150, 65))
        glow.setColorAt(.6, QColor(67, 22, 89, 24))
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(r, glow)
        y = r.height() - 11
        for offset, alpha in ((-2, 35), (0, 170), (2, 35)):
            p.setPen(QPen(QColor(236, 162, 67, alpha), 1 + (offset == 0)))
            p.drawLine(22, y + offset, r.width() - 22, y + offset)
        # Two decorative golden rails do not overlap the main wordmark.
        for side in (0, 1):
            mid = r.width() * (.18 if side == 0 else .82)
            outer = 12 if side == 0 else r.width() - 12
            p.setPen(QPen(QColor(220, 155, 57, 100), 2))
            p.drawLine(int(outer), 124, int(mid), 124)
            p.setPen(QPen(QColor(173, 77, 226, 80), 1))
            p.drawLine(int(outer), 131, int(mid), 131)
        p.end()


class GlyphButton(QPushButton):
    """Compact bevelled buttons with vector icons and violet hover glow."""

    def __init__(self, glyph: str, tooltip: str, parent=None):
        super().__init__(parent)
        self.glyph = glyph
        self.setFixedSize(39, 36)
        self.setToolTip(tooltip)
        self.setAccessibleName(tooltip)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCheckable(glyph == "pause")

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(1.5, 1.5, self.width()-3, self.height()-3)
        hot = self.underMouse() or self.hasFocus() or self.isChecked()
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor("#49305f") if hot else QColor("#292336"))
        gradient.setColorAt(1, QColor("#21102e") if hot else QColor("#12121e"))
        p.setBrush(gradient)
        p.setPen(QPen(QColor("#bc73f0") if hot else QColor("#5c4a73"), 1.4))
        p.drawRoundedRect(rect, 8, 8)
        if hot:
            p.setPen(QPen(QColor(228, 155, 255, 65), 3))
            p.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 6, 6)
        p.translate(self.width()/2, self.height()/2)
        pen_color = QColor("#ff757e") if self.glyph == "trash" else (QColor("#f8d68a") if hot else QColor("#e7c8ff"))
        p.setPen(QPen(pen_color, 2.3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        g = self.glyph
        if g == "plus":
            p.drawLine(-8, 0, 8, 0); p.drawLine(0, -8, 0, 8)
        elif g == "copy":
            p.drawRoundedRect(QRectF(-10, -6, 14, 16), 2, 2)
            p.drawRoundedRect(QRectF(-4, -11, 14, 16), 2, 2)
        elif g == "trash":
            p.drawLine(-9, -8, 9, -8); p.drawLine(-4, -11, 4, -11)
            p.drawRoundedRect(QRectF(-7, -6, 14, 17), 1, 1)
            p.drawLine(-2, -2, -2, 6); p.drawLine(2, -2, 2, 6)
        elif g == "refresh":
            p.drawArc(QRectF(-10, -10, 20, 20), 30*16, 285*16)
            p.drawLine(8, -9, 10, -1); p.drawLine(10, -1, 3, -3)
        elif g == "pause":
            if self.isChecked():
                path = QPainterPath()
                path.moveTo(-4, -9); path.lineTo(9, 0); path.lineTo(-4, 9); path.closeSubpath()
                p.setBrush(pen_color); p.drawPath(path)
            else:
                p.drawLine(-4, -8, -4, 8); p.drawLine(4, -8, 4, 8)
        elif g == "search":
            p.drawEllipse(QRectF(-9, -9, 13, 13)); p.drawLine(3, 3, 10, 10)
        p.end()


class HistoryDelegate(QStyledItemDelegate):
    """Draws the purple-selected history rows seen in the design mockup."""

    def sizeHint(self, option, index):
        return QSize(200, 67)

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(option.rect.adjusted(4, 3, -4, -3))
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        grad = QLinearGradient(r.topLeft(), r.bottomRight())
        if selected:
            grad.setColorAt(0, QColor("#4a1c66"))
            grad.setColorAt(.45, QColor("#251536"))
            grad.setColorAt(1, QColor("#342047"))
        else:
            grad.setColorAt(0, QColor("#20202d"))
            grad.setColorAt(1, QColor("#11121c"))
        painter.setPen(QPen(QColor("#c274ff") if selected else QColor("#373246"), 1.6 if selected else 1))
        painter.setBrush(grad)
        painter.drawRoundedRect(r, 11, 11)
        if selected:
            painter.setPen(QPen(QColor(213, 125, 255, 65), 3))
            painter.drawRoundedRect(r.adjusted(2.5, 2.5, -2.5, -2.5), 9, 9)
        left = r.left() + 15
        painter.setPen(QColor("#edc5ff") if selected else QColor("#9f88ca"))
        icon_font = QFont("DejaVu Sans Mono", 13, QFont.Weight.Bold)
        painter.setFont(icon_font)
        painter.drawText(QRectF(left, r.top()+9, 38, 31), Qt.AlignmentFlag.AlignVCenter, "</>")
        painter.setPen(TEXT)
        main_font = QFont("DejaVu Sans", 10)
        main_font.setWeight(QFont.Weight.DemiBold if selected else QFont.Weight.Normal)
        painter.setFont(main_font)
        fm = painter.fontMetrics()
        summary = str(index.data(Qt.ItemDataRole.UserRole + 1) or "")
        summary = fm.elidedText(summary, Qt.TextElideMode.ElideRight, max(20, int(r.width()-157)))
        painter.drawText(QRectF(left+45, r.top()+9, max(20, r.width()-165), 22), Qt.AlignmentFlag.AlignVCenter, summary)
        painter.setFont(QFont("DejaVu Sans", 9))
        painter.setPen(MUTED)
        painter.drawText(QRectF(left+46, r.top()+34, r.width()-160, 20), Qt.AlignmentFlag.AlignVCenter,
                         str(index.data(Qt.ItemDataRole.UserRole + 2) or ""))
        painter.setPen(QColor("#d2b0e4"))
        painter.drawText(QRectF(r.right()-77, r.top()+8, 65, 22), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                         str(index.data(Qt.ItemDataRole.UserRole + 3) or ""))
        painter.restore()


class TextEntryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add clipboard entry")
        self.setMinimumSize(540, 350)
        self.setStyleSheet(DIALOG_STYLESHEET)
        root = QVBoxLayout(self)
        title = QLabel("Add a text entry")
        title.setObjectName("dialogTitle")
        root.addWidget(title)
        help_text = QLabel("Entries are checked for possible secrets before being saved.")
        help_text.setObjectName("mutedText")
        root.addWidget(help_text)
        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("Paste or type text here...")
        root.addWidget(self.editor, 1)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)


ROOT_STYLESHEET = """
QMainWindow { background: #090910; color: #f4edf7; }
QWidget#canvas { background: qlineargradient(x1:0,y1:0,x2:0.92,y2:1,
    stop:0 #0a090f, stop:0.37 #191324, stop:0.78 #0d0d16, stop:1 #180c23); }
QFrame#panel { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
    stop:0 #1d1725, stop:0.25 #11121d, stop:1 #0b0c15);
    border: 1px solid #b27b44; border-radius: 14px; }
QFrame#panelHeader { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
    stop:0 #282033, stop:1 #17121e); border: none;
    border-bottom: 1px solid #4c3657; border-top-left-radius: 13px;
    border-top-right-radius: 13px; }
QLabel#panelTitle { color: #fbf4ff; font: 600 17px "DejaVu Sans"; }
QLabel#countPill { background: #3c1a58; color: #e6b7ff;
    border: 1px solid #a65ce8; border-radius: 11px;
    padding: 3px 10px; font-weight: bold; }
QLabel#mutedText { color: #b6a4c6; }
QLabel#metaTag { background: #222031; border: 1px solid #514262;
    border-radius: 7px; padding: 6px 11px; color: #e1d5ec; }
QLabel#statusTag { color: #d4c4e2; }
QFrame#footer { background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
    stop:0 #282033, stop:1 #13111b); border: 1px solid #5e4171; border-radius: 11px; }
QLineEdit#search { background: #151320; color: #f4ebfb;
    border: 1px solid #675078; border-radius: 10px; padding: 10px 12px;
    selection-background-color: #8e42cf; font-size: 13px; }
QLineEdit#search:focus { border: 1px solid #ca7cff; background: #1c122b; }
QListWidget#history { background: transparent; border: none; outline: none; color: #f1eaf8; }
QTextEdit#preview { background: #0f101a; color: #e9e6f2; border: 1px solid #4d405c;
    border-radius: 11px; padding: 8px; selection-background-color: #613582;
    selection-color: #ffffff; }
QComboBox { background: #231b2d; color: #f0e6f6; border: 1px solid #765191;
    border-radius: 8px; padding: 7px 10px; min-height: 18px; }
QComboBox:hover, QComboBox:focus { border-color: #c17bfc; }
QComboBox QAbstractItemView { background: #191423; color: #f3ecfa;
    selection-background-color: #693b99; border: 1px solid #785395; }
QScrollBar:vertical { background: #151321; width: 9px; border-radius: 4px; }
QScrollBar::handle:vertical { background: #675079; border-radius: 4px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #ad63e7; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QSplitter::handle:horizontal { background: transparent; width: 9px; }
QStatusBar { color: #baa8c9; background: transparent; border: none; }
QStatusBar::item { border: none; }
"""

DIALOG_STYLESHEET = """
QDialog { background: #15101d; color: #f5effa; }
QLabel#dialogTitle { color: #edc6ff; font-size: 19px; font-weight: 600; }
QLabel#mutedText { color: #c2abc9; }
QPlainTextEdit { background: #0d0e18; color: #f2eaf8; border: 1px solid #75568b;
    border-radius: 8px; padding: 10px; font-family: monospace; }
QPushButton { background: #38204b; color: #f4e6ff; border: 1px solid #a569d6;
    border-radius: 6px; padding: 7px 17px; }
QPushButton:hover { background: #56316c; }
"""


class ClipvaultWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ClipVault — Clipboard History")
        self.setMinimumSize(990, 650)
        self.resize(1320, 855)
        self.setWindowIcon(make_tray_icon())
        self.last_digest: bytes | None = None
        self.paused = False
        self.database_ok = False
        self.all_entries: list[ClipEntry] = []
        self.clipboard = QApplication.clipboard()
        self.tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        self._create_widgets()
        self._setup_shortcuts()
        if self.tray_available:
            self._setup_tray()
        self.load_history()
        # Do not capture the existing clipboard when the application starts.
        self.clipboard.dataChanged.connect(self.on_clipboard_changed)

    def _create_widgets(self):
        canvas = QWidget(self)
        canvas.setObjectName("canvas")
        root = QVBoxLayout(canvas)
        root.setContentsMargins(8, 0, 8, 0)
        root.setSpacing(8)
        root.addWidget(LogoHeader(LOGO_PATH))

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setHandleWidth(9)
        self.history_panel = self._make_panel()
        self.preview_panel = self._make_panel()
        self.splitter.addWidget(self.history_panel)
        self.splitter.addWidget(self.preview_panel)
        self.splitter.setSizes([555, 750])
        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 6)
        root.addWidget(self.splitter, 1)
        self._build_history_panel()
        self._build_preview_panel()
        self._build_footer(root)
        self._notice_timer = QTimer(self)
        self._notice_timer.setSingleShot(True)
        self._notice_timer.timeout.connect(self._clear_status)
        self.setCentralWidget(canvas)
        self.setStyleSheet(ROOT_STYLESHEET)
        # The custom footer provides status feedback; do not create a QStatusBar.

    def _make_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setMinimumWidth(340)
        glow = QGraphicsDropShadowEffect(panel)
        glow.setBlurRadius(22)
        glow.setOffset(0, 2)
        glow.setColor(QColor(137, 52, 174, 60))
        panel.setGraphicsEffect(glow)
        return panel

    def _build_history_panel(self):
        layout = QVBoxLayout(self.history_panel)
        layout.setContentsMargins(1, 1, 1, 7)
        layout.setSpacing(8)
        bar = QFrame()
        bar.setObjectName("panelHeader")
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(13, 10, 10, 10)
        bar_layout.setSpacing(6)
        bar_layout.addWidget(self._heading("▤  History"))
        self.count_label = QLabel("0")
        self.count_label.setObjectName("countPill")
        bar_layout.addWidget(self.count_label)
        bar_layout.addStretch(1)
        self.add_button = self._button("plus", "Add entry  (Ctrl+N)", self.add_manual_entry)
        self.copy_button = self._button("copy", "Copy selected entry  (Ctrl+Shift+C)", self.copy_selected)
        self.trash_button = self._button("trash", "Delete selected entry  (Delete)", self.delete_selected)
        self.refresh_button = self._button("refresh", "Refresh history  (F5)", self.load_history)
        for b in (self.add_button, self.copy_button, self.trash_button, self.refresh_button):
            bar_layout.addWidget(b)
        layout.addWidget(bar)

        search_box = QHBoxLayout()
        search_box.setContentsMargins(12, 0, 12, 0)
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("⌕  Fuzzy search history...  (Ctrl+F)")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.apply_filter)
        search_box.addWidget(self.search)
        self.pause_button = self._button("pause", "Pause/resume monitoring", self._pause_from_button)
        search_box.addWidget(self.pause_button)
        layout.addLayout(search_box)

        self.entries = QListWidget()
        self.entries.setObjectName("history")
        self.entries.setItemDelegate(HistoryDelegate(self.entries))
        self.entries.setSpacing(1)
        self.entries.setFrameShape(QFrame.Shape.NoFrame)
        self.entries.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.entries.currentItemChanged.connect(self.show_entry)
        self.entries.itemDoubleClicked.connect(lambda _item: self.copy_selected())
        layout.addWidget(self.entries, 1)

    def _build_preview_panel(self):
        layout = QVBoxLayout(self.preview_panel)
        layout.setContentsMargins(1, 1, 1, 10)
        layout.setSpacing(9)
        bar = QFrame()
        bar.setObjectName("panelHeader")
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(13, 10, 10, 10)
        bar_layout.setSpacing(8)
        bar_layout.addWidget(self._heading("◉  Preview"))
        bar_layout.addStretch()
        self.language = QComboBox()
        self.language.setToolTip("Syntax highlighting language")
        for title, alias in (
            ("Auto", "auto"), ("Python", "python"), ("Bash", "bash"),
            ("C++", "cpp"), ("Rust", "rust"), ("JSON", "json"), ("Plain text", "text"),
        ):
            self.language.addItem(title, alias)
        self.language.setMinimumWidth(110)
        self.language.currentIndexChanged.connect(self.update_preview)
        bar_layout.addWidget(self.language)
        self.preview_copy = self._button("copy", "Copy preview to clipboard", self.copy_selected)
        bar_layout.addWidget(self.preview_copy)
        layout.addWidget(bar)

        self.preview = QTextEdit()
        self.preview.setObjectName("preview")
        self.preview.setReadOnly(True)
        self.preview.setFont(QFont("DejaVu Sans Mono", 11))
        self.preview.setPlaceholderText("Select a clipboard entry to preview it.")
        layout.addWidget(self.preview, 1)

        bottom = QHBoxLayout()
        bottom.setContentsMargins(11, 0, 11, 0)
        self.language_tag = self._meta_label("Plain text")
        self.size_tag = self._meta_label("0 B")
        self.time_tag = self._meta_label("—")
        bottom.addWidget(self.language_tag)
        bottom.addWidget(self.size_tag)
        bottom.addWidget(self.time_tag)
        bottom.addStretch(1)
        layout.addLayout(bottom)

    def _build_footer(self, root):
        footer = QFrame()
        footer.setObjectName("footer")
        footer.setFixedHeight(50)
        row = QHBoxLayout(footer)
        row.setContentsMargins(17, 0, 17, 0)
        row.setSpacing(15)
        self.monitor_label = QLabel("●  Monitoring: Active")
        self.monitor_label.setObjectName("statusTag")
        row.addWidget(self.monitor_label)
        row.addWidget(self._divider())
        self.database_label = QLabel("PostgreSQL: Connecting")
        self.database_label.setObjectName("statusTag")
        row.addWidget(self.database_label)
        row.addWidget(self._divider())
        self.secret_label = QLabel("◆  Secret filter: On")
        self.secret_label.setObjectName("statusTag")
        row.addWidget(self.secret_label)
        # Temporary notices take the place of the secret-filter label,
        # so they don't require an extra, mostly empty status-bar row.
        self.notice_label = QLabel()
        self.notice_label.setObjectName("statusTag")
        self.notice_label.setStyleSheet("color: #e9bdff;")
        self.notice_label.hide()
        row.addWidget(self.notice_label)
        row.addStretch()
        self.total_label = QLabel("0 entries")
        self.total_label.setObjectName("statusTag")
        row.addWidget(self.total_label)
        root.addWidget(footer)

    def _show_status(self, message: str, duration_ms: int = 3000):
        """Show temporary feedback inside the existing decorated footer."""
        self._notice_timer.stop()
        # Use elision to avoid pushing the entry counter out of the footer.
        max_width = max(130, min(360, self.width() // 3))
        preview = self.notice_label.fontMetrics().elidedText(
            message, Qt.TextElideMode.ElideRight, max_width
        )
        self.notice_label.setText(preview)
        self.notice_label.setToolTip(message)
        self.secret_label.hide()
        self.notice_label.show()
        if duration_ms > 0:
            self._notice_timer.start(duration_ms)

    def _clear_status(self):
        self.notice_label.hide()
        self.secret_label.show()

    @staticmethod
    def _divider():
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color:#624973; border-left: 1px solid #624973;")
        sep.setFixedHeight(21)
        return sep

    @staticmethod
    def _heading(label: str) -> QLabel:
        result = QLabel(label)
        result.setObjectName("panelTitle")
        return result

    @staticmethod
    def _meta_label(text: str) -> QLabel:
        result = QLabel(text)
        result.setObjectName("metaTag")
        return result

    @staticmethod
    def _button(glyph: str, tip: str, callback) -> GlyphButton:
        b = GlyphButton(glyph, tip)
        b.clicked.connect(callback)
        return b

    def _setup_shortcuts(self):
        for key, callback in (
            ("Ctrl+F", self.focus_search),
            ("Ctrl+N", self.add_manual_entry),
            ("Ctrl+Shift+C", self.copy_selected),
            ("F5", self.load_history),
        ):
            sc = QShortcut(QKeySequence(key), self)
            sc.setContext(Qt.ShortcutContext.WindowShortcut)
            sc.activated.connect(callback)
        # Delete is local to the history list. It must NOT intercept Backspace
        # or Delete while the user edits the fuzzy-search field.
        delete_sc = QShortcut(QKeySequence("Delete"), self.entries)
        delete_sc.setContext(Qt.ShortcutContext.WidgetShortcut)
        delete_sc.activated.connect(self.delete_selected)

    def _setup_tray(self):
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip("ClipVault — Clipboard History")
        menu = QMenu(self)
        menu.setStyleSheet("QMenu {background:#181221;color:#f0e8f8;border:1px solid #855aa7;}"
                           "QMenu::item:selected {background:#51316e;}")
        open_action = QAction("Open ClipVault", self)
        open_action.triggered.connect(self.restore_window)
        menu.addAction(open_action)
        self.pause_action = QAction("Pause monitoring", self)
        self.pause_action.setCheckable(True)
        self.pause_action.toggled.connect(self.set_paused)
        menu.addAction(self.pause_action)
        menu.addSeparator()
        quit_action = QAction("Quit ClipVault", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    def focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def _selected_id(self) -> int | None:
        item = self.entries.currentItem()
        return int(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

    def _selected_entry(self) -> ClipEntry | None:
        selected = self._selected_id()
        return next((entry for entry in self.all_entries if entry.id == selected), None)

    def load_history(self):
        selected_id = self._selected_id()
        try:
            rows = get_history(MAX_VISIBLE_ENTRIES)
            self.all_entries = [
                ClipEntry(int(entry_id), str(content), created_at if isinstance(created_at, datetime) else None)
                for entry_id, content, created_at in rows
            ]
        except Exception as exc:
            self.database_ok = False
            self._update_footer()
            self._show_status(f"History load failed: {type(exc).__name__}", 6000)
            return
        self.database_ok = True
        self._update_footer()
        self.apply_filter(self.search.text(), selected_id)
        self._show_status(f"History updated — {len(self.all_entries)} entries", 2500)

    def apply_filter(self, query: str, preferred_id: int | None = None):
        if preferred_id is None:
            preferred_id = self._selected_id()
        matches = []
        for entry in self.all_entries:
            score = fuzzy_score(query, entry.content[:20_000])
            if score is not None:
                matches.append((score, entry))
        if query.strip():
            matches.sort(key=lambda pair: (pair[0], pair[1].id), reverse=True)
        self.entries.blockSignals(True)
        self.entries.clear()
        row_to_select = -1
        for index, (_score, entry) in enumerate(matches):
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, entry.id)
            item.setData(Qt.ItemDataRole.UserRole + 1, entry.summary)
            item.setData(Qt.ItemDataRole.UserRole + 2, f"Entry #{entry.id}  ·  {len(entry.content)} characters")
            item.setData(Qt.ItemDataRole.UserRole + 3, entry.timestamp)
            item.setSizeHint(QSize(250, 67))
            self.entries.addItem(item)
            if entry.id == preferred_id:
                row_to_select = index
        self.entries.blockSignals(False)
        if matches:
            self.entries.setCurrentRow(row_to_select if row_to_select >= 0 else 0)
        else:
            self.preview.clear()
            self.language_tag.setText("Plain text")
            self.size_tag.setText("0 B")
            self.time_tag.setText("—")
        self.count_label.setText(str(len(matches)))
        self.total_label.setText(f"{len(self.all_entries)} entries")

    def show_entry(self, _current, _previous):
        self.update_preview()

    def update_preview(self, _index=None):
        entry = self._selected_entry()
        if entry is None:
            self.preview.clear()
            return
        safe = sanitize_terminal(entry.content)
        selected_alias = self.language.currentData()
        try:
            lexer = detect_syntax(safe) if selected_alias == "auto" else get_lexer_by_name(selected_alias)
        except ClassNotFound:
            lexer = get_lexer_by_name("text")
        colored = highlight(
            safe,
            lexer,
            HtmlFormatter(style=THEME, noclasses=True, nowrap=True),
        )
        # Pygments escapes the clipboard text in the resulting HTML.
        self.preview.setHtml(
            '<html><body style="background-color:#0f101a;color:#ece8f4;">'
            '<pre style="font-family:monospace;font-size:11pt;white-space:pre-wrap;">'
            + colored + '</pre></body></html>'
        )
        self.preview.moveCursor(QTextCursor.MoveOperation.Start)
        self.language_tag.setText(lexer.name)
        byte_size = len(entry.content.encode("utf-8"))
        self.size_tag.setText(f"{byte_size:,} B")
        self.time_tag.setText(entry.detail_time)

    def _save_new_content(self, content: str) -> bool:
        if not content.strip():
            return False
        if len(content) > MAX_CONTENT_LENGTH:
            self._show_status("Entry too large — not saved", 5000)
            return False
        if is_secret(content):
            self._show_status("Possible secret detected — not saved", 6000)
            return False
        try:
            entry_id = save_clipboard(content)
        except Exception as exc:
            self.database_ok = False
            self._update_footer()
            self._show_status(f"PostgreSQL write failed: {type(exc).__name__}", 6000)
            return False
        self.database_ok = True
        self.all_entries.insert(0, ClipEntry(int(entry_id), content, datetime.now().astimezone()))
        self.all_entries = self.all_entries[:MAX_VISIBLE_ENTRIES]
        self._update_footer()
        self.apply_filter(self.search.text(), entry_id)
        self._show_status(f"Saved entry #{entry_id}", 3000)
        return True

    def on_clipboard_changed(self):
        if self.paused:
            return
        mime_data = self.clipboard.mimeData()
        if mime_data is None or not mime_data.hasText():
            return
        content = self.clipboard.text()
        new_digest = digest_for(content)
        if new_digest == self.last_digest:
            return
        # This hash is kept only in memory and prevents duplicate captures.
        if self._save_new_content(content):
            self.last_digest = new_digest
        elif is_secret(content):
            # Do not repeatedly process a secret for repeated notifications.
            self.last_digest = new_digest

    def add_manual_entry(self):
        dialog = TextEntryDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._save_new_content(dialog.editor.toPlainText())

    def copy_selected(self):
        entry = self._selected_entry()
        if entry is None:
            self._show_status("Choose an entry to copy", 3000)
            return
        self.last_digest = digest_for(entry.content)
        self.clipboard.setText(entry.content)
        self._show_status(f"Entry #{entry.id} copied to clipboard", 3000)

    def delete_selected(self):
        entry = self._selected_entry()
        if entry is None:
            self._show_status("Choose an entry to delete", 3000)
            return
        # Confirmation is required for both the trash button and Delete key.
        dialog = QMessageBox(self)
        dialog.setWindowTitle("Confirm deletion")
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setText(f"Are you sure you want to delete entry #{entry.id}?")
        dialog.setInformativeText(
            "This entry will be permanently removed from PostgreSQL. "
            "This action cannot be undone."
        )
        delete_button = dialog.addButton(
            "Delete", QMessageBox.ButtonRole.DestructiveRole
        )
        cancel_button = dialog.addButton(
            "Cancel", QMessageBox.ButtonRole.RejectRole
        )
        dialog.setDefaultButton(cancel_button)
        dialog.setEscapeButton(cancel_button)
        dialog.setStyleSheet("""
            QMessageBox { background: #15101d; color: #f5effa; }
            QLabel { color: #f5effa; font-size: 13px; }
            QPushButton { background: #38204b; color: #f4e6ff;
                border: 1px solid #a569d6; border-radius: 7px;
                padding: 8px 19px; min-width: 85px; }
            QPushButton:hover { background: #56316c; border-color: #d795ff; }
        """)
        dialog.exec()
        if dialog.clickedButton() is not delete_button:
            return
        try:
            deleted = delete_clipboard(entry.id)
        except Exception as exc:
            self.database_ok = False
            self._update_footer()
            self._show_status(f"Deletion failed: {type(exc).__name__}", 6000)
            return
        if deleted:
            self.all_entries = [item for item in self.all_entries if item.id != entry.id]
            self._update_footer()
            self.apply_filter(self.search.text(), None)
            self._show_status(f"Entry #{entry.id} deleted", 3000)
        else:
            self._show_status("Entry no longer exists — refresh history", 4000)

    def _pause_from_button(self, _checked=False):
        self.set_paused(not self.paused)

    def set_paused(self, paused: bool):
        self.paused = bool(paused)
        self.pause_button.blockSignals(True)
        self.pause_button.setChecked(self.paused)
        self.pause_button.blockSignals(False)
        if self.tray_available:
            self.pause_action.blockSignals(True)
            self.pause_action.setChecked(self.paused)
            self.pause_action.blockSignals(False)
        self._update_footer()
        self._show_status("Monitoring paused" if paused else "Monitoring active", 4000)

    def _update_footer(self):
        self.monitor_label.setText("●  Monitoring: Paused" if self.paused else "●  Monitoring: Active")
        self.monitor_label.setStyleSheet("color:#e8bd72;" if self.paused else "color:#8dea9e;")
        self.database_label.setText("◫  PostgreSQL: Local" if self.database_ok else "◫  PostgreSQL: Unavailable")
        self.database_label.setStyleSheet("color:#c8b5d8;" if self.database_ok else "color:#f48d8d;")
        self.total_label.setText(f"{len(self.all_entries)} entries")

    def restore_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.hide() if self.isVisible() else self.restore_window()

    def closeEvent(self, event):
        if self.tray_available:
            event.ignore()
            self.hide()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("ClipVault")
    app.setQuitOnLastWindowClosed(not QSystemTrayIcon.isSystemTrayAvailable())
    window = ClipvaultWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
