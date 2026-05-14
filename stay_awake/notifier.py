"""Cross-platform desktop notifications + daily reminder scheduling.

Notifications use OS-native tooling (osascript / notify-send / Windows toast
via PowerShell) so we don't have to ship a notification library.
"""
from __future__ import annotations
import ctypes
import datetime as _dt
import shutil
import subprocess
import sys
import threading
from typing import Optional


APP_NAME = "StayAwake"


# --- Notify ------------------------------------------------------------------
def notify(title: str, message: str) -> bool:
    if sys.platform == "darwin":
        return _notify_macos(title, message)
    if sys.platform.startswith("win"):
        return _notify_windows(title, message)
    return _notify_linux(title, message)


def _notify_macos(title: str, message: str) -> bool:
    if not shutil.which("osascript"):
        return False
    safe_title = title.replace('"', "'")
    safe_msg = message.replace('"', "'")
    script = f'display notification "{safe_msg}" with title "{safe_title}"'
    try:
        subprocess.run(["osascript", "-e", script], check=False, timeout=5)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _notify_linux(title: str, message: str) -> bool:
    if shutil.which("notify-send"):
        try:
            subprocess.run(
                ["notify-send", "-a", APP_NAME, title, message],
                check=False, timeout=5,
            )
            return True
        except (OSError, subprocess.SubprocessError):
            pass
    return False


def _notify_windows(title: str, message: str) -> bool:
    # First try the Action Center toast via PowerShell (no external dep).
    ps = (
        "[Windows.UI.Notifications.ToastNotificationManager,"
        "Windows.UI.Notifications,ContentType=WindowsRuntime] | Out-Null;"
        f"$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent("
        "[Windows.UI.Notifications.ToastTemplateType]::ToastText02);"
        f"$t.GetElementsByTagName('text')[0].AppendChild($t.CreateTextNode('{title}')) | Out-Null;"
        f"$t.GetElementsByTagName('text')[1].AppendChild($t.CreateTextNode('{message}')) | Out-Null;"
        f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('{APP_NAME}')"
        ".Show([Windows.UI.Notifications.ToastNotification]::new($t));"
    )
    if shutil.which("powershell"):
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps],
                check=False, timeout=8,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            return True
        except (OSError, subprocess.SubprocessError):
            pass
    # Fallback: classic MessageBox.
    try:
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)
        return True
    except (AttributeError, OSError):
        return False


# --- Daily reminder ----------------------------------------------------------
class DailyReminder:
    """Schedules a one-shot notification at the next occurrence of `hh:mm`,
    then re-arms for the next day. Cheap: a single sleeping thread."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._hh = 15
        self._mm = 0
        self._message = "Time to fill out your timesheet."
        self._enabled = False

    def configure(self, time_str: str, message: str, enabled: bool) -> None:
        with self._lock:
            self._hh, self._mm = _parse_hhmm(time_str)
            self._message = message
            was_enabled = self._enabled
            self._enabled = enabled
        if enabled and not was_enabled:
            self.start()
        elif not enabled and was_enabled:
            self.stop()
        elif enabled:
            # Restart so the new time/message takes effect immediately.
            self.stop()
            self.start()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        t = threading.Thread(target=self._run, daemon=True, name="StayAwake-reminder")
        self._thread = t
        t.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread = None

    def next_fire_at(self) -> _dt.datetime:
        now = _dt.datetime.now()
        with self._lock:
            target = now.replace(hour=self._hh, minute=self._mm, second=0, microsecond=0)
        if target <= now:
            target = target + _dt.timedelta(days=1)
        return target

    def _run(self) -> None:
        while not self._stop.is_set():
            target = self.next_fire_at()
            wait = max(1.0, (target - _dt.datetime.now()).total_seconds())
            if self._stop.wait(wait):
                return
            with self._lock:
                msg = self._message
            notify(f"{APP_NAME} Reminder", msg)


def _parse_hhmm(s: str) -> tuple[int, int]:
    try:
        h, m = s.strip().split(":")
        hh, mm = int(h), int(m)
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            return hh, mm
    except (ValueError, AttributeError):
        pass
    return 15, 0
