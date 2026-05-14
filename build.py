#!/usr/bin/env python
"""Cross-platform PyInstaller build script for StayAwake.

Produces a single-file executable on Windows, macOS, and Linux.
Aggressive size trimming: excludes unused stdlib modules.

With --package, also produces an OS-conventional installer:
  Windows → StayAwake-Setup.exe (Inno Setup)
  macOS   → StayAwake.dmg
  Linux   → StayAwake-x86_64.AppImage

Examples:
  python build.py                  # build if changes
  python build.py --force          # always rebuild
  python build.py --watch          # auto-rebuild on change
  python build.py --console        # keep console window (debugging)
  python build.py --package        # build + create installer
"""
from __future__ import annotations
import argparse
import hashlib
import os
import platform
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
SRC_DIR = PROJECT_ROOT / "stay_awake"
LAUNCHER = PROJECT_ROOT / "stay_awake_launcher.py"
HASH_FILE = PROJECT_ROOT / ".build_hash"
DIST_DIR = PROJECT_ROOT / "dist"
PACKAGING_DIR = PROJECT_ROOT / "packaging"

EXCLUDES = [
    "tkinter.test", "test", "unittest", "pydoc", "pydoc_data",
    "doctest", "lib2to3", "pdb",
    "_pytest", "pip", "wheel", "email.test",
]


def _exe_path() -> Path:
    name = "StayAwake.exe" if sys.platform.startswith("win") else "StayAwake"
    return DIST_DIR / name


def _macos_app_path() -> Path:
    return DIST_DIR / "StayAwake.app"


def _iter_sources():
    for p in SRC_DIR.rglob("*.py"):
        yield p
    yield LAUNCHER


def _compute_hash() -> str:
    h = hashlib.sha256()
    for path in sorted(_iter_sources()):
        h.update(path.as_posix().encode("utf-8"))
        h.update(path.read_bytes())
    h.update(platform.system().encode("utf-8"))
    return h.hexdigest()


def _read_prev_hash() -> str | None:
    if HASH_FILE.is_file():
        try:
            return HASH_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            return None
    return None


def _size_mb(p: Path) -> str:
    try:
        return f"{p.stat().st_size / (1024 * 1024):.1f} MB"
    except OSError:
        return "?"


# --- Build -------------------------------------------------------------------
def build(force: bool = False, keep_console: bool = False) -> bool:
    current = _compute_hash()
    prev = _read_prev_hash()
    exe = _exe_path()
    if not force and prev == current and exe.is_file():
        print("[build] No changes; skipping. (use --force to rebuild)")
        return False

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--onefile", "--clean",
        "--name", "StayAwake",
    ]
    if not keep_console:
        cmd.append("--noconsole" if sys.platform.startswith("win") else "--windowed")
    for mod in EXCLUDES:
        cmd.extend(["--exclude-module", mod])

    icon = PROJECT_ROOT / ("icon.ico" if sys.platform.startswith("win") else "icon.icns")
    if icon.is_file():
        cmd.extend(["--icon", str(icon)])

    cmd.append(str(LAUNCHER))
    print("[build] Running:", " ".join(cmd))
    try:
        subprocess.check_call(cmd, cwd=PROJECT_ROOT)
    except subprocess.CalledProcessError as e:
        print(f"[build] PyInstaller failed (exit {e.returncode})")
        return False
    except FileNotFoundError:
        print("[build] PyInstaller not found. Install with: pip install pyinstaller")
        return False

    HASH_FILE.write_text(current, encoding="utf-8")
    if exe.is_file():
        print(f"[build] Success → {exe}  ({_size_mb(exe)})")
    else:
        print("[build] Build finished but executable not found.")
    return True


def watch(keep_console: bool, interval: float = 1.5) -> None:
    print("[watch] Watching for changes. Ctrl+C to stop.")
    last = _compute_hash()
    while True:
        time.sleep(interval)
        new = _compute_hash()
        if new != last:
            print("[watch] Change detected → rebuilding…")
            build(force=True, keep_console=keep_console)
            last = new


# --- Package -----------------------------------------------------------------
def package() -> bool:
    if not _exe_path().is_file():
        print("[package] No binary in dist/. Run `python build.py --force` first.")
        return False
    if sys.platform == "darwin":
        return _package_macos()
    if sys.platform.startswith("win"):
        return _package_windows()
    return _package_linux()


def _package_macos() -> bool:
    app = _macos_app_path()
    if not app.exists():
        print(f"[package] {app} not found. Rebuild without --console (need --windowed).")
        return False
    dmg = DIST_DIR / "StayAwake.dmg"
    if dmg.exists():
        dmg.unlink()
    cmd = [
        "hdiutil", "create",
        "-volname", "StayAwake",
        "-srcfolder", str(app),
        "-ov", "-format", "UDZO",
        str(dmg),
    ]
    print("[package] Creating DMG…")
    try:
        subprocess.check_call(cmd)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"[package] hdiutil failed: {e}")
        return False
    print(f"[package] DMG → {dmg}  ({_size_mb(dmg)})")
    return True


def _find_iscc() -> str | None:
    for name in ("iscc", "ISCC", "iscc.exe", "ISCC.exe"):
        p = shutil.which(name)
        if p:
            return p
    for candidate in (
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
    ):
        if Path(candidate).is_file():
            return candidate
    return None


def _package_windows() -> bool:
    iss = PACKAGING_DIR / "windows" / "installer.iss"
    if not iss.is_file():
        print(f"[package] Missing {iss}")
        return False
    iscc = _find_iscc()
    if not iscc:
        print("[package] Inno Setup (ISCC) not found.")
        print("[package] Install from https://jrsoftware.org/isinfo.php  or skip --package.")
        return False
    print(f"[package] Running {iscc} {iss}")
    try:
        subprocess.check_call([iscc, str(iss)], cwd=PROJECT_ROOT)
    except subprocess.CalledProcessError as e:
        print(f"[package] Inno Setup failed (exit {e.returncode})")
        return False
    setup = DIST_DIR / "StayAwake-Setup.exe"
    if setup.is_file():
        print(f"[package] Installer → {setup}  ({_size_mb(setup)})")
        return True
    print("[package] Inno Setup finished but installer not found.")
    return False


def _package_linux() -> bool:
    appimagetool = shutil.which("appimagetool") or shutil.which("appimagetool-x86_64.AppImage")
    if not appimagetool:
        print("[package] appimagetool not found.")
        print("[package] Download from https://github.com/AppImage/AppImageKit/releases")
        return False

    binary = _exe_path()
    appdir = DIST_DIR / "StayAwake.AppDir"
    if appdir.exists():
        shutil.rmtree(appdir)
    (appdir / "usr" / "bin").mkdir(parents=True)
    shutil.copy2(binary, appdir / "usr" / "bin" / "StayAwake")
    os.chmod(appdir / "usr" / "bin" / "StayAwake",
             os.stat(appdir / "usr" / "bin" / "StayAwake").st_mode | stat.S_IEXEC)

    shutil.copy2(PACKAGING_DIR / "linux" / "StayAwake.desktop", appdir / "StayAwake.desktop")
    apprun = appdir / "AppRun"
    shutil.copy2(PACKAGING_DIR / "linux" / "AppRun", apprun)
    os.chmod(apprun, os.stat(apprun).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    icon_png = appdir / "StayAwake.png"
    try:
        from stay_awake.icon import make_icon
        make_icon(active=True, size=256).save(icon_png)
    except Exception as e:
        print(f"[package] Could not generate icon: {e}")
        # Tiny 1x1 transparent PNG fallback
        icon_png.write_bytes(
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc\xfc\xcf"
            b"\xc0\x00\x00\x00\x03\x00\x01\xae\xc3\xe8\x95\x00\x00\x00\x00IEND\xaeB`\x82"
        )

    # AppImage convention: .DirIcon mirrors the icon
    dir_icon = appdir / ".DirIcon"
    if dir_icon.exists() or dir_icon.is_symlink():
        dir_icon.unlink()
    try:
        dir_icon.symlink_to("StayAwake.png")
    except OSError:
        shutil.copy2(icon_png, dir_icon)

    out = DIST_DIR / "StayAwake-x86_64.AppImage"
    if out.exists():
        out.unlink()

    print(f"[package] Running {appimagetool} {appdir}")
    env = os.environ.copy()
    env.setdefault("ARCH", "x86_64")
    cmd = [appimagetool]
    # appimagetool is itself an AppImage; in CI without FUSE we need this:
    if appimagetool.endswith(".AppImage"):
        cmd.append("--appimage-extract-and-run")
    cmd.extend([str(appdir), str(out)])
    try:
        subprocess.check_call(cmd, cwd=PROJECT_ROOT, env=env)
    except subprocess.CalledProcessError as e:
        print(f"[package] appimagetool failed (exit {e.returncode})")
        return False
    if out.is_file():
        os.chmod(out, os.stat(out).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
        print(f"[package] AppImage → {out}  ({_size_mb(out)})")
        return True
    return False


# --- CLI ---------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="Force rebuild")
    ap.add_argument("--watch", action="store_true", help="Auto-rebuild on change")
    ap.add_argument("--console", action="store_true", help="Keep console window")
    ap.add_argument("--package", action="store_true",
                    help="After building, produce OS installer (.exe/.dmg/.AppImage)")
    args = ap.parse_args()

    built = build(force=args.force, keep_console=args.console)

    if args.package:
        # Make sure we have a fresh binary; if build skipped and exe exists we proceed
        if not _exe_path().is_file():
            print("[package] No binary present; building first.")
            built = build(force=True, keep_console=args.console)
            if not built:
                sys.exit(1)
        ok = package()
        if not ok:
            sys.exit(2)

    if args.watch:
        try:
            watch(keep_console=args.console)
        except KeyboardInterrupt:
            print("\n[watch] Stopped.")


if __name__ == "__main__":
    main()
