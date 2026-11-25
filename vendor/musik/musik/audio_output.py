"""Select a playback endpoint and, optionally, send explicitly formatted PCM to it."""
import numpy as np
from shiboken6 import delete
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtMultimedia import (
    QAudioBufferOutput, QAudioDevice, QAudioFormat, QAudioSink, QMediaDevices,
    QMediaPlayer, QtAudio,
)
from PySide6.QtWidgets import QComboBox, QLabel


WIDTHS = {"auto": "Automatic", "16": "16-bit integer", "24": "24-bit integer (32-bit container)",
          "32": "32-bit integer", "float": "32-bit float"}
RATES = (22050, 32000, 44100, 48000, 88200, 96000, 176400, 192000)
SAMPLES = {"16": QAudioFormat.Int16, "24": QAudioFormat.Int32,
           "32": QAudioFormat.Int32, "float": QAudioFormat.Float}


def device_key(device):
    return bytes(device.id()).hex()


def resolve_device(key):
    return next((d for d in QMediaDevices.audioOutputs() if device_key(d) == key),
                QMediaDevices.defaultAudioOutput())


def pcm_format(device, rate, width):
    fmt = device.preferredFormat()
    if width != "auto":
        fmt.setSampleFormat(SAMPLES[width])
    if rate:
        fmt.setSampleRate(rate)
    return fmt


class OutputControls:
    def __init__(self, form, values):
        self.devices = QMediaDevices()
        self.device = QComboBox()
        self.width = QComboBox()
        self.rate = QComboBox()
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        form.addRow("Output device", self.device)
        form.addRow("Bit width", self.width)
        form.addRow("Bitrate (PCM)", self.rate)
        form.addRow("", self.summary)
        self.refresh_devices(values["output_device"])
        self.refresh_formats(values["output_width"], values["output_rate"])
        self.device.currentIndexChanged.connect(self.refresh)
        self.width.currentIndexChanged.connect(self.refresh)
        self.rate.currentIndexChanged.connect(self.describe)
        self.devices.audioOutputsChanged.connect(self.hotplug)

    def hotplug(self):
        key = self.device.currentData()
        self.refresh_devices(key)
        self.refresh()

    def refresh_devices(self, key):
        self.device.blockSignals(True)
        self.device.clear()
        self.device.addItem("System default", "")
        for device in QMediaDevices.audioOutputs():
            self.device.addItem(device.description(), device_key(device))
        if key and self.device.findData(key) < 0:
            self.device.addItem("Disconnected device (using system default)", key)
        self.device.setCurrentIndex(max(0, self.device.findData(key)))
        self.device.blockSignals(False)

    def refresh(self, *_):
        self.refresh_formats(self.width.currentData(), self.rate.currentData())

    def refresh_formats(self, width, rate):
        device = resolve_device(self.device.currentData())
        self.width.blockSignals(True)
        self.width.clear()
        rates = sorted(set(RATES) | {device.preferredFormat().sampleRate()})
        for key, label in WIDTHS.items():
            if key == "auto" or any(device.isFormatSupported(pcm_format(device, hz, key)) for hz in rates):
                self.width.addItem(label, key)
        self.width.setCurrentIndex(max(0, self.width.findData(width)))
        self.width.blockSignals(False)
        self.rate.blockSignals(True)
        self.rate.clear()
        self.rate.addItem("Automatic", 0)
        for hz in rates:
            fmt = pcm_format(device, hz, self.width.currentData())
            if hz > 0 and device.isFormatSupported(fmt):
                kbps = fmt.bytesPerFrame() * hz * 8 / 1000
                self.rate.addItem(f"{kbps:g} kb/s  ·  {hz/1000:g} kHz", hz)
        self.rate.setCurrentIndex(max(0, self.rate.findData(rate)))
        self.rate.blockSignals(False)
        self.describe()

    def describe(self, *_):
        dev = resolve_device(self.device.currentData())
        if dev.isNull():
            self.summary.setText("No audio output available.")
            return
        fmt = pcm_format(dev, self.rate.currentData(), self.width.currentData())
        self.summary.setText(f"{dev.description()} · {fmt.channelCount()} channels. "
                             "Bitrate refers to decoded PCM playback.")

    def values(self):
        return {"output_device": self.device.currentData(), "output_width": self.width.currentData(),
                "output_rate": self.rate.currentData()}


class PlaybackOutput(QObject):
    warning = Signal(str)

    def __init__(self, player, volume, analysis, parent):
        super().__init__(parent)
        self.player, self.volume, self.analysis = player, volume, analysis
        self.devices = QMediaDevices(self)
        self.devices.audioOutputsChanged.connect(self.reconfigure)
        self.selection = self.active = None
        self.sink = self.tap = self.writer = None
        self.pending = bytearray()
        self.pump = QTimer(self, interval=8)
        self.pump.timeout.connect(self.write_pending)
        volume.volumeChanged.connect(self.sync_volume)
        volume.mutedChanged.connect(self.sync_volume)
        player.sourceChanged.connect(self.flush)
        player.playbackStateChanged.connect(self.transport)

    def close(self):
        self.selection = None
        self.flush()
        self.player.setAudioBufferOutput(None)
        self.player.setAudioOutput(None)
        if self.tap is not None:
            self.tap.audioBufferReceived.disconnect(self.receive)
            delete(self.tap)
            self.tap = None

    def configure(self, values):
        self.selection = (values["output_device"], values["output_rate"], values["output_width"])
        self.reconfigure()

    def reconfigure(self):
        if self.selection is None:
            return
        key, rate, width = self.selection
        device = resolve_device(key)
        signature = (key, device_key(device), rate, width)
        if signature == self.active:
            return
        self.active = signature
        self.install(device, rate, width)

    def install(self, device, rate, width):
        self.flush()
        if self.sink:
            self.sink.deleteLater()
            self.sink = None
        if self.tap:
            self.tap.audioBufferReceived.disconnect(self.receive)
            self.player.setAudioBufferOutput(None)
            # Destroy the detached tap before attaching its successor. In Qt
            # 6.12 a deferred destructor can clear the newly attached output.
            delete(self.tap)
        self.volume.setDevice(device if self.selection[0] else QAudioDevice())
        fmt = pcm_format(device, rate, width)
        if (rate or width != "auto") and not device.isNull() and device.isFormatSupported(fmt):
            self.player.setAudioOutput(None)
            self.sink = QAudioSink(device, fmt, self)
            self.sink.setBufferSize(fmt.bytesForDuration(100000))
            self.sync_volume()
            self.tap = QAudioBufferOutput(fmt, self)
        else:
            if rate or width != "auto":
                self.warning.emit("Selected PCM format unavailable. Using automatic playback.")
            self.player.setAudioOutput(self.volume)
            self.tap = QAudioBufferOutput(self)
        self.tap.audioBufferReceived.connect(self.receive)
        self.player.setAudioBufferOutput(self.tap)

    def sync_volume(self, *_):
        if self.sink:
            self.sink.setVolume(0. if self.volume.isMuted() else self.volume.volume())

    def flush(self, *_):
        self.pump.stop()
        self.pending.clear()
        self.writer = None
        if self.sink:
            self.sink.reset()

    def transport(self, state):
        if not self.sink:
            return
        if state == QMediaPlayer.PausedState:
            self.pump.stop()
            if self.writer:
                self.sink.suspend()
        elif state == QMediaPlayer.PlayingState:
            if self.sink.state() == QtAudio.SuspendedState:
                self.sink.resume()
                self.write_pending()
        else:
            self.flush()

    def receive(self, buffer):
        self.analysis.receive(buffer)
        if not self.sink or not buffer.isValid():
            return
        if self.sender() is not self.tap or self.player.playbackState() != QMediaPlayer.PlayingState:
            return
        if buffer.format() != self.sink.format():
            self.fallback()
            return
        if self.writer is None:
            self.writer = self.sink.start()
            if self.writer is None:
                self.fallback()
                return
        data = buffer.constData()
        if self.selection[2] == "24":
            data = (np.frombuffer(data, dtype=np.int32) & np.int32(-256)).tobytes()
        self.pending.extend(data)
        self.write_pending()

    def write_pending(self):
        if not self.writer:
            return
        if (self.sink.error() not in (QtAudio.NoError, QtAudio.UnderrunError)
                or len(self.pending) > self.sink.format().bytesForDuration(1000000)):
            self.fallback()
            return
        n = min(len(self.pending), self.sink.bytesFree())
        if n:
            written = self.writer.write(bytes(self.pending[:n]))
            if written < 0:
                self.fallback()
                return
            del self.pending[:written]
        if self.pending:
            self.pump.start()
        else:
            self.pump.stop()

    def fallback(self):
        self.warning.emit("Audio device could not play the selected PCM format. Using automatic playback.")
        failed = self.tap
        self.flush()
        QTimer.singleShot(0, self, lambda: self.install(resolve_device(self.selection[0]), 0, "auto")
                          if self.tap is failed else None)

