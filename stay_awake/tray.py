"""Optional system tray integration via pystray. Gracefully degrades if
pystray/Pillow aren't installed."""
from __future__ import annotations
import threading
from typing import Callable, Optional

try:
    import pystray  # type: ignore
    from pystray import MenuItem as Item, Menu  # type: ignore
    _HAS_TRAY = True
except ImportError:
    pystray = None  # type: ignore
    _HAS_TRAY = False

from .icon import make_icon


class Tray:
    def __init__(
        self,
        on_toggle: Callable[[], None],
        on_show: Callable[[], None],
        on_quit: Callable[[], None],
        is_active: Callable[[], bool],
    ) -> None:
        self._on_toggle = on_toggle
        self._on_show = on_show
        self._on_quit = on_quit
        self._is_active = is_active
        self._icon = None
        self._thread: Optional[threading.Thread] = None

    @property
    def available(self) -> bool:
        return _HAS_TRAY

    def start(self) -> None:
        if not _HAS_TRAY or self._icon is not None:
            return

        def _state_text(_item):
            return "Pause" if self._is_active() else "Resume"

        menu = Menu(
            Item("Show window", lambda *_: self._on_show(), default=True),
            Item(_state_text, lambda *_: self._on_toggle()),
            Menu.SEPARATOR,
            Item("Quit", lambda *_: self._on_quit()),
        )
        self._icon = pystray.Icon(
            "StayAwake",
            icon=make_icon(active=self._is_active()),
            title="StayAwake",
            menu=menu,
        )
        self._thread = threading.Thread(target=self._icon.run, daemon=True, name="StayAwake-tray")
        self._thread.start()

    def update(self) -> None:
        if self._icon is None:
            return
        try:
            self._icon.icon = make_icon(active=self._is_active())
            self._icon.title = "StayAwake — " + ("active" if self._is_active() else "paused")
        except Exception:
            pass

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
            self._icon = None
            self._thread = None
