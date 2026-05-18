# Testing & Benchmarks

## add-test

Generate `qa_<Block>.cpp` for a block that has no test yet.

```bash
gr4_modtool add-test [BLOCK_NAME] [OPTIONS]
```

| Option | Description |
|---|---|
| `--group TEXT` | Group containing the block |
| `--project-dir PATH` | Project root |
| `--yes / -y` | Skip confirmation |

Parses the block header via regex to recover template parameters, ports, type list, and processing style, then renders `qa_block.cpp.j2` and adds the entry to CMakeLists.txt and meson.build.

---

## newbench

Generate a throughput benchmark for an existing block.

```bash
gr4_modtool newbench [BLOCK_NAME] [OPTIONS]
```

| Option | Description |
|---|---|
| `--group TEXT` | Group containing the block |
| `--wire-build` | Add CMake/Meson entries for the benchmark |
| `--project-dir PATH` | Project root |
| `--yes / -y` | Skip confirmation |

Creates `blocks/<group>/benchmarks/bench_<Name>.cpp` with `<chrono>` timing over 2²⁰ samples and CSV output (`block,config,N,throughput_MSas`).

When `--wire-build` is set:
- Creates `blocks/<group>/benchmarks/CMakeLists.txt` if it doesn't exist
- Adds the executable entry
- Wraps the `add_subdirectory(benchmarks)` call in an `if(ENABLE_BENCHMARKING)` guard in the group CMakeLists.txt
- Does the equivalent for Meson (`enable_benchmarking` option in `meson_options.txt`)

---

## test

Run a single block's test binary inside an existing build directory — no rebuild.

```bash
gr4_modtool test BLOCK_NAME [OPTIONS]
```

| Option | Description |
|---|---|
| `--build-dir PATH` | Build directory (default: `build`) |
| `--verbose / -v` | Pass `--verbose` to ctest/meson |
| `--project-dir PATH` | Project root |

For CMake projects runs:

```bash
ctest --test-dir <build_dir> -R qa_<BLOCK_NAME> --output-on-failure
```

For Meson projects runs:

```bash
meson test -C <build_dir> qa_<BLOCK_NAME>
```
