# Building & Formatting

## build

Configure and build the project using CMake or Meson. Does not require `.gr4modtool.toml`.

```bash
gr4_modtool build [OPTIONS]
```

| Option | Description |
|---|---|
| `--build-dir PATH` | Build directory (default: `build`) |
| `--clean` | Delete build directory before configuring |
| `--test` | Run tests after building |
| `--jobs / -j INT` | Parallel build jobs (default: CPU count) |
| `--reconfigure` | Re-run cmake/meson setup even if already configured |
| `--cmake-args TEXT` | Extra arguments passed to `cmake` (repeatable) |
| `--project-dir PATH` | Project root |

Auto-detects the build system: CMake if `CMakeLists.txt` is present, otherwise Meson.

**CMake flow:**

```bash
cmake -B build [--cmake-args]
cmake --build build --parallel <jobs>
ctest --test-dir build --output-on-failure   # if --test
```

**Meson flow:**

```bash
meson setup build .
ninja -C build [-j jobs]
meson test -C build                          # if --test
```

---

## format

Run `clang-format` over all block headers and test sources.

```bash
gr4_modtool format [OPTIONS]
```

| Option | Description |
|---|---|
| `--group TEXT` | Format only this group |
| `--check` | Dry-run mode: exit 1 if any file needs formatting |
| `--style TEXT` | clang-format style (`file`, `llvm`, `google`, …) |
| `--project-dir PATH` | Project root |

If `clang-format` is not installed, the command prints a warning and exits 0 (so it doesn't break CI on machines without it — add a separate CI step to enforce installation if needed).

**CI usage:**

```yaml
- name: Check C++ formatting
  run: gr4_modtool format --check --style file
```
