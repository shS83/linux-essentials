"""Optional keyboard debug controls for MusiK Fireworks (PySide6)."""
from PySide6.QtCore import QObject, QEvent, Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import QLabel, QGraphicsOpacityEffect


class FireworksDebug(QObject):
    """Attach to the widget that receives visualizer keyboard input."""

    def __init__(self, widget, fireworks):
        super().__init__(widget)
        self.widget = widget
        self.fireworks = fireworks
        self.enabled = False
        self.banner = QLabel('DEBUG MODE ON', widget)
        self.banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.banner.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.banner.setStyleSheet("""color:#ecfaff; background:rgba(10,15,35,175);
            border:1px solid rgba(90,210,255,125);
            border-radius:12px; padding:12px 20px;
            font-size:25px; font-weight:700;""")
        self.banner.hide()
        self.opacity = QGraphicsOpacityEffect(self.banner)
        self.banner.setGraphicsEffect(self.opacity)
        self.fade = QPropertyAnimation(self.opacity, b'opacity', self)
        self.fade.setDuration(1600)
        self.fade.setStartValue(1.0)
        self.fade.setEndValue(0.0)
        self.fade.setEasingCurve(QEasingCurve.Type.InCubic)
        self.fade.finished.connect(self.banner.hide)
        widget.installEventFilter(self)

    def show_banner(self, text):
        self.fade.stop()
        self.banner.setText(text)
        self.banner.adjustSize()
        self.banner.move(max(0, (self.widget.width()-self.banner.width())//2), 28)
        self.banner.show()
        self.banner.raise_()
        self.opacity.setOpacity(1.)
        self.fade.start()

    def eventFilter(self, watched, event):
        if watched is self.widget and event.type() == QEvent.Type.KeyPress:
            # event.text() handles the Nordic § key in layouts where Key_Section differs.
            if event.text() == '§' or event.key() == Qt.Key.Key_section:
                self.enabled = not self.enabled
                self.show_banner('DEBUG MODE ON' if self.enabled else 'DEBUG MODE OFF')
                return True
            text = event.text()
            if self.enabled and len(text) == 1 and text in '123456789':
                if self.fireworks.debug_burst(int(text)):
                    self.widget.update()
                    return True
        return super().eventFilter(watched, event)
