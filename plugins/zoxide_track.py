# ~/.config/ranger/plugins/zoxide_track.py
# Każdy katalog odwiedzony w rangerze trafia do bazy zoxide,
# więc :z (commands.py) i `z` w terminalu znają też te katalogi.
from __future__ import absolute_import, division, print_function

import subprocess
from shutil import which

import ranger.api

_old_hook_init = ranger.api.hook_init


def _on_cd(signal):
    if signal.new is not None:
        try:
            subprocess.Popen(['zoxide', 'add', '--', signal.new.path],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass


def hook_init(fm):
    if which('zoxide'):
        fm.signal_bind('cd', _on_cd)
    return _old_hook_init(fm)


ranger.api.hook_init = hook_init
