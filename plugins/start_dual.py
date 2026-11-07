# ~/.config/ranger/plugins/start_dual.py
# Ranger startuje od razu w trybie dwupanelowym (to samo co ,d / :dual).
from __future__ import absolute_import, division, print_function

import ranger.api

_old_hook_ready = ranger.api.hook_ready


def hook_ready(fm):
    if fm.settings.viewmode != 'multipane':
        fm.execute_console('dual')
    return _old_hook_ready(fm)


ranger.api.hook_ready = hook_ready
