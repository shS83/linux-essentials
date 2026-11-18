#!/usr/bin/env python3
"""Upgrade shS83/cmedia's V1 browser renderer to a batched delta renderer.

Only the browser rendering function is changed. Media playback, Chafa and
key handling are untouched. The patch fails closed on unknown source layouts.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import sys

OLD_MARKER = 'CMEDIA_DIFF_RENDER_V1'
NEW_MARKER = 'CMEDIA_DIFF_RENDER_V2'

DRAW_V2 = r'''def draw_browser(term: Terminal, directory: Path, paths: list[Path], index: int,
                 format_: str, cache: PreviewCache, video_window: bool = False, message: str = '') -> None:
    """CMEDIA_DIFF_RENDER_V2: batch the changes and never clear on navigation.

    Keep the list, header, borders and metadata separately cached. Only a new
    browser layout clears the terminal; individual keypresses emit the changed
    rows in ONE terminal write, without flickering between clear and repaint.
    """
    output_name = 'pygame' if video_window else 'chafa'
    indicator_width = len('output: ') + len(output_name)
    width, height = term.size()
    title_width = max(0, width - indicator_width - 2)
    title = safe_text(str(directory))[:title_width]
    hint = safe_text(message or '↑↓ selaa PgUp/Dn sivu Enter avaa * vaihda / polku q lopeta')[:width]
    has_preview = width >= 72 and height >= 14
    left_width = width * 52 // 100 if has_preview else width
    visible = max(1, height - 3)
    items = [None, *paths]
    start = max(0, min(index - visible // 2, len(items) - visible))
    layout = (directory, tuple(paths), format_, video_window, width, height)
    previous = getattr(term, '_cmedia_browser_state', None)
    full = previous is None or previous.get('layout') != layout

    # Collect text and graphics output in memory. No flush between erasing the
    # old thumbnail and drawing its replacement or between the highlight rows.
    parts: list[bytes] = []

    def emit(value: str | bytes) -> None:
        parts.append(value.encode('utf-8') if isinstance(value, str) else value)

    def paint_box(left: int, top: int, box_width: int, box_height: int, label: str) -> None:
        emit(f'{ESC}[{top};{left}H┌{label[:box_width - 2]:─<{box_width - 2}}┐')
        for y in range(top + 1, top + box_height - 1):
            emit(f'{ESC}[{y};{left}H│{ESC}[{y};{left + box_width - 1}H│')
        emit(f'{ESC}[{top + box_height - 1};{left}H└{"─" * (box_width - 2)}┘')

    if full:
        emit(f'{ESC}[?25l{ESC}[2J{ESC}[H')
    # Never rewrite the title/guide line unless it changed.
    if full or previous['title'] != title:
        emit(f'{ESC}[1;1H{ESC}[0m{ESC}[2K{ESC}[1m{title}{ESC}[0m')
    if full:
        column = max(1, width - indicator_width + 1)
        mode_color = 94 if video_window else 97
        emit(f'{ESC}[1;{column}H{ESC}[97moutput: {ESC}[{mode_color}m{output_name}{ESC}[0m')
    if full or previous['hint'] != hint:
        emit(f'{ESC}[{height};1H{ESC}[0m{ESC}[2K{hint}')

    rows: dict[int, tuple[str, str]] = {}
    old_rows = {} if full else previous['rows']
    for y, item in enumerate(items[start:start + visible], start=2):
        actual = start + y - 2
        label = '../' if item is None else safe_text(item.name) + ('/' if item.is_dir() else '')
        marker = '> ' if actual == index else ' '
        color = ({'video': 91, 'image': 92, 'audio': 93}.get(media_kind(item))
                 if item is not None and item.is_file() else None)
        if color:
            style = f'{ESC}[1;{color}' + (';4m' if actual == index else 'm')
        else:
            style = f'{ESC}[7m' if actual == index else ''
        content = (marker + label)[:left_width].ljust(left_width)
        state = (style, content)
        rows[y] = state
        if full or old_rows.get(y) != state:
            emit(f'{ESC}[{y};1H{ESC}[0m{style}{content}{ESC}[0m')
    for y in old_rows.keys() - rows.keys():
        emit(f'{ESC}[{y};1H{ESC}[0m' + ' ' * left_width)

    counter = f'{index + 1}/{len(items)}'
    if full or previous['counter'] != counter:
        emit(f'{ESC}[{height - 1};1H{ESC}[0m{ESC}[2K{counter}')

    selected = items[index]
    detail_rows: dict[int, str] = {}
    thumb_text: dict[int, str] = {}
    thumb_picture = False
    if has_preview:
        right = left_width + 2
        panel_width = width - right
        inside = panel_width - 2
        thumb_height = max(5, min(12, (height - 3) // 2))
        details_top = thumb_height + 3
        details_height = height - details_top - 1
        if full:
            paint_box(right, 2, panel_width, thumb_height, ' Esikatselu ')
            paint_box(right, details_top, panel_width, details_height, ' Tiedot ')

        if selected is None:
            lines, picture = [], None
        elif selected.is_dir():
            lines, picture = ['Hakemisto', safe_text(selected.name)], None
        else:
            lines, picture = cache.get(selected, format_, inside, thumb_height - 2)

        thumb_picture = bool(picture)
        if not picture and selected is not None and selected.is_file():
            label = ('Ei kuvaesikatselua' if media_kind(selected) == 'audio'
                     else 'Esikatselu ei saatavilla')
            thumb_text[3] = label[:inside].ljust(inside)
        for y, line in enumerate(lines[:max(0, details_height - 2)], start=details_top + 1):
            detail_rows[y] = safe_text(line)[:inside].ljust(inside)

        old_details = {} if full else previous['details']
        for y in sorted(set(old_details) | set(detail_rows)):
            new = detail_rows.get(y, ' ' * inside)
            if full or old_details.get(y, ' ' * inside) != new:
                emit(f'{ESC}[{y};{right + 1}H{ESC}[0m{new}')

        # Only the INTERIOR of the thumbnail changes. Borders, detail box and
        # list selection bars remain visible throughout navigation.
        old_thumb = {} if full else previous['thumb_text']
        was_picture = False if full else previous['thumb_picture']
        changed_selection = full or previous['selected'] != selected
        if changed_selection:
            if picture or was_picture:
                blank = ' ' * inside
                for y in range(3, 2 + thumb_height - 1):
                    emit(f'{ESC}[{y};{right + 1}H{ESC}[0m{blank}')
            else:
                for y in sorted(set(old_thumb) | set(thumb_text)):
                    old = old_thumb.get(y, ' ' * inside)
                    new = thumb_text.get(y, ' ' * inside)
                    if full or old != new:
                        emit(f'{ESC}[{y};{right + 1}H{ESC}[0m{new}')
            if picture:
                # Preserve the existing Chafa placement/output protocol.
                emit(term.image_bytes(picture, 3, right + 1))
            elif was_picture:
                for y in sorted(thumb_text):
                    emit(f'{ESC}[{y};{right + 1}H{ESC}[0m{thumb_text[y]}')

    term._cmedia_browser_state = {
        'layout': layout, 'title': title, 'hint': hint, 'rows': rows,
        'counter': counter, 'selected': selected, 'details': detail_rows,
        'thumb_text': thumb_text, 'thumb_picture': thumb_picture,
    }
    if parts:
        # Park cursor, then submit one terminal write. Avoid intermediate flushes.
        emit(f'{ESC}[?25l{ESC}[{height};{width}H')
        term.write(b''.join(parts))
'''


def patch(root: Path) -> bool:
    target = root / 'src' / 'cmedia' / 'app.py'
    if not target.is_file():
        raise RuntimeError(f'cmedian lähdekoodia ei löydy: {target}')
    original = target.read_text(encoding='utf-8')
    if NEW_MARKER in original:
        print('cmedian differentiaalinen piirtäminen V2 on jo käytössä.')
        return False
    if original.count(OLD_MARKER) != 1:
        raise RuntimeError('Tuntematon cmedia-versio. Päivitä ensin shS83/cmedian root-haaraan; muutoksia ei tehty.')
    anchor = re.compile(
        r'(?ms)^def draw_browser\(term: Terminal, directory: Path, paths: list\[Path\], index: int,\n'
        r'.*?(?=^KITTY_PACKET\s*=)'
    )
    if len(anchor.findall(original)) != 1:
        raise RuntimeError('draw_browser ei vastaa tunnettua lähdekoodin rakennetta; muutoksia ei tehty.')
    updated = anchor.sub(lambda _: DRAW_V2 + '\n', original, count=1)
    compile(updated, str(target), 'exec')
    backup = target.with_name('app.py.before-diff-v2.bak')
    if not backup.exists():
        shutil.copy2(target, backup)
    temp = target.with_name('.app.py.cmedia-new')
    try:
        temp.write_text(updated, encoding='utf-8')
        os.chmod(temp, target.stat().st_mode & 0o777)
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    print(f'Korjattu: {target}\nVarmuuskopio: {backup}')
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description='cmedia: eräajettu differentiaalinen TTY-renderöinti')
    ap.add_argument('project', type=Path, help='cmedia-repositorion juurihakemisto')
    args = ap.parse_args()
    try:
        patch(args.project.expanduser().resolve())
    except (OSError, RuntimeError, SyntaxError) as e:
        print(f'Virhe: {e}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
