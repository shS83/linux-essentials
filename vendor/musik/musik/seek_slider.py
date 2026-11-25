"""Playback timeline that seeks immediately when its track is clicked."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QSlider, QStyle, QStyleOptionSlider


class SeekSlider(QSlider):
    track_clicked = Signal(int)

    def mousePressEvent(self, event):
        if (event.button() != Qt.MouseButton.LeftButton or not self.isEnabled()
                or self.maximum() <= self.minimum()):
            return super().mousePressEvent(event)

        option = QStyleOptionSlider()
        self.initStyleOption(option)
        handle = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, option,
            QStyle.SubControl.SC_SliderHandle, self)
        if handle.contains(event.position().toPoint()):
            return super().mousePressEvent(event)

        groove = self.style().subControlRect(
            QStyle.ComplexControl.CC_Slider, option,
            QStyle.SubControl.SC_SliderGroove, self)
        span = max(1, groove.width() - handle.width())
        offset = event.position().toPoint().x() - groove.x() - handle.width() // 2
        value = QStyle.sliderValueFromPosition(
            self.minimum(), self.maximum(), offset, span, option.upsideDown)
        self.setValue(value)
        self.track_clicked.emit(value)
        event.accept()
