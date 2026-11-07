# ~/.config/ranger/colorschemes/nocturne.py
# Ciemny schemat inspirowany Tokyo Night (kolory xterm-256).
# Włączenie: set colorscheme nocturne
from __future__ import absolute_import, division, print_function

import curses

from ranger.gui.colorscheme import ColorScheme
from ranger.gui.color import default, normal, bold, reverse, dim, default_colors

# ── paleta ──────────────────────────────────────────────────
FG = 189          # #c0caf5 tekst
COMMENT = 243     # szary – rzeczy mniej ważne
MUTED = 60        # ciemny niebiesko-szary
SEL_BG = 237      # tło kursora (aktywny panel)
SEL_BG_DIM = 235  # tło kursora (nieaktywny panel)
DARK = 234        # tekst na kolorowym tle
BLUE = 111        # katalogi
CYAN = 117        # linki
GREEN = 150       # wykonywalne
YELLOW = 179      # obrazy
ORANGE = 215      # zaznaczone
MAGENTA = 141     # audio / wideo
PINK = 211        # archiwa
RED = 204         # błędy, zepsute linki
TEAL = 73         # dokumenty


# odpowiedniki kolorów palety w 8 podstawowych
_FALLBACK = {
    FG: 7, COMMENT: 7, MUTED: 4, DARK: 0,
    BLUE: 4, CYAN: 6, GREEN: 2, YELLOW: 3, ORANGE: 3,
    MAGENTA: 5, PINK: 5, RED: 1, TEAL: 6,
}


def _few_colors():
    return getattr(curses, 'COLORS', 8) < 256


def _fit(color, is_bg=False):
    """Kolor xterm-256 -> najbliższy z 8 podstawowych, gdy terminal ma mniej kolorów
    (tmux z TERM=screen, konsola TTY). Bez tego ranger się wywraca."""
    if color < 8 or color >= 256 or getattr(curses, 'COLORS', 8) > color:
        return color
    if color in _FALLBACK:
        return _FALLBACK[color]
    if color >= 232:                       # skala szarości
        result = 0 if color - 232 < 8 else 7
    elif color >= 16:                      # kostka 6x6x6
        idx = color - 16
        red, green, blue = idx // 36, idx // 6 % 6, idx % 6
        result = (red >= 3) * 1 + (green >= 3) * 2 + (blue >= 3) * 4
    else:                                  # jasne 8-15
        result = color - 8
    if result == 0 and not is_bg:
        result = 7                         # czarny tekst na domyślnym tle byłby niewidoczny
    return result


class Nocturne(ColorScheme):
    progress_bar_color = BLUE

    def use(self, context):  # pylint: disable=too-many-branches,too-many-statements
        fg, bg, attr = default_colors

        if context.reset:
            return default_colors

        elif context.in_browser:
            fg = FG
            attr = normal

            if context.border:
                fg = MUTED

            # typy plików
            if context.document:
                fg = TEAL
            if context.media:
                fg = YELLOW if context.image else MAGENTA
            if context.container:
                fg = PINK
            if context.directory:
                fg = BLUE
                attr |= bold
            elif context.executable and not any((context.media, context.container,
                                                 context.fifo, context.socket)):
                fg = GREEN
                attr |= bold
            if context.socket:
                fg = MAGENTA
                attr |= bold
            if context.fifo or context.device:
                fg = ORANGE
                if context.device:
                    attr |= bold
            if context.link:
                fg = CYAN if context.good else RED
            if context.empty or context.error:
                fg = RED

            # rozmiar / info po prawej
            if context.infostring and not context.selected:
                fg = COMMENT

            # skopiowane / wycięte – przygaszone
            if not context.selected and (context.cut or context.copied):
                fg = COMMENT
                attr |= dim

            # tagi
            if context.tag_marker and not context.selected:
                fg = RED
                attr |= bold

            # zaznaczone (Space)
            if context.marked:
                fg = ORANGE
                attr |= bold

            # kursor: tło zamiast odwrócenia kolorów
            if context.selected and _few_colors():
                attr |= reverse            # brak ciemnoszarego tła – odwróć kolory
            elif context.selected:
                if context.inactive_pane or not context.main_column:
                    bg = SEL_BG_DIM
                else:
                    bg = SEL_BG
                    attr |= bold

            if context.badinfo:
                fg = RED

        elif context.in_titlebar:
            attr |= bold
            if context.hostname:
                fg = RED if context.bad else GREEN
            elif context.directory:
                fg = BLUE
            elif context.tab:
                if context.good:
                    fg, bg = DARK, BLUE
                else:
                    fg = COMMENT
            elif context.link:
                fg = CYAN
            else:
                fg = FG

        elif context.in_statusbar:
            fg = COMMENT
            if context.permissions:
                fg = CYAN if context.good else RED
            if context.owner or context.group:
                fg = MUTED
            if context.mtime:
                fg = COMMENT
            if context.marked:
                fg, bg = DARK, ORANGE
                attr |= bold
            if context.frozen:
                fg, bg = DARK, CYAN
                attr |= bold
            if context.message:
                fg = RED if context.bad else FG
                if context.bad:
                    attr |= bold
            if context.loaded:
                bg = self.progress_bar_color
                fg = DARK
            if context.vcsinfo:
                fg = BLUE
            if context.vcscommit:
                fg = YELLOW
            if context.vcsdate:
                fg = CYAN

        elif context.in_console:
            fg = FG

        if context.text:
            if context.highlight:
                attr |= reverse

        if context.in_taskview:
            fg = FG
            if context.title:
                fg = BLUE
                attr |= bold
            if context.selected:
                bg = SEL_BG
            if context.loaded:
                if context.selected:
                    fg = self.progress_bar_color
                else:
                    bg = self.progress_bar_color
                    fg = DARK

        # git
        if context.vcsfile and not context.selected:
            attr &= ~bold
            if context.vcsconflict:
                fg = MAGENTA
            elif context.vcsuntracked:
                fg = CYAN
            elif context.vcschanged:
                fg = ORANGE
            elif context.vcsunknown:
                fg = RED
            elif context.vcsstaged:
                fg = GREEN
            elif context.vcssync:
                fg = GREEN
            elif context.vcsignored:
                fg = COMMENT
        elif context.vcsremote and not context.selected:
            attr &= ~bold
            if context.vcssync or context.vcsnone:
                fg = GREEN
            elif context.vcsbehind:
                fg = RED
            elif context.vcsahead:
                fg = BLUE
            elif context.vcsdiverged:
                fg = MAGENTA
            elif context.vcsunknown:
                fg = RED

        return _fit(fg), _fit(bg, is_bg=True), attr
