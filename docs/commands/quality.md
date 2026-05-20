# CI & Code Quality

## ci

Write GitHub Actions workflow files for CI quality gates.

```bash
gr4_modtool ci [OPTIONS]
```

| Option | Description |
|---|---|
| `--coverage` | Write `.github/workflows/coverage.yml` |
| `--release` | Write `.github/workflows/release.yml` |
| `--matrix / --no-matrix` | Write `.github/workflows/matrix.yml` |
| `--project-dir PATH` | Project root |

At least one of `--coverage`, `--release`, or `--matrix` must be specified.

### `--coverage`

Builds with `gcovr`, uploads an HTML report as an artifact, and fails the job if line coverage drops below a configurable threshold.

### `--release`

Triggers on `v*.*.*` tags and uses `softprops/action-gh-release` to create a GitHub Release with a source tarball.

### `--matrix`

Generates a build matrix across two compilers and two build types:

```yaml
strategy:
  matrix:
    compiler: [gcc, clang]
    build_type: [Debug, Release]
```

Each combination sets `CC`/`CXX` environment variables via `include:` entries.

---

## presets

Write `CMakePresets.json` and optionally a sanitizer CI workflow.

```bash
gr4_modtool presets [OPTIONS]
```

| Option | Description |
|---|---|
| `--init` | Write both `CMakePresets.json` and `.github/workflows/sanitizers.yml` |
| `--presets-only` | Write only `CMakePresets.json` |
| `--project-dir PATH` | Project root |

**CMakePresets.json** defines five presets:

| Preset | Purpose |
|---|---|
| `default` | Standard Debug build |
| `release` | Optimised Release build |
| `asan` | AddressSanitizer + Debug |
| `ubsan` | UndefinedBehaviorSanitizer + Debug |
| `tsan` | ThreadSanitizer + Debug |

Use presets directly:

```bash
cmake --preset asan
cmake --build --preset asan
```

**`sanitizers.yml`** (with `--init`) runs `asan` and `ubsan` presets as separate CI jobs.

---

## pre-commit

Write a `.pre-commit-config.yaml` with local C++ quality hooks.

```bash
gr4_modtool pre-commit [OPTIONS]
```

| Option | Description |
|---|---|
| `--project-dir PATH` | Project root |
| `--yes / -y` | Skip confirmation |

The generated config installs two local hooks that run on every commit:

| Hook | Command | Files |
|---|---|---|
| `clang-format` | `clang-format --dry-run --Werror` | `*.cpp`, `*.hpp`, `*.h` |
| `gr4-tidy` | `gr4_modtool tidy` | `*.hpp` |

**Install pre-commit and activate:**

```bash
pip install pre-commit
pre-commit install
```

After activation, both hooks run automatically on `git commit`. Run manually with:

```bash
pre-commit run --all-files
```
