"""Install and uninstall the AbletonLiveMCP Remote Script."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import sys
from pathlib import Path

REMOTE_SCRIPT_NAME = "AbletonLiveMCP"

BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def _supports_color() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _fmt(text: str, code: str) -> str:
    if not _supports_color():
        return text
    return f"{code}{text}{RESET}"


def find_remote_script_source() -> Path:
    """Locate the ``remote_script/AbletonLiveMCP/`` directory in the project."""
    project_root = Path(__file__).resolve().parents[2]
    source = project_root / "remote_script" / REMOTE_SCRIPT_NAME
    if not source.is_dir():
        raise FileNotFoundError(
            f"Remote Script source not found at {source}. "
            "Are you running from the project repository?"
        )
    return source


def _macos_user_library() -> Path:
    return Path.home() / "Music" / "Ableton" / "User Library" / "Remote Scripts"


def _macos_candidate_dirs() -> list[Path]:
    candidates: list[Path] = [_macos_user_library()]

    prefs_dir = Path.home() / "Library" / "Preferences" / "Ableton"
    if prefs_dir.is_dir():
        for version_dir in sorted(prefs_dir.iterdir(), reverse=True):
            user_remote = version_dir / "User Remote Scripts"
            if user_remote.is_dir():
                candidates.append(user_remote)

    return candidates


def _windows_user_library() -> Path:
    return Path.home() / "Documents" / "Ableton" / "User Library" / "Remote Scripts"


def _windows_candidate_dirs() -> list[Path]:
    candidates: list[Path] = [_windows_user_library()]

    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    ableton_prefs = appdata / "Ableton"
    if ableton_prefs.is_dir():
        for version_dir in sorted(ableton_prefs.iterdir(), reverse=True):
            user_remote = version_dir / "Preferences" / "User Remote Scripts"
            if user_remote.is_dir():
                candidates.append(user_remote)

    return candidates


def _user_library_dir() -> Path:
    """Return the OS-specific User Library Remote Scripts path."""
    if platform.system() == "Darwin":
        return _macos_user_library()
    return _windows_user_library()


def detect_remote_scripts_dirs() -> list[Path]:
    """Return candidate Remote Scripts directories that exist on this system.

    The User Library directory is always first when present, followed by any
    per-version ``User Remote Scripts`` directories.
    """
    system = platform.system()
    if system == "Darwin":
        candidates = _macos_candidate_dirs()
    elif system == "Windows":
        candidates = _windows_candidate_dirs()
    else:
        print(_fmt(f"Unsupported platform: {system}", RED))
        print("See docs/installation.md for manual installation instructions.")
        sys.exit(1)

    return [d for d in candidates if d.is_dir()]


def _choose_target(dirs: list[Path]) -> Path:
    """Pick the best target directory, prompting only when necessary.

    If the User Library directory is among the candidates it is selected
    automatically (it works across all Ableton versions). The user is only
    prompted when multiple per-version directories exist and the User Library
    is not available.
    """
    user_library = _user_library_dir()
    if user_library in dirs:
        print(f"Using User Library: {user_library}")
        return user_library

    if len(dirs) == 1:
        return dirs[0]

    print(f"Found {len(dirs)} Remote Scripts directories:\n")
    for i, d in enumerate(dirs, 1):
        print(f"  {i}) {d}")
    print()

    while True:
        try:
            choice = input("Select a directory [1]: ").strip()
            if not choice:
                return dirs[0]
            idx = int(choice) - 1
            if 0 <= idx < len(dirs):
                return dirs[idx]
        except (ValueError, EOFError):
            pass
        print(f"Please enter a number between 1 and {len(dirs)}.")


def install(
    target_dir: Path,
    source: Path,
    *,
    method: str = "symlink",
    dry_run: bool = False,
) -> None:
    """Install the Remote Script into *target_dir*."""
    dest = target_dir / REMOTE_SCRIPT_NAME

    if dest.exists() or dest.is_symlink():
        if dest.is_symlink():
            existing_target = dest.resolve()
            if existing_target == source.resolve():
                print(
                    _fmt("Already installed", GREEN)
                    + f" (symlink at {dest} -> {existing_target})"
                )
                return
            label = f"symlink -> {existing_target}"
        else:
            label = "directory"
        print(f"Removing existing {label} at {dest}")
        if not dry_run:
            if dest.is_symlink() or dest.is_file():
                dest.unlink()
            else:
                shutil.rmtree(dest)

    if method == "symlink":
        print(f"Creating symlink: {dest} -> {source}")
        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
            dest.symlink_to(source)
    else:
        print(f"Copying files to {dest}")
        if not dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, dest)

    status = "[dry run] " if dry_run else ""
    print(_fmt(f"\n{status}Remote Script installed successfully!", GREEN))
    print("\nNext steps:")
    print("  1. Open (or restart) Ableton Live")
    print("  2. Go to Preferences > Link, Tempo & MIDI")
    print(f'  3. Set a Control Surface to "{REMOTE_SCRIPT_NAME}"')
    print('  4. Set Input and Output to "None"')


def uninstall(target_dir: Path, *, dry_run: bool = False) -> None:
    """Remove the Remote Script from *target_dir*."""
    dest = target_dir / REMOTE_SCRIPT_NAME

    if not dest.exists() and not dest.is_symlink():
        print(f"Nothing to uninstall at {dest}")
        return

    label = f"symlink -> {dest.resolve()}" if dest.is_symlink() else "directory"
    print(f"Found {label} at {dest}")

    if not dry_run:
        confirm = input("Remove it? [y/N]: ").strip().lower()
        if confirm not in ("y", "yes"):
            print("Aborted.")
            return

    if not dry_run:
        if dest.is_symlink() or dest.is_file():
            dest.unlink()
        else:
            shutil.rmtree(dest)

    status = "[dry run] " if dry_run else ""
    print(_fmt(f"{status}Remote Script uninstalled.", GREEN))
    print("Restart Ableton Live to complete removal.")


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="mcp-ableton-setup",
        description="Install or uninstall the AbletonLiveMCP Remote Script.",
    )
    parser.add_argument(
        "--uninstall",
        action="store_true",
        help="Remove the Remote Script instead of installing it.",
    )
    parser.add_argument(
        "--method",
        choices=["symlink", "copy"],
        default="symlink",
        help='Installation method (default: symlink). Use "copy" if symlinks '
        "are not supported on your system.",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Override auto-detection and install into this directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without making changes.",
    )
    return parser


def main() -> None:
    """CLI entry point for Remote Script setup."""
    parser = build_parser()
    args = parser.parse_args()

    print(_fmt("AbletonLiveMCP Remote Script Setup\n", BOLD))

    if args.dry_run:
        print(_fmt("[dry-run mode — no changes will be made]\n", YELLOW))

    source = find_remote_script_source()

    if args.target:
        target_dir = args.target.expanduser().resolve()
        if not target_dir.is_dir() and not args.uninstall:
            print(_fmt(f"Target directory does not exist: {target_dir}", RED))
            sys.exit(1)
    else:
        dirs = detect_remote_scripts_dirs()
        if not dirs:
            print(_fmt("No Ableton Remote Scripts directory found.", RED))
            print()
            default = _user_library_dir()
            print(f"Expected location: {default}")
            print("Create this directory or use --target to specify a path.")
            sys.exit(1)
        else:
            target_dir = _choose_target(dirs)

    if args.uninstall:
        uninstall(target_dir, dry_run=args.dry_run)
    else:
        install(target_dir, source, method=args.method, dry_run=args.dry_run)
