"""Portable local-file M3U playlists (relative to the playlist directory)."""
import os
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname


def load_playlist(filename):
    source = Path(filename)
    tracks, missing = [], []
    for line in source.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("file://"):
            url = urlparse(line)
            server = "//" + url.netloc if url.netloc and url.netloc != "localhost" else ""
            line = url2pathname(server + url.path)
        elif "://" in line:
            missing.append(line)
            continue
        path = Path(line).expanduser()
        if not path.is_absolute():
            path = source.parent / path
        if path.is_file():
            tracks.append(path.resolve())
        else:
            missing.append(line)
    return tracks, missing


def save_playlist(filename, tracks):
    target = Path(filename).resolve()
    lines = ["#EXTM3U"]
    for track in tracks:
        relative = os.path.relpath(Path(track).resolve(), target.parent)
        if "\n" in relative or "\r" in relative:
            raise ValueError("A filename contains a line break and cannot be saved as M3U.")
        lines.append("./" + relative if relative.startswith("#") else relative)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
