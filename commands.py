# ~/.config/ranger/commands.py — własne komendy
from __future__ import absolute_import, division, print_function

import os
import subprocess

from ranger.api.commands import Command
from ranger.core.loader import CommandLoader, CopyLoader


class fzf_select(Command):
    """:fzf_select — wybierz plik/katalog przez fzf (z ukrytymi, bez .git)."""

    def execute(self):
        if subprocess.call(['which', 'fd'], stdout=subprocess.DEVNULL) == 0:
            cmd = "fd --hidden --follow --exclude .git"
        else:
            cmd = ("find -L . -mindepth 1 \\( -path '*/.git' -o -fstype dev "
                   "-o -fstype proc \\) -prune -o -print 2>/dev/null | cut -b3-")
        preview = "--preview '[ -d {} ] && ls -la {} || head -100 {}'"
        proc = self.fm.execute_command(cmd + " | fzf +m " + preview,
                                       universal_newlines=True,
                                       stdout=subprocess.PIPE)
        out, _ = proc.communicate()
        if proc.returncode == 0:
            path = os.path.abspath(out.rstrip('\n'))
            if os.path.isdir(path):
                self.fm.cd(path)
            else:
                self.fm.select_file(path)


class fzf_grep(Command):
    """:fzf_grep — szukaj w treści plików (rg/grep) i skocz do pliku."""

    def execute(self):
        if subprocess.call(['which', 'rg'], stdout=subprocess.DEVNULL) == 0:
            cmd = "rg --line-number --no-heading --color=never --hidden -g '!.git' ''"
        else:
            cmd = "grep -rIn --exclude-dir=.git ''"
        proc = self.fm.execute_command(cmd + " | fzf +m --delimiter : "
                                       "--preview 'sed -n \"{2},+30p\" {1}'",
                                       universal_newlines=True,
                                       stdout=subprocess.PIPE)
        out, _ = proc.communicate()
        if proc.returncode == 0 and out:
            self.fm.select_file(os.path.abspath(out.split(':', 1)[0]))


class mkcd(Command):
    """:mkcd <dir> — utwórz katalog i wejdź do niego."""

    def execute(self):
        dirname = os.path.expanduser(self.rest(1))
        if not dirname:
            return self.fm.notify("Podaj nazwę katalogu", bad=True)
        os.makedirs(dirname, exist_ok=True)
        self.fm.cd(dirname)


_ARCHIVE_EXTS = ('.tar.gz', '.tar.xz', '.tar.bz2', '.tar.zst', '.tgz', '.tar',
                 '.zip', '.7z', '.rar')


def _extract_dir(parent, base):
    """Nowy folder na zawartość archiwum: paczka.zip -> paczka/ (albo paczka_1/, ...)."""
    for ext in _ARCHIVE_EXTS:
        if base.lower().endswith(ext) and len(base) > len(ext):
            name = base[:-len(ext)]
            break
    else:
        name = os.path.splitext(base)[0] or base
    target = os.path.join(parent, name)
    i = 1
    while os.path.exists(target):
        target = os.path.join(parent, '%s_%d' % (name, i))
        i += 1
    os.makedirs(target)
    return target


class extract(Command):
    """:extract — rozpakuj zaznaczone archiwa, każde do osobnego folderu
    nazwanego jak archiwum (paczka.zip -> paczka/)."""

    def execute(self):
        cwd = self.fm.thisdir
        files = [f.path for f in self.fm.thistab.get_selection()]
        if not files:
            return
        for path in files:
            base = os.path.basename(path)
            dest = _extract_dir(cwd.path, base)
            if base.endswith(('.tar.gz', '.tgz', '.tar.xz', '.tar.bz2', '.tar.zst', '.tar')):
                args = ['tar', 'xf', path, '-C', dest]
            elif base.endswith('.zip'):
                args = ['unzip', '-o', path, '-d', dest]
            else:
                args = ['7z', 'x', '-y', '-o' + dest, path]
            obj = CommandLoader(args=args, descr="Rozpakowuję " + base)
            obj.signal_bind('after', lambda *_: cwd.load_content())
            self.fm.loader.add(obj)


class compress(Command):
    """:compress <nazwa.zip|nazwa.tar.gz|...> — spakuj zaznaczone pliki."""

    def execute(self):
        cwd = self.fm.thisdir
        names = [os.path.relpath(f.path, cwd.path)
                 for f in self.fm.thistab.get_selection()]
        if not names:
            return
        archive = self.rest(1) or (names[0] + '.tar.gz')
        if archive.endswith('.zip'):
            args = ['zip', '-r', archive] + names
        elif archive.endswith('.7z'):
            args = ['7z', 'a', archive] + names
        else:
            args = ['tar', 'caf', archive] + names
        obj = CommandLoader(args=args, descr="Pakuję do " + archive)
        obj.signal_bind('after', lambda *_: cwd.load_content())
        self.fm.loader.add(obj)

    def tab(self, tabnum):
        ext = ['.zip', '.tar.gz', '.tar.xz', '.7z']
        return ['compress ' + os.path.basename(self.fm.thisfile.path) + e for e in ext]



class zip(Command):  # pylint: disable=redefined-builtin
    """:zip <nazwa>[.zip] — spakuj zaznaczone pliki do zipa (.zip dopisze się sam)."""

    def execute(self):
        name = self.rest(1)
        if name and not name.endswith('.zip'):
            name += '.zip'
        if not name and self.fm.thisfile:
            name = self.fm.thisfile.basename + '.zip'
        self.fm.execute_console('compress ' + name)

    def tab(self, tabnum):
        return ['zip ' + self.fm.thisfile.basename + '.zip'] if self.fm.thisfile else None

# ===== Tryb dwupanelowy (a la Double Commander) =====

class _SelectingCopyLoader(CopyLoader):
    """CopyLoader, który po skończeniu ustawia kursor na skopiowanym elemencie
    (przy wielu – na ostatnim) we wszystkich tabach otwartych w katalogu docelowym."""

    def generate(self):
        dest = self.original_path
        last = self.copy_buffer[-1].basename if self.copy_buffer else None
        try:
            before = set(os.listdir(dest))
        except OSError:
            before = set()

        for step in CopyLoader.generate(self):
            yield step

        try:
            new = set(os.listdir(dest)) - before
        except OSError:
            return
        # przy konflikcie nazw ranger dopisuje sufiks, np. "dir_" / "dir_0"
        target = None
        if last:
            candidates = sorted(n for n in new if n.startswith(last))
            target = candidates[-1] if candidates else last
        elif new:
            target = sorted(new)[-1]
        if not target or not os.path.lexists(os.path.join(dest, target)):
            return

        directory = self.fm.get_directory(dest)
        directory.load_content(schedule=False)
        directory.move_to_obj(os.path.join(dest, target))
        for tab in self.fm.tabs.values():
            if tab.path == dest:
                # w multipane każdy panel rysuje kursor z tab.pointer
                tab.pointer = directory.pointer
                tab.thisfile = directory.pointed_obj
        self.fm.ui.need_redraw = True


def paste_and_select(fm, dest):
    if not fm.copy_buffer:
        return fm.notify("Nic nie jest skopiowane", bad=True)
    if not os.path.isdir(dest):
        return fm.notify("Nieprawidłowy katalog docelowy: " + dest, bad=True)
    fm.loader.add(_SelectingCopyLoader(fm.copy_buffer, fm.do_cut, False, dest))
    fm.do_cut = False


class paste_select(Command):
    """:paste_select — wklej (jak pp) i ustaw kursor na wklejonym elemencie."""

    def execute(self):
        paste_and_select(self.fm, self.fm.thisdir.path)


def _other_pane_path(fm):
    """Ścieżka następnego taba (drugiego panelu) albo None."""
    others = [k for k in sorted(fm.tabs) if k != fm.current_tab]
    if not others:
        fm.notify("Brak drugiego panelu (otwórz tab lub użyj :dual)", bad=True)
        return None
    after = [k for k in others if k > fm.current_tab]
    return fm.tabs[(after or others)[0]].path


class dual(Command):
    """:dual — przełącz widok dwupanelowy (multipane) <-> zwykły (miller)."""

    def execute(self):
        if self.fm.settings.viewmode == 'multipane':
            self.fm.set_option_from_string('viewmode', 'miller')
            return
        if len(self.fm.tabs) < 2:
            current = self.fm.current_tab
            self.fm.tab_new(path=self.fm.thisdir.path)
            self.fm.tab_open(current)
        self.fm.set_option_from_string('viewmode', 'multipane')


class copy_to_other(Command):
    """:copy_to_other — kopiuj zaznaczone pliki do katalogu drugiego panelu."""

    def execute(self):
        dest = _other_pane_path(self.fm)
        if dest:
            self.fm.copy()
            paste_and_select(self.fm, dest)


class move_to_other(Command):
    """:move_to_other — przenieś zaznaczone pliki do katalogu drugiego panelu."""

    def execute(self):
        dest = _other_pane_path(self.fm)
        if dest:
            self.fm.cut()
            paste_and_select(self.fm, dest)


class sync_other(Command):
    """:sync_other — ustaw drugi panel na ten sam katalog co bieżący."""

    def execute(self):
        dest_tab = None
        for k in sorted(self.fm.tabs):
            if k != self.fm.current_tab:
                dest_tab = k
                break
        if dest_tab is not None:
            self.fm.tabs[dest_tab].enter_dir(self.fm.thisdir.path)
            self.fm.ui.redraw_window()


# ===== Dyski wymienne (pasek z plugins/drives_bar.py) =====

class drive(Command):
    """:drive <n> — zamontuj n-ty dysk z paska USB i wejdź do niego."""

    def execute(self):
        self.fm.drives.open(self.arg(1) or 1)


class eject(Command):
    """:eject [n] — odmontuj i bezpiecznie odłącz dysk (domyślnie ten, na którym jesteś)."""

    def execute(self):
        self.fm.drives.eject(self.arg(1) or None)


class pane_switch(Command):
    """:pane_switch left|right — w trybie dual przełącza panel,
    w zwykłym widoku działa jak domyślna strzałka (katalog wyżej / wejdź)."""

    def execute(self):
        direction = self.arg(1)
        if self.fm.settings.viewmode != 'multipane':
            if direction == 'left':
                self.fm.move(left=1)
            else:
                self.fm.move(right=1)
            return
        keys = list(self.fm.tabs)  # ta sama kolejność, w jakiej rysowane są panele
        idx = keys.index(self.fm.current_tab)
        idx += -1 if direction == 'left' else 1
        if 0 <= idx < len(keys):
            self.fm.tab_open(keys[idx])


# ===== Sortowanie jednym klawiszem =====

_SORT_CYCLE = [
    # (sort, sort_reverse, opis)
    ('natural', False, 'nazwa'),
    ('mtime', False, 'data (najnowsze na górze)'),
    ('size', False, 'rozmiar (największe na górze)'),
    ('extension', False, 'rozszerzenie'),
]


class sort_cycle(Command):
    """:sort_cycle — przełącz na następny sposób sortowania z _SORT_CYCLE."""

    def execute(self):
        current = (self.fm.settings.sort, self.fm.settings.sort_reverse)
        idx = -1
        for i, (sort, reverse, _desc) in enumerate(_SORT_CYCLE):
            if (sort, reverse) == current:
                idx = i
                break
        sort, reverse, desc = _SORT_CYCLE[(idx + 1) % len(_SORT_CYCLE)]
        self.fm.settings.sort = sort
        self.fm.settings.sort_reverse = reverse
        self.fm.notify('Sortowanie: ' + desc)


_SORT_NAMES = {
    # nazwa w :sort -> (sort, sort_reverse)
    'nazwa': ('natural', False),
    'data': ('mtime', False),
    'rozmiar': ('size', False),
    'rozszerzenie': ('extension', False),
    'typ': ('type', False),
    'losowo': ('random', False),
}


class sort(Command):
    """:sort <nazwa|data|rozmiar|rozszerzenie|typ|losowo> [odwrotnie]
    :sort odwrotnie — odwróć bieżącą kolejność. Tab podpowiada nazwy."""

    def execute(self):
        name = self.arg(1)
        if name == 'odwrotnie':
            self.fm.settings.sort_reverse = not self.fm.settings.sort_reverse
            return
        if name not in _SORT_NAMES:
            self.fm.notify('Użycie: :sort ' + '|'.join(_SORT_NAMES) + ' [odwrotnie]',
                           bad=bool(name))
            return
        sort_key, reverse = _SORT_NAMES[name]
        if self.arg(2) == 'odwrotnie':
            reverse = not reverse
        self.fm.settings.sort = sort_key
        self.fm.settings.sort_reverse = reverse

    def tab(self, tabnum):
        if self.arg(2) or self.rest(1).endswith(' '):
            return ['sort ' + self.arg(1) + ' odwrotnie']
        start = self.arg(1)
        return ['sort ' + n for n in list(_SORT_NAMES) + ['odwrotnie'] if n.startswith(start)]


# ===== Podgląd =====

class preview(Command):
    """:preview — włącz/wyłącz cały podgląd (pliki, katalogi, obrazki).
    :preview obrazki — włącz/wyłącz tylko podgląd obrazków."""

    def execute(self):
        settings = self.fm.settings
        if self.arg(1) == 'obrazki':
            settings.preview_images = not settings.preview_images
            state = settings.preview_images
            what = 'Podgląd obrazków'
        else:
            state = not settings.preview_files
            settings.preview_files = state
            settings.preview_directories = state
            settings.preview_images = state
            what = 'Podgląd'
        if not state:
            # obrazek (ueberzug/kitty) wisi poza curses – zdejmij go
            ui = self.fm.ui
            try:
                self.fm.image_displayer.clear(0, 0, ui.termsize[1], ui.termsize[0])
            except Exception:  # pylint: disable=broad-except
                pass
        self.fm.ui.redraw_window()
        self.fm.notify(what + (': włączony' if state else ': wyłączony'))

    def tab(self, tabnum):
        return ['preview obrazki']


# ===== Dual: zamiana i porównanie paneli (jak w Double Commanderze) =====

def _pane_tabs(fm):
    """(bieżący tab, drugi tab) albo None, gdy nie ma drugiego panelu."""
    others = [k for k in sorted(fm.tabs) if k != fm.current_tab]
    if not others:
        fm.notify("Brak drugiego panelu (otwórz tab lub użyj :dual)", bad=True)
        return None
    after = [k for k in others if k > fm.current_tab]
    return fm.tabs[fm.current_tab], fm.tabs[(after or others)[0]]


class swap_panes(Command):
    """:swap_panes — zamień katalogi w lewym i prawym panelu."""

    def execute(self):
        tabs = _pane_tabs(self.fm)
        if not tabs:
            return
        this, other = tabs
        this_path, other_path = this.thisdir.path, other.thisdir.path
        this.enter_dir(other_path)
        other.enter_dir(this_path)
        self.fm.ui.redraw_window()


def _loaded_files(directory):
    if directory.files is None:
        directory.load_content(schedule=False)
    return {f.basename: f for f in directory.files or []}


class compare_panes(Command):
    """:compare_panes — zaznacz w obu panelach pliki, których nie ma po drugiej
    stronie, oraz nowszą wersję plików, które się różnią (rozmiar/data)."""

    def execute(self):
        tabs = _pane_tabs(self.fm)
        if not tabs:
            return
        dir_a, dir_b = tabs[0].thisdir, tabs[1].thisdir
        files_a, files_b = _loaded_files(dir_a), _loaded_files(dir_b)
        for directory in (dir_a, dir_b):
            for fobj in directory.files or []:
                directory.mark_item(fobj, False)

        count = 0
        for name, fa in files_a.items():
            fb = files_b.get(name)
            if fb is None:
                dir_a.mark_item(fa, True)
                count += 1
            elif not fa.is_directory and not fb.is_directory and (
                    fa.size != fb.size or int(fa.stat.st_mtime) != int(fb.stat.st_mtime)):
                if fa.stat.st_mtime >= fb.stat.st_mtime:
                    dir_a.mark_item(fa, True)
                else:
                    dir_b.mark_item(fb, True)
                count += 1
        for name, fb in files_b.items():
            if name not in files_a:
                dir_b.mark_item(fb, True)
                count += 1

        self.fm.ui.redraw_window()
        if count:
            self.fm.notify("Różnice: %d (zaznaczone – F5 skopiuje je na drugą stronę)" % count)
        else:
            self.fm.notify("Katalogi są takie same")


# ===== Skakanie do katalogów (zoxide) =====

class z(Command):
    """:z <fragment nazwy> — skocz do najczęściej używanego pasującego katalogu
    (zoxide; ranger sam zapisuje odwiedzane katalogi, patrz plugins/zoxide_track.py)."""

    def execute(self):
        if not self.arg(1):
            self.fm.notify('Użycie: :z <fragment nazwy katalogu>', bad=True)
            return
        try:
            out = subprocess.run(['zoxide', 'query', '--exclude', self.fm.thisdir.path, '--']
                                 + self.args[1:], capture_output=True, text=True, check=False)
        except FileNotFoundError:
            self.fm.notify('Brak zoxide – zainstaluj: sudo pacman -S zoxide', bad=True)
            return
        path = out.stdout.strip()
        if out.returncode != 0 or not path:
            self.fm.notify('Nie znalazłem katalogu: ' + self.rest(1), bad=True)
            return
        self.fm.cd(path)

    def tab(self, tabnum):
        try:
            out = subprocess.run(['zoxide', 'query', '--list', '--'] + self.args[1:],
                                 capture_output=True, text=True, check=False)
        except FileNotFoundError:
            return None
        return ['z ' + p for p in out.stdout.splitlines()[:20]]


# ===== Rozmiar katalogów =====

class du(Command):
    """:du — policz rozmiar (z zawartością) wszystkich katalogów w bieżącym widoku.
    Na dużych katalogach chwilę trwa; dc liczy tylko dla zaznaczonych."""

    def execute(self):
        dirs = [f for f in self.fm.thisdir.files or [] if f.is_directory]
        for fobj in dirs:
            fobj.look_up_cumulative_size()
        if self.fm.settings.sort == 'size':
            self.fm.thisdir.sort()
        self.fm.ui.status.request_redraw()
        self.fm.ui.redraw_main_column()
        self.fm.notify('Policzono rozmiar %d katalogów' % len(dirs))


class toggle_hidden(Command):
    """:toggle_hidden — pokaż/ukryj ukryte pliki (to samo co zh)."""

    def execute(self):
        self.fm.settings.show_hidden = not self.fm.settings.show_hidden
        self.fm.notify('Ukryte pliki: ' + ('widoczne' if self.fm.settings.show_hidden else 'schowane'))
