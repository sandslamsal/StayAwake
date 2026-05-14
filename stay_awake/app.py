"""Tkinter GUI for StayAwake.

Compact, single-window app. Uses ttk for native look on every platform.
"""
from __future__ import annotations
import sys
import tkinter as tk
from tkinter import ttk

from . import APP_NAME, __version__, __url__
from . import config as _config
from .core import KeepAwake, platform_label
from .notifier import DailyReminder, notify
from .tray import Tray


PALETTE = {
    "bg": "#0f172a",
    "panel": "#111c33",
    "muted": "#64748b",
    "text": "#e2e8f0",
    "accent": "#22c55e",
    "accent_dim": "#16a34a",
    "warn": "#f59e0b",
    "danger": "#ef4444",
}


class App:
    def __init__(self) -> None:
        self.cfg = _config.load()
        self.keep = KeepAwake(on_state_change=lambda _a: self._refresh_state())
        self.reminder = DailyReminder()

        self.root = tk.Tk()
        self.root.title(f"{APP_NAME}")
        self.root.minsize(380, 320)
        self.root.configure(bg=PALETTE["bg"])
        try:
            self.root.tk.call("tk", "scaling", 1.2)
        except tk.TclError:
            pass
        self._setup_styles()
        self._build_ui()

        self.tray = Tray(
            on_toggle=self._toggle_keepawake,
            on_show=self._show_window,
            on_quit=self._quit,
            is_active=lambda: self.keep.active,
        )
        self.tray.start()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.reminder.configure(
            self.cfg["reminder_time"],
            self.cfg["reminder_message"],
            bool(self.cfg["reminder_enabled"]),
        )

        if self.cfg.get("auto_start_keep_awake"):
            self._toggle_keepawake()
        if self.cfg.get("start_minimized") and self.tray.available:
            self.root.withdraw()

        self._tick_status()

    # --- UI ------------------------------------------------------------
    def _setup_styles(self) -> None:
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=PALETTE["bg"])
        style.configure("Panel.TFrame", background=PALETTE["panel"])
        style.configure(
            "TLabel",
            background=PALETTE["bg"],
            foreground=PALETTE["text"],
            font=("Helvetica", 10),
        )
        style.configure(
            "Title.TLabel",
            background=PALETTE["bg"],
            foreground=PALETTE["text"],
            font=("Helvetica", 18, "bold"),
        )
        style.configure(
            "Muted.TLabel",
            background=PALETTE["bg"],
            foreground=PALETTE["muted"],
            font=("Helvetica", 9),
        )
        style.configure(
            "Status.TLabel",
            background=PALETTE["panel"],
            foreground=PALETTE["accent"],
            font=("Helvetica", 11, "bold"),
        )
        style.configure(
            "Accent.TButton",
            background=PALETTE["accent"],
            foreground="#04140a",
            font=("Helvetica", 11, "bold"),
            padding=(16, 8),
            borderwidth=0,
        )
        style.map(
            "Accent.TButton",
            background=[("active", PALETTE["accent_dim"]), ("pressed", PALETTE["accent_dim"])],
        )
        style.configure(
            "Danger.TButton",
            background=PALETTE["danger"],
            foreground="#1a0606",
            font=("Helvetica", 11, "bold"),
            padding=(16, 8),
            borderwidth=0,
        )
        style.map("Danger.TButton", background=[("active", "#dc2626")])
        style.configure(
            "TEntry",
            fieldbackground="#1e293b",
            foreground=PALETTE["text"],
            insertcolor=PALETTE["text"],
            bordercolor=PALETTE["muted"],
        )
        style.configure(
            "TCheckbutton",
            background=PALETTE["bg"],
            foreground=PALETTE["text"],
        )

    def _build_ui(self) -> None:
        wrap = ttk.Frame(self.root, padding=18)
        wrap.pack(fill="both", expand=True)

        header = ttk.Frame(wrap)
        header.pack(fill="x")
        ttk.Label(header, text=APP_NAME, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text=f"by SyncStruct  •  {__url__}",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 12))

        # Status panel
        panel = ttk.Frame(wrap, style="Panel.TFrame", padding=14)
        panel.pack(fill="x", pady=(0, 14))
        self.status_var = tk.StringVar(value="Paused")
        self.status_lbl = ttk.Label(panel, textvariable=self.status_var, style="Status.TLabel")
        self.status_lbl.pack(anchor="w")
        ttk.Label(
            panel,
            text=platform_label(),
            background=PALETTE["panel"],
            foreground=PALETTE["muted"],
            font=("Helvetica", 9),
        ).pack(anchor="w", pady=(2, 0))
        self.next_var = tk.StringVar(value="")
        self.next_lbl = tk.Label(
            panel,
            textvariable=self.next_var,
            bg=PALETTE["panel"],
            fg=PALETTE["muted"],
            font=("Helvetica", 9),
        )
        self.next_lbl.pack(anchor="w", pady=(2, 0))

        # Controls
        controls = ttk.Frame(wrap)
        controls.pack(fill="x", pady=(0, 14))
        self.toggle_btn = ttk.Button(
            controls, text="Start", style="Accent.TButton", command=self._toggle_keepawake
        )
        self.toggle_btn.pack(side="left")

        # Interval
        form = ttk.Frame(wrap)
        form.pack(fill="x", pady=(0, 8))
        ttk.Label(form, text="Heartbeat interval (seconds)").grid(row=0, column=0, sticky="w")
        self.interval_var = tk.StringVar(value=str(self.cfg["interval_seconds"]))
        ttk.Entry(form, textvariable=self.interval_var, width=8).grid(row=0, column=1, padx=(8, 0))

        # Reminder
        rem = ttk.Frame(wrap)
        rem.pack(fill="x", pady=(8, 0))
        self.reminder_enabled = tk.BooleanVar(value=bool(self.cfg["reminder_enabled"]))
        ttk.Checkbutton(
            rem,
            text="Daily reminder",
            variable=self.reminder_enabled,
            command=self._apply_reminder,
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(rem, text="at").grid(row=0, column=1, padx=(8, 4))
        self.reminder_time = tk.StringVar(value=self.cfg["reminder_time"])
        ttk.Entry(rem, textvariable=self.reminder_time, width=7).grid(row=0, column=2)
        ttk.Label(rem, text="(24h, HH:MM)", style="Muted.TLabel").grid(row=0, column=3, padx=(6, 0))

        ttk.Label(wrap, text="Reminder message").pack(anchor="w", pady=(10, 2))
        self.reminder_msg = tk.StringVar(value=self.cfg["reminder_message"])
        ttk.Entry(wrap, textvariable=self.reminder_msg).pack(fill="x")

        # Misc options
        opts = ttk.Frame(wrap)
        opts.pack(fill="x", pady=(10, 0))
        self.auto_start = tk.BooleanVar(value=bool(self.cfg["auto_start_keep_awake"]))
        ttk.Checkbutton(opts, text="Start keep-awake on launch", variable=self.auto_start).pack(anchor="w")
        self.start_min = tk.BooleanVar(value=bool(self.cfg["start_minimized"]))
        ttk.Checkbutton(opts, text="Start minimized to tray", variable=self.start_min).pack(anchor="w")

        # Footer
        footer = ttk.Frame(wrap)
        footer.pack(fill="x", pady=(14, 0))
        ttk.Button(footer, text="Test notification", command=self._test_notify).pack(side="left")
        ttk.Button(footer, text="Apply", style="Accent.TButton", command=self._apply_all).pack(side="right")

        ttk.Label(
            wrap,
            text=f"v{__version__}  ·  syncstruct.com",
            style="Muted.TLabel",
        ).pack(anchor="e", pady=(8, 0))

    # --- Actions -------------------------------------------------------
    def _toggle_keepawake(self) -> None:
        if self.keep.active:
            self.keep.stop()
        else:
            try:
                interval = max(5, int(self.interval_var.get()))
            except ValueError:
                interval = 60
            ok = self.keep.start(interval)
            if not ok:
                notify(APP_NAME, "Could not enable keep-awake on this platform.")
        self._refresh_state()

    def _apply_reminder(self) -> None:
        self.reminder.configure(
            self.reminder_time.get(),
            self.reminder_msg.get(),
            bool(self.reminder_enabled.get()),
        )
        self._refresh_state()

    def _apply_all(self) -> None:
        try:
            self.cfg["interval_seconds"] = max(5, int(self.interval_var.get()))
        except ValueError:
            self.cfg["interval_seconds"] = 60
        self.cfg["reminder_enabled"] = bool(self.reminder_enabled.get())
        self.cfg["reminder_time"] = self.reminder_time.get().strip() or "15:00"
        self.cfg["reminder_message"] = self.reminder_msg.get().strip() or "Time to fill out your timesheet."
        self.cfg["auto_start_keep_awake"] = bool(self.auto_start.get())
        self.cfg["start_minimized"] = bool(self.start_min.get())
        _config.save(self.cfg)
        self._apply_reminder()
        notify(APP_NAME, "Settings saved.")

    def _test_notify(self) -> None:
        if not notify(APP_NAME, "Notifications are working."):
            self.status_var.set("Notifications unavailable on this system")

    # --- State refresh -------------------------------------------------
    def _refresh_state(self) -> None:
        if self.keep.active:
            self.status_var.set("Keep-awake: ACTIVE")
            self.status_lbl.configure(foreground=PALETTE["accent"])
            self.toggle_btn.configure(text="Stop", style="Danger.TButton")
        else:
            self.status_var.set("Keep-awake: PAUSED")
            self.status_lbl.configure(foreground=PALETTE["warn"])
            self.toggle_btn.configure(text="Start", style="Accent.TButton")
        if self.reminder_enabled.get():
            try:
                nxt = self.reminder.next_fire_at()
                self.next_var.set(f"Next reminder: {nxt.strftime('%a %H:%M')}")
            except Exception:
                self.next_var.set("")
        else:
            self.next_var.set("Reminder disabled")
        self.tray.update()

    def _tick_status(self) -> None:
        self._refresh_state()
        self.root.after(30_000, self._tick_status)

    # --- Window/tray glue ---------------------------------------------
    def _show_window(self) -> None:
        try:
            self.root.after(0, self._show_window_main)
        except RuntimeError:
            pass

    def _show_window_main(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _on_close(self) -> None:
        if self.tray.available:
            self.root.withdraw()
        else:
            self._quit()

    def _quit(self) -> None:
        try:
            self.keep.stop()
        except Exception:
            pass
        try:
            self.reminder.stop()
        except Exception:
            pass
        try:
            self.tray.stop()
        except Exception:
            pass
        try:
            self.root.after(0, self.root.destroy)
        except Exception:
            sys.exit(0)

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    App().run()


if __name__ == "__main__":
    main()
