"""newblock command — add a block to an existing group."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import click
import questionary

from gr4_modtool.project.discovery import load_config, discover_groups
from gr4_modtool.project import cmake as cmake_mod
from gr4_modtool.project import meson as meson_mod
from gr4_modtool.templates import render


# --------------------------------------------------------------------------- #
# Archetypes
# --------------------------------------------------------------------------- #

ARCHETYPES: dict[str, dict] = {
    "source": {
        "in_ports": [],
        "out_ports": [{"name": "out", "type": "T"}],
        "processing_style": "processBulk",
    },
    "sink": {
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [],
        "processing_style": "processBulk",
    },
    "filter": {
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [{"name": "out", "type": "T"}],
        "processing_style": "processOne",
    },
    "decimator": {
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [{"name": "out", "type": "T"}],
        "processing_style": "processBulk",
    },
    "interpolator": {
        "in_ports": [{"name": "in", "type": "T"}],
        "out_ports": [{"name": "out", "type": "T"}],
        "processing_style": "processBulk",
    },
}

_ARCHETYPE_NAMES = list(ARCHETYPES.keys())

# --------------------------------------------------------------------------- #
# Validation helpers
# --------------------------------------------------------------------------- #

def _is_camel(name: str) -> bool:
    return bool(re.match(r"^[A-Z][A-Za-z0-9]*$", name))


def _resolve_port_type(raw: str, template_params: list[str]) -> str:
    """Turn short shorthands like 'T', 'complex<T>', 'TIN' into proper C++ types."""
    raw = raw.strip()
    if raw in template_params:
        return raw
    if raw.startswith("complex<") and raw.endswith(">"):
        inner = raw[8:-1].strip()
        return f"std::complex<{inner}>"
    # Allow 'std::complex<T>' as-is
    return raw


def _build_template_ctx(
    block_name: str,
    namespace: str,
    group: str,
    description: str,
    template_params: list[str],
    in_ports: list[dict],
    out_ports: list[dict],
    type_list: str,
    processing_style: str,
    gr4_include_prefix: str,
) -> dict:
    multi_output = len(out_ports) > 1
    uses_complex = any("complex" in p["type"] for p in in_ports + out_ports)

    template_decl = ", ".join(f"typename {p}" for p in template_params)
    template_args = ", ".join(template_params)

    if len(template_params) == 1:
        template_param_macro = f"([{template_params[0]}])"
    else:
        template_param_macro = f"([ {', '.join(template_params)} ])"

    if multi_output:
        return_type = "std::tuple<" + ", ".join(p["type"] for p in out_ports) + ">"
    else:
        return_type = out_ports[0]["type"] if out_ports else "void"

    if processing_style == "processOne":
        params_str = ", ".join(f"{p['type']} {p['name']}" for p in in_ports)
        bulk_params_str = ""
    else:
        in_spans = ", ".join(f"std::span<const {p['type']}> {p['name']}" for p in in_ports)
        out_spans = ", ".join(f"std::span<{p['type']}> {p['name']}" for p in out_ports)
        bulk_params_str = ", ".join(filter(None, [in_spans, out_spans]))
        params_str = ""

    all_port_names = [p["name"] for p in in_ports + out_ports]

    # Determine first_type for graph test (first element of type_list)
    first_type = type_list.split(",")[0].strip()
    # Resolve graph test port types
    first_port_type = in_ports[0]["type"].replace(template_params[0], first_type) if in_ports else first_type
    first_out_type = out_ports[0]["type"].replace(template_params[0], first_type) if out_ports else first_type

    return {
        "block_name": block_name,
        "namespace": namespace,
        "group": group,
        "description": description,
        "template_params": template_params,
        "template_decl": template_decl,
        "template_args": template_args,
        "template_param_macro": template_param_macro,
        "in_ports": in_ports,
        "out_ports": out_ports,
        "all_port_names": all_port_names,
        "type_list": type_list,
        "processing_style": processing_style,
        "uses_complex": uses_complex,
        "multi_output": multi_output,
        "return_type": return_type,
        "params_str": params_str,
        "bulk_params_str": bulk_params_str,
        "gr4_include_prefix": gr4_include_prefix,
        "first_type": first_type,
        "first_port_type": first_port_type,
        "first_out_type": first_out_type,
        "needs_graph_test": True,
    }


# --------------------------------------------------------------------------- #
# Prompt flow (shared between CLI and TUI)
# --------------------------------------------------------------------------- #

def prompt_newblock(
    cfg,
    group_name: str | None = None,
    archetype: str | None = None,
) -> dict | None:
    """Run the interactive prompt flow. Returns context dict or None if aborted."""
    groups = discover_groups(cfg)
    group_names = [g.name for g in groups]

    if not group_names:
        click.echo("No groups found. Run 'gr4_modtool newgroup' first.", err=True)
        return None

    if group_name is None:
        group_name = questionary.select("Group to add block to:", choices=group_names).ask()
        if group_name is None:
            return None

    block_name = questionary.text(
        "Block name (CamelCase, e.g. MyFilter):",
        validate=lambda v: _is_camel(v) or "Must be CamelCase starting with uppercase letter",
    ).ask()
    if block_name is None:
        return None

    description = questionary.text("One-line description:").ask()
    if description is None:
        return None

    # Template params
    multi_type = questionary.confirm("Multiple template type parameters? (e.g. TIN, TOUT)", default=False).ask()
    if multi_type:
        raw = questionary.text("Template parameter names (comma-separated, e.g. TIN,TOUT):").ask()
        if raw is None:
            return None
        template_params = [p.strip() for p in raw.split(",") if p.strip()]
    else:
        template_params = ["T"]

    # If archetype given, skip port/style prompts
    if archetype and archetype in ARCHETYPES:
        arch = ARCHETYPES[archetype]
        in_ports = arch["in_ports"]
        out_ports = arch["out_ports"]
        style = arch["processing_style"]
    else:
        # Input ports
        n_in = questionary.text(
            "Number of input ports:",
            default="1",
            validate=lambda v: v.isdigit() or "Enter a number",
        ).ask()
        if n_in is None:
            return None

        type_choices = [p for p in template_params] + [f"std::complex<{template_params[0]}>", "custom"]
        in_ports = []
        for i in range(int(n_in)):
            pname = questionary.text(f"  Input port {i+1} name:", default=f"in{i+1}" if int(n_in) > 1 else "in").ask()
            if pname is None:
                return None
            ptype_raw = questionary.select(f"  Input port {i+1} data type:", choices=type_choices).ask()
            if ptype_raw is None:
                return None
            if ptype_raw == "custom":
                ptype_raw = questionary.text("    Custom type:").ask() or "T"
            ptype = _resolve_port_type(ptype_raw, template_params)
            in_ports.append({"name": pname, "type": ptype})

        # Output ports
        n_out = questionary.text(
            "Number of output ports:",
            default="1",
            validate=lambda v: v.isdigit() or "Enter a number",
        ).ask()
        if n_out is None:
            return None

        out_ports = []
        for i in range(int(n_out)):
            pname = questionary.text(f"  Output port {i+1} name:", default=f"out{i+1}" if int(n_out) > 1 else "out").ask()
            if pname is None:
                return None
            ptype_raw = questionary.select(f"  Output port {i+1} data type:", choices=type_choices).ask()
            if ptype_raw is None:
                return None
            if ptype_raw == "custom":
                ptype_raw = questionary.text("    Custom type:").ask() or "T"
            ptype = _resolve_port_type(ptype_raw, template_params)
            out_ports.append({"name": pname, "type": ptype})

        # Processing style
        style = questionary.select(
            "Processing style:",
            choices=["processOne", "processBulk"],
        ).ask()
        if style is None:
            return None

    # Type list
    uses_complex = any("complex" in p["type"] for p in in_ports + out_ports)
    default_types = "float, double" if uses_complex or template_params == ["T"] else ", ".join(template_params)
    type_list = questionary.text(
        "GR_REGISTER_BLOCK type list (comma-separated C++ types):",
        default=default_types,
    ).ask()
    if type_list is None:
        return None

    gen_test = questionary.confirm("Generate test file?", default=True).ask()

    return {
        "group_name": group_name,
        "block_name": block_name,
        "description": description,
        "template_params": template_params,
        "in_ports": in_ports,
        "out_ports": out_ports,
        "processing_style": style,
        "type_list": type_list,
        "gen_test": gen_test,
    }


# --------------------------------------------------------------------------- #
# File writing (shared between CLI and TUI)
# --------------------------------------------------------------------------- #

def write_block_files(cfg, answers: dict) -> list[Path]:
    """Write all files for a new block. Returns list of created/modified paths."""
    group_name = answers["group_name"]
    block_name = answers["block_name"]
    gen_test = answers.get("gen_test", True)

    ctx = _build_template_ctx(
        block_name=block_name,
        namespace=cfg.cpp_namespace + f"::{group_name}",
        group=group_name,
        description=answers["description"],
        template_params=answers["template_params"],
        in_ports=answers["in_ports"],
        out_ports=answers["out_ports"],
        type_list=answers["type_list"],
        processing_style=answers["processing_style"],
        gr4_include_prefix=cfg.gr4_include_prefix,
    )

    written: list[Path] = []

    # Block header
    header_dir = cfg.group_include_dir(group_name)
    header_dir.mkdir(parents=True, exist_ok=True)
    header_path = header_dir / f"{block_name}.hpp"
    header_path.write_text(render("block.hpp.j2", ctx, cfg.root))
    written.append(header_path)

    if gen_test:
        test_dir = cfg.group_test_dir(group_name)
        test_dir.mkdir(parents=True, exist_ok=True)

        # Test source
        test_path = test_dir / f"qa_{block_name}.cpp"
        test_path.write_text(render("qa_block.cpp.j2", ctx, cfg.root))
        written.append(test_path)

        # Update CMakeLists.txt
        cmake_test = test_dir / "CMakeLists.txt"
        if cfg.build_cmake and cmake_test.exists():
            target_libs = f"{cfg.cmake_prefix}::blocks_{group_name}_headers"
            cmake_mod.append_test_entry(cmake_test, block_name, target_libs)
            written.append(cmake_test)

        # Update meson.build
        meson_test = test_dir / "meson.build"
        if cfg.build_meson and meson_test.exists():
            dep_var = f"gr4_{group_name}_blocks_dep"
            meson_mod.append_test_entry(meson_test, block_name, extra_deps=[dep_var])
            written.append(meson_test)

    return written


# --------------------------------------------------------------------------- #
# Click command
# --------------------------------------------------------------------------- #

@click.command("newblock")
@click.option("--project-dir", default=None, type=click.Path(exists=True))
@click.option("--group", default=None, help="Target group name.")
@click.option(
    "--template", "-T",
    type=click.Choice(_ARCHETYPE_NAMES + ["custom"]),
    default=None,
    help="Block archetype to use (pre-fills ports and processing style).",
)
def cmd(project_dir: str | None, group: str | None, template: str | None) -> None:
    """Add a new block to an existing group."""
    cfg = load_config(Path(project_dir) if project_dir else None)
    archetype = template if template and template != "custom" else None
    answers = prompt_newblock(cfg, group_name=group, archetype=archetype)
    if answers is None:
        sys.exit(0)

    click.echo("\nFiles to be written:")
    ctx = _build_template_ctx(
        block_name=answers["block_name"],
        namespace=cfg.cpp_namespace + f"::{answers['group_name']}",
        group=answers["group_name"],
        description=answers["description"],
        template_params=answers["template_params"],
        in_ports=answers["in_ports"],
        out_ports=answers["out_ports"],
        type_list=answers["type_list"],
        processing_style=answers["processing_style"],
        gr4_include_prefix=cfg.gr4_include_prefix,
    )
    header = cfg.group_include_dir(answers["group_name"]) / f"{answers['block_name']}.hpp"
    click.echo(f"  {header}")
    if answers.get("gen_test"):
        test_dir = cfg.group_test_dir(answers["group_name"])
        click.echo(f"  {test_dir / ('qa_' + answers['block_name'] + '.cpp')}")
        click.echo(f"  (update) {test_dir / 'CMakeLists.txt'}")
        click.echo(f"  (update) {test_dir / 'meson.build'}")

    confirm = questionary.confirm("\nProceed?", default=True).ask()
    if not confirm:
        sys.exit(0)

    written = write_block_files(cfg, answers)
    click.echo("\nCreated:")
    for p in written:
        click.echo(f"  {p}")
