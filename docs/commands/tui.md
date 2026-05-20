# TUI

Launch an interactive terminal UI for keyboard-driven block management.

```bash
gr4_modtool tui [OPTIONS]
```

| Option | Description |
|---|---|
| `--project-dir PATH` | Project root (default: auto-detect) |

## Key bindings

| Key | Action |
|---|---|
| `n` | New block (interactive form) |
| `p` | Add parameter to selected block |
| `m` | Move block to another group |
| `c` | Copy block to a new name |
| `t` | Add test to selected block |
| `b` | New benchmark for selected block |
| `k` | Run `check` and show results |
| `s` | Show selected block's header |
| `f` | Format current group |
| `r` | Refresh the block tree |
| `q` | Quit |
| `Ctrl+P` | Command palette |
| `Escape` | Cancel / dismiss modal |

## Layout

The TUI shows a tree of groups and blocks on the left. Selecting a block highlights it. Pressing an action key opens a modal form (where applicable) or runs the operation directly and shows the result in the status bar.
