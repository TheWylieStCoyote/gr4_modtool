# `gr4 migrate` — GNURadio 3 → GNURadio 4 Migration Command

## Overview

`gr4 migrate` ingests a GNURadio 3 OOT module and produces a GNURadio 4 OOT module
skeleton in gr4_modtool's standard layout. The goal is not full, silent migration — it
is **maximum automation with transparent residue**: everything that can be mechanically
translated is translated; everything that cannot is flagged with a structured `TODO`
comment and a line-item in the migration report. The user lands in a working build
skeleton with placeholders, not a broken partial state.

---

## Background: GR3 vs GR4 structural differences

| Dimension | GNURadio 3 | GNURadio 4 |
|-----------|-----------|-----------|
| File layout | `include/<mod>/Foo.h` + `lib/Foo_impl.h` + `lib/Foo_impl.cc` | Single `Foo.hpp` (header-only) |
| Base class | `gr::sync_block`, `gr::block`, `gr::decim_block<D>`, `gr::interp_block<I>` | `gr::Block<Derived<T>>` (CRTP) |
| Type handling | Fixed at instantiation via `sizeof(float)` in io_signature | Template parameter `T`; one struct covers all types |
| Processing | `int work(int n, gr_vector_const_void_star&, gr_vector_void_star&)` — raw void* | `T processOne(T x)` or `work::Status processBulk(SpanLike...)` — typed |
| Properties | `d_<name>` private + `virtual void set_<name>(T)` + `virtual T <name>() const` | `Annotated<T, "name", ...> name = default` + `GR_MAKE_REFLECTABLE` |
| Registration | `MYMOD_API` export + `make()` factory | `GR_REGISTER_BLOCK("ns::Name", Type, ([T]), [types])` |
| Header guard | `#ifndef INCLUDED_…` | `#pragma once` |
| Build system | `GrMakefile`, `GR_REGISTER_COMPONENT`, Python/SWIG targets | `gr4_modtool_add_ut_test`, `find_package(gnuradio-4.0)` |
| Namespaces | `gr::<mod>` (two levels) | `gr::<mod>::<group>` (three levels) |
| Python/GRC | SWIG/pybind11 bindings + `.block.yml` | Not yet available in GR4 |

---

## Command Interface

```
gr4 migrate [OPTIONS] SOURCE_DIR
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--output DIR` | `./gr4-<name>` | Where to write the migrated project |
| `--group TEXT` | Detected from CMakeLists | Override target group name for all blocks |
| `--dry-run / -n` | off | Show what would be created without writing anything |
| `--force` | off | Overwrite output directory if it already exists |
| `--json` | off | Emit migration report as JSON to stdout |
| `--skip-build` | off | Do not generate CMakeLists.txt / meson.build |
| `--namespace TEXT` | Inferred from module | Override the target C++ namespace |
| `--project-dir DIR` | None | Append to existing gr4_modtool project instead of creating a new one |

### Two primary modes

**Standalone** (default): creates a new project directory with `.gr4modtool.toml`,
`CMakeLists.txt`, and all block skeletons.

**Append** (`--project-dir`): adds a new group to an existing gr4_modtool project,
migrating all discovered GR3 blocks into that group. Does not touch existing groups.

---

## Files Added / Changed

### New files

```
gr4_modtool/commands/migrate.py           # CLI entry point, orchestration (~250 lines)
gr4_modtool/migrate/__init__.py           # Re-exports public symbols
gr4_modtool/migrate/detect.py             # GR3 project detection and metadata extraction
gr4_modtool/migrate/parse_gr3.py          # GR3 block parser (header + impl)
gr4_modtool/migrate/transform.py          # GR3BlockInfo → GR4 template context
gr4_modtool/migrate/report.py             # MigrationResult / MigrationReport data structures + renderers
tests/test_migrate.py                     # ~60 tests
tests/fixtures/gr3_oot/                   # Synthetic GR3 OOT project fixture (static files)
    CMakeLists.txt
    include/testmod/api.h
    include/testmod/sync_block.h
    include/testmod/source_block.h
    include/testmod/sink_block.h
    include/testmod/param_block.h
    include/testmod/hier_block.h
    lib/CMakeLists.txt
    lib/sync_block_impl.h
    lib/sync_block_impl.cc
    lib/source_block_impl.h
    lib/source_block_impl.cc
    lib/sink_block_impl.h
    lib/sink_block_impl.cc
    lib/param_block_impl.h
    lib/param_block_impl.cc
```

### Changed files

| File | Change |
|------|--------|
| `gr4_modtool/cli.py` | `from gr4_modtool.commands.migrate import cmd as migrate_cmd` + `cli.add_command(migrate_cmd, name="migrate")` |
| `gr4_modtool/api.py` | Add `MigrationResult`, `MigrationReport`, `detect_gr3_project`, `parse_gr3_block`, `migrate_project` to exports and `__all__` |

---

## Data Structures

### `Gr3BlockInfo` (internal, in `parse_gr3.py`)

```python
@dataclass
class Gr3BlockInfo:
    name: str                       # class name without _impl suffix (e.g. "my_block")
    header_path: Path               # include/mymod/my_block.h
    impl_header_path: Path | None   # lib/my_block_impl.h (may be absent)
    impl_source_path: Path | None   # lib/my_block_impl.cc (may be absent)
    base_class: str                 # "sync_block" | "block" | "decim_block" | "interp_block" | "hier_block2"
    in_types: list[str]             # deduced from io_signature (e.g. ["float"])
    out_types: list[str]            # deduced from io_signature
    in_port_count: int | None       # None = variable (io_signature::makev)
    out_port_count: int | None      # None = variable
    constructor_params: list[tuple[str, str]]  # [(type, name), ...]
    properties: list[Gr3Property]
    has_message_ports: bool
    has_set_history: bool           # set_history() call → decimation hint
    has_output_multiple: bool       # set_output_multiple() call
    work_body: str | None           # raw text of the work() function body
```

### `Gr3Property` (internal)

```python
@dataclass
class Gr3Property:
    name: str        # e.g. "alpha" (from set_alpha / alpha())
    type: str        # e.g. "float"
    default: str     # extracted from impl constructor, or "" if unknown
```

### `MigrationResult` (public, in `report.py`)

```python
@dataclass
class MigrationResult:
    block_name: str         # GR4 CamelCase name (e.g. "MyBlock")
    gr3_name: str           # original GR3 snake_case name (e.g. "my_block")
    status: str             # "auto" | "partial" | "manual" | "skipped"
    written_files: list[Path]
    todos: list[str]        # human-readable list of items needing manual attention
    detail: str             # one-line summary
```

**Status semantics:**
- `"auto"` — full skeleton generated; only `work()` body translation remains (a TODO comment is planted)
- `"partial"` — skeleton generated with notable caveats (variable ports, complex type deduction failed)
- `"manual"` — block requires manual porting (hier_block2, message ports, variable port counts)
- `"skipped"` — block was explicitly excluded or already exists at destination

### `MigrationReport` (public, in `report.py`)

```python
@dataclass
class MigrationReport:
    source_dir: Path
    output_dir: Path
    module_name: str
    target_namespace: str
    results: list[MigrationResult]

    @property
    def auto_count(self) -> int: ...
    @property
    def partial_count(self) -> int: ...
    @property
    def manual_count(self) -> int: ...
    @property
    def skipped_count(self) -> int: ...
```

---

## Module Breakdown

### `detect.py` — GR3 project detection

**Public function:**

```python
def detect_gr3_project(source: Path) -> Gr3ProjectMeta | None:
    """Return metadata if source looks like a GR3 OOT module, else None."""
```

**Detection heuristics (all must pass):**

1. `include/<name>/api.h` exists (GR3 OOT always has this)
2. `lib/` directory exists
3. Root `CMakeLists.txt` contains `GR_REGISTER_COMPONENT` or `find_package(Gnuradio`

**Metadata extracted:**

- `name` — from `project(gr-<name> ...)` in CMakeLists.txt
- `version` — from `set(VERSION_MAJOR ...)` / `project(... VERSION x.y.z ...)`
- `namespace` — inferred as `gr::<name>` (GR3 convention)
- `cmake_prefix` — inferred as `gr4_<name>`
- `block_names` — list of `.h` stems in `include/<name>/` excluding `api.h`

**`Gr3ProjectMeta` dataclass:**

```python
@dataclass
class Gr3ProjectMeta:
    name: str
    version: str
    gr3_namespace: str     # e.g. "gr::testmod"
    source_dir: Path
    block_header_dir: Path    # include/testmod/
    lib_dir: Path
    block_stems: list[str]    # ["sync_block", "param_block", ...]
```

---

### `parse_gr3.py` — GR3 block parser

**Public function:**

```python
def parse_gr3_block(
    name: str,
    header_path: Path,
    impl_header_path: Path | None,
    impl_source_path: Path | None,
) -> Gr3BlockInfo:
```

**Parsing steps:**

#### 1. Base class detection (from public header)

```python
_BASE_CLASS_PATTERNS = {
    "sync_block":   re.compile(r'public\s+gr::sync_block'),
    "block":        re.compile(r'public\s+gr::block\b'),
    "decim_block":  re.compile(r'public\s+gr::decim_block<(\d+)>'),
    "interp_block": re.compile(r'public\s+gr::interp_block<(\d+)>'),
    "hier_block2":  re.compile(r'public\s+gr::hier_block2'),
}
```

#### 2. I/O type extraction (from impl .cc)

```python
# Matches: io_signature::make(1, 1, sizeof(float))
_IOSIG_FIXED_RE  = re.compile(
    r'io_signature::make\(\s*(\d+)\s*,\s*(\d+)\s*,\s*sizeof\((\w[\w<>:, ]*)\)\s*\)'
)
# Matches: io_signature::make(0, 0, 0)  → no ports
_IOSIG_ZERO_RE   = re.compile(r'io_signature::make\(\s*0\s*,\s*0\s*,\s*0\s*\)')
# Matches: io_signature::makev(...)     → variable, can't auto-migrate
_IOSIG_VARV_RE   = re.compile(r'io_signature::makev\(')
```

`sizeof(float)` → `"float"`, `sizeof(gr_complex)` → `"std::complex<float>"`,
`sizeof(int)` → `"int32_t"`, `sizeof(short)` → `"int16_t"`.

The `sizeof` → C++ type mapping is a small lookup table; unrecognised types are kept
as-is with a TODO annotation.

#### 3. Property detection (from public header)

```python
# Finds: virtual void set_alpha(float val) = 0;
_SETTER_RE = re.compile(r'virtual\s+void\s+set_(\w+)\s*\(\s*(\w[\w<>:, ]*)\s+\w+\s*\)')
# Finds: virtual float alpha() const = 0;
_GETTER_RE = re.compile(r'virtual\s+(\w[\w<>:, ]*)\s+(\w+)\s*\(\s*\)\s*const')
```

A property is only emitted when a getter/setter pair with matching name exists.
Lone getters or lone setters are flagged in `todos`.

#### 4. Constructor parameter extraction (from impl .cc)

```python
# Matches constructor definition: my_block_impl::my_block_impl(int n, float alpha)
_CTOR_RE = re.compile(r'\w+_impl::\w+_impl\s*\(([^)]*)\)')
```

Param list is tokenised by comma; each token is split into type + name.
Constructor params that match a property name are omitted (they'll be represented
as `Annotated<>` members instead). Remaining non-property constructor params become
`Annotated<>` members with a `// TODO: review initial value` comment.

#### 5. Feature flags

```python
has_message_ports   = bool(re.search(r'message_port_register', combined_text))
has_set_history     = bool(re.search(r'set_history\s*\(',      combined_text))
has_output_multiple = bool(re.search(r'set_output_multiple\s*\(', combined_text))
```

#### 6. Work body extraction

```python
# Extracts the body of work() from the impl .cc
_WORK_BODY_RE = re.compile(
    r'int\s+\w+_impl::work\s*\([^)]*\)\s*\{(.*?)\n\}',
    re.DOTALL
)
```

The extracted body is stored verbatim and used to populate a `// TODO: translate` block
in the generated GR4 header.

---

### `transform.py` — GR3 → GR4 conversion

**Public function:**

```python
def gr3_to_gr4_context(
    block: Gr3BlockInfo,
    target_namespace: str,
    target_group: str,
    gr4_include_prefix: str = "gnuradio-4.0",
) -> tuple[dict, MigrationResult]:
    """
    Build the Jinja2 template context for a GR4 block header from a parsed GR3 block.
    Returns (context_dict, migration_result).
    """
```

**Archetype mapping:**

| GR3 base class | in_port_count | out_port_count | GR4 archetype |
|----------------|---------------|----------------|---------------|
| `sync_block` | 1 | 1 | `sync` |
| `sync_block` | 0 | 1 | `source` |
| `sync_block` | 1 | 0 | `sink` |
| `block` | 1 | 1 | `sync_bulk` |
| `block` | 0 | 1 | `source` |
| `block` | 1 | 0 | `sink` |
| `decim_block<D>` | 1 | 1 | `decimator` |
| `interp_block<I>` | 1 | 1 | `interpolator` |
| `hier_block2` | any | any | `manual` |
| any | None | any | `manual` (variable ports) |

**Type list construction:**

The GR3 `sizeof(T)` type(s) become the initial GR4 type list. The transformer also
adds the complex variant if the base type is `float` or `double` (common pattern),
but marks added types as "inferred" so the user can remove them if incorrect.

**Name conversion:**

`snake_case` → `UpperCamelCase`: `"my_block"` → `"MyBlock"`.

**Property conversion:**

Each `Gr3Property(name, type, default)` becomes:

```cpp
Annotated<float, "alpha", Visible,
    Doc<"TODO: describe alpha">> alpha = 0.0f;  // migrated from GR3 set_alpha/alpha()
```

If `default` is empty (couldn't be extracted), the default is the C++ zero-value
and a `// TODO: set initial value` comment is added.

**Work body placement:**

If `work_body` is non-None, it is inserted as a comment block in the processing function:

```cpp
[[nodiscard]] T processOne(T in) noexcept {
    // TODO: translate from GR3 work() body:
    // const float *in_buf = (const float *) input_items[0];
    // float *out_buf = (float *) output_items[0];
    // for (int i = 0; i < noutput_items; i++) { out_buf[i] = in_buf[i]; }
    // return noutput_items;
    return {};
}
```

**`manual` blocks:**

For `hier_block2` or variable-port blocks, no `.hpp` is generated. Instead, a
`<BlockName>_MANUAL.md` stub is written explaining why the block cannot be
auto-migrated and what the user needs to do.

---

### `report.py` — renderers

Two renderers mirror the pattern used in `ls.py` and `validate.py`:

**`_render_table(report, console=None)`** — Rich table:

```
Project: testmod  v0.9.0  gr::testmod
Migrated to: ./gr4-testmod

 Block           GR3 Class     Status    Notes
 ─────────────────────────────────────────────────
 MySync          sync_block    ✓ auto    work() body needs translation
 MySource        sync_block    ✓ auto    work() body needs translation
 ParamBlock      sync_block    ⚠ partial  property 'taps' type deduction failed
 HierBlock       hier_block2   ✗ manual  hier_block2 not auto-migratable

4 blocks: 2 auto, 1 partial, 1 manual

Next steps:
  1. Translate TODO work() bodies in each .hpp
  2. Review ParamBlock.hpp — taps property type needs manual verification
  3. Port HierBlock manually (see HierBlock_MANUAL.md)
  4. Run: gr4 validate --project-dir ./gr4-testmod
```

**`_render_json(report)`** — JSON with the full `MigrationReport` dict.

---

### `commands/migrate.py` — CLI orchestration

**Flow:**

```
1. detect_gr3_project(source_dir)
   └── None → error: "not a GR3 OOT module"

2. Resolve output_dir (default: ./gr4-<name>)
   ├── exists and not --force → error
   └── create directory tree

3. For each block_stem in meta.block_stems:
   a. parse_gr3_block(stem, header, impl_header, impl_source)
   b. gr3_to_gr4_context(block_info, namespace, group)
   c. If status != "manual":
      └── render block.hpp.j2 → output_dir/blocks/<group>/include/.../BlockName.hpp
   d. Generate test stub → output_dir/blocks/<group>/test/qa_BlockName.cpp
   e. Collect MigrationResult

4. If not --project-dir:
   a. Write .gr4modtool.toml  (via save_config)
   b. Write CMakeLists.txt skeleton (if not --skip-build)
   c. Write meson.build skeleton (if not --skip-build)

5. If --project-dir:
   a. load_config(project_dir)
   b. write_group_skeleton(cfg, group)
   c. Add group to config; save_config(cfg)

6. Print / emit MigrationReport
```

---

## Jinja2 Template Extension

A new template `migrate_todo.hpp.j2` is added alongside `block.hpp.j2`. It renders
the partially-migrated block header for cases where the work body is present but
type deduction succeeded. The template is identical to `block.hpp.j2` except the
processing function body includes the verbatim GR3 `work()` body as a comment block.

No changes to the existing `block.hpp.j2` — the migrate path uses the same template
with an extended context dict that includes `work_body_comment`.

---

## `api.py` additions

```python
from gr4_modtool.migrate.detect   import detect_gr3_project
from gr4_modtool.migrate.parse_gr3 import parse_gr3_block, Gr3BlockInfo
from gr4_modtool.migrate.report    import MigrationResult, MigrationReport
from gr4_modtool.commands.migrate  import migrate_project   # top-level convenience function

__all__ += [
    "detect_gr3_project",
    "parse_gr3_block",
    "Gr3BlockInfo",
    "MigrationResult",
    "MigrationReport",
    "migrate_project",
]
```

---

## Test Plan

### Fixture: `tests/fixtures/gr3_oot/`

A static synthetic GR3 OOT project committed to the test directory covering all
significant cases:

| Fixture block | GR3 base | Ports | Properties | Features |
|---|---|---|---|---|
| `sync_block` | sync_block | 1 in / 1 out `float` | none | identity work() |
| `source_block` | sync_block | 0 in / 1 out `float` | none | simple work() |
| `sink_block` | sync_block | 1 in / 0 out `float` | none | simple work() |
| `param_block` | sync_block | 1 in / 1 out `float` | `alpha: float = 0.5` | getter/setter + work() |
| `complex_block` | block | 1 in / 1 out `gr_complex` | none | raw block, bulk-style |
| `decim_block` | decim_block<4> | 1 in / 1 out `float` | none | |
| `interp_block` | interp_block<4> | 1 in / 1 out `float` | none | |
| `hier_block` | hier_block2 | 1 in / 1 out | none | manual only |
| `msg_block` | sync_block | 1 in / 1 out `float` | none | message_port_register |
| `varport_block` | block | variable | none | io_signature::makev |

**Root CMakeLists.txt** includes `project(gr-testmod VERSION 0.9.0)`,
`GR_REGISTER_COMPONENT("testmod" ...)`, `find_package(Gnuradio "3.10" REQUIRED)`.

---

### Test file: `tests/test_migrate.py`

#### Detection tests

| Test | Verifies |
|---|---|
| `test_detect_valid_gr3_project` | returns `Gr3ProjectMeta` for fixture |
| `test_detect_extracts_name` | `meta.name == "testmod"` |
| `test_detect_extracts_version` | `meta.version == "0.9.0"` |
| `test_detect_extracts_block_stems` | fixture block names appear in `meta.block_stems` |
| `test_detect_returns_none_for_gr4_project` | returns `None` when pointed at a GR4 project |
| `test_detect_returns_none_for_empty_dir` | returns `None` for empty directory |
| `test_detect_returns_none_for_random_dir` | returns `None` for a non-OOT directory |

#### Parser tests

| Test | Verifies |
|---|---|
| `test_parse_sync_block_base_class` | `base_class == "sync_block"` |
| `test_parse_sync_block_ports` | `in_port_count == 1`, `out_port_count == 1` |
| `test_parse_sync_block_types` | `in_types == ["float"]` |
| `test_parse_source_block_ports` | `in_port_count == 0`, `out_port_count == 1` |
| `test_parse_sink_block_ports` | `in_port_count == 1`, `out_port_count == 0` |
| `test_parse_param_block_properties` | `len(properties) == 1`, `properties[0].name == "alpha"` |
| `test_parse_param_block_property_type` | `properties[0].type == "float"` |
| `test_parse_param_block_default` | `properties[0].default == "0.5"` |
| `test_parse_complex_block_type` | `in_types == ["std::complex<float>"]` |
| `test_parse_decim_block_base_class` | `base_class == "decim_block"` |
| `test_parse_hier_block_base_class` | `base_class == "hier_block2"` |
| `test_parse_msg_block_flag` | `has_message_ports is True` |
| `test_parse_varport_block_port_count` | `in_port_count is None` |
| `test_parse_work_body_extracted` | `work_body` is non-empty string |
| `test_parse_missing_impl_graceful` | returns `Gr3BlockInfo` with `None` impl paths when absent |

#### Transformer tests

| Test | Verifies |
|---|---|
| `test_transform_sync_archetype` | context `processing_style == "processOne"` |
| `test_transform_source_archetype` | context `in_ports == []` |
| `test_transform_sink_archetype` | context `out_ports == []` |
| `test_transform_decim_archetype` | context maps to `decimator` processing style |
| `test_transform_name_camelcase` | `"my_block"` → `"MyBlock"` in context `block_name` |
| `test_transform_namespace` | context `namespace` matches `target_namespace` |
| `test_transform_property_becomes_annotated` | rendered hpp contains `Annotated<float` |
| `test_transform_work_body_in_todo` | rendered hpp contains original work() body as comment |
| `test_transform_hier_block_status_manual` | `result.status == "manual"` |
| `test_transform_varport_status_manual` | `result.status == "manual"` |
| `test_transform_msg_block_todo` | `result.todos` contains message-port warning |
| `test_transform_pragma_once_present` | rendered hpp starts with `#pragma once` |
| `test_transform_gr_register_block_present` | rendered hpp contains `GR_REGISTER_BLOCK` |
| `test_transform_type_list_from_gr3_type` | `float` in GR3 → `float, double` candidate types in hpp |

#### Report / renderer tests

| Test | Verifies |
|---|---|
| `test_migration_result_is_dataclass` | `hasattr(MigrationResult, "__dataclass_fields__")` |
| `test_migration_report_is_dataclass` | `hasattr(MigrationReport, "__dataclass_fields__")` |
| `test_report_auto_count` | `report.auto_count == 2` for 2 auto results |
| `test_report_manual_count` | `report.manual_count == 1` for 1 manual result |
| `test_render_table_contains_block_name` | Rich table output contains block name |
| `test_render_table_shows_auto_tick` | `"✓"` in output for auto block |
| `test_render_table_shows_manual_cross` | `"✗"` in output for manual block |
| `test_render_json_parses` | `json.loads(_render_json(report))` succeeds |
| `test_render_json_has_results_key` | JSON contains `"results"` list |

#### CLI integration tests

| Test | Verifies |
|---|---|
| `test_cli_dry_run_creates_no_files` | `--dry-run`: no files written to output dir |
| `test_cli_creates_output_dir` | output directory is created |
| `test_cli_creates_gr4modtool_toml` | `.gr4modtool.toml` exists in output |
| `test_cli_creates_block_headers` | `.hpp` file exists for each auto block |
| `test_cli_creates_test_stubs` | `qa_<Block>.cpp` exists for each auto block |
| `test_cli_manual_block_creates_md` | `<Block>_MANUAL.md` exists for hier_block |
| `test_cli_json_output_parses` | `--json` output is valid JSON with `results` key |
| `test_cli_invalid_source_exits_nonzero` | non-GR3 dir → exit code 1 |
| `test_cli_force_overwrites` | `--force` succeeds if output dir already exists |
| `test_cli_no_force_existing_dir_fails` | no `--force`, existing dir → exit code 1 |
| `test_cli_generated_hpp_validates` | `gr4 validate` on output reports no H-category errors |
| `test_cli_append_to_existing_project` | `--project-dir` adds group to existing config |

#### `api.py` regression

| Test | Verifies |
|---|---|
| `test_api_all_symbols_importable` | (existing test) catches new `__all__` entries |
| `test_detect_gr3_project_via_api` | `api.detect_gr3_project(fixture_path)` returns non-None |
| `test_migrate_project_clean` | `api.migrate_project(...)` returns `MigrationReport` |

---

## Limitations and Out of Scope

The following are intentionally deferred and documented in `_MANUAL.md` stubs:

| Feature | Reason not auto-migrated |
|---|---|
| `work()` body | Requires semantic understanding of void* pointer arithmetic |
| `gr::hier_block2` | GR4 has no direct equivalent hierarchy mechanism yet |
| Variable port counts (`io_signature::makev`) | GR4 ports are compile-time members, not runtime arrays |
| Message ports (`message_port_register_in/out`) | GR4 uses a different message passing API |
| Python bindings (SWIG/pybind11) | GR4 Python support is not yet stable |
| GRC `.block.yml` definitions | GR4 UI layer not yet settled |
| Custom `set_output_multiple` constraints | GR4 uses different scheduler hints |
| `set_history()` (guard samples) | GR4 history API is still evolving |
| Tagged stream blocks | GR4 tag propagation API differs significantly |

Each limitation produces a TODO item in `MigrationResult.todos` and a note in the
rendered report.

---

## Verification Sequence

```bash
cd /home/wylie/Documents/work/gnuradio/gr4_modtool

# Unit tests for the new command
.venv/bin/python -m pytest tests/test_migrate.py -v

# Full regression
.venv/bin/python -m pytest tests/ -q --tb=short

# Ruff
.venv/bin/ruff check gr4_modtool/migrate/ gr4_modtool/commands/migrate.py tests/test_migrate.py

# Smoke test against the real gr4-incubator structure (should detect as NOT gr3)
.venv/bin/gr4 migrate /home/wylie/Documents/work/gnuradio/worktree/gr4-incubator.git/space2 --dry-run
# Expected: "Error: not a GNURadio 3 OOT module"
```
