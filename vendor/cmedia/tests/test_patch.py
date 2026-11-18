#!/usr/bin/env python3
"""Offline regression tests for renderer patch; no Chafa/Pygame needed."""
from __future__ import annotations
from pathlib import Path
import importlib.util
import tempfile
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import patch_cmedia


def v1_fixture() -> str:
    draw = (ROOT/'tests/fixture_v1_draw.txt').read_text(encoding='utf-8')
    return 'from __future__ import annotations\n' + draw + '\nKITTY_PACKET = None\n'


class MockTerminal:
    def __init__(self, width=100, height=24):
        self.cols, self.rows = width, height
        self.writes = []

    def size(self):
        return self.cols, self.rows

    def write(self, data):
        self.writes.append(data.encode() if isinstance(data, str) else data)

    def image_bytes(self, data, row, column):
        return b'IMAGE-' + data + f'-{row}-{column}'.encode()


class MockCache:
    def get(self, item, fmt, width, height):
        if item.suffix == '.png':
            return ['Image info', item.name], item.name.encode()
        return ['Image info', item.name], None


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        app = root/'src/cmedia/app.py'
        app.parent.mkdir(parents=True)
        app.write_text(v1_fixture())
        before = app.read_bytes()
        assert patch_cmedia.patch(root) is True
        assert patch_cmedia.NEW_MARKER in app.read_text()
        assert patch_cmedia.patch(root) is False
        assert app.with_name('app.py.before-diff-v2.bak').read_bytes() == before
        namespace = {'ESC': '\x1b', 'safe_text': str,
                     'media_kind': lambda p: 'image' if p and p.suffix.lower() in ('.png', '.jpg') else None,
                     'Path': Path}
        exec(compile(app.read_text(), str(app), 'exec'), namespace)
        draw = namespace['draw_browser']
        d = root/'test-items'
        d.mkdir()
        files = [d/'first.png', d/'second.png', d/'third.jpg']
        for file in files: file.write_bytes(b'test')
        term = MockTerminal()
        cache = MockCache()
        draw(term, d, files, 0, 'kitty', cache)
        assert len(term.writes) == 1, 'initial frame should be one atomic write'
        assert term.writes[-1].count(b'\x1b[2J') == 1
        term.writes.clear()
        draw(term, d, files, 1, 'kitty', cache)
        assert len(term.writes) == 1, 'selection update must be single write'
        data = term.writes[0]
        assert b'\x1b[2J' not in data, 'do not clear full screen on navigation'
        assert b'\x1b[1;1H' not in data, 'do not redraw header when index changes'
        assert b'\x1b[2;1H' in data and b'\x1b[3;1H' in data, 'two changed list rows'
        assert b'IMAGE-first.png' in data
        assert data.count(b'\x1b[2K') == 1, 'only counter line is cleared'
        term.writes.clear()
        draw(term, d, files, 1, 'kitty', cache)
        assert not term.writes, 'nothing changed: no terminal output'
        draw(term, d, files, 2, 'kitty', cache)
        assert len(term.writes) == 1 and b'\x1b[2J' not in term.writes[0]
        term.writes.clear()
        draw(term, d, files, 2, 'kitty', cache, message='Warning!')
        assert len(term.writes) == 1 and b'Warning!' in term.writes[0]
        assert b'\x1b[2J' not in term.writes[0]
        term.writes.clear()
        term.cols=125
        draw(term, d, files, 2, 'kitty', cache)
        assert term.writes[0].count(b'\x1b[2J') == 1, 'resizing requires a repaint'
        # More items than visible: scrolling must also be incremental.
        many = [d/f'{i:03d}.png' for i in range(55)]
        for path in many: path.write_bytes(b'x')
        term = MockTerminal(100,20)
        draw(term, d, many, 0, 'kitty', cache)
        term.writes.clear()
        for n in range(1,45): draw(term, d, many, n, 'kitty', cache)
        assert all(b'\x1b[2J' not in x for x in term.writes)
        # Terminals too narrow for preview must never clear on selection either.
        small = MockTerminal(50,12)
        draw(small, d, files, 0, 'symbols', cache)
        small.writes.clear()
        draw(small, d, files, 1, 'symbols', cache)
        assert b'\x1b[2J' not in small.writes[0]
        # An unknown source layout is rejected without writing anything.
        app.write_text('print("unknown source")\n')
        try:
            patch_cmedia.patch(root)
        except RuntimeError:
            assert app.read_text() == 'print("unknown source")\n'
        else:
            raise AssertionError('patch should refuse unrecognized code')
    print('PASS: initial frame, incremental selection, no-op, resize, scroll, narrow view, backups, idempotence, safe refusal')

if __name__ == '__main__':
    main()
