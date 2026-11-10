#!/usr/bin/env python3
"""Patches shS83/cmedia (root branch) to redraw only changed browser rows.

Safe/idempotent: refuses unrecognized upstream layouts and saves a .bak copy.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys

MARKER = 'CMEDIA_DIFF_RENDER_V1'

SCREEN = '''    def screen(self, title: str, hint: str, *, clear: bool = True) -> tuple[int, int]:
        width, height = self.size()
        if clear:
            # A full-screen media view (or a fresh browser) invalidates our cache.
            self._cmedia_browser_state = None
            self.write(f'{ESC}[?25l{ESC}[2J{ESC}[H{ESC}[1m{safe_text(title)[:width]}{ESC}[0m{ESC}[{height};1H{ESC}[2K{safe_text(hint)[:width]}')
        else:
            # Do NOT clear the screen on cursor movement in the browser.
            self.write(f'{ESC}[?25l{ESC}[1;1H{ESC}[2K{ESC}[1m{safe_text(title)[:width]}{ESC}[0m{ESC}[{height};1H{ESC}[2K{safe_text(hint)[:width]}')
        return width, height
'''

DRAW = '''def draw_browser(term: Terminal, directory: Path, paths: list[Path], index: int,
                 format_: str, cache: PreviewCache, video_window: bool = False, message: str = '') -> None:
    # CMEDIA_DIFF_RENDER_V1: redraw changed file-list rows, not the full screen.
    output_name = 'pygame' if video_window else 'chafa'
    indicator_width = len('output: ') + len(output_name)
    terminal_width, terminal_height = term.size()
    title_width = max(0, terminal_width - indicator_width - 2)
    hint = '↑↓ selaa PgUp/Dn sivu Enter avaa * vaihda / polku q lopeta'
    preview = terminal_width >= 72 and terminal_height >= 14
    left_width = terminal_width * 52 // 100 if preview else terminal_width
    visible = max(1, terminal_height - 3)
    items = [None, *paths]
    start = max(0, min(index - visible // 2, len(items) - visible))

    # Directory, window mode and geometry changes force the initial repaint.
    layout_key = (directory, tuple(paths), format_, video_window, terminal_width, terminal_height)
    previous = getattr(term, '_cmedia_browser_state', None)
    full = previous is None or previous['layout'] != layout_key
    width, height = term.screen(str(directory)[:title_width], message or hint, clear=full)

    column = max(1, width - indicator_width + 1)
    mode_color = 94 if video_window else 97
    if full:
        term.write(f'{ESC}[1;{column}H{ESC}[97moutput: {ESC}[{mode_color}m{output_name}{ESC}[0m')

    previous_rows = {} if full else previous['rows']
    rows = {}
    for row, item in enumerate(items[start:start + visible], start=2):
        actual = start + row - 2
        label = '../' if item is None else safe_text(item.name) + ('/' if item.is_dir() else '')
        marker = '> ' if actual == index else ' '
        color = ({'video': 91, 'image': 92, 'audio': 93}.get(media_kind(item))
                 if item is not None and item.is_file() else None)
        if color:
            style = f'{ESC}[1;{color}' + (';4m' if actual == index else 'm')
        else:
            style = f'{ESC}[7m' if actual == index else ''
        # Pad while the style is active: stale highlights/text can't remain.
        content = (marker + label)[:left_width].ljust(left_width)
        value = (style, content)
        rows[row] = value
        if full or previous_rows.get(row) != value:
            term.write(f'{ESC}[{row};1H{ESC}[0m{style}{content}{ESC}[0m')

    # Remove rows that disappeared when the item count changes.
    for row in previous_rows.keys() - rows.keys():
        term.write(f'{ESC}[{row};1H{ESC}[0m' + ' ' * left_width)

    term.write(f'{ESC}[{height - 1};1H{ESC}[2K{index + 1}/{len(items)}')

    selected = items[index]
    if preview and (full or previous['selected'] != selected):
        right = left_width + 2
        panel_width = width - right
        thumb_height = max(5, min(12, (height - 3) // 2))
        details_top = thumb_height + 3
        details_height = height - details_top - 1
        if not full:
            # Only clear the right-hand pane, never the selected list bars.
            # ED/EL at the left edge would erase the whole terminal graphics.
            blank = ' ' * (width - right + 1)
            for row in range(2, height - 1):
                term.write(f'{ESC}[{row};{right}H{ESC}[0m{blank}')
        box(term, right, 2, panel_width, thumb_height, ' Esikatselu ')
        box(term, right, details_top, panel_width, details_height, ' Tiedot ')
        if selected is not None:
            if selected.is_dir():
                lines, picture = ['Hakemisto', safe_text(selected.name)], None
            else:
                lines, picture = cache.get(selected, format_, panel_width - 2, thumb_height - 2)
            if picture:
                term.image(picture, 3, right + 1)
            elif selected.is_file():
                text = 'Ei kuvaesikatselua' if media_kind(selected) == 'audio' else 'Esikatselu ei saatavilla'
                term.write(f'{ESC}[3;{right + 1}H{text[:panel_width - 2]}')
            for row, line in enumerate(lines[:details_height - 2], start=details_top + 1):
                term.write(f'{ESC}[{row};{right + 1}H{safe_text(line)[:panel_width - 2]}')

    term._cmedia_browser_state = {'layout': layout_key, 'rows': rows, 'selected': selected}
    term.park()
'''
# Syntax check on template above: nested curly in f-string is accepted by Python >= 3.12.


def patch(source: Path) -> bool:
    target = source / 'src' / 'cmedia' / 'app.py'
    if not target.is_file():
        raise RuntimeError(f'cmedian lähdekoodi ei löydy: {target}')
    original = target.read_text(encoding='utf-8')
    if MARKER in original:
        print('Differentiaalinen piirtäminen on jo asennettu.')
        return False

    # Search boundaries are checked before writing a single byte.
    screen_pattern = re.compile(
        r'(?m)^    def screen\(self, title: str, hint: str\) -> tuple\[int, int\]:\n'
        r'(?:(?!^    def |^def |^class ).*\n)*?'
        r'        return width, height\n',
    )
    draw_pattern = re.compile(
        r'(?ms)^def draw_browser\(term: Terminal, directory: Path, paths: list\[Path\], index: int,\n'
        r'.*?(?=^KITTY_PACKET\s*=)',
    )
    if len(screen_pattern.findall(original)) != 1 or len(draw_pattern.findall(original)) != 1:
        raise RuntimeError('Lähdekoodin rakenne poikkeaa tunnetusta versiosta. Ei tehty muutoksia.')
    # Separate media views must invalidate stale rows before browser returns.
    present_anchor = 'def present_frame(term: Terminal, path: Path, frame: bytes, format_: str, hint: str,'
    dialog_anchor = 'def directory_dialog(term: Terminal, directory: Path) -> Path | None:'
    if original.count(present_anchor) != 1 or original.count(dialog_anchor) != 1:
        raise RuntimeError('Piirtonäkymien rakenne poikkeaa tunnetusta versiosta. Ei tehty muutoksia.')

    updated = screen_pattern.sub(lambda m: SCREEN, original, count=1)
    updated = draw_pattern.sub(lambda m: DRAW + '\n', updated, count=1)
    # Mark terminal image playback and modal overlays as needing a fresh screen.
    # This is essential because the previous browser's cached rows remain in memory.
    updated = updated.replace(present_anchor, present_anchor, 1)
    # Inject at stable statements near the respective function entrances.
    updated = updated.replace(
        '    """Read an absolute path or a path relative to the current directory."""',
        '    """Read an absolute path or a path relative to the current directory."""\n'
        '    term._cmedia_browser_state = None', 1,
    )
    updated = updated.replace(
        '    """Keep the old frame visible until the complete replacement is ready."""',
        '    """Keep the old frame visible until the complete replacement is ready."""\n'
        '    term._cmedia_browser_state = None', 1,
    )
    compile(updated, str(target), 'exec')
    backup = target.with_suffix('.py.bak')
    if not backup.exists():
        backup.write_text(original, encoding='utf-8')
    target.write_text(updated, encoding='utf-8')
    print(f'Korjattu: {target} (varmuuskopio: {backup})')
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description='cmedian differentiaalinen listapäivitys')
    parser.add_argument('project', type=Path, help='cmedia-repositorion juurihakemisto')
    args = parser.parse_args()
    try:
        patch(args.project.resolve())
    except (OSError, RuntimeError, SyntaxError) as exc:
        print(f'Virhe: {exc}', file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == '__main__':
    main()
