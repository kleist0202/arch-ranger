# ~/.config/ranger/plugins/drives_bar.py
# Pasek dysków wymiennych (pendrive, karty SD, dyski USB) pod paskiem tytułu.
#  - pojawia się sam, gdy podłączysz urządzenie (odświeżanie co ~2 s, z lsblk),
#  - LPM na wpisie: zamontuj (udisksctl, bez sudo) i wejdź do katalogu,
#  - PPM na wpisie: odmontuj i bezpiecznie odłącz,
#  - z klawiatury: :drive <n>, :eject [n] (mapowania w rc.conf).
from __future__ import absolute_import, division, print_function

import curses
import json
import os
import subprocess
import time

from ranger.gui.color import get_color, bold
from ranger.gui.ui import UI
from ranger.gui.widgets import Widget

REFRESH_SECONDS = 2.0
LSBLK_COLUMNS = 'NAME,PATH,LABEL,SIZE,MOUNTPOINT,RM,TRAN,TYPE,FSTYPE,MODEL'
SKIP_FSTYPES = ('swap', 'crypto_LUKS', 'LVM2_member')


def _attr(fg, bg=-1, extra=0):
    if fg >= getattr(curses, 'COLORS', 8):
        fg = curses.COLOR_WHITE
    if bg >= getattr(curses, 'COLORS', 8):
        bg = curses.COLOR_BLACK
    return curses.color_pair(get_color(fg, bg)) | extra


def _run(args, timeout=30):
    try:
        proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as ex:
        return 1, str(ex)
    return proc.returncode, (proc.stderr or proc.stdout).strip()


def list_drives():
    """Partycje z systemem plików na dyskach wymiennych / USB."""
    try:
        out = subprocess.run(['lsblk', '-J', '-o', LSBLK_COLUMNS],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             universal_newlines=True, timeout=3).stdout
        data = json.loads(out)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []

    drives = []
    for disk in data.get('blockdevices', []):
        if disk.get('type') != 'disk':
            continue
        if disk.get('rm') not in (True, '1', 1) and disk.get('tran') != 'usb':
            continue
        parts = [c for c in disk.get('children') or [] if c.get('fstype')]
        if not parts and disk.get('fstype'):
            parts = [disk]
        for part in parts:
            if part.get('fstype') in SKIP_FSTYPES:
                continue
            name = (part.get('label') or (disk.get('model') or '').strip()
                    or part.get('name'))
            drives.append({
                'dev': part.get('path') or '/dev/' + part['name'],
                'disk': disk.get('path') or '/dev/' + disk['name'],
                'name': name,
                'size': part.get('size') or '',
                'mount': part.get('mountpoint'),
            })

    # takie same nazwy (np. dwa pendrive'y "KINGSTON") -> dopisz urządzenie
    names = [d['name'] for d in drives]
    for item in drives:
        if names.count(item['name']) > 1:
            item['name'] += '(%s)' % os.path.basename(item['dev'])
    return drives


class Drives(object):
    def __init__(self, fm):
        self.fm = fm
        self.items = []
        self.stamp = 0.0

    def refresh(self, force=False):
        """Zwraca True, jeśli lista się zmieniła."""
        if not force and time.time() - self.stamp < REFRESH_SECONDS:
            return False
        self.stamp = time.time()
        new = list_drives()
        changed = new != self.items
        self.items = new
        return changed

    def _get(self, num):
        try:
            return self.items[int(num) - 1]
        except (ValueError, IndexError):
            self.fm.notify("Nie ma dysku nr %s" % num, bad=True)
            return None

    def _by_dev(self, dev):
        for item in self.items:
            if item['dev'] == dev:
                return item
        return None

    def _current(self):
        path = self.fm.thisdir.path
        for item in self.items:
            mount = item['mount']
            if mount and (path == mount or path.startswith(mount + os.sep)):
                return item
        self.fm.notify("Nie jesteś na żadnym dysku wymiennym", bad=True)
        return None

    def open(self, num):
        self.refresh(force=True)
        item = self._get(num)
        if not item:
            return
        if not item['mount']:
            code, msg = _run(['udisksctl', 'mount', '--no-user-interaction',
                              '-b', item['dev']])
            if code:
                self.fm.notify("Montowanie nie powiodło się: " + msg, bad=True)
                return
            self.refresh(force=True)
            item = self._by_dev(item['dev'])
        if item and item['mount']:
            self.fm.cd(item['mount'])
        self._changed()

    def _busy(self, mount):
        """Czy w kolejce rangera jest operacja dotycząca tego dysku."""
        def inside(path):
            path = str(path or '')
            return path == mount or path.startswith(mount + os.sep)

        for job in list(self.fm.loader.queue):
            if inside(getattr(job, 'original_path', None)):
                return True
            if any(inside(f.path) for f in getattr(job, 'copy_buffer', ()) or ()):
                return True
            if mount in str(getattr(job, 'description', '')):
                return True
        return False

    def eject(self, num=None):
        self.refresh(force=True)
        item = self._get(num) if num else self._current()
        if not item:
            return
        mount = item['mount']
        if mount:
            if self._busy(mount):
                self.fm.notify("Trwa kopiowanie na/z " + item['name'] +
                               " – poczekaj, aż się skończy (podgląd: w)", bad=True)
                return

            # jawny zapis buforów na dysk (umount też to robi, ale tu widać, co się dzieje)
            self.fm.notify("Zapisywanie danych na " + item['name'] + "…")
            self.fm.ui.redraw()
            code, msg = _run(['sync', '-f', mount], timeout=600)
            if code:
                self.fm.notify("sync nie powiódł się: " + msg, bad=True)
                return

            # wyjdź z dysku we wszystkich tabach, inaczej będzie "target is busy"
            home = os.path.expanduser('~')
            for tab in self.fm.tabs.values():
                if tab.path == mount or tab.path.startswith(mount + os.sep):
                    if tab is self.fm.thistab:
                        self.fm.cd(home)
                    else:
                        tab.enter_dir(home)
            code, msg = _run(['udisksctl', 'unmount', '--no-user-interaction',
                              '-b', item['dev']])
            if code:
                self.fm.notify("Odmontowanie nie powiodło się: " + msg, bad=True)
                return
        self.refresh(force=True)
        if not any(i['mount'] for i in self.items if i['disk'] == item['disk']):
            _run(['udisksctl', 'power-off', '--no-user-interaction',
                  '-b', item['disk']])
            self.refresh(force=True)
            self.fm.notify("Można bezpiecznie wyjąć: " + item['name'])
        else:
            self.fm.notify("Odmontowano: " + item['name'])
        self._changed()

    def _changed(self):
        bar = getattr(self.fm.ui, 'drivebar', None)
        if bar:
            bar.sync_visibility()


class DriveBar(Widget):
    def __init__(self, win, drives):
        Widget.__init__(self, win)
        self.drives = drives
        self.hits = []
        self.visible = bool(drives.items)

    def sync_visibility(self):
        self.need_redraw = True
        visible = bool(self.drives.items)
        if visible != self.visible:
            self.visible = visible
            self.fm.ui.update_size()
            self.fm.ui.redraw_window()

    def poke(self):
        Widget.poke(self)
        if self.drives.refresh():
            self.sync_visibility()

    def draw(self):
        width = self.wid
        self.hits = []
        self.addstr(0, 0, ' ' * max(0, width - 1), _attr(-1))
        col = 0

        label = ' ⏏ USB '
        self.addstr(0, col, label, _attr(234, 179, bold))
        col += len(label) + 1

        for num, item in enumerate(self.drives.items, 1):
            mounted = bool(item['mount'])
            text = ' %s %d:%s %s ' % ('●' if mounted else '○', num, item['name'], item['size'])
            if col + len(text) >= width:
                break
            attr = (_attr(234, 150, bold) if mounted
                    else _attr(189, 237))
            self.addstr(0, col, text, attr)
            self.hits.append((col, col + len(text), num))
            col += len(text) + 1

        hint = 'LPM: otwórz  PPM: wysuń '
        if col + len(hint) < width:
            self.addstr(0, width - len(hint) - 1, hint, _attr(243))

    def click(self, event):
        x = event.x - self.x
        for start, end, num in self.hits:
            if start <= x < end:
                if event.pressed(1):
                    self.drives.open(num)
                elif event.pressed(3):
                    self.drives.eject(num)
                return True
        return False


_orig_setup = UI.setup
_orig_update_size = UI.update_size


def _setup(self):
    _orig_setup(self)
    self.fm.drives = Drives(self.fm)
    self.fm.drives.refresh(force=True)
    self.drivebar = DriveBar(self.win, self.fm.drives)
    self.add_child(self.drivebar)


def _update_size(self):
    _orig_update_size(self)
    bar = getattr(self, 'drivebar', None)
    if bar is None or not bar.visible:
        return
    rows, cols = self.termsize
    top = 2 if self.settings.status_bar_on_top else 1
    bar.resize(top, 0, 1, cols)
    for widget in (self.browser, self.taskview, self.pager):
        widget.resize(top + 1, 0, rows - 3, cols)


UI.setup = _setup
UI.update_size = _update_size
