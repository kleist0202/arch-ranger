# ~/.config/ranger/plugins/image_preview_method.py
# Dobiera preview_images_method do terminala, w którym działa ranger:
#   WezTerm / iTerm2 -> iterm2, kitty -> kitty,
#   reszta (np. st pod X11) -> ueberzug (ueberzugpp), awaryjnie w3m.
# Odpala się w hook_init, czyli PO rc.conf, więc ma ostatnie słowo.
from __future__ import absolute_import, division, print_function

import os
from shutil import which

import ranger.api

_old_hook_init = ranger.api.hook_init


def _pick_method():
    env = os.environ
    term_program = env.get('TERM_PROGRAM', '')
    if term_program in ('WezTerm', 'iTerm.app') or 'WEZTERM_PANE' in env:
        return 'iterm2'
    if 'KITTY_WINDOW_ID' in env or env.get('TERM') == 'xterm-kitty':
        return 'kitty'
    if which('ueberzug') and (env.get('DISPLAY') or env.get('WAYLAND_DISPLAY')):
        return 'ueberzug'
    if os.path.exists('/usr/lib/w3m/w3mimgdisplay') and env.get('DISPLAY'):
        return 'w3m'
    return None


def hook_init(fm):
    method = _pick_method()
    if method:
        fm.settings.preview_images_method = method
    else:
        fm.settings.preview_images = False
    return _old_hook_init(fm)


ranger.api.hook_init = hook_init
