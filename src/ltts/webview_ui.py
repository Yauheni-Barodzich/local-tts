"""WinForms / WebView2: выполнять код только в UI-потоке окна."""

from __future__ import annotations

import logging
from typing import Any, Callable

_LOG = logging.getLogger(__name__)


def run_on_ui(form: Any, fn: Callable[[], None], *, block: bool = True) -> None:
    if form is None:
        fn()
        return
    try:
        from System import Action

        if not form.InvokeRequired:
            fn()
            return
        action = Action(fn)
        if block:
            form.Invoke(action)
        else:
            form.BeginInvoke(action)
    except Exception as e:
        _LOG.warning("run_on_ui: %s", e)


def run_on_ui_async(form: Any, fn: Callable[[], None]) -> None:
    run_on_ui(form, fn, block=False)
