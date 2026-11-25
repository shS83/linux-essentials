"""Audio-file discovery shared by the file picker and folder import."""
import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal


AUDIO_EXTENSIONS = frozenset({
    ".mp3", ".flac", ".wav", ".wave", ".ogg", ".oga", ".opus",
    ".m4a", ".m4b", ".aac", ".aiff", ".aif", ".aifc", ".wma",
})
AUDIO_FILE_FILTER = "Audio (" + " ".join(f"*{ext}" for ext in sorted(AUDIO_EXTENSIONS)) + ");;All files (*)"


def scan_audio_files(folder, cancelled=lambda: False, on_error=None):
    """Walk albums in stable order without following directory-symlink loops."""
    for root, directories, filenames in os.walk(folder, onerror=on_error, followlinks=False):
        if cancelled():
            return
        directories.sort(key=lambda name: (name.casefold(), name))
        for filename in sorted(filenames, key=lambda name: (name.casefold(), name)):
            if cancelled():
                return
            path = Path(root) / filename
            if path.suffix.lower() in AUDIO_EXTENSIONS and path.is_file():
                yield path


def scan_audio_folders(folders, cancelled=lambda: False, on_error=None):
    """Deduplicate overlapping selections while retaining the chosen order."""
    seen = set()
    for folder in folders:
        if cancelled():
            return
        for path in scan_audio_files(folder, cancelled, on_error):
            key = os.path.normcase(str(path.resolve()))
            if key not in seen:
                seen.add(key)
                yield path


class FolderScanner(QThread):
    files_found = Signal(object)
    scan_error = Signal(str)

    def __init__(self, folder, parent=None):
        super().__init__(parent)
        self.folders = [folder] if isinstance(folder, (str, Path)) else list(folder)

    def run(self):
        batch = []
        try:
            for path in scan_audio_folders(self.folders, self.isInterruptionRequested,
                                         lambda exc: self.scan_error.emit(str(exc))):
                batch.append(path)
                if len(batch) == 128:
                    self.files_found.emit(batch)
                    batch = []
            if batch:
                self.files_found.emit(batch)
        except OSError as exc:
            self.scan_error.emit(str(exc))
