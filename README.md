# gr4_modtool

A command-line tool for creating and managing [GNURadio 4](https://github.com/gnuradio/gnuradio) out-of-tree (OOT) block modules. It scaffolds projects, generates block headers and tests from templates, manages build-system wiring, and keeps everything in sync.

[![Tests](https://github.com/TheWylieStCoyote/gr4_modtool/actions/workflows/tests.yml/badge.svg)](https://github.com/TheWylieStCoyote/gr4_modtool/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)

---

## Features

| Category | Commands |
|---|---|
| Scaffolding | `newmod`, `newgroup` |
| Block lifecycle | `newblock`, `newparam`, `cp`, `mv`, `rename`, `rm` |
| Testing | `add-test`, `test` |
| Benchmarking | `newbench` |
| Project health | `init`, `check`, `info`, `show` |
| Building | `build`, `format` |
| Interactive | `tui` |

- **CMake and Meson** build systems supported side-by-side
- **Jinja2 templates** with per-project override support
- **Plugin system** — third-party packages can register extra commands and templates via entry-points
- **Textual TUI** for keyboard-driven block management

---

## Installation

```bash
pip install gr4_modtool
```

For development:

```bash
git clone https://github.com/TheWylieStCoyote/gr4_modtool
cd gr4_modtool
pip install -e ".[dev]"
```

---

## Quick Start

### Create a new OOT module

```bash
gr4_modtool newmod --name myfilters
cd myfilters
```

### Add a block group and a block

```bash
gr4_modtool newgroup --name dsp
gr4_modtool newblock --group dsp
# Interactive prompts: block name, ports, template params, …
```

### Check project health

```bash
gr4_modtool check           # Rich table of warnings/errors
gr4_modtool check --json    # Machine-readable output for CI
```

### View a block's header with syntax highlighting

```bash
gr4_modtool show MyFilter --group dsp
```

### Add a parameter to an existing block

```bash
gr4_modtool newparam MyFilter gain --group dsp \
    --type float --description "Linear gain" --default "1.0f"
```

### Copy or move blocks

```bash
gr4_modtool cp MyFilter MyFilter2 --from-group dsp --gen-test
gr4_modtool mv MyFilter --from dsp --to channel
```

### Generate a benchmark

```bash
gr4_modtool newbench MyFilter --group dsp --wire-build
```

### Build the project

```bash
gr4_modtool build --test          # configure, build, run tests
gr4_modtool test MyFilter         # re-run one block's test only
gr4_modtool format --check        # lint C++ formatting (CI mode)
```

### Adopt an existing project

```bash
cd /path/to/existing/gr4-oot-project
gr4_modtool init --yes            # auto-detect groups and write .gr4modtool.toml
gr4_modtool info --json           # list all blocks as JSON
```

### Interactive TUI

```bash
gr4_modtool tui
```

---

## Command Reference

See the [full documentation](https://thewyliestcoyote.github.io/gr4_modtool) for detailed options.

| Command | Description |
|---|---|
| `newmod` | Scaffold a new GNURadio 4 OOT project |
| `newgroup` | Add a new block group directory |
| `newblock` | Add a new block (header + test + build entries) |
| `newparam` | Insert an `Annotated<>` parameter into an existing block |
| `newbench` | Generate a throughput benchmark for a block |
| `add-test` | Generate a test file for a block that has none |
| `cp` | Copy a block to a new name (optionally into a different group) |
| `mv` | Move a block from one group to another |
| `rename` | Rename a block everywhere (header, test, build files) |
| `rm` | Remove a block and all its associated files |
| `init` | Bootstrap `.gr4modtool.toml` for an existing project |
| `check` | Audit the project for out-of-sync headers, tests, and build entries |
| `info` | List all groups and blocks |
| `show` | Display a block's header or test file with syntax highlighting |
| `build` | Configure and build using CMake or Meson |
| `test` | Run a single block's test binary without rebuilding |
| `format` | Run clang-format over headers and test sources |
| `tui` | Launch the interactive Textual TUI |

---

## Configuration

gr4_modtool stores project metadata in `.gr4modtool.toml` at the project root:

```toml
[project]
name = "myfilters"
version = "0.1.0"
cpp_namespace = "gr::myfilters"
cmake_prefix = "gr4_myfilters"
gr4_include_prefix = "gnuradio-4.0"

[build]
cmake = true
meson = false

[groups]
dsp = "blocks/dsp"
channel = "blocks/channel"
```

---

## License

MIT — see [LICENSE](LICENSE).
