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

Place a `.j2` file with the same name as a built-in template in a directory
pointed to by the `MODTOOL_TEMPLATE_DIR` environment variable. gr4_modtool
searches user templates before built-in ones.

Built-in templates:

| File | Generated output |
|---|---|
| `block.hpp.j2` | Block header |
| `qa_block.cpp.j2` | Test file |
| `bench_block.cpp.j2` | Benchmark file |
| `group_CMakeLists.txt.j2` | Group CMakeLists.txt |
| `group_meson.build.j2` | Group meson.build |
| `test_CMakeLists.txt.j2` | Test CMakeLists.txt |
| `test_meson.build.j2` | Test meson.build |
| `toplevel_CMakeLists.txt.j2` | Top-level CMakeLists.txt |
| `toplevel_meson.build.j2` | Top-level meson.build |
| `bench_CMakeLists.txt.j2` | Benchmarks CMakeLists.txt |
