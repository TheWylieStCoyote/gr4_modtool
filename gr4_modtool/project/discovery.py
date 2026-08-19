"""Project root discovery and config loading."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_FILE = ".gr4modtool.toml"
_HEURISTIC_MARKERS = ("CMakeLists.txt",)


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
    groups: dict[str, str]  # name -> relative path string
    flat: bool = False  # True → no groups; blocks live directly under blocks/

    @property
    def blocks_dir(self) -> Path:
        return self.root / "blocks"

    def block_include_dir(self) -> Path:
        """Flat-mode include dir: blocks/include/<gr4_prefix>/"""
        return self.blocks_dir / "include" / self.gr4_include_prefix

    def block_test_dir(self) -> Path:
        """Flat-mode test dir: blocks/test/"""
        return self.blocks_dir / "test"

    def group_path(self, group: str) -> Path:
        rel = self.groups.get(group, f"blocks/{group}")
        return self.root / rel

    def group_include_dir(self, group: str) -> Path:
        if self.flat and not group:
            return self.block_include_dir()
        return self.group_path(group) / "include" / self.gr4_include_prefix / group

    def group_test_dir(self, group: str) -> Path:
        if self.flat and not group:
            return self.block_test_dir()
        return self.group_path(group) / "test"

    def group_bench_dir(self, group: str) -> Path:
        return self.group_path(group) / "benchmarks"


def _project_base_name(name: str) -> str:
    """Slug of the project name with any leading gr4_/gr_ prefix stripped."""
    base = name.lower().replace(" ", "_").replace("-", "_")
    for prefix in ("gr4_", "gr_"):
        if base.startswith(prefix) and len(base) > len(prefix):
            return base[len(prefix) :]
    return base


def default_namespace(name: str) -> str:
    """Default C++ namespace for a project name: 'gr4_josh' -> 'gr::josh'."""
    return f"gr::{_project_base_name(name)}"


def default_cmake_prefix(name: str) -> str:
    """Default CMake prefix for a project name: 'gr4_josh' -> 'gr4_josh', 'josh' -> 'gr4_josh'."""
    return f"gr4_{_project_base_name(name)}"


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
        _found = find_project_root()
        if _found is None:
            raise FileNotFoundError(
                f"No {CONFIG_FILE} found. Run 'gr4_modtool newmod' to create a project, "
                "or use --project-dir to specify the project root."
            )
        root = _found
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
        cpp_namespace=proj.get("cpp_namespace", default_namespace(root.name)),
        cmake_prefix=proj.get("cmake_prefix", default_cmake_prefix(root.name)),
        gr4_include_prefix=proj.get("gr4_include_prefix", "gnuradio-4.0"),
        build_cmake=build.get("cmake", True),
        groups=groups,
        flat=proj.get("flat", False),
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
    ]
    if cfg.flat:
        lines.append("flat = true")
    lines += [
        "",
        "[build]",
        f"cmake = {'true' if cfg.build_cmake else 'false'}",
        "",
        "[groups]",
    ]
    for name, path in cfg.groups.items():
        lines.append(f'{name} = "{path}"')
    lines.append("")

    (cfg.root / CONFIG_FILE).write_text("\n".join(lines))


def discover_groups(cfg: ProjectConfig) -> list[GroupInfo]:
    """Return all known groups with their block lists.

    In flat mode returns a single synthetic GroupInfo(name="") whose blocks are
    scanned from block_include_dir(). All iteration-based commands work unchanged.
    """
    if cfg.flat:
        include_dir = cfg.block_include_dir()
        blocks = []
        if include_dir.exists():
            for hpp in sorted(include_dir.glob("*.hpp")):
                blocks.append(BlockInfo(name=hpp.stem, path=hpp))
        return [GroupInfo(name="", path=cfg.blocks_dir, blocks=blocks)]

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
