# Project Health

## init

Bootstrap `.gr4modtool.toml` for an existing GNURadio 4 OOT project that doesn't have one.

```bash
gr4_modtool init [OPTIONS]
```

| Option | Description |
|---|---|
| `--project-dir PATH` | Project root (default: current directory) |
| `--yes / -y` | Accept all auto-detected values without prompting |

Auto-detects from the directory tree:

- **Project name** from `CMakeLists.txt` `project(...)` call
- **Groups** from `blocks/*/include/` subdirectories
- **GR4 include prefix** (e.g. `gnuradio-4.0`) from the include directory layout
- **Build systems** (CMake / Meson) from file presence

Raises an error if `.gr4modtool.toml` already exists.

---

## check

Audit the project for out-of-sync state between headers, test sources, and build files.

```bash
gr4_modtool check [OPTIONS]
```

| Option | Description |
|---|---|
| `--group TEXT` | Audit only this group |
| `--json` | Output results as JSON (for CI / scripting) |
| `--project-dir PATH` | Project root |

**Issues reported:**

| Severity | Condition |
|---|---|
| warning | Header has no matching `qa_*.cpp` test source |
| warning | Header is missing `GR_REGISTER_BLOCK` macro |
| error | Test source has no CMake entry |
| error | Test source has no Meson entry |
| error | CMake entry has no matching test source |
| error | Meson entry has no matching test source |

Exit code 1 if any errors are found. Example JSON output:

```json
{
  "issues": [
    {"group": "dsp", "block": "Ghost", "issue": "CMake entry has no test source", "severity": "error"}
  ],
  "error_count": 1,
  "warning_count": 0
}
```

---

## info

List all groups and blocks in the project.

```bash
gr4_modtool info [OPTIONS]
```

| Option | Description |
|---|---|
| `--json` | Output as JSON |
| `--project-dir PATH` | Project root |

Example JSON output:

```json
{
  "name": "myfilters",
  "version": "0.1.0",
  "cpp_namespace": "gr::myfilters",
  "build_cmake": true,
  "build_meson": false,
  "groups": [
    {
      "name": "dsp",
      "blocks": [{"name": "LowPassFilter"}, {"name": "HighPassFilter"}]
    }
  ]
}
```

---

## show

Display a block's header or test file with C++ syntax highlighting.

```bash
gr4_modtool show BLOCK_NAME [OPTIONS]
```

| Option | Description |
|---|---|
| `--group TEXT` | Group containing the block |
| `--test` | Show the test file instead of the header |
| `--project-dir PATH` | Project root |
