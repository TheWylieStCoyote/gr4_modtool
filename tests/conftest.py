"""Shared pytest fixtures for gr4_modtool tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from gr4_modtool.project.discovery import ProjectConfig, save_config
from gr4_modtool.commands.newgroup import write_group_skeleton


@pytest.fixture()
def project(tmp_path: Path) -> ProjectConfig:
    """Create a minimal fake project tree with one group ('basic')."""
    cfg = ProjectConfig(
        root=tmp_path,
        name="testmod",
        version="0.1.0",
        cpp_namespace="gr::testmod",
        cmake_prefix="gr4_testmod",
        gr4_include_prefix="gnuradio-4.0",
        build_cmake=True,
        build_meson=True,
        groups={"basic": "blocks/basic"},
    )
    save_config(cfg)

    # blocks/ directory
    blocks = tmp_path / "blocks"
    blocks.mkdir()
    (blocks / "CMakeLists.txt").write_text(
        "add_library(gr4_testmod_blocks_headers INTERFACE)\n"
        "add_library(gr4_testmod::blocks_headers ALIAS gr4_testmod_blocks_headers)\n"
        "target_link_libraries(gr4_testmod_blocks_headers INTERFACE)\n"
    )
    (blocks / "meson.build").write_text("subdir('basic')\n")

    write_group_skeleton(cfg, "basic")
    return cfg
