# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.1.0] — 2025-05-17

Initial release.

### Added

**Scaffolding**
- `newmod` — scaffold a complete GNURadio 4 OOT project (CMakeLists.txt, meson.build, blocks/ layout, .gr4modtool.toml)
- `newgroup` — add a new block group directory with include/, test/, and build-system wiring

**Block lifecycle**
- `newblock` — generate a block header (`Block<>`, `PortIn/Out`, `GR_REGISTER_BLOCK`) plus optional test, with interactive prompts for template params, ports, processing style, and type list
- `newparam` — insert an `Annotated<T, Doc<"...">>` member variable into an existing block and update `GR_MAKE_REFLECTABLE`
- `cp` — copy a block to a new name with whole-word substitution; optionally copy into a different group or generate a test
- `mv` — move a block (header, test, build entries) from one group to another, rewriting namespace and includes
- `rename` — rename a block everywhere (header filename, struct name, test, build files)
- `rm` — remove a block and all its associated files and build entries

**Testing & benchmarking**
- `add-test` — generate `qa_<Block>.cpp` for a block that has no test, using header introspection
- `newbench` — generate `bench_<Block>.cpp` with `<chrono>` timing and CSV output; optional `--wire-build` flag to add CMake/Meson entries under an `ENABLE_BENCHMARKING` guard
- `test` — run a single block's `qa_*` binary inside an existing build directory via ctest or meson test

**Project health**
- `init` — auto-detect project name, groups, and include prefix from an existing project tree; write `.gr4modtool.toml`
- `check` — audit headers, test sources, and build entries for mismatches; `--json` flag for CI pipelines
- `info` — list all groups and blocks; `--json` flag for scripting
- `show` — display a block's header or test file with Rich C++ syntax highlighting

**Building & formatting**
- `build` — configure and build using CMake or Meson; optional `--test` and `--clean` flags
- `format` — run clang-format over all block headers and test sources; `--check` mode for CI

**Interactive**
- `tui` — Textual-based terminal UI with keyboard-driven block management (newblock, mv, cp, add-test, newbench, check)

**Infrastructure**
- Jinja2 template engine with per-project user-override search path
- Plugin system via `importlib.metadata` entry-points (`gr4_modtool.commands`, `gr4_modtool.templates`)
- CMake and Meson build-file surgery utilities (`project/cmake.py`, `project/meson.py`)
- Header introspection via `parse_header_info()` (template params, ports, type list, processing style)
- 107 unit tests
