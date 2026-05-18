# Configuration

gr4_modtool stores project metadata in `.gr4modtool.toml` at the project root. This file is created by `newmod` or `init` and read by all other commands.

## File format

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

## Fields

### `[project]`

| Field | Description |
|---|---|
| `name` | Module name (snake_case) |
| `version` | Semantic version string |
| `cpp_namespace` | Root C++ namespace, e.g. `gr::myfilters` |
| `cmake_prefix` | CMake target prefix, e.g. `gr4_myfilters` |
| `gr4_include_prefix` | Include prefix directory, typically `gnuradio-4.0` |

### `[build]`

| Field | Description |
|---|---|
| `cmake` | Whether the project uses CMake |
| `meson` | Whether the project uses Meson |

Both can be `true` if the project supports both build systems.

### `[groups]`

A mapping from group name to relative path from the project root.

```toml
[groups]
dsp = "blocks/dsp"
```

## Template overrides

gr4_modtool searches for templates in three locations, in order:

1. **Per-project overrides** — `.gr4modtool/templates/` in the project root
2. **Plugin templates** — registered via the `gr4_modtool.templates` entry point
3. **Built-in templates** — shipped with the package

Place a `.j2` file with the same name as a built-in template in `.gr4modtool/templates/` to override it for a specific project. The `MODTOOL_TEMPLATE_DIR` environment variable can also point to a directory of overrides.

### Built-in templates

| File | Generated output |
|---|---|
| `block.hpp.j2` | Block header (C++ struct, ports, GR_REGISTER_BLOCK) |
| `qa_block.cpp.j2` | Block unit test source |
| `bench_block.cpp.j2` | Throughput benchmark source |
| `plot_bench.py.j2` | Benchmark matplotlib plot script |
| `group_CMakeLists.txt.j2` | Group CMakeLists.txt |
| `group_meson.build.j2` | Group meson.build |
| `test_CMakeLists.txt.j2` | Test directory CMakeLists.txt |
| `test_meson.build.j2` | Test directory meson.build |
| `bench_CMakeLists.txt.j2` | Benchmarks CMakeLists.txt |
| `toplevel_CMakeLists.txt.j2` | Top-level CMakeLists.txt |
| `toplevel_meson.build.j2` | Top-level meson.build |
| `Doxyfile.j2` | Doxygen configuration |
| `clang-format.j2` | `.clang-format` style file |
| `clang-tidy.j2` | `.clang-tidy` checks file |
| `cmake_presets.json.j2` | `CMakePresets.json` (debug/release/asan/ubsan/tsan) |
| `vscode_settings.json.j2` | `.vscode/settings.json` |
| `vscode_launch.json.j2` | `.vscode/launch.json` |
| `devcontainer.json.j2` | `.devcontainer/devcontainer.json` |
| `Dockerfile.devcontainer.j2` | `.devcontainer/Dockerfile` |
| `ci_coverage.yml.j2` | `.github/workflows/coverage.yml` |
| `ci_release.yml.j2` | `.github/workflows/release.yml` |
| `ci_matrix.yml.j2` | `.github/workflows/matrix.yml` |
| `ci_sanitizers.yml.j2` | `.github/workflows/sanitizers.yml` |
| `pre_commit_config.yaml.j2` | `.pre-commit-config.yaml` |
| `gitignore.j2` | `.gitignore` |

## Plugin system

Third-party packages can register additional commands and templates by declaring entry points in their `pyproject.toml`:

```toml
[project.entry-points."gr4_modtool.commands"]
my_command = "my_package.commands.my_cmd:cmd"

[project.entry-points."gr4_modtool.templates"]
my_templates = "my_package:get_template_dir"
```

Plugin commands appear alongside the built-in commands in `gr4_modtool --help`. Plugin templates are searched after per-project overrides but before built-in templates.
