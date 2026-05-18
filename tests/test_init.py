"""Tests for init command."""

from pathlib import Path

import pytest

from gr4_modtool.commands.init import scan_project_dir, write_init_config
from gr4_modtool.project.discovery import CONFIG_FILE, load_config


def _make_project_skeleton(tmp_path: Path, name: str = "myproj") -> Path:
    (tmp_path / "CMakeLists.txt").write_text(
        f'cmake_minimum_required(VERSION 3.22)\nproject({name} LANGUAGES CXX)\n'
    )
    (tmp_path / "meson.build").write_text("project('myproj', 'cpp')\n")
    blocks = tmp_path / "blocks"
    blocks.mkdir()
    for group in ("basic", "filter"):
        inc = blocks / group / "include" / "gnuradio-4.0" / group
        inc.mkdir(parents=True)
    return tmp_path


def test_scan_detects_name(tmp_path: Path) -> None:
    (tmp_path / "CMakeLists.txt").write_text("project(mymod LANGUAGES CXX VERSION 0.1)\n")
    result = scan_project_dir(tmp_path)
    assert result["name"] == "mymod"


def test_scan_detects_groups(tmp_path: Path) -> None:
    _make_project_skeleton(tmp_path)
    result = scan_project_dir(tmp_path)
    assert "basic" in result["groups"]
    assert "filter" in result["groups"]


def test_scan_detects_include_prefix(tmp_path: Path) -> None:
    _make_project_skeleton(tmp_path)
    result = scan_project_dir(tmp_path)
    assert result["gr4_include_prefix"] == "gnuradio-4.0"


def test_scan_detects_cmake_meson(tmp_path: Path) -> None:
    _make_project_skeleton(tmp_path)
    result = scan_project_dir(tmp_path)
    assert result["has_cmake"] is True
    assert result["has_meson"] is True


def test_write_init_config_creates_toml(tmp_path: Path) -> None:
    write_init_config(
        tmp_path, "testmod", "0.1.0", "gr::testmod", "gr4_testmod",
        "gnuradio-4.0", True, False, {"basic": "blocks/basic"},
    )
    assert (tmp_path / CONFIG_FILE).exists()
    cfg = load_config(tmp_path)
    assert cfg.name == "testmod"
    assert cfg.cmake_prefix == "gr4_testmod"
    assert "basic" in cfg.groups


def test_write_init_config_raises_if_exists(tmp_path: Path) -> None:
    (tmp_path / CONFIG_FILE).write_text("[project]\nname = 'x'\n")
    with pytest.raises(FileExistsError):
        write_init_config(
            tmp_path, "x", "0.1.0", "gr::x", "gr4_x", "gnuradio-4.0", True, False, {}
        )


def test_scan_no_blocks_dir(tmp_path: Path) -> None:
    (tmp_path / "CMakeLists.txt").write_text("project(empty LANGUAGES CXX)\n")
    result = scan_project_dir(tmp_path)
    assert result["groups"] == {}
