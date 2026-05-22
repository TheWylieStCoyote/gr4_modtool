"""migrate command — port a GNURadio 3 OOT module to GNURadio 4 layout."""

from __future__ import annotations

import dataclasses
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import click
from rich import box
from rich.console import Console
from rich.table import Table

from gr4_modtool.commands.newblock import _build_template_ctx
from gr4_modtool.commands.newgroup import write_group_skeleton
from gr4_modtool.project.discovery import ProjectConfig, save_config
from gr4_modtool.templates import render

# ---------------------------------------------------------------------------
# GR3 detection regexes
# ---------------------------------------------------------------------------

_GR3_CMAKE_RE = re.compile(
    r"find_package\s*\(\s*[Gg]nuradio|GR_REGISTER_COMPONENT|gnuradio_version",
    re.MULTILINE,
)
_GR3_PROJECT_NAME_RE = re.compile(r"project\s*\(\s*gr-(\w+)", re.IGNORECASE)
_GR3_PROJECT_VERSION_RE = re.compile(
    r"project\s*\([^)]*\bVERSION\s+([\d.]+)"
    r"|set\s*\(\s*VERSION\s+[\"']?([\d.]+)[\"']?\s*\)",
    re.DOTALL | re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# GR3 parser regexes
# ---------------------------------------------------------------------------

_BASE_MAP: dict[str, re.Pattern] = {
    "sync_block": re.compile(r"public\s+gr::sync_block\b"),
    "block": re.compile(r"public\s+gr::block\b"),
    "decim_block": re.compile(r"public\s+gr::decim_block<"),
    "interp_block": re.compile(r"public\s+gr::interp_block<"),
    "hier_block2": re.compile(r"public\s+gr::hier_block2\b"),
}

_IOSIG_FIXED_RE = re.compile(
    r"io_signature::make\(\s*(\d+)\s*,\s*(\d+)\s*,\s*sizeof\(\s*([\w<>:, *]+?)\s*\)\s*\)"
)
_IOSIG_ZERO_RE = re.compile(r"io_signature::make\(\s*0\s*,\s*0\s*,\s*0\s*\)")
_IOSIG_VARV_RE = re.compile(r"io_signature::makev\(|io_signature::make\(\s*\d+\s*,\s*-1")

_SETTER_RE = re.compile(r"virtual\s+void\s+set_(\w+)\s*\(\s*([\w<>:, *&]+?)\s+\w+\s*\)")
_GETTER_RE = re.compile(r"virtual\s+([\w<>:, *]+?)\s+(\w+)\s*\(\s*\)\s*const")

_MEMBER_INIT_RE = re.compile(r"\bd_(\w+)\s*\(\s*([^,)]+?)\s*\)")
_WORK_BODY_RE = re.compile(
    r"int\s+\w+_impl::work\s*\([^{]*\)\s*\{(.*?)\n\}",
    re.DOTALL,
)

# ---------------------------------------------------------------------------
# sizeof → C++ type map
# ---------------------------------------------------------------------------

_SIZEOF_MAP: dict[str, str] = {
    "float": "float",
    "double": "double",
    "gr_complex": "std::complex<float>",
    "int": "int32_t",
    "short": "int16_t",
    "char": "int8_t",
    "uint8_t": "uint8_t",
    "int8_t": "int8_t",
    "int16_t": "int16_t",
    "int32_t": "int32_t",
    "int64_t": "int64_t",
    "uint32_t": "uint32_t",
    "uint64_t": "uint64_t",
}

# base_class × (in_count, out_count) → processing_style string
_STYLE_MAP: dict[tuple[str, int, int], str] = {
    ("sync_block", 1, 1): "processOne",
    ("sync_block", 0, 1): "processBulk",
    ("sync_block", 1, 0): "processBulk",
    ("block", 1, 1): "processBulk",
    ("block", 0, 1): "processBulk",
    ("block", 1, 0): "processBulk",
    ("decim_block", 1, 1): "processBulk",
    ("interp_block", 1, 1): "processBulk",
}

# ---------------------------------------------------------------------------
# Internal metadata container
# ---------------------------------------------------------------------------


@dataclass
class Gr3Property:
    name: str
    type: str
    default: str  # empty string if unknown


@dataclass
class Gr3BlockInfo:
    name: str
    header_path: Path
    impl_header_path: Path | None
    impl_source_path: Path | None
    base_class: str
    in_port_count: int | None  # None → variable ports
    out_port_count: int | None
    in_types: list[str]
    out_types: list[str]
    properties: list[Gr3Property]
    constructor_params: list[tuple[str, str]]
    has_message_ports: bool
    has_set_history: bool
    has_output_multiple: bool
    work_body: str | None


# ---------------------------------------------------------------------------
# Public data structures
# ---------------------------------------------------------------------------


@dataclass
class MigrationResult:
    block_name: str
    gr3_name: str
    status: str  # "auto" | "partial" | "manual" | "skipped"
    written_files: list[Path] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)
    detail: str = ""


@dataclass
class MigrationReport:
    source_dir: Path
    output_dir: Path
    module_name: str
    target_namespace: str
    results: list[MigrationResult] = field(default_factory=list)

    @property
    def auto_count(self) -> int:
        return sum(1 for r in self.results if r.status == "auto")

    @property
    def partial_count(self) -> int:
        return sum(1 for r in self.results if r.status == "partial")

    @property
    def manual_count(self) -> int:
        return sum(1 for r in self.results if r.status == "manual")

    @property
    def skipped_count(self) -> int:
        return sum(1 for r in self.results if r.status == "skipped")


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


@dataclass
class _Gr3Meta:
    name: str
    version: str
    include_dir: Path  # include/<mod>/
    lib_dir: Path
    block_stems: list[str]


def detect_gr3_project(source: Path) -> _Gr3Meta | None:
    """Return metadata if source is a GR3 OOT module, else None."""
    cmake = source / "CMakeLists.txt"
    lib = source / "lib"
    if not cmake.exists() or not lib.is_dir():
        return None
    if not _GR3_CMAKE_RE.search(cmake.read_text()):
        return None

    # Find include/<mod>/api.h
    include_root = source / "include"
    if not include_root.is_dir():
        return None
    api_files = list(include_root.glob("*/api.h")) + list(include_root.glob("*/api.hpp"))
    if not api_files:
        return None
    include_dir = api_files[0].parent

    cmake_text = cmake.read_text()
    name_m = _GR3_PROJECT_NAME_RE.search(cmake_text)
    name = name_m.group(1) if name_m else source.name.removeprefix("gr-")

    ver_m = _GR3_PROJECT_VERSION_RE.search(cmake_text)
    if ver_m:
        version = next(g for g in ver_m.groups() if g is not None)
    else:
        version = "0.1.0"

    block_stems = [
        p.stem
        for p in sorted(include_dir.glob("*.h")) + sorted(include_dir.glob("*.hpp"))
        if p.stem not in ("api", "api")
    ]

    return _Gr3Meta(
        name=name,
        version=version,
        include_dir=include_dir,
        lib_dir=lib,
        block_stems=block_stems,
    )


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _resolve_sizeof(raw: str) -> str:
    key = raw.strip()
    return _SIZEOF_MAP.get(key, key)


def _parse_iosig(text: str) -> tuple[int | None, int | None, list[str], list[str]]:
    """Return (in_count, out_count, in_types, out_types) from impl source text."""
    if _IOSIG_VARV_RE.search(text):
        return None, None, [], []

    matches = _IOSIG_FIXED_RE.findall(text)
    # First match = input sig, second = output sig
    in_count, out_count = None, None
    in_types: list[str] = []
    out_types: list[str] = []

    for idx, (lo, _hi, type_raw) in enumerate(matches[:2]):
        count = int(lo)
        cpp_type = _resolve_sizeof(type_raw)
        if idx == 0:
            in_count = count
            in_types = [cpp_type] if count > 0 else []
        else:
            out_count = count
            out_types = [cpp_type] if count > 0 else []

    # Handle explicit zero-port signatures
    zero_matches = _IOSIG_ZERO_RE.findall(text)
    if not matches:
        if len(zero_matches) >= 2:
            return 0, 0, [], []
        # Try to get zero from the zero pattern combined with a fixed pattern
        if len(zero_matches) == 1 and len(matches) == 0:
            in_count = 0
            in_types = []

    return in_count, out_count, in_types, out_types


def _parse_properties(header_text: str, impl_text: str) -> list[Gr3Property]:
    setters: dict[str, str] = {}
    for m in _SETTER_RE.finditer(header_text):
        name, type_ = m.group(1), m.group(2).strip()
        setters[name] = type_

    getters: dict[str, str] = {}
    for m in _GETTER_RE.finditer(header_text):
        type_, name = m.group(1).strip(), m.group(2)
        # Filter out known non-property virtual methods
        if name not in ("make", "unique_id", "name", "symbol_name"):
            getters[name] = type_

    defaults: dict[str, str] = {}
    for m in _MEMBER_INIT_RE.finditer(impl_text):
        pname, val = m.group(1), m.group(2).strip()
        # Strip numeric literal suffixes
        cleaned = re.sub(r"([0-9.]+)[fFlLuU]+$", r"\1", val)
        defaults[pname] = cleaned

    props = []
    for name in sorted(setters.keys() & getters.keys()):
        props.append(
            Gr3Property(
                name=name,
                type=setters[name],
                default=defaults.get(name, ""),
            )
        )
    return props


def parse_gr3_block(
    name: str,
    header_path: Path,
    impl_header_path: Path | None,
    impl_source_path: Path | None,
) -> Gr3BlockInfo:
    """Parse a GR3 block's files and return a Gr3BlockInfo."""
    header_text = header_path.read_text() if header_path.exists() else ""
    impl_h_text = (
        impl_header_path.read_text() if impl_header_path and impl_header_path.exists() else ""
    )
    impl_cc_text = (
        impl_source_path.read_text() if impl_source_path and impl_source_path.exists() else ""
    )
    combined = header_text + impl_h_text + impl_cc_text

    # Base class
    base_class = "unknown"
    for cls, pat in _BASE_MAP.items():
        if pat.search(header_text):
            base_class = cls
            break

    # I/O signature
    in_count, out_count, in_types, out_types = _parse_iosig(impl_cc_text)

    # Properties
    properties = _parse_properties(header_text, impl_cc_text)

    # Constructor params (non-property)
    prop_names = {p.name for p in properties}
    ctor_params: list[tuple[str, str]] = []
    ctor_m = re.search(r"\w+_impl::\w+_impl\s*\(([^)]*)\)", impl_cc_text)
    if ctor_m and ctor_m.group(1).strip():
        for token in ctor_m.group(1).split(","):
            parts = token.strip().rsplit(None, 1)
            if len(parts) == 2:
                ptype, pname = parts
                pname_clean = pname.lstrip("*&")
                if pname_clean not in prop_names:
                    ctor_params.append((ptype.strip(), pname_clean))

    # Feature flags
    has_message_ports = "message_port_register" in combined
    has_set_history = "set_history(" in combined
    has_output_multiple = "set_output_multiple(" in combined

    # Work body
    work_body: str | None = None
    wb_m = _WORK_BODY_RE.search(impl_cc_text)
    if wb_m:
        work_body = wb_m.group(1)

    return Gr3BlockInfo(
        name=name,
        header_path=header_path,
        impl_header_path=impl_header_path,
        impl_source_path=impl_source_path,
        base_class=base_class,
        in_port_count=in_count,
        out_port_count=out_count,
        in_types=in_types,
        out_types=out_types,
        properties=properties,
        constructor_params=ctor_params,
        has_message_ports=has_message_ports,
        has_set_history=has_set_history,
        has_output_multiple=has_output_multiple,
        work_body=work_body,
    )


# ---------------------------------------------------------------------------
# Name conversion
# ---------------------------------------------------------------------------


def _to_camel(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_"))


# ---------------------------------------------------------------------------
# Type list inference
# ---------------------------------------------------------------------------

_COMPLEX_EXPAND = {
    "float": "float, double, std::complex<float>, std::complex<double>",
    "double": "float, double, std::complex<float>, std::complex<double>",
    "std::complex<float>": "std::complex<float>, std::complex<double>",
    "std::complex<double>": "std::complex<float>, std::complex<double>",
    "int32_t": "int8_t, int16_t, int32_t",
    "int16_t": "int8_t, int16_t, int32_t",
    "uint8_t": "uint8_t, uint16_t, uint32_t",
}


def _infer_type_list(cpp_types: list[str], todos: list[str]) -> str:
    for t in cpp_types:
        if t in _COMPLEX_EXPAND:
            return _COMPLEX_EXPAND[t]
        if t in _SIZEOF_MAP.values():
            return t
    if cpp_types:
        todos.append(
            f"type list: could not auto-infer from '{cpp_types[0]}' — review GR_REGISTER_BLOCK types"
        )
        return cpp_types[0] if cpp_types else "float, double"
    return "float, double"


def _make_ports(count: int, types: list[str], prefix: str, todos: list[str]) -> list[dict]:
    if count == 0:
        return []
    cpp_type = types[0] if types else "float"
    # Map to template param T when type is a standard scalar
    if cpp_type in ("float", "double", "int32_t"):
        port_type = "T"
    elif cpp_type in ("std::complex<float>", "std::complex<double>"):
        port_type = "T"
    else:
        port_type = "T"
        if cpp_type not in _SIZEOF_MAP.values():
            todos.append(
                f"port type '{cpp_type}' not recognised — verify port type in generated header"
            )

    if count == 1:
        return [{"name": prefix, "type": port_type}]
    return [{"name": f"{prefix}{i}", "type": port_type} for i in range(count)]


# ---------------------------------------------------------------------------
# Property injection
# ---------------------------------------------------------------------------

_REFLECTABLE_RE = re.compile(r"(    GR_MAKE_REFLECTABLE\([^)]+\);)")


def _inject_properties(hpp: str, properties: list[Gr3Property]) -> str:
    if not properties:
        return hpp
    lines = ["", "    // Properties migrated from GR3 getter/setter pairs:"]
    for p in properties:
        default_str = f" = {p.default}" if p.default else ""
        lines.append(
            f'    Annotated<{p.type}, "{p.name}", Visible,'
            f' Doc<"TODO: describe {p.name}">>'
            f" {p.name}{default_str};"
            f"  // migrated from set_{p.name}()/{p.name}()"
        )
    lines.append("    // TODO: add property names to GR_MAKE_REFLECTABLE() above")
    insert = "\n".join(lines) + "\n"

    def _replacer(m: re.Match) -> str:
        return m.group(0) + insert

    return _REFLECTABLE_RE.sub(_replacer, hpp, count=1)


# ---------------------------------------------------------------------------
# Transformer
# ---------------------------------------------------------------------------

_MANUAL_MD = """\
# {block_name} — Manual Migration Required

This block could not be automatically migrated from GNURadio 3.

**GR3 name:** `{gr3_name}`
**Reason:** {reason}

## Steps to port manually

1. Create `{block_name}.hpp` in the appropriate include directory.
2. Inherit from `gr::Block<{block_name}<T>>` (CRTP pattern).
3. Declare `PortIn<T>` / `PortOut<T>` members for each port.
4. Implement `processOne()` or `processBulk()` with your logic.
5. Add `GR_REGISTER_BLOCK(...)` and `GR_MAKE_REFLECTABLE(...)`.
6. Run `gr4 validate` to check the result.

See the [GNURadio 4 block documentation](https://gnuradio.org/doc/doxygen/group__runtime.html)
for details.
"""


def _gr3_to_answers(
    block: Gr3BlockInfo,
    cfg: ProjectConfig,
    group: str,
) -> tuple[dict, MigrationResult]:
    todos: list[str] = []
    block_name = _to_camel(block.name)

    # Hard manual cases
    if block.base_class == "hier_block2":
        return {}, MigrationResult(
            block_name,
            block.name,
            "manual",
            [],
            ["hier_block2 has no GR4 equivalent yet"],
            "hier_block2 — manual port required",
        )
    if block.in_port_count is None or block.out_port_count is None:
        return {}, MigrationResult(
            block_name,
            block.name,
            "manual",
            [],
            ["variable port count (io_signature::makev) cannot be auto-migrated"],
            "variable ports — manual port required",
        )

    # Determine processing style
    key = (block.base_class, block.in_port_count, block.out_port_count)
    processing_style = _STYLE_MAP.get(key)
    status = "auto"

    if processing_style is None:
        # Multi-port or unknown pattern — fall back to processBulk
        processing_style = "processBulk"
        todos.append(
            f"multi-port block ({block.in_port_count} in, {block.out_port_count} out)"
            " — review port names and types"
        )
        status = "partial"

    # Ports
    in_ports = _make_ports(block.in_port_count, block.in_types, "in", todos)
    out_ports = _make_ports(block.out_port_count, block.out_types, "out", todos)
    type_list = _infer_type_list(block.in_types + block.out_types, todos)

    # Feature flag todos
    if block.has_message_ports:
        todos.append("message ports: translate message_port_register_in/out to GR4 message API")
        status = "partial"
    if block.has_set_history:
        todos.append("set_history(): GR4 history API differs — review scheduler hints")
        status = "partial"
    if block.has_output_multiple:
        todos.append("set_output_multiple(): GR4 uses different scheduler hints")
        status = "partial"

    # Work body comment
    work_body_comment = ""
    if block.work_body:
        comment_lines = ["        // TODO: translate GR3 work() body:"]
        for line in block.work_body.strip().splitlines():
            comment_lines.append(f"        //   {line.rstrip()}")
        work_body_comment = "\n".join(comment_lines)
    else:
        todos.append("work() body not found — implement processing logic manually")

    if todos and status == "auto":
        status = "partial"

    detail = "work() body needs translation" if block.work_body else "no work() body found"

    answers = {
        "group_name": group,
        "block_name": block_name,
        "description": f"Migrated from GR3 gr::{block.name}",
        "template_params": ["T"],
        "in_ports": in_ports,
        "out_ports": out_ports,
        "processing_style": processing_style,
        "type_list": type_list,
        "gen_test": True,
        "simd": False,
        "work_body_comment": work_body_comment,
        "properties": block.properties,
    }
    result = MigrationResult(block_name, block.name, status, [], todos, detail)
    return answers, result


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

_STATUS_STYLE = {
    "auto": "[green]✓ auto[/green]",
    "partial": "[yellow]⚠ partial[/yellow]",
    "manual": "[red]✗ manual[/red]",
    "skipped": "[dim]– skipped[/dim]",
}


def _render_table(report: MigrationReport, console: Console | None = None) -> None:
    if console is None:
        console = Console()

    console.print(
        f"\n[bold]Project:[/bold] {report.module_name}"
        f"  [dim]{report.source_dir}[/dim]"
        f"  [dim]→[/dim]  [bold]{report.output_dir}[/bold]"
    )
    console.print()

    tbl = Table(
        title="Migration Results",
        box=box.SIMPLE,
        show_header=True,
        header_style="bold cyan",
    )
    tbl.add_column("Block", style="white")
    tbl.add_column("GR3 Base", style="dim")
    tbl.add_column("Status", justify="center")
    tbl.add_column("Detail", style="dim")

    for r in report.results:
        tbl.add_row(
            r.block_name,
            r.gr3_name,
            _STATUS_STYLE.get(r.status, r.status),
            r.detail,
        )

    console.print(tbl)

    total = len(report.results)
    console.print(
        f"[bold]{total} block(s):[/bold] "
        f"[green]{report.auto_count} auto[/green], "
        f"[yellow]{report.partial_count} partial[/yellow], "
        f"[red]{report.manual_count} manual[/red], "
        f"[dim]{report.skipped_count} skipped[/dim]"
    )

    todos_all = [(r.block_name, t) for r in report.results for t in r.todos]
    if todos_all:
        console.print("\n[bold]Next steps:[/bold]")
        for i, (bname, todo) in enumerate(todos_all, 1):
            console.print(f"  {i}. [cyan]{bname}[/cyan]: {todo}")
    console.print(f"\n  Run: [bold]gr4 validate --project-dir {report.output_dir}[/bold]")


def _render_json(report: MigrationReport) -> str:
    def _serialise(obj):
        if isinstance(obj, Path):
            return str(obj)
        raise TypeError(f"Not serialisable: {type(obj)}")

    data = {
        "source_dir": str(report.source_dir),
        "output_dir": str(report.output_dir),
        "module_name": report.module_name,
        "target_namespace": report.target_namespace,
        "summary": {
            "auto": report.auto_count,
            "partial": report.partial_count,
            "manual": report.manual_count,
            "skipped": report.skipped_count,
        },
        "results": [dataclasses.asdict(r) for r in report.results],
    }
    return json.dumps(data, indent=2, default=_serialise)


# ---------------------------------------------------------------------------
# Manual stub writer
# ---------------------------------------------------------------------------


def _write_manual_stub(output_dir: Path, result: MigrationResult) -> None:
    reason = result.todos[0] if result.todos else "unknown"
    text = _MANUAL_MD.format(
        block_name=result.block_name,
        gr3_name=result.gr3_name,
        reason=reason,
    )
    (output_dir / f"{result.block_name}_MANUAL.md").write_text(text)


# ---------------------------------------------------------------------------
# Public orchestrator
# ---------------------------------------------------------------------------


def migrate_project(
    source_dir: Path,
    output_dir: Path,
    *,
    group: str | None = None,
    namespace_override: str | None = None,
    dry_run: bool = False,
) -> MigrationReport:
    """Migrate a GR3 OOT module to a GR4 project skeleton.

    Returns a MigrationReport describing every block's outcome.
    Raises ValueError if source_dir is not a GR3 OOT module.
    """
    meta = detect_gr3_project(source_dir)
    if meta is None:
        raise ValueError(f"{source_dir} does not look like a GNURadio 3 OOT module")

    target_group = group or meta.name
    target_namespace = namespace_override or f"gr::{meta.name}"

    cfg = ProjectConfig(
        root=output_dir,
        name=meta.name,
        version=meta.version,
        cpp_namespace=target_namespace,
        cmake_prefix=f"gr4_{meta.name}",
        gr4_include_prefix="gnuradio-4.0",
        build_cmake=True,
        build_meson=False,
        groups={target_group: f"blocks/{target_group}"},
    )

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        save_config(cfg)
        write_group_skeleton(cfg, target_group)

    results: list[MigrationResult] = []

    for stem in meta.block_stems:
        header = meta.include_dir / f"{stem}.h"
        if not header.exists():
            header = meta.include_dir / f"{stem}.hpp"
        impl_h = meta.lib_dir / f"{stem}_impl.h"
        impl_cc = meta.lib_dir / f"{stem}_impl.cc"

        block_info = parse_gr3_block(
            stem,
            header,
            impl_h if impl_h.exists() else None,
            impl_cc if impl_cc.exists() else None,
        )

        answers, result = _gr3_to_answers(block_info, cfg, target_group)

        if result.status == "manual":
            if not dry_run:
                _write_manual_stub(output_dir, result)
                result.written_files.append(output_dir / f"{result.block_name}_MANUAL.md")
            results.append(result)
            continue

        if not dry_run:
            group_ns = target_namespace + f"::{target_group}"
            ctx = _build_template_ctx(
                block_name=answers["block_name"],
                namespace=group_ns,
                group=target_group,
                description=answers["description"],
                template_params=answers["template_params"],
                in_ports=answers["in_ports"],
                out_ports=answers["out_ports"],
                type_list=answers["type_list"],
                processing_style=answers["processing_style"],
                gr4_include_prefix=cfg.gr4_include_prefix,
            )
            ctx["work_body_comment"] = answers["work_body_comment"]

            hpp_text = render("block.hpp.j2", ctx, cfg.root)
            hpp_text = _inject_properties(hpp_text, answers["properties"])

            header_dir = cfg.group_include_dir(target_group)
            header_dir.mkdir(parents=True, exist_ok=True)
            hpp_path = header_dir / f"{answers['block_name']}.hpp"
            hpp_path.write_text(hpp_text)
            result.written_files.append(hpp_path)

            # Test stub + CMake/meson wiring
            from gr4_modtool.commands.add_test import write_test_for_block

            try:
                test_files = write_test_for_block(cfg, target_group, answers["block_name"])
                result.written_files.extend(test_files)
            except (FileExistsError, FileNotFoundError, ValueError):
                pass

        results.append(result)

    return MigrationReport(
        source_dir=source_dir,
        output_dir=output_dir,
        module_name=meta.name,
        target_namespace=target_namespace,
        results=results,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.command("migrate")
@click.argument("source_dir", type=click.Path(exists=True, file_okay=False))
@click.option(
    "--output",
    "output_dir",
    default=None,
    help="Output directory (default: ./gr4-<name>).",
)
@click.option("--group", default=None, help="Target group name for all migrated blocks.")
@click.option(
    "--namespace", "namespace_override", default=None, help="Override target C++ namespace."
)
@click.option(
    "--dry-run", "-n", is_flag=True, help="Show what would be created without writing anything."
)
@click.option("--force", is_flag=True, help="Overwrite output directory if it already exists.")
@click.option("--json", "output_json", is_flag=True, help="Emit migration report as JSON.")
def cmd(
    source_dir: str,
    output_dir: str | None,
    group: str | None,
    namespace_override: str | None,
    dry_run: bool,
    force: bool,
    output_json: bool,
) -> None:
    """Migrate a GNURadio 3 OOT module to GNURadio 4 layout."""
    src = Path(source_dir).resolve()

    meta = detect_gr3_project(src)
    if meta is None:
        click.echo(f"Error: {src} does not look like a GNURadio 3 OOT module", err=True)
        sys.exit(1)

    out = Path(output_dir).resolve() if output_dir else Path.cwd() / f"gr4-{meta.name}"

    if out.exists() and not dry_run and not force:
        click.echo(
            f"Error: output directory '{out}' already exists. Use --force to overwrite.",
            err=True,
        )
        sys.exit(1)

    try:
        report = migrate_project(
            src,
            out,
            group=group,
            namespace_override=namespace_override,
            dry_run=dry_run,
        )
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    if output_json:
        click.echo(_render_json(report))
        return

    _render_table(report)
