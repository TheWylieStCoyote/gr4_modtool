# Scaffolding

## newmod

Scaffold a complete GNURadio 4 OOT project.

```bash
gr4_modtool newmod [OPTIONS]
```

| Option | Description |
|---|---|
| `--name TEXT` | Module name (snake_case) |
| `--version TEXT` | Initial version (default: `0.1.0`) |
| `--namespace TEXT` | C++ namespace (default: `gr::<name>`) |
| `--yes / -y` | Skip confirmation prompts |

**What it creates:**

```
<name>/
├── .gr4modtool.toml      # tool configuration
├── CMakeLists.txt
├── meson.build
├── meson_options.txt
└── blocks/
    ├── CMakeLists.txt
    └── meson.build
```

---

## newgroup

Add a block group directory to an existing project.

```bash
gr4_modtool newgroup [OPTIONS]
```

| Option | Description |
|---|---|
| `--name TEXT` | Group name (snake_case) |
| `--project-dir PATH` | Project root (default: auto-detect) |
| `--yes / -y` | Skip confirmation |

**What it creates:**

```
blocks/<name>/
├── CMakeLists.txt
├── meson.build
├── include/gnuradio-4.0/<name>/   # block headers go here
└── test/
    ├── CMakeLists.txt
    └── meson.build
```

It also updates `blocks/CMakeLists.txt` and `blocks/meson.build` to include the new group.
