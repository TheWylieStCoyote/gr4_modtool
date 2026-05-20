"""templates command group — list, init, and validate project template overrides."""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from gr4_modtool.project.discovery import load_config

CONTEXT_FREE_TEMPLATES: frozenset[str] = frozenset(
    {
        "flat_blocks_meson.build.j2",
        "test_meson.build.j2",
    }
)

_BLOCK_CONTEXT: list[dict] = [
    {"name": "block_name", "type": "str", "dummy": "MyBlock", "desc": "CamelCase struct name"},
    {"name": "namespace", "type": "str", "dummy": "gr::mymod", "desc": "Full C++ namespace"},
    {"name": "description", "type": "str", "dummy": "A block.", "desc": "Doc<> string"},
    {
        "name": "template_params",
        "type": "list",
        "dummy": ["T"],
        "desc": "Template type parameter names",
    },
    {
        "name": "template_decl",
        "type": "str",
        "dummy": "typename T",
        "desc": "template<> declaration string",
    },
    {
        "name": "template_args",
        "type": "str",
        "dummy": "T",
        "desc": "Template argument list for Block<Foo<T>>",
    },
    {
        "name": "template_param_macro",
        "type": "str",
        "dummy": "T",
        "desc": "Comma-separated params for GR_REGISTER_BLOCK",
    },
    {
        "name": "in_ports",
        "type": "list",
        "dummy": [{"name": "in", "type": "T"}],
        "desc": "Input port dicts",
    },
    {
        "name": "out_ports",
        "type": "list",
        "dummy": [{"name": "out", "type": "T"}],
        "desc": "Output port dicts",
    },
    {
        "name": "all_port_names",
        "type": "list",
        "dummy": ["in", "out"],
        "desc": "All port names (in + out)",
    },
    {
        "name": "type_list",
        "type": "str",
        "dummy": "float, double",
        "desc": "GR_REGISTER_BLOCK instantiation types",
    },
    {
        "name": "processing_style",
        "type": "str",
        "dummy": "processOne",
        "desc": "processOne or processBulk",
    },
    {
        "name": "uses_complex",
        "type": "bool",
        "dummy": False,
        "desc": "True when type_list includes complex<>",
    },
    {
        "name": "multi_output",
        "type": "bool",
        "dummy": False,
        "desc": "True when block has >1 output port",
    },
    {"name": "return_type", "type": "str", "dummy": "T", "desc": "processOne return type"},
    {"name": "params_str", "type": "str", "dummy": "T x", "desc": "processOne parameter signature"},
    {
        "name": "bulk_params_str",
        "type": "str",
        "dummy": "",
        "desc": "processBulk parameter signature",
    },
    {
        "name": "gr4_include_prefix",
        "type": "str",
        "dummy": "gnuradio-4.0",
        "desc": "Header include prefix",
    },
    {
        "name": "group",
        "type": "str",
        "dummy": "basic",
        "desc": "Group name; empty string in flat mode",
    },
    {"name": "first_type", "type": "str", "dummy": "float", "desc": "First type from type_list"},
    {
        "name": "first_port_type",
        "type": "str",
        "dummy": "float",
        "desc": "Type of first input port",
    },
    {
        "name": "first_out_type",
        "type": "str",
        "dummy": "float",
        "desc": "Type of first output port",
    },
    {
        "name": "needs_graph_test",
        "type": "bool",
        "dummy": False,
        "desc": "True when graph integration test should be generated",
    },
    {"name": "simd", "type": "bool", "dummy": False, "desc": "True when SIMD archetype is used"},
]

TEMPLATE_CONTEXT: dict[str, list[dict] | str] = {
    "block.hpp.j2": _BLOCK_CONTEXT,
    "qa_block.cpp.j2": "block.hpp.j2",
    "bench_block.cpp.j2": "block.hpp.j2",
    "group_CMakeLists.txt.j2": [
        {
            "name": "cmake_prefix",
            "type": "str",
            "dummy": "gr4_mymod",
            "desc": "CMake target prefix",
        },
        {"name": "group_name", "type": "str", "dummy": "basic", "desc": "Group directory name"},
        {
            "name": "gr4_include_prefix",
            "type": "str",
            "dummy": "gnuradio-4.0",
            "desc": "Include path prefix",
        },
        {
            "name": "dep_var_name",
            "type": "str",
            "dummy": "gr4_basic_blocks_dep",
            "desc": "Meson dep variable name",
        },
    ],
    "group_meson.build.j2": "group_CMakeLists.txt.j2",
    "test_CMakeLists.txt.j2": [
        {"name": "group_name", "type": "str", "dummy": "basic", "desc": "Group directory name"},
    ],
    "toplevel_CMakeLists.txt.j2": [
        {"name": "project_name", "type": "str", "dummy": "mymod", "desc": "Project name"},
        {"name": "version", "type": "str", "dummy": "0.1.0", "desc": "Project version"},
        {
            "name": "cmake_prefix",
            "type": "str",
            "dummy": "gr4_mymod",
            "desc": "CMake target prefix",
        },
        {
            "name": "gr4_include_prefix",
            "type": "str",
            "dummy": "gnuradio-4.0",
            "desc": "Include path prefix",
        },
        {"name": "cpp_namespace", "type": "str", "dummy": "gr::mymod", "desc": "C++ namespace"},
    ],
    "toplevel_meson.build.j2": "toplevel_CMakeLists.txt.j2",
    "flat_blocks_CMakeLists.txt.j2": [
        {
            "name": "cmake_prefix",
            "type": "str",
            "dummy": "gr4_mymod",
            "desc": "CMake target prefix",
        },
        {
            "name": "gr4_include_prefix",
            "type": "str",
            "dummy": "gnuradio-4.0",
            "desc": "Include path prefix",
        },
    ],
    "gitignore.j2": [
        {"name": "project_name", "type": "str", "dummy": "mymod", "desc": "Project name"},
    ],
    "pre_commit_config.yaml.j2": "gitignore.j2",
    "ci_clang.yml.j2": "gitignore.j2",
    "ci_sanitizers.yml.j2": "gitignore.j2",
    "ci_coverage.yml.j2": "gitignore.j2",
    "ci_release.yml.j2": "gitignore.j2",
    "ci_matrix.yml.j2": "gitignore.j2",
    "plot_bench.py.j2": [
        {"name": "block_name", "type": "str", "dummy": "MyBlock", "desc": "CamelCase block name"},
    ],
    "bench_CMakeLists.txt.j2": [
        {"name": "group_name", "type": "str", "dummy": "basic", "desc": "Group directory name"},
    ],
    "devcontainer.json.j2": [
        {"name": "project_name", "type": "str", "dummy": "mymod", "desc": "Project name"},
        {
            "name": "cmake_prefix",
            "type": "str",
            "dummy": "gr4_mymod",
            "desc": "CMake target prefix",
        },
        {
            "name": "gr4_include_prefix",
            "type": "str",
            "dummy": "gnuradio-4.0",
            "desc": "Include path prefix",
        },
        {"name": "build_cmake", "type": "bool", "dummy": True, "desc": "Whether CMake is enabled"},
        {"name": "build_meson", "type": "bool", "dummy": True, "desc": "Whether Meson is enabled"},
    ],
    "Dockerfile.devcontainer.j2": "devcontainer.json.j2",
    "clang-format.j2": [
        {"name": "project_name", "type": "str", "dummy": "mymod", "desc": "Project name"},
        {
            "name": "gr4_include_prefix",
            "type": "str",
            "dummy": "gnuradio-4.0",
            "desc": "Include path prefix",
        },
    ],
    "clang-tidy.j2": "clang-format.j2",
    "cmake_presets.json.j2": [
        {"name": "project_name", "type": "str", "dummy": "mymod", "desc": "Project name"},
        {
            "name": "cmake_prefix",
            "type": "str",
            "dummy": "gr4_mymod",
            "desc": "CMake target prefix",
        },
    ],
    "vscode_settings.json.j2": "cmake_presets.json.j2",
    "vscode_launch.json.j2": "cmake_presets.json.j2",
    "Doxyfile.j2": [
        {"name": "project_name", "type": "str", "dummy": "mymod", "desc": "Project name"},
        {"name": "version", "type": "str", "dummy": "0.1.0", "desc": "Project version"},
        {
            "name": "gr4_include_prefix",
            "type": "str",
            "dummy": "gnuradio-4.0",
            "desc": "Include path prefix",
        },
    ],
}


def _override_dir(project_root: Path) -> Path:
    return project_root / ".gr4modtool" / "templates"


def _resolve(name: str) -> list[dict]:
    """Dereference alias strings in TEMPLATE_CONTEXT."""
    entry = TEMPLATE_CONTEXT.get(name, [])
    if isinstance(entry, str):
        entry = TEMPLATE_CONTEXT.get(entry, [])
    return entry  # type: ignore[return-value]


@click.group("templates")
def cmd() -> None:
    """Manage project-local template overrides."""


@cmd.command("list")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def list_cmd(project_dir: str | None) -> None:
    """List built-in templates and mark any project-local overrides."""
    from gr4_modtool.templates import builtin_templates_dir

    builtin_names = sorted(p.name for p in builtin_templates_dir().glob("*.j2"))

    override_names: set[str] = set()
    root: Path | None = None
    try:
        cfg = load_config(Path(project_dir) if project_dir else None)
        root = cfg.root
        od = _override_dir(root)
        if od.is_dir():
            override_names = {p.name for p in od.glob("*.j2")}
    except FileNotFoundError:
        pass

    console = Console()
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Template")
    table.add_column("Status")
    for name in builtin_names:
        if name in override_names:
            table.add_row(name, "[yellow]overridden[/yellow]")
        else:
            table.add_row(name, "[dim]built-in[/dim]")
    if root:
        for name in sorted(override_names - set(builtin_names)):
            table.add_row(name, "[green]custom[/green]")
    console.print(table)


@cmd.command("init")
@click.argument("template_name")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
@click.option("--force", is_flag=True, help="Overwrite existing override.")
def init_cmd(template_name: str, project_dir: str | None, force: bool) -> None:
    """Copy a built-in template into .gr4modtool/templates/ for editing."""
    from gr4_modtool.templates import builtin_templates_dir

    cfg = load_config(Path(project_dir) if project_dir else None)

    builtin_path = builtin_templates_dir() / template_name
    if not builtin_path.exists():
        click.echo(f"Unknown template: {template_name}", err=True)
        click.echo("Run 'gr4_modtool templates list' to see available templates.", err=True)
        sys.exit(1)

    dest_dir = _override_dir(cfg.root)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / template_name

    if dest.exists() and not force:
        click.echo(f"{dest} already exists. Use --force to overwrite.", err=True)
        sys.exit(1)

    dest.write_text(builtin_path.read_text())
    click.echo(f"Copied {template_name} → {dest.relative_to(cfg.root)}")

    vars_ = _resolve(template_name)
    if vars_:
        click.echo("\nContext variables:")
        for v in vars_:
            click.echo(f"  {v['name']:<22} {v['type']:<6}  {v['desc']}")
    elif template_name in CONTEXT_FREE_TEMPLATES:
        click.echo("\n(No context variables — this template uses no Jinja2 substitutions.)")


@cmd.command("check")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
def check_cmd(project_dir: str | None) -> None:
    """Render all override templates with dummy context to catch errors early."""
    from jinja2 import TemplateError

    from gr4_modtool.templates import make_env

    cfg = load_config(Path(project_dir) if project_dir else None)
    od = _override_dir(cfg.root)

    if not od.is_dir() or not list(od.glob("*.j2")):
        click.echo("No override templates found.")
        return

    overrides = sorted(od.glob("*.j2"))
    click.echo(f"Checking {len(overrides)} override template(s)...")
    errors = 0

    for path in overrides:
        name = path.name
        dummy_ctx = {v["name"]: v["dummy"] for v in _resolve(name)}
        try:
            env = make_env(project_root=cfg.root)
            env.get_template(name).render(**dummy_ctx)
            click.echo(f"  {name:<40} OK")
        except TemplateError as exc:
            click.echo(f"  {name:<40} ERROR: {exc}")
            errors += 1

    if errors:
        click.echo(f"\n{errors} error(s) found.")
        sys.exit(1)
