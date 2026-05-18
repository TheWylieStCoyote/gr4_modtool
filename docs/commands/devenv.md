# Developer Environment

## vscode

Write `.vscode/settings.json` and `.vscode/launch.json` for the project.

```bash
gr4_modtool vscode [OPTIONS]
```

| Option | Description |
|---|---|
| `--project-dir PATH` | Project root |
| `--yes / -y` | Skip confirmation |

**`settings.json`** configures:

- `cmake.buildDirectory` pointing at `${workspaceFolder}/build`
- `clangd.arguments` with `--compile-commands-dir=build` for accurate symbol resolution
- `editor.formatOnSave` with `clangd` as the C++ formatter

**`launch.json`** adds a `C++ (GDB)` debug configuration with a `promptString` input so you can pick the test binary to debug without editing the file.

Running the command again is safe: files are merged rather than overwritten, so any manual edits are preserved.

---

## devcontainer

Write a `.devcontainer/` directory with a Dockerfile and `devcontainer.json`.

```bash
gr4_modtool devcontainer [OPTIONS]
```

| Option | Description |
|---|---|
| `--project-dir PATH` | Project root |
| `--yes / -y` | Skip confirmation |

Creates:

```
.devcontainer/
├── devcontainer.json    # VS Code / GitHub Codespaces config
└── Dockerfile           # Ubuntu-based image with GNURadio 4 dependencies
```

The Dockerfile installs: `cmake`, `ninja-build`, `clang`, `clang-tidy`, `clang-format`, `libfmt-dev`, `python3-pip`, and `gr4_modtool` itself.

---

## completion

Print the shell completion setup line for bash, zsh, or fish.

```bash
gr4_modtool completion --shell SHELL
```

| Option | Description |
|---|---|
| `--shell TEXT` | One of `bash`, `zsh`, `fish` (required) |
| `--print-script` | Emit the full completion script (pipe to a file) |

**Setup (one-time):**

```bash
# bash — add to ~/.bashrc
eval "$(_GR4_MODTOOL_COMPLETE=bash_source gr4_modtool)"

# zsh — add to ~/.zshrc
eval "$(_GR4_MODTOOL_COMPLETE=zsh_source gr4_modtool)"

# fish — add to ~/.config/fish/config.fish
_GR4_MODTOOL_COMPLETE=fish_source gr4_modtool | source
```

Run `gr4_modtool completion --shell bash` to print the correct line for your shell without having to remember the syntax.

To install the script to a file (e.g. for system-wide completions):

```bash
gr4_modtool completion --shell bash --print-script > /etc/bash_completion.d/gr4_modtool
```
