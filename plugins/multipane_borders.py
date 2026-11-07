# ~/.config/ranger/plugins/multipane_borders.py
# Ramki w trybie dwupanelowym (viewmode multipane), w stylu Double Commandera:
#  - każdy panel w zaokrąglonej ramce,
#  - ścieżka katalogu w górnej krawędzi,
#  - liczba pozycji / zaznaczonych w dolnej krawędzi,
#  - aktywny panel wyróżniony kolorem.
from __future__ import absolute_import, division, print_function

import curses
import os

from ranger.gui.color import get_color, bold
from ranger.gui.widgets.view_base import ViewBase
from ranger.gui.widgets.view_multipane import ViewMultipane

# Kolory (xterm-256, pasują do colorschemes/nocturne.py; -1 = domyślne tło)
ACTIVE_BORDER = 111                     # niebieski
INACTIVE_BORDER = 238                   # ciemnoszary
ACTIVE_TITLE_FG, ACTIVE_TITLE_BG = 234, 111
INACTIVE_TITLE_FG = 243

UL, UR, LL, LR, H, V = '╭', '╮', '╰', '╯', '─', '│'


def _attr(fg, bg=-1, extra=0):
    # terminal z 8 kolorami (tmux z TERM=screen, TTY): zamień na podstawowe,
    # inaczej curses rzuca ValueError i ranger się wywraca
    colors = getattr(curses, 'COLORS', 8)
    if fg >= colors:
        fg = {ACTIVE_BORDER: curses.COLOR_BLUE, ACTIVE_TITLE_FG: curses.COLOR_BLACK}.get(
            fg, curses.COLOR_WHITE)
    if bg >= colors:
        bg = curses.COLOR_BLUE
    return curses.color_pair(get_color(fg, bg)) | extra


def _put(win, y, x, text, attr):
    try:
        win.addstr(y, x, text, attr)
    except curses.error:
        pass  # ostatnia komórka okna zawsze rzuca błąd po zapisie


def _short_path(path, maxlen):
    home = os.path.expanduser('~')
    if path == home or path.startswith(home + os.sep):
        path = '~' + path[len(home):]
    if maxlen < 2:
        return ''
    if len(path) > maxlen:
        path = '…' + path[-(maxlen - 1):]
    return path


def _resize(self, y, x, hei=None, wid=None):
    ViewBase.resize(self, y, x, hei, wid)
    self._pane_rects = []
    count = len(self.columns)
    if not count:
        return
    base = self.wid // count
    left = 0
    for i, column in enumerate(self.columns):
        width = base if i < count - 1 else self.wid - left
        self._pane_rects.append((column, left, width))
        column.resize(1, left + 2, max(1, self.hei - 2), max(1, width - 3))
        column.need_redraw = True
        left += width
    self.need_redraw = True


def _draw(self):
    ViewBase.draw(self)
    win, hei = self.win, self.hei
    if hei < 3:
        return
    for column, left, width in getattr(self, '_pane_rects', []):
        if width < 4:
            continue
        active = column.tab is self.fm.thistab
        border = _attr(ACTIVE_BORDER, extra=bold) if active else _attr(INACTIVE_BORDER)
        right = left + width - 1

        # ramka
        _put(win, 0, left, UL + H * (width - 2) + UR, border)
        for row in range(1, hei - 1):
            _put(win, row, left, V, border)
            _put(win, row, right, V, border)
        _put(win, hei - 1, left, LL + H * (width - 2) + LR, border)

        # tytuł: ścieżka
        directory = column.tab.thisdir if column.tab else None
        path = directory.path if directory else (column.tab.path if column.tab else '')
        title = _short_path(path, width - 6)
        if title:
            title_attr = (_attr(ACTIVE_TITLE_FG, ACTIVE_TITLE_BG, bold) if active
                          else _attr(INACTIVE_TITLE_FG))
            _put(win, 0, left + 2, ' ' + title + ' ', title_attr)

        # stopka: liczba pozycji i zaznaczonych
        if directory is not None and directory.files is not None:
            info = ' %d poz. ' % len(directory.files)
            if directory.marked_items:
                info = ' %d zazn. ·%s' % (len(directory.marked_items), info)
            if len(info) < width - 4:
                _put(win, hei - 1, right - 1 - len(info), info, border)


ViewMultipane.resize = _resize
ViewMultipane.draw = _draw
