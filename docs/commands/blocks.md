# Block Lifecycle

## newblock

Generate a block header, test file, and build entries.

```bash
gr4_modtool newblock [OPTIONS]
```

| Option | Description |
|---|---|
| `--group TEXT` | Target group |
| `--template / -T ARCHETYPE` | Pre-fill ports and style from an archetype |
| `--simd` | Generate a SIMD-vectorization-friendly `processBulk` skeleton |
| `--project-dir PATH` | Project root |
| `--yes / -y` | Skip confirmation |

### Archetypes

Use `--template` to skip the port/style prompts with a sensible default:

| Archetype | Ports | Style |
|---|---|---|
| `source` | — → `out:T` | `processBulk` |
| `sink` | `in:T` → — | `processBulk` |
| `filter` | `in:T` → `out:T` | `processOne` |
| `decimator` | `in:T` → `out:T` | `processBulk` |
| `interpolator` | `in:T` → `out:T` | `processBulk` |
| `custom` | interactive | interactive |

```bash
gr4_modtool newblock --group dsp --template filter
```

### Interactive prompts

Without `--template`, you are asked for: block name, description, template parameters, input/output ports, processing style (`processOne` or `processBulk`), type list, and whether to generate a test.

**Generated files:**

- `blocks/<group>/include/gnuradio-4.0/<group>/<Name>.hpp`
- `blocks/<group>/test/qa_<Name>.cpp` (if `gen_test`)
- Updated `blocks/<group>/test/CMakeLists.txt` and `meson.build`

### SIMD / vectorization hints

`--simd` forces `processBulk` and generates a loop skeleton that a modern C++ compiler can auto-vectorize:

```bash
gr4_modtool newblock --group dsp --template filter --simd
```

The generated body uses `#pragma GCC ivdep` to tell GCC there are no loop-carried dependencies, and names `n` explicitly so the loop bound is invariant:

```cpp
[[nodiscard]] gr::work::Status processBulk(
    std::span<const T> in, std::span<T> out) noexcept {
    // SIMD-vectorizable: loop body has no cross-iteration dependencies.
    const std::size_t n = in.size();
#pragma GCC ivdep
    for (std::size_t i = 0; i != n; ++i) {
        out[i] = in[i]; // TODO: implement
    }
    return gr::work::Status::OK;
}
```

Tips for keeping the loop vectorizable:
- Avoid branches inside the loop body — use `std::clamp` or ternary expressions.
- Keep the element stride at 1 (sequential access).
- Do not call virtual functions or non-inline helpers inside the loop.
- If ports use different template types (e.g. `std::complex<T>`) verify that the compiler supports SIMD for that type.

---

## newparam

Insert an `Annotated<>` parameter into an existing block header.

```bash
gr4_modtool newparam [BLOCK_NAME] [PARAM_NAME] [OPTIONS]
```

| Option | Description |
|---|---|
| `--group TEXT` | Group containing the block |
| `--type TEXT` | C++ type (e.g. `float`, `int32_t`) |
| `--description TEXT` | Description for `Doc<"...">` |
| `--default TEXT` | C++ default value (e.g. `1.0f`) |
| `--project-dir PATH` | Project root |
| `--yes / -y` | Skip confirmation |

**Example:**

```bash
gr4_modtool newparam LowPass cutoff_freq --group dsp \
    --type float --description "Cutoff frequency in Hz" --default "1000.0f"
```

Inserts into the block struct (before `GR_MAKE_REFLECTABLE`):

```cpp
Annotated<float, Doc<"Cutoff frequency in Hz">> cutoff_freq{1000.0f};
```

And updates:

```cpp
GR_MAKE_REFLECTABLE(LowPass, in, out, cutoff_freq);
```

---

## cp

Copy a block to a new name, optionally into a different group.

```bash
gr4_modtool cp SRC_NAME DST_NAME [OPTIONS]
```

| Option | Description |
|---|---|
| `--from-group TEXT` | Source group (default: prompted) |
| `--to-group TEXT` | Destination group (default: same as source) |
| `--gen-test` | Also generate a test for the copy |
| `--project-dir PATH` | Project root |
| `--yes / -y` | Skip confirmation |

All occurrences of `SrcName` in the header are replaced with `DstName` using whole-word substitution. Cross-group copies update the namespace.

---

## mv

Move a block (header, test, build entries) from one group to another.

```bash
gr4_modtool mv [BLOCK_NAME] [OPTIONS]
```

| Option | Description |
|---|---|
| `--from TEXT` | Source group |
| `--to TEXT` | Destination group |
| `--project-dir PATH` | Project root |
| `--yes / -y` | Skip confirmation |

Updates namespace references in the header, `#include` paths in the test file, and removes/adds CMake and Meson entries in both groups.

---

## rename

Rename a block everywhere.

```bash
gr4_modtool rename [OLD_NAME] [NEW_NAME] [OPTIONS]
```

| Option | Description |
|---|---|
| `--group TEXT` | Group containing the block |
| `--project-dir PATH` | Project root |
| `--yes / -y` | Skip confirmation |

Renames: the header file, all symbol occurrences inside it, the test file and its include, and CMake/Meson entries.

---

## rm

Remove a block and all its associated files.

```bash
gr4_modtool rm [BLOCK_NAME] [OPTIONS]
```

| Option | Description |
|---|---|
| `--group TEXT` | Group containing the block |
| `--project-dir PATH` | Project root |
| `--yes / -y` | Skip confirmation |

Deletes the header, test source (if present), and removes CMake/Meson entries.
