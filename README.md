# StayAwake

A tiny cross-platform desktop utility that keeps your computer from sleeping —
plus an optional daily reminder (e.g. "fill out your timesheet").

Runs on **Windows, macOS, and Linux** with a single Python codebase and a
compact GUI. By [SyncStruct](https://syncstruct.com).

## Highlights

- **Native, no-input wake-keeping.** Uses the same OS APIs that media players
  rely on instead of simulating mouse/keyboard:
  - Windows → `SetThreadExecutionState`
  - macOS → `caffeinate`
  - Linux → `systemd-inhibit` (with `xdg-screensaver` fallback)
- **Small footprint.** No `pyautogui`, no `win10toast`. Only `pystray` +
  `Pillow` for the tray icon; everything else is stdlib.
- **System-tray support.** Minimize the window and StayAwake keeps running
  silently from the tray. Right-click for quick pause/resume.
- **Configurable daily reminder.** Pick any time and message. Notifications
  use the OS-native channel:
  - Windows → toast via PowerShell (no extra dependencies)
  - macOS → `osascript display notification`
  - Linux → `notify-send`
- **Persistent settings.** Stored per-user in the standard config location for
  each OS.
- **Optional auto-start** keep-awake on launch, and start-minimized to tray.

## Install & run from source

```bash
pip install -r requirements.txt
python stay_awake_launcher.py
# or
python -m stay_awake.app
```

The tray dependencies (`pystray`, `Pillow`) are optional — the app still runs
as a normal window without them.

## Build a standalone binary

PyInstaller produces a single executable per platform. The build script
auto-detects the host OS:

```bash
pip install pyinstaller
python build.py            # rebuilds only if sources changed
python build.py --force    # always rebuild
python build.py --console  # keep the console window (debugging)
```

Drop an `icon.ico` (Windows) or `icon.icns` (macOS) at the project root and
the build script picks it up automatically.

## Build a one-click installer

Add `--package` and the script also produces the OS-native installer format:

```bash
python build.py --package
```

| Platform | Portable binary | Installer / disk image | Requires |
| --- | --- | --- | --- |
| Windows | `dist/StayAwake.exe` | `dist/StayAwake-Setup.exe` | [Inno Setup 6](https://jrsoftware.org/isinfo.php) (`iscc` in PATH) |
| macOS | `dist/StayAwake.app` | `dist/StayAwake.dmg` | `hdiutil` (built into macOS) |
| Linux | `dist/StayAwake` | `dist/StayAwake-x86_64.AppImage` | [`appimagetool`](https://github.com/AppImage/AppImageKit/releases) in PATH |

User experience:

- **Windows installer**: double-click `StayAwake-Setup.exe` → Start Menu entry,
  optional desktop shortcut, optional "launch on Windows startup" registry
  entry, proper Add/Remove Programs uninstaller.
- **macOS DMG**: double-click `StayAwake.dmg` → drag `StayAwake.app` into
  `Applications`. First launch: right-click → Open (unsigned build, Gatekeeper
  will prompt once).
- **Linux AppImage**: `chmod +x StayAwake-x86_64.AppImage && ./StayAwake-x86_64.AppImage`.
  No install needed, runs on most distros.

## Automated releases (GitHub Actions)

This repo ships two workflows under [.github/workflows/](.github/workflows/):

- **`ci.yml`** — runs on every push/PR to `main`. Compiles all sources and
  runs a smoke-test on Windows, macOS, and Linux.
- **`release.yml`** — runs when you push a tag starting with `v` (e.g.
  `v1.0.0`). It builds the binary on each OS via PyInstaller, then attaches
  `StayAwake-windows.exe`, `StayAwake-macos`, and `StayAwake-linux` to a new
  GitHub Release.

To cut a release:

```bash
git tag v1.0.0
git push origin v1.0.0
```

The workflow also runs on manual dispatch from the Actions tab, in which case
the binaries are saved as workflow artifacts (no release is created).

## Project layout

```text
stay_awake/
  __init__.py        # version + branding
  app.py             # Tkinter GUI
  core.py            # OS-native wake-keeping (Win/macOS/Linux)
  notifier.py        # Notifications + daily reminder scheduler
  config.py          # Per-user JSON config (platform-correct location)
  tray.py            # Optional pystray integration
  icon.py            # Procedural tray icon (no image assets shipped)
build.py             # Cross-platform PyInstaller wrapper
stay_awake_launcher.py
```

## How it works

When **active**, StayAwake registers a system-level "don't go idle" request
with the OS — the same mechanism Spotify or VLC uses. There is **no fake
input**, so your mouse never twitches and your cursor focus is never stolen.

When **inactive**, that request is released and the system resumes its normal
power policy.

## License

MIT © SyncStruct — [syncstruct.com](https://syncstruct.com)
