"""Tests for the Remote Script setup / installer module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from mcp_ableton.setup import (
    REMOTE_SCRIPT_NAME,
    _choose_target,
    detect_remote_scripts_dirs,
    find_remote_script_source,
    install,
    uninstall,
)


@pytest.fixture()
def source_dir(tmp_path: Path) -> Path:
    """Create a fake Remote Script source directory."""
    source = tmp_path / "remote_script" / REMOTE_SCRIPT_NAME
    source.mkdir(parents=True)
    (source / "__init__.py").write_text("# stub")
    (source / "tcp_server.py").write_text("# stub")
    return source


@pytest.fixture()
def target_dir(tmp_path: Path) -> Path:
    """Create a fake Ableton Remote Scripts directory."""
    target = tmp_path / "Remote Scripts"
    target.mkdir(parents=True)
    return target


class TestFindRemoteScriptSource:
    def test_finds_source_from_project_root(self) -> None:
        source = find_remote_script_source()
        assert source.is_dir()
        assert source.name == REMOTE_SCRIPT_NAME
        assert (source / "__init__.py").exists()

    def test_raises_if_source_missing(self, tmp_path: Path) -> None:
        fake_setup = tmp_path / "src" / "mcp_ableton" / "setup.py"
        fake_setup.parent.mkdir(parents=True)
        fake_setup.write_text("")

        with (
            patch("mcp_ableton.setup.__file__", str(fake_setup)),
            pytest.raises(FileNotFoundError, match="Remote Script source"),
        ):
            find_remote_script_source()


class TestDetectRemoteScriptsDirs:
    def test_returns_existing_dirs_macos(self, tmp_path: Path) -> None:
        user_library = (
            tmp_path / "Music" / "Ableton" / "User Library" / "Remote Scripts"
        )
        user_library.mkdir(parents=True)

        with (
            patch("mcp_ableton.setup.platform.system", return_value="Darwin"),
            patch("mcp_ableton.setup.Path.home", return_value=tmp_path),
        ):
            dirs = detect_remote_scripts_dirs()

        assert user_library in dirs

    def test_returns_empty_when_no_dirs_exist(self, tmp_path: Path) -> None:
        with (
            patch("mcp_ableton.setup.platform.system", return_value="Darwin"),
            patch("mcp_ableton.setup.Path.home", return_value=tmp_path),
        ):
            dirs = detect_remote_scripts_dirs()

        assert dirs == []

    def test_finds_user_remote_scripts_macos(self, tmp_path: Path) -> None:
        prefs = tmp_path / "Library" / "Preferences" / "Ableton" / "Live 12.1"
        user_remote = prefs / "User Remote Scripts"
        user_remote.mkdir(parents=True)

        with (
            patch("mcp_ableton.setup.platform.system", return_value="Darwin"),
            patch("mcp_ableton.setup.Path.home", return_value=tmp_path),
        ):
            dirs = detect_remote_scripts_dirs()

        assert user_remote in dirs

    def test_returns_existing_dirs_windows(self, tmp_path: Path) -> None:
        user_library = (
            tmp_path / "Documents" / "Ableton" / "User Library" / "Remote Scripts"
        )
        user_library.mkdir(parents=True)

        with (
            patch("mcp_ableton.setup.platform.system", return_value="Windows"),
            patch("mcp_ableton.setup.Path.home", return_value=tmp_path),
        ):
            dirs = detect_remote_scripts_dirs()

        assert user_library in dirs

    def test_exits_on_unsupported_platform(self) -> None:
        with (
            patch("mcp_ableton.setup.platform.system", return_value="Linux"),
            pytest.raises(SystemExit),
        ):
            detect_remote_scripts_dirs()


class TestChooseTarget:
    def test_auto_selects_user_library_macos(self, tmp_path: Path) -> None:
        user_library = (
            tmp_path / "Music" / "Ableton" / "User Library" / "Remote Scripts"
        )
        user_library.mkdir(parents=True)
        per_version = (
            tmp_path
            / "Library"
            / "Preferences"
            / "Ableton"
            / "Live 12.2.5"
            / "User Remote Scripts"
        )
        per_version.mkdir(parents=True)

        with (
            patch("mcp_ableton.setup.platform.system", return_value="Darwin"),
            patch("mcp_ableton.setup.Path.home", return_value=tmp_path),
        ):
            result = _choose_target([user_library, per_version])

        assert result == user_library

    def test_prompts_when_no_user_library(self, tmp_path: Path) -> None:
        dir_a = tmp_path / "Live 12" / "User Remote Scripts"
        dir_b = tmp_path / "Live 11" / "User Remote Scripts"
        dir_a.mkdir(parents=True)
        dir_b.mkdir(parents=True)

        with (
            patch("mcp_ableton.setup.platform.system", return_value="Darwin"),
            patch("mcp_ableton.setup.Path.home", return_value=tmp_path),
            patch("builtins.input", return_value="2"),
        ):
            result = _choose_target([dir_a, dir_b])

        assert result == dir_b

    def test_returns_single_dir_without_prompting(self, tmp_path: Path) -> None:
        single = tmp_path / "User Remote Scripts"
        single.mkdir(parents=True)

        with (
            patch("mcp_ableton.setup.platform.system", return_value="Darwin"),
            patch("mcp_ableton.setup.Path.home", return_value=tmp_path),
        ):
            result = _choose_target([single])

        assert result == single


class TestInstall:
    def test_install_symlink(self, target_dir: Path, source_dir: Path) -> None:
        install(target_dir, source_dir, method="symlink")

        dest = target_dir / REMOTE_SCRIPT_NAME
        assert dest.is_symlink()
        assert dest.resolve() == source_dir.resolve()

    def test_install_copy(self, target_dir: Path, source_dir: Path) -> None:
        install(target_dir, source_dir, method="copy")

        dest = target_dir / REMOTE_SCRIPT_NAME
        assert dest.is_dir()
        assert not dest.is_symlink()
        assert (dest / "__init__.py").exists()
        assert (dest / "tcp_server.py").exists()

    def test_install_idempotent_symlink(
        self, target_dir: Path, source_dir: Path
    ) -> None:
        install(target_dir, source_dir, method="symlink")
        install(target_dir, source_dir, method="symlink")

        dest = target_dir / REMOTE_SCRIPT_NAME
        assert dest.is_symlink()
        assert dest.resolve() == source_dir.resolve()

    def test_install_replaces_existing_copy_with_symlink(
        self, target_dir: Path, source_dir: Path
    ) -> None:
        install(target_dir, source_dir, method="copy")
        assert not (target_dir / REMOTE_SCRIPT_NAME).is_symlink()

        install(target_dir, source_dir, method="symlink")
        dest = target_dir / REMOTE_SCRIPT_NAME
        assert dest.is_symlink()
        assert dest.resolve() == source_dir.resolve()

    def test_install_replaces_stale_symlink(
        self, target_dir: Path, source_dir: Path, tmp_path: Path
    ) -> None:
        old_source = tmp_path / "old_source"
        old_source.mkdir()
        dest = target_dir / REMOTE_SCRIPT_NAME
        dest.symlink_to(old_source)

        install(target_dir, source_dir, method="symlink")
        assert dest.is_symlink()
        assert dest.resolve() == source_dir.resolve()

    def test_install_dry_run(self, target_dir: Path, source_dir: Path) -> None:
        install(target_dir, source_dir, method="symlink", dry_run=True)

        dest = target_dir / REMOTE_SCRIPT_NAME
        assert not dest.exists()

    def test_install_creates_target_dir(self, tmp_path: Path, source_dir: Path) -> None:
        new_target = tmp_path / "new" / "Remote Scripts"
        install(new_target, source_dir, method="symlink")
        assert (new_target / REMOTE_SCRIPT_NAME).is_symlink()


class TestUninstall:
    def test_uninstall_symlink(self, target_dir: Path, source_dir: Path) -> None:
        install(target_dir, source_dir, method="symlink")

        with patch("builtins.input", return_value="y"):
            uninstall(target_dir)

        assert not (target_dir / REMOTE_SCRIPT_NAME).exists()

    def test_uninstall_copy(self, target_dir: Path, source_dir: Path) -> None:
        install(target_dir, source_dir, method="copy")

        with patch("builtins.input", return_value="y"):
            uninstall(target_dir)

        assert not (target_dir / REMOTE_SCRIPT_NAME).exists()

    def test_uninstall_aborted(self, target_dir: Path, source_dir: Path) -> None:
        install(target_dir, source_dir, method="symlink")

        with patch("builtins.input", return_value="n"):
            uninstall(target_dir)

        assert (target_dir / REMOTE_SCRIPT_NAME).exists()

    def test_uninstall_nothing_to_remove(self, target_dir: Path) -> None:
        uninstall(target_dir)

    def test_uninstall_dry_run(self, target_dir: Path, source_dir: Path) -> None:
        install(target_dir, source_dir, method="symlink")
        uninstall(target_dir, dry_run=True)
        assert (target_dir / REMOTE_SCRIPT_NAME).exists()
