"""Project root discovery and config loading."""

from __future__ import annotations

import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


CONFIG_FILE = ".gr4modtool.toml"
_HEURISTIC_MARKERS = ("CMakeLists.txt", "meson.build")


@dataclass
class BlockInfo:
    name: str
    path: Path


@dataclass
class GroupInfo:
    name: str
    path: Path
    blocks: list[BlockInfo] = field(default_factory=list)


@dataclass
class ProjectConfig:
    root: Path
    name: str
    version: str
    cpp_namespace: str
    cmake_prefix: str
    gr4_include_prefix: str
    build_cmake: bool
    build_meson: bool
    groups: dict[str, str]  # name -> relative path string

    @property
    def blocks_dir(self) -> Path:
        return self.root / "blocks"

    def group_path(self, group: str) -> Path:
        rel = self.groups.get(group, f"blocks/{group}")
        return self.root / rel

    def group_include_dir(self, group: str) -> Path:
        return self.group_path(group) / "include" / self.gr4_include_prefix / group

    def group_test_dir(self, group: str) -> Path:
        return self.group_path(group) / "test"

    def group_bench_dir(self, group: str) -> Path:
        return self.group_path(group) / "benchmarks"


def find_project_root(start: Path | None = None) -> Path | None:
    """Walk upward from start (default: cwd) looking for .gr4modtool.toml."""
    current = (start or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        if (directory / CONFIG_FILE).exists():
            return directory
    return None


def load_config(project_dir: Path | None = None) -> ProjectConfig:
    """Load and return ProjectConfig. Raises FileNotFoundError if not found."""
    if project_dir is not None:
        root = Path(project_dir).resolve()
        config_path = root / CONFIG_FILE
    else:
        root = find_project_root()
        if root is None:
            raise FileNotFoundError(
                f"No {CONFIG_FILE} found. Run 'gr4_modtool newmod' to create a project, "
                "or use --project-dir to specify the project root."
            )
        config_path = root / CONFIG_FILE

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    proj = data.get("project", {})
    build = data.get("build", {})
    groups = data.get("groups", {})

    return ProjectConfig(
        root=root,
        name=proj.get("name", root.name),
        version=proj.get("version", "0.1.0"),
        cpp_namespace=proj.get("cpp_namespace", f"gr::{root.name}"),
        cmake_prefix=proj.get("cmake_prefix", f"gr4_{root.name}"),
        gr4_include_prefix=proj.get("gr4_include_prefix", "gnuradio-4.0"),
        build_cmake=build.get("cmake", True),
        build_meson=build.get("meson", True),
        groups=groups,
    )


def save_config(cfg: ProjectConfig) -> None:
    """Write the config back to .gr4modtool.toml (overwrites)."""
    # tomllib is read-only; build the TOML manually
    lines = [
        "[project]",
        f'name = "{cfg.name}"',
        f'version = "{cfg.version}"',
        f'cpp_namespace = "{cfg.cpp_namespace}"',
        f'cmake_prefix = "{cfg.cmake_prefix}"',
        f'gr4_include_prefix = "{cfg.gr4_include_prefix}"',
        "",
        "[build]",
        f"cmake = {'true' if cfg.build_cmake else 'false'}",
        f"meson = {'true' if cfg.build_meson else 'false'}",
        "",
        "[groups]",
    ]
    for name, path in cfg.groups.items():
        lines.append(f'{name} = "{path}"')
    lines.append("")

    (cfg.root / CONFIG_FILE).write_text("\n".join(lines))


def discover_groups(cfg: ProjectConfig) -> list[GroupInfo]:
    """Return all known groups with their block lists."""
    groups = []
    for name, rel in cfg.groups.items():
        group_path = cfg.root / rel
        include_dir = group_path / "include" / cfg.gr4_include_prefix / name
        blocks = []
        if include_dir.exists():
            for hpp in sorted(include_dir.glob("*.hpp")):
                blocks.append(BlockInfo(name=hpp.stem, path=hpp))
        groups.append(GroupInfo(name=name, path=group_path, blocks=blocks))
    return groups
