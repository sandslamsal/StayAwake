"""Cross-platform wake-keeping using OS-native idle inhibitors.

No mouse/keyboard simulation — uses the same APIs that media players use to
prevent sleep, so we never interfere with whatever the user is doing.
"""
from __future__ import annotations
import ctypes
import shutil
import subprocess
import sys
import threading
import time
from typing import Callable, Optional


# --- Windows -----------------------------------------------------------------
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002


def _win_set(flags: int) -> bool:
    try:
        return ctypes.windll.kernel32.SetThreadExecutionState(ctypes.c_uint(flags)) != 0
    except (AttributeError, OSError):
        return False


# --- POSIX -------------------------------------------------------------------
class _SubprocessInhibitor:
    """Holds a long-running subprocess that keeps the system awake."""

    def __init__(self, argv: list[str]) -> None:
        self.argv = argv
        self.proc: Optional[subprocess.Popen] = None

    def start(self) -> bool:
        if self.proc and self.proc.poll() is None:
            return True
        try:
            self.proc = subprocess.Popen(
                self.argv,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except (FileNotFoundError, OSError):
            self.proc = None
            return False

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            except OSError:
                pass
        self.proc = None


# --- Public API --------------------------------------------------------------
class KeepAwake:
    """Start/stop wake-keeping. Thread-safe; idempotent start/stop."""

    def __init__(self, on_state_change: Optional[Callable[[bool], None]] = None) -> None:
        self._lock = threading.Lock()
        self._active = False
        self._on_state_change = on_state_change
        self._inhibitor: Optional[_SubprocessInhibitor] = None
        self._heartbeat_stop: Optional[threading.Event] = None
        self._heartbeat_thread: Optional[threading.Thread] = None

    @property
    def active(self) -> bool:
        return self._active

    def start(self, interval_seconds: int = 60) -> bool:
        with self._lock:
            if self._active:
                return True
            ok = self._start_platform(interval_seconds)
            if ok:
                self._active = True
                if self._on_state_change:
                    self._on_state_change(True)
            return ok

    def stop(self) -> None:
        with self._lock:
            if not self._active:
                return
            self._stop_platform()
            self._active = False
            if self._on_state_change:
                self._on_state_change(False)

    # --- platform helpers ---
    def _start_platform(self, interval_seconds: int) -> bool:
        if sys.platform.startswith("win"):
            if _win_set(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED):
                # Re-assert periodically; some power policies expire the request.
                self._start_heartbeat(interval_seconds)
                return True
            return False

        if sys.platform == "darwin":
            if shutil.which("caffeinate"):
                self._inhibitor = _SubprocessInhibitor(["caffeinate", "-dimsu"])
                return self._inhibitor.start()
            return False

        # Linux / *BSD
        if shutil.which("systemd-inhibit"):
            self._inhibitor = _SubprocessInhibitor([
                "systemd-inhibit",
                "--what=idle:sleep:handle-lid-switch",
                "--who=StayAwake",
                "--why=User requested keep-awake",
                "--mode=block",
                "sleep", "infinity",
            ])
            if self._inhibitor.start():
                return True
        if shutil.which("xdg-screensaver"):
            self._start_heartbeat(interval_seconds, posix_fallback=True)
            return True
        return False

    def _stop_platform(self) -> None:
        if sys.platform.startswith("win"):
            _win_set(ES_CONTINUOUS)
        if self._inhibitor:
            self._inhibitor.stop()
            self._inhibitor = None
        self._stop_heartbeat()

    def _start_heartbeat(self, interval: int, posix_fallback: bool = False) -> None:
        self._stop_heartbeat()
        stop_evt = threading.Event()
        self._heartbeat_stop = stop_evt

        def _run() -> None:
            while not stop_evt.wait(max(5, interval)):
                if sys.platform.startswith("win"):
                    _win_set(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED)
                elif posix_fallback and shutil.which("xdg-screensaver"):
                    try:
                        subprocess.run(
                            ["xdg-screensaver", "reset"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=5,
                        )
                    except (OSError, subprocess.SubprocessError):
                        pass

        t = threading.Thread(target=_run, daemon=True, name="StayAwake-heartbeat")
        self._heartbeat_thread = t
        t.start()

    def _stop_heartbeat(self) -> None:
        if self._heartbeat_stop:
            self._heartbeat_stop.set()
        self._heartbeat_stop = None
        self._heartbeat_thread = None


def platform_label() -> str:
    if sys.platform.startswith("win"):
        return "Windows (SetThreadExecutionState)"
    if sys.platform == "darwin":
        return "macOS (caffeinate)"
    if shutil.which("systemd-inhibit"):
        return "Linux (systemd-inhibit)"
    return f"{sys.platform} (best-effort)"
