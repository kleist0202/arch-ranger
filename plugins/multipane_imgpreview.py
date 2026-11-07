# ~/.config/ranger/plugins/multipane_imgpreview.py
# Tryb dual (multipane): gdy kursor stoi na obrazku, na środku aktywnego panelu
# pokazuje się okienko z podglądem.
# Używa tej samej metody co zwykły podgląd (set preview_images_method ...).
# Ładuje się po multipane_borders.py (kolejność alfabetyczna), więc rysuje na wierzchu.
from __future__ import absolute_import, division, print_function

import curses
import os

from ranger.gui.color import get_color, bold
from ranger.gui.ui import UI
from ranger.gui.widgets.view_multipane import ViewMultipane

WIDTH_RATIO, HEIGHT_RATIO = 85, 75  # rozmiar okienka w % aktywnego panelu
MAX_WIDTH, MAX_HEIGHT = 80, 30     # ...ale nie więcej niż tyle znaków
MIN_WIDTH, MIN_HEIGHT = 16, 6
BORDER = 111                       # kolory jak w colorschemes/nocturne.py
TITLE_FG, TITLE_BG = 234, 111

# key: (ścieżka, top, left, wys, szer) aktualnie pokazanego okienka
# pending: okienko, w którym trzeba (ponownie) narysować obrazek
_state = {'key': None, 'pending': None}


def _attr(fg, bg=-1, extra=0):
    colors = getattr(curses, 'COLORS', 8)
    if fg >= colors:
        fg = curses.COLOR_BLUE
    if bg >= colors:
        bg = curses.COLOR_BLUE
    return curses.color_pair(get_color(fg, bg)) | extra


def _put(win, y, x, text, attr):
    try:
        win.addstr(y, x, text, attr)
    except curses.error:
        pass


def _geometry(view):
    fobj = view.fm.thisfile
    col = view.main_column
    if (col is None or fobj is None or not view.settings.preview_images
            or not getattr(fobj, 'image', False) or not fobj.is_file):
        return None
    if view.fm.ui.console.visible:
        return None

    # okienko na środku aktywnego panelu (tego, w którym stoi kursor)
    width = min(MAX_WIDTH, col.wid * WIDTH_RATIO // 100)
    height = min(MAX_HEIGHT, (view.hei - 2) * HEIGHT_RATIO // 100)
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        return None
    top = view.y + (view.hei - height) // 2
    left = col.x + (col.wid - width) // 2
    return (fobj.path, top, left, height, width)


def _draw_box(win, path, top, left, height, width):
    border = _attr(BORDER, extra=bold)
    _put(win, top, left, '╭' + '─' * (width - 2) + '╮', border)
    blank = ' ' * (width - 2)
    for row in range(top + 1, top + height - 1):
        _put(win, row, left, '│', border)
        _put(win, row, left + 1, blank, _attr(-1))
        _put(win, row, left + width - 1, '│', border)
    _put(win, top + height - 1, left, '╰' + '─' * (width - 2) + '╯', border)

    name = os.path.basename(path)
    if len(name) > width - 6:
        name = name[:width - 7] + '…'
    _put(win, top, left + 2, ' ' + name + ' ', _attr(TITLE_FG, TITLE_BG, bold))


def _clear_image(fm, geo):
    # ueberzug/kitty trzymają obrazek poza curses (nakładka), więc samo
    # odświeżenie ekranu go nie zdejmie – trzeba poprosić displayer o usunięcie
    _path, top, left, height, width = geo
    try:
        fm.image_displayer.clear(left + 1, top + 1, width - 2, height - 2)
    except Exception:  # pylint: disable=broad-except
        pass


_orig_draw = ViewMultipane.draw


def _draw(self):
    geo = _geometry(self)
    if geo != _state['key']:
        if _state['key'] is not None:
            # okienko zachodzi na oba panele: wyczyść cały widok i narysuj go od nowa,
            # a obrazek (rysowany poza curses) zetrzyj pełnym odświeżeniem ekranu
            _clear_image(self.fm, _state['key'])
            self.need_clear = True
            self.fm.ui.win.redrawwin()
        _state['key'] = geo
        _state['pending'] = geo
    _orig_draw(self)
    if geo:
        _draw_box(self.fm.ui.win, *geo)


_orig_draw_images = UI.draw_images


def _draw_images(self):
    _orig_draw_images(self)
    if self.settings.viewmode != 'multipane':
        if _state['key'] is not None:   # wyszliśmy z dual z otwartym okienkiem
            _clear_image(self.fm, _state['key'])
            _state['key'] = _state['pending'] = None
            self.win.redrawwin()
            self.win.refresh()
        return
    geo = _state['pending']
    if not geo:
        return
    _state['pending'] = None
    path, top, left, height, width = geo
    try:
        self.fm.image_displayer.draw(path, left + 1, top + 1, width - 2, height - 2)
    except Exception as ex:  # pylint: disable=broad-except
        self.fm.notify("Podgląd obrazka: %s" % ex, bad=True)


_orig_redraw_window = UI.redraw_window


def _redraw_window(self):
    _orig_redraw_window(self)
    _state['pending'] = _state['key']   # po pełnym odświeżeniu narysuj obrazek jeszcze raz


ViewMultipane.draw = _draw
UI.draw_images = _draw_images
UI.redraw_window = _redraw_window
