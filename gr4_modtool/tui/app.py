"""Textual TUI for gr4_modtool."""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import ClassVar

from rich.syntax import Syntax
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Select,
    Static,
    Tree,
)
from textual.widgets.tree import TreeNode

from gr4_modtool.project.discovery import (
    BlockInfo,
    GroupInfo,
    ProjectConfig,
    discover_groups,
    load_config,
)

# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------

_HELP_TEXT = """\
[bold]Navigation[/bold]
  Arrow keys          Move in tree
  /                   Focus filter input

[bold]Block actions[/bold]
  n   New block          r   Rename block
  d   Delete block       p   Add parameter
  m   Move block         c   Copy block
  s   Show header        t   Add test
  b   New benchmark      f   Format group
  X   Run block test

[bold]Project[/bold]
  g   New group          B   Build project
  k   Run check          F5  Refresh
  ?   This help          q   Quit
"""

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_APP_CSS = """
Screen {
    layout: vertical;
}
#main-area {
    layout: horizontal;
    height: 1fr;
}
#left-panel {
    width: 36;
    layout: vertical;
}
ProjectTree {
    height: 1fr;
    border: solid $primary;
}
#filter-input {
    border: solid $surface-lighten-1;
    height: 3;
}
DetailPanel {
    width: 1fr;
    border: solid $primary;
    padding: 1 2;
    overflow-y: auto;
}
.modal-form {
    width: 66;
    height: auto;
    max-height: 90vh;
    border: solid $primary;
    background: $surface;
    padding: 2 4;
    margin: 1 2;
}
.modal-form--narrow {
    width: 52;
}
.modal-form--wide {
    width: 100%;
    height: 80vh;
}
.modal-form--wide RichLog {
    height: 1fr;
    border: solid $surface-lighten-2;
    margin-top: 1;
}
.button-row {
    margin-top: 1;
    height: 3;
}
.button-row Button {
    margin-right: 1;
}
Label {
    margin-top: 1;
}
"""


# ---------------------------------------------------------------------------
# Port spec helper
# ---------------------------------------------------------------------------

def _parse_ports(raw: str) -> list[dict]:
    """Parse 'in:T; aux:std::complex<T>' into [{"name": "in", "type": "T"}, …]."""
    ports = []
    for part in raw.split(";"):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            name, typ = part.split(":", 1)
            ports.append({"name": name.strip(), "type": typ.strip()})
        else:
            ports.append({"name": part, "type": "T"})
    return ports


# ---------------------------------------------------------------------------
# Project tree
# ---------------------------------------------------------------------------

class ProjectTree(Tree):
    """Left-panel tree: groups → blocks with status badges."""

    def populate(
        self,
        groups: list[GroupInfo],
        cfg: ProjectConfig,
        filter_query: str = "",
    ) -> None:
        self.clear()
        self.root.expand()
        q = filter_query.lower()
        for group in groups:
            blocks = [b for b in group.blocks if not q or q in b.name.lower()]
            group_label = Text()
            group_label.append(group.name, style="bold cyan")
            group_label.append(f"  {len(group.blocks)}", style="dim")
            node = self.root.add(group_label, expand=True, data=group)
            if not blocks:
                node.add_leaf(Text("(no blocks)", style="dim"), data=None)
                continue
            for block in blocks:
                has_header = (cfg.group_include_dir(group.name) / f"{block.name}.hpp").exists()
                has_test = (cfg.group_test_dir(group.name) / f"qa_{block.name}.cpp").exists()
                label = Text(block.name)
                if has_header and has_test:
                    label.append("  ✓", style="bold green")
                elif has_header:
                    label.append("  ~", style="yellow")
                else:
                    label.append("  ✗", style="bold red")
                node.add_leaf(label, data=block)


# ---------------------------------------------------------------------------
# Detail panel
# ---------------------------------------------------------------------------

class DetailPanel(ScrollableContainer):
    """Right-panel: syntax-highlighted block preview or project stats."""

    def show_welcome(self, cfg: ProjectConfig, groups: list[GroupInfo]) -> None:
        self.remove_children()
        build = " + ".join(
            s for s, flag in [("CMake", cfg.build_cmake), ("Meson", cfg.build_meson)] if flag
        ) or "none"
        total = sum(len(g.blocks) for g in groups)
        g_s = "s" if len(groups) != 1 else ""
        b_s = "s" if total != 1 else ""
        self.mount(
            Static(f"[bold cyan]● {cfg.name}[/bold cyan]  [dim]v{cfg.version}[/dim]"),
            Static(f"[dim]Namespace:[/dim]  {cfg.cpp_namespace}"),
            Static(f"[dim]Build:[/dim]      {build}"),
            Static(""),
            Static(f"[bold]{len(groups)} group{g_s}  •  {total} block{b_s}[/bold]"),
            Static(""),
        )
        for g in groups:
            bc = len(g.blocks)
            self.mount(Static(f"  [cyan]{g.name}[/cyan]  [dim]{bc} block{'s' if bc != 1 else ''}[/dim]"))
        self.mount(
            Static(""),
            Static("[dim]Select a block in the tree  •  [bold]?[/bold] for help[/dim]"),
        )

    def show_block(self, block_name: str, header_path: Path) -> None:
        self.remove_children()
        self.mount(
            Static(f"[bold]{block_name}.hpp[/bold]"),
            Static(f"[dim]{header_path}[/dim]"),
            Static(""),
        )
        try:
            code = header_path.read_text()
            self.mount(Static(Syntax(code, "cpp", line_numbers=True, theme="monokai")))
        except OSError:
            self.mount(Static("[red]Could not read header.[/red]"))

    def show_message(self, message: str) -> None:
        self.remove_children()
        self.mount(Static(message))


# ---------------------------------------------------------------------------
# Help modal
# ---------------------------------------------------------------------------

class HelpScreen(ModalScreen):
    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "dismiss", "Close"),
        Binding("question_mark", "dismiss", "Close"),
    ]

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-form"):
            yield Label("[bold]gr4_modtool — Keyboard Shortcuts[/bold]")
            yield Static("")
            yield Static(_HELP_TEXT)
            yield Button("Close", variant="primary", id="close-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()


# ---------------------------------------------------------------------------
# Build output screen
# ---------------------------------------------------------------------------

class BuildOutputScreen(ModalScreen):
    """Runs one or more commands sequentially, streaming output into a log."""

    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "dismiss", "Close")]

    def __init__(self, cmds: list[list[str]], cwd: Path) -> None:
        super().__init__()
        self._cmds = cmds
        self._cwd = cwd

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-form modal-form--wide"):
            yield Label(f"[bold]$ {' '.join(self._cmds[0])}[/bold]", id="cmd-label")
            yield RichLog(id="output-log", highlight=False, markup=False)
            yield Button("Close", variant="default", id="close-btn", disabled=True)

    def on_mount(self) -> None:
        threading.Thread(target=self._run_all, daemon=True).start()

    def _run_all(self) -> None:
        import subprocess
        log = self.query_one(RichLog)
        for cmd in self._cmds:
            self.app.call_from_thread(
                self.query_one("#cmd-label", Label).update,
                f"[bold]$ {' '.join(cmd)}[/bold]",
            )
            self.app.call_from_thread(log.write, f"$ {' '.join(cmd)}")
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=self._cwd,
            )
            assert proc.stdout is not None
            for line in proc.stdout:
                self.app.call_from_thread(log.write, line.rstrip())
            proc.wait()
            rc = proc.returncode
            self.app.call_from_thread(log.write, f"\n[Exit code {rc}]\n")
            if rc != 0:
                self.app.call_from_thread(self._finish, rc)
                return
        self.app.call_from_thread(self._finish, 0)

    def _finish(self, rc: int) -> None:
        btn = self.query_one("#close-btn", Button)
        btn.disabled = False
        btn.label = f"Close  (exit {rc})"
        btn.variant = "primary" if rc == 0 else "error"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()


# ---------------------------------------------------------------------------
# New group modal
# ---------------------------------------------------------------------------

class NewGroupScreen(ModalScreen):
    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "dismiss", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-form modal-form--narrow"):
            yield Label("[bold]New Group[/bold]")
            yield Label("Group name [dim](snake_case)[/dim]:")
            yield Input(placeholder="dsp", id="group-name")
            yield Horizontal(
                Button("Create", variant="primary", id="ok-btn"),
                Button("Cancel", variant="default", id="cancel-btn"),
                classes="button-row",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
            return
        name = self.query_one("#group-name", Input).value.strip()
        if not name:
            self.query_one("#group-name", Input).border_title = "Required!"
            return
        self.dismiss(name)


# ---------------------------------------------------------------------------
# New block modal
# ---------------------------------------------------------------------------

class NewBlockScreen(ModalScreen):
    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "dismiss", "Cancel")]

    def __init__(
        self,
        cfg: ProjectConfig,
        groups: list[GroupInfo],
        default_group: str | None = None,
    ) -> None:
        super().__init__()
        self._cfg = cfg
        self._groups = groups
        self._default_group = default_group

    def compose(self) -> ComposeResult:
        from gr4_modtool.commands.newblock import ARCHETYPES
        options = [(g.name, g.name) for g in self._groups]
        default = self._default_group or (self._groups[0].name if self._groups else Select.BLANK)
        archetype_opts = [("custom", "custom")] + [(k, k) for k in ARCHETYPES]
        with Vertical(classes="modal-form"):
            yield Label("[bold]New Block[/bold]")
            yield Label("Group:")
            yield Select(options=options, value=default, id="group-select")
            yield Label("Block name [dim](CamelCase)[/dim]:")
            yield Input(placeholder="MyFilter", id="block-name")
            yield Label("Description:")
            yield Input(placeholder="One-line description", id="description")
            yield Label("Archetype [dim](pre-fills ports/style)[/dim]:")
            yield Select(options=archetype_opts, value="custom", id="archetype-select")
            yield Label("Template params [dim](comma-sep, e.g. T or TIN,TOUT)[/dim]:")
            yield Input(value="T", placeholder="T", id="template-params")
            yield Label("Input ports [dim](name:type separated by ;)[/dim]:")
            yield Input(value="in:T", placeholder="in:T; aux:float", id="in-ports")
            yield Label("Output ports [dim](name:type separated by ;)[/dim]:")
            yield Input(value="out:T", placeholder="out:T", id="out-ports")
            yield Label("Processing style:")
            yield Select(
                options=[("processOne", "processOne"), ("processBulk", "processBulk")],
                value="processOne",
                id="style-select",
            )
            yield Label("Type list [dim](comma-sep C++ types)[/dim]:")
            yield Input(placeholder="float, double", id="type-list")
            yield Horizontal(
                Button("Create", variant="primary", id="ok-btn"),
                Button("Cancel", variant="default", id="cancel-btn"),
                classes="button-row",
            )

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "archetype-select":
            return
        from gr4_modtool.commands.newblock import ARCHETYPES
        arch = str(event.value)
        if arch == "custom" or arch not in ARCHETYPES:
            return
        a = ARCHETYPES[arch]
        in_str = "; ".join(f"{p['name']}:{p['type']}" for p in a["in_ports"]) if a["in_ports"] else ""
        out_str = "; ".join(f"{p['name']}:{p['type']}" for p in a["out_ports"]) if a["out_ports"] else ""
        self.query_one("#in-ports", Input).value = in_str
        self.query_one("#out-ports", Input).value = out_str
        self.query_one("#style-select", Select).value = a["processing_style"]

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
            return
        block_name = self.query_one("#block-name", Input).value.strip()
        if not re.match(r"^[A-Z][A-Za-z0-9]*$", block_name):
            self.query_one("#block-name", Input).border_title = "Must be CamelCase!"
            return
        raw_params = self.query_one("#template-params", Input).value.strip() or "T"
        template_params = [p.strip() for p in raw_params.split(",") if p.strip()]
        in_ports = _parse_ports(self.query_one("#in-ports", Input).value or "in:T")
        out_ports = _parse_ports(self.query_one("#out-ports", Input).value or "out:T")
        type_list = self.query_one("#type-list", Input).value.strip() or "float, double"
        self.dismiss({
            "group_name": self.query_one("#group-select", Select).value,
            "block_name": block_name,
            "description": self.query_one("#description", Input).value.strip(),
            "template_params": template_params,
            "in_ports": in_ports,
            "out_ports": out_ports,
            "processing_style": self.query_one("#style-select", Select).value,
            "type_list": type_list,
            "gen_test": True,
        })


# ---------------------------------------------------------------------------
# Rename modal
# ---------------------------------------------------------------------------

class RenameBlockScreen(ModalScreen):
    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "dismiss", "Cancel")]

    def __init__(
        self,
        cfg: ProjectConfig,
        groups: list[GroupInfo],
        default_group: str | None = None,
        default_block: str | None = None,
    ) -> None:
        super().__init__()
        self._cfg = cfg
        self._groups = groups
        self._default_group = default_group
        self._default_block = default_block

    def compose(self) -> ComposeResult:
        options = [(g.name, g.name) for g in self._groups]
        default_group = self._default_group or (self._groups[0].name if self._groups else Select.BLANK)
        with Vertical(classes="modal-form modal-form--narrow"):
            yield Label("[bold]Rename Block[/bold]")
            yield Label("Group:")
            yield Select(options=options, value=default_group, id="group-select")
            yield Label("Current name:")
            yield Input(value=self._default_block or "", placeholder="OldName", id="old-name")
            yield Label("New name [dim](CamelCase)[/dim]:")
            yield Input(placeholder="NewName", id="new-name")
            yield Horizontal(
                Button("Rename", variant="primary", id="ok-btn"),
                Button("Cancel", variant="default", id="cancel-btn"),
                classes="button-row",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
            return
        new_name = self.query_one("#new-name", Input).value.strip()
        if not re.match(r"^[A-Z][A-Za-z0-9]*$", new_name):
            self.query_one("#new-name", Input).border_title = "Must be CamelCase!"
            return
        self.dismiss({
            "group": self.query_one("#group-select", Select).value,
            "old_name": self.query_one("#old-name", Input).value.strip(),
            "new_name": new_name,
        })


# ---------------------------------------------------------------------------
# Delete confirmation modal
# ---------------------------------------------------------------------------

class ConfirmDeleteScreen(ModalScreen):
    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "dismiss", "Cancel")]

    def __init__(self, block_name: str, group: str) -> None:
        super().__init__()
        self._block_name = block_name
        self._group = group

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-form modal-form--narrow"):
            yield Label("[bold red]Delete Block[/bold red]")
            yield Static("")
            yield Static(
                f"Delete [bold]{self._block_name}[/bold] "
                f"from group [cyan]{self._group}[/cyan]?"
            )
            yield Static("[dim]Removes header, test file, and build entries.[/dim]")
            yield Static("")
            yield Horizontal(
                Button("Delete", variant="error", id="ok-btn"),
                Button("Cancel", variant="default", id="cancel-btn"),
                classes="button-row",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "ok-btn")


# ---------------------------------------------------------------------------
# Add parameter modal
# ---------------------------------------------------------------------------

class NewParamScreen(ModalScreen):
    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "dismiss", "Cancel")]

    def __init__(
        self,
        cfg: ProjectConfig,
        groups: list[GroupInfo],
        default_group: str | None = None,
        default_block: str | None = None,
    ) -> None:
        super().__init__()
        self._cfg = cfg
        self._groups = groups
        self._default_group = default_group
        self._default_block = default_block

    def compose(self) -> ComposeResult:
        options = [(g.name, g.name) for g in self._groups]
        default_group = self._default_group or (self._groups[0].name if self._groups else Select.BLANK)
        with Vertical(classes="modal-form"):
            yield Label("[bold]Add Parameter[/bold]")
            yield Label("Group:")
            yield Select(options=options, value=default_group, id="group-select")
            yield Label("Block name:")
            yield Input(value=self._default_block or "", placeholder="MyFilter", id="block-name")
            yield Label("Parameter name [dim](snake_case)[/dim]:")
            yield Input(placeholder="gain", id="param-name")
            yield Label("C++ type:")
            yield Input(placeholder="float", id="param-type")
            yield Label("Description:")
            yield Input(placeholder="Gain factor", id="description")
            yield Label("Default value [dim](C++ literal)[/dim]:")
            yield Input(placeholder="{}", id="default-value")
            yield Horizontal(
                Button("Add", variant="primary", id="ok-btn"),
                Button("Cancel", variant="default", id="cancel-btn"),
                classes="button-row",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
            return
        self.dismiss({
            "group": self.query_one("#group-select", Select).value,
            "block_name": self.query_one("#block-name", Input).value.strip(),
            "param_name": self.query_one("#param-name", Input).value.strip(),
            "param_type": self.query_one("#param-type", Input).value.strip() or "float",
            "description": self.query_one("#description", Input).value.strip(),
            "default_value": self.query_one("#default-value", Input).value.strip() or "{}",
        })


# ---------------------------------------------------------------------------
# Move block modal
# ---------------------------------------------------------------------------

class MoveBlockScreen(ModalScreen):
    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "dismiss", "Cancel")]

    def __init__(
        self,
        cfg: ProjectConfig,
        groups: list[GroupInfo],
        default_group: str | None = None,
        default_block: str | None = None,
    ) -> None:
        super().__init__()
        self._cfg = cfg
        self._groups = groups
        self._default_group = default_group
        self._default_block = default_block

    def compose(self) -> ComposeResult:
        options = [(g.name, g.name) for g in self._groups]
        default_group = self._default_group or (self._groups[0].name if self._groups else Select.BLANK)
        with Vertical(classes="modal-form modal-form--narrow"):
            yield Label("[bold]Move Block[/bold]")
            yield Label("Source group:")
            yield Select(options=options, value=default_group, id="src-group")
            yield Label("Block name:")
            yield Input(value=self._default_block or "", placeholder="BlockName", id="block-name")
            yield Label("Destination group:")
            yield Select(options=options, id="dst-group")
            yield Horizontal(
                Button("Move", variant="primary", id="ok-btn"),
                Button("Cancel", variant="default", id="cancel-btn"),
                classes="button-row",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
            return
        self.dismiss({
            "src_group": self.query_one("#src-group", Select).value,
            "block_name": self.query_one("#block-name", Input).value.strip(),
            "dst_group": self.query_one("#dst-group", Select).value,
        })


# ---------------------------------------------------------------------------
# Copy block modal
# ---------------------------------------------------------------------------

class CopyBlockScreen(ModalScreen):
    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "dismiss", "Cancel")]

    def __init__(
        self,
        cfg: ProjectConfig,
        groups: list[GroupInfo],
        default_group: str | None = None,
        default_block: str | None = None,
    ) -> None:
        super().__init__()
        self._cfg = cfg
        self._groups = groups
        self._default_group = default_group
        self._default_block = default_block

    def compose(self) -> ComposeResult:
        options = [(g.name, g.name) for g in self._groups]
        default_group = self._default_group or (self._groups[0].name if self._groups else Select.BLANK)
        with Vertical(classes="modal-form modal-form--narrow"):
            yield Label("[bold]Copy Block[/bold]")
            yield Label("Source group:")
            yield Select(options=options, value=default_group, id="src-group")
            yield Label("Source block:")
            yield Input(value=self._default_block or "", placeholder="OldName", id="src-name")
            yield Label("New name:")
            yield Input(placeholder="NewName", id="dst-name")
            yield Label("Destination group:")
            yield Select(options=options, value=default_group, id="dst-group")
            yield Horizontal(
                Button("Copy", variant="primary", id="ok-btn"),
                Button("Cancel", variant="default", id="cancel-btn"),
                classes="button-row",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
            return
        self.dismiss({
            "src_group": self.query_one("#src-group", Select).value,
            "src_name": self.query_one("#src-name", Input).value.strip(),
            "dst_name": self.query_one("#dst-name", Input).value.strip(),
            "dst_group": self.query_one("#dst-group", Select).value,
            "gen_test": False,
        })


# ---------------------------------------------------------------------------
# Add test modal
# ---------------------------------------------------------------------------

class AddTestScreen(ModalScreen):
    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "dismiss", "Cancel")]

    def __init__(
        self,
        cfg: ProjectConfig,
        groups: list[GroupInfo],
        default_group: str | None = None,
        default_block: str | None = None,
    ) -> None:
        super().__init__()
        self._cfg = cfg
        self._groups = groups
        self._default_group = default_group
        self._default_block = default_block

    def compose(self) -> ComposeResult:
        options = [(g.name, g.name) for g in self._groups]
        default_group = self._default_group or (self._groups[0].name if self._groups else Select.BLANK)
        with Vertical(classes="modal-form modal-form--narrow"):
            yield Label("[bold]Add Test[/bold]")
            yield Label("Group:")
            yield Select(options=options, value=default_group, id="group-select")
            yield Label("Block name:")
            yield Input(value=self._default_block or "", placeholder="BlockName", id="block-name")
            yield Horizontal(
                Button("Generate", variant="primary", id="ok-btn"),
                Button("Cancel", variant="default", id="cancel-btn"),
                classes="button-row",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
            return
        self.dismiss({
            "group": self.query_one("#group-select", Select).value,
            "block_name": self.query_one("#block-name", Input).value.strip(),
        })


# ---------------------------------------------------------------------------
# New benchmark modal
# ---------------------------------------------------------------------------

class NewBenchScreen(ModalScreen):
    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "dismiss", "Cancel")]

    def __init__(
        self,
        cfg: ProjectConfig,
        groups: list[GroupInfo],
        default_group: str | None = None,
        default_block: str | None = None,
    ) -> None:
        super().__init__()
        self._cfg = cfg
        self._groups = groups
        self._default_group = default_group
        self._default_block = default_block

    def compose(self) -> ComposeResult:
        options = [(g.name, g.name) for g in self._groups]
        default_group = self._default_group or (self._groups[0].name if self._groups else Select.BLANK)
        with Vertical(classes="modal-form modal-form--narrow"):
            yield Label("[bold]New Benchmark[/bold]")
            yield Label("Group:")
            yield Select(options=options, value=default_group, id="group-select")
            yield Label("Block name:")
            yield Input(value=self._default_block or "", placeholder="BlockName", id="block-name")
            yield Horizontal(
                Button("Generate", variant="primary", id="ok-btn"),
                Button("Cancel", variant="default", id="cancel-btn"),
                classes="button-row",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
            return
        self.dismiss({
            "group": self.query_one("#group-select", Select).value,
            "block_name": self.query_one("#block-name", Input).value.strip(),
            "wire_build": False,
        })


# ---------------------------------------------------------------------------
# Build modal
# ---------------------------------------------------------------------------

class BuildScreen(ModalScreen):
    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "dismiss", "Cancel")]

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-form modal-form--narrow"):
            yield Label("[bold]Build Project[/bold]")
            yield Label("Build directory:")
            yield Input(value="build", id="build-dir")
            yield Label("Parallel jobs [dim](blank = auto)[/dim]:")
            yield Input(placeholder="auto", id="jobs")
            yield Checkbox("Clean build directory first", id="clean")
            yield Checkbox("Force reconfigure", id="reconfigure")
            yield Checkbox("Run tests after build", id="run-tests")
            yield Horizontal(
                Button("Build", variant="primary", id="ok-btn"),
                Button("Cancel", variant="default", id="cancel-btn"),
                classes="button-row",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
            return
        jobs_str = self.query_one("#jobs", Input).value.strip()
        self.dismiss({
            "build_dir": self.query_one("#build-dir", Input).value.strip() or "build",
            "clean": self.query_one("#clean", Checkbox).value,
            "reconfigure": self.query_one("#reconfigure", Checkbox).value,
            "run_tests": self.query_one("#run-tests", Checkbox).value,
            "jobs": int(jobs_str) if jobs_str.isdigit() else None,
        })


# ---------------------------------------------------------------------------
# Run test modal
# ---------------------------------------------------------------------------

class RunTestScreen(ModalScreen):
    BINDINGS: ClassVar[list[Binding]] = [Binding("escape", "dismiss", "Cancel")]

    def __init__(self, default_block: str | None = None) -> None:
        super().__init__()
        self._default_block = default_block

    def compose(self) -> ComposeResult:
        with Vertical(classes="modal-form modal-form--narrow"):
            yield Label("[bold]Run Block Test[/bold]")
            yield Label("Block name:")
            yield Input(value=self._default_block or "", placeholder="MyFilter", id="block-name")
            yield Label("Build directory:")
            yield Input(value="build", id="build-dir")
            yield Horizontal(
                Button("Run", variant="primary", id="ok-btn"),
                Button("Cancel", variant="default", id="cancel-btn"),
                classes="button-row",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
            return
        self.dismiss({
            "block_name": self.query_one("#block-name", Input).value.strip(),
            "build_dir": self.query_one("#build-dir", Input).value.strip() or "build",
        })


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class GR4ModtoolApp(App):
    """GNURadio 4 OOT module management TUI."""

    TITLE = "gr4_modtool"
    CSS = _APP_CSS

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "quit", "Quit"),
        Binding("question_mark", "help", "Help", key_display="?"),
        Binding("ctrl+p", "command_palette", "Commands"),
        Binding("n", "new_block", "New Block"),
        Binding("g", "new_group", "New Group"),
        Binding("r", "rename_block", "Rename"),
        Binding("d", "delete_block", "Delete"),
        Binding("p", "new_param", "Add Param"),
        Binding("m", "move_block", "Move"),
        Binding("c", "copy_block", "Copy"),
        Binding("s", "show_header", "Show"),
        Binding("t", "add_test", "Add Test"),
        Binding("b", "new_bench", "Benchmark"),
        Binding("f", "format_group", "Format"),
        Binding("k", "check", "Check"),
        Binding("shift+b", "build", "Build", key_display="B"),
        Binding("shift+x", "run_test", "Run Test", key_display="X"),
        Binding("f5", "refresh", "Refresh"),
        Binding("slash", "focus_filter", "Filter", key_display="/"),
    ]

    def __init__(self, project_dir: Path | None = None) -> None:
        super().__init__()
        self._project_dir = project_dir
        self._cfg: ProjectConfig | None = None
        self._groups: list[GroupInfo] = []
        self._selected_group: str | None = None
        self._selected_block: str | None = None
        self._filter_query: str = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-area"):
            with Vertical(id="left-panel"):
                yield ProjectTree("Project", id="project-tree")
                yield Input(placeholder="/ to filter blocks…", id="filter-input")
            yield DetailPanel(id="detail")
        yield Footer()

    def on_mount(self) -> None:
        self._load_project()

    # -----------------------------------------------------------------------
    # Project loading
    # -----------------------------------------------------------------------

    def _load_project(self) -> None:
        try:
            self._cfg = load_config(self._project_dir)
            self._groups = discover_groups(self._cfg)
        except FileNotFoundError as exc:
            self.query_one(DetailPanel).show_message(f"[red]{exc}[/red]")
            return
        self._repopulate_tree()
        self.query_one(DetailPanel).show_welcome(self._cfg, self._groups)

    def _repopulate_tree(self) -> None:
        if self._cfg is None:
            return
        self.query_one(ProjectTree).populate(self._groups, self._cfg, self._filter_query)

    # -----------------------------------------------------------------------
    # Event handlers
    # -----------------------------------------------------------------------

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:  # type: ignore[type-arg]
        node: TreeNode = event.node  # type: ignore[assignment]
        if node.data is None:
            return
        if isinstance(node.data, BlockInfo):
            self._selected_block = node.data.name
            if node.parent and isinstance(node.parent.data, GroupInfo):
                self._selected_group = node.parent.data.name
            self.query_one(DetailPanel).show_block(node.data.name, node.data.path)
        elif isinstance(node.data, GroupInfo):
            self._selected_group = node.data.name
            self._selected_block = None

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "filter-input":
            self._filter_query = event.value
            self._repopulate_tree()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "filter-input":
            self.query_one(ProjectTree).focus()

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _guard(self) -> bool:
        if self._cfg is None or not self._groups:
            self.notify("No project loaded.", severity="error")
            return False
        return True

    # -----------------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------------

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_focus_filter(self) -> None:
        self.query_one("#filter-input", Input).focus()

    def action_refresh(self) -> None:
        self._load_project()
        self.notify("Project refreshed.")

    def action_new_group(self) -> None:
        if self._cfg is None:
            self.notify("No project loaded.", severity="error")
            return

        def _handle(name: str | None) -> None:
            if not name:
                return
            from gr4_modtool.commands.newgroup import write_group_skeleton
            from gr4_modtool.project.discovery import save_config
            from gr4_modtool.project import cmake as cmake_mod, meson as meson_mod
            cfg = self._cfg  # type: ignore[assignment]
            if name in cfg.groups:
                self.notify(f"Group '{name}' already exists.", severity="error")
                return
            try:
                write_group_skeleton(cfg, name)
                cfg.groups[name] = f"blocks/{name}"
                save_config(cfg)
                blocks_cmake = cfg.blocks_dir / "CMakeLists.txt"
                blocks_meson = cfg.blocks_dir / "meson.build"
                if cfg.build_cmake and blocks_cmake.exists():
                    cmake_mod.add_group_to_blocks_cmake(blocks_cmake, name, cfg.cmake_prefix)
                if cfg.build_meson and blocks_meson.exists():
                    meson_mod.add_group_to_blocks_meson(blocks_meson, name)
                self._load_project()
                self.notify(f"Created group '{name}'.")
            except Exception as exc:  # noqa: BLE001
                self.notify(str(exc), severity="error")

        self.push_screen(NewGroupScreen(), _handle)

    def action_new_block(self) -> None:
        if not self._guard():
            return

        def _handle(answers: dict | None) -> None:
            if answers is None:
                return
            from gr4_modtool.commands.newblock import write_block_files
            try:
                write_block_files(self._cfg, answers)  # type: ignore[arg-type]
                self._load_project()
                self.notify(f"Created {answers['block_name']} in {answers['group_name']}.")
            except Exception as exc:  # noqa: BLE001
                self.notify(str(exc), severity="error")

        self.push_screen(
            NewBlockScreen(self._cfg, self._groups, self._selected_group),  # type: ignore[arg-type]
            _handle,
        )

    def action_rename_block(self) -> None:
        if not self._guard():
            return

        def _handle(answers: dict | None) -> None:
            if answers is None:
                return
            from gr4_modtool.commands.rename import _rename_in_header
            from gr4_modtool.project import cmake as cmake_mod, meson as meson_mod
            cfg = self._cfg  # type: ignore[assignment]
            group = answers["group"]
            old_name, new_name = answers["old_name"], answers["new_name"]
            old_header = cfg.group_include_dir(group) / f"{old_name}.hpp"
            new_header = cfg.group_include_dir(group) / f"{new_name}.hpp"
            old_test = cfg.group_test_dir(group) / f"qa_{old_name}.cpp"
            new_test = cfg.group_test_dir(group) / f"qa_{new_name}.cpp"
            cmake_test = cfg.group_test_dir(group) / "CMakeLists.txt"
            meson_test = cfg.group_test_dir(group) / "meson.build"
            try:
                if old_header.exists():
                    _rename_in_header(old_header, old_name, new_name)
                    old_header.rename(new_header)
                if old_test.exists():
                    text = re.sub(rf"\b{re.escape(old_name)}\b", new_name, old_test.read_text())
                    old_test.write_text(text)
                    old_test.rename(new_test)
                if cfg.build_cmake and cmake_test.exists():
                    cmake_mod.rename_test_entry(cmake_test, old_name, new_name)
                if cfg.build_meson and meson_test.exists():
                    meson_mod.rename_test_entry(meson_test, old_name, new_name)
                self._selected_block = new_name
                self._load_project()
                self.notify(f"Renamed '{old_name}' → '{new_name}'.")
            except Exception as exc:  # noqa: BLE001
                self.notify(str(exc), severity="error")

        self.push_screen(
            RenameBlockScreen(  # type: ignore[arg-type]
                self._cfg, self._groups, self._selected_group, self._selected_block
            ),
            _handle,
        )

    def action_delete_block(self) -> None:
        if not self._guard():
            return
        if self._selected_block is None or self._selected_group is None:
            self.notify("Select a block first.", severity="warning")
            return

        block_name = self._selected_block
        group = self._selected_group

        def _handle(confirmed: bool | None) -> None:
            if not confirmed:
                return
            from gr4_modtool.project import cmake as cmake_mod, meson as meson_mod
            cfg = self._cfg  # type: ignore[assignment]
            try:
                for f in [
                    cfg.group_include_dir(group) / f"{block_name}.hpp",
                    cfg.group_test_dir(group) / f"qa_{block_name}.cpp",
                ]:
                    if f.exists():
                        f.unlink()
                cmake_test = cfg.group_test_dir(group) / "CMakeLists.txt"
                meson_test = cfg.group_test_dir(group) / "meson.build"
                if cfg.build_cmake and cmake_test.exists():
                    cmake_mod.remove_test_entry(cmake_test, block_name)
                if cfg.build_meson and meson_test.exists():
                    meson_mod.remove_test_entry(meson_test, block_name)
                self._selected_block = None
                self._load_project()
                self.notify(f"Deleted '{block_name}'.")
            except Exception as exc:  # noqa: BLE001
                self.notify(str(exc), severity="error")

        self.push_screen(ConfirmDeleteScreen(block_name, group), _handle)

    def action_new_param(self) -> None:
        if not self._guard():
            return

        def _handle(answers: dict | None) -> None:
            if answers is None:
                return
            from gr4_modtool.commands.newparam import add_param
            try:
                add_param(
                    self._cfg,  # type: ignore[arg-type]
                    answers["group"], answers["block_name"],
                    answers["param_name"], answers["param_type"],
                    answers["description"], answers["default_value"],
                )
                self.notify(f"Added '{answers['param_name']}' to {answers['block_name']}.")
                if (
                    self._selected_block == answers["block_name"]
                    and self._selected_group == answers["group"]
                    and self._cfg is not None
                ):
                    header = self._cfg.group_include_dir(answers["group"]) / f"{answers['block_name']}.hpp"
                    self.query_one(DetailPanel).show_block(answers["block_name"], header)
            except Exception as exc:  # noqa: BLE001
                self.notify(str(exc), severity="error")

        self.push_screen(
            NewParamScreen(  # type: ignore[arg-type]
                self._cfg, self._groups, self._selected_group, self._selected_block
            ),
            _handle,
        )

    def action_move_block(self) -> None:
        if not self._guard():
            return
        if len(self._groups) < 2:
            self.notify("Need at least two groups to move a block.", severity="warning")
            return

        def _handle(answers: dict | None) -> None:
            if answers is None:
                return
            from gr4_modtool.commands.mv import move_block
            try:
                move_block(
                    self._cfg,  # type: ignore[arg-type]
                    answers["src_group"], answers["block_name"], answers["dst_group"],
                )
                self._load_project()
                self.notify(f"Moved '{answers['block_name']}' to {answers['dst_group']}.")
            except Exception as exc:  # noqa: BLE001
                self.notify(str(exc), severity="error")

        self.push_screen(
            MoveBlockScreen(  # type: ignore[arg-type]
                self._cfg, self._groups, self._selected_group, self._selected_block
            ),
            _handle,
        )

    def action_copy_block(self) -> None:
        if not self._guard():
            return

        def _handle(answers: dict | None) -> None:
            if answers is None:
                return
            from gr4_modtool.commands.cp import copy_block
            try:
                copy_block(
                    self._cfg,  # type: ignore[arg-type]
                    answers["src_group"], answers["src_name"], answers["dst_name"],
                    dst_group=answers.get("dst_group"),
                    gen_test=answers.get("gen_test", False),
                )
                self._load_project()
                self.notify(f"Copied '{answers['src_name']}' → '{answers['dst_name']}'.")
            except Exception as exc:  # noqa: BLE001
                self.notify(str(exc), severity="error")

        self.push_screen(
            CopyBlockScreen(  # type: ignore[arg-type]
                self._cfg, self._groups, self._selected_group, self._selected_block
            ),
            _handle,
        )

    def action_show_header(self) -> None:
        if not self._guard():
            return
        if self._selected_block is None or self._selected_group is None:
            self.notify("Select a block first.", severity="warning")
            return
        cfg = self._cfg  # type: ignore[assignment]
        header = cfg.group_include_dir(self._selected_group) / f"{self._selected_block}.hpp"
        self.query_one(DetailPanel).show_block(self._selected_block, header)

    def action_add_test(self) -> None:
        if not self._guard():
            return

        def _handle(answers: dict | None) -> None:
            if answers is None:
                return
            from gr4_modtool.commands.add_test import write_test_for_block
            try:
                write_test_for_block(
                    self._cfg, answers["group"], answers["block_name"]  # type: ignore[arg-type]
                )
                self._load_project()
                self.notify(f"Created test for {answers['block_name']}.")
            except Exception as exc:  # noqa: BLE001
                self.notify(str(exc), severity="error")

        self.push_screen(
            AddTestScreen(  # type: ignore[arg-type]
                self._cfg, self._groups, self._selected_group, self._selected_block
            ),
            _handle,
        )

    def action_new_bench(self) -> None:
        if not self._guard():
            return

        def _handle(answers: dict | None) -> None:
            if answers is None:
                return
            from gr4_modtool.commands.newbench import write_bench_file
            try:
                write_bench_file(
                    self._cfg,  # type: ignore[arg-type]
                    answers["group"], answers["block_name"],
                    wire_build=answers.get("wire_build", False),
                )
                self.notify(f"Created benchmark for {answers['block_name']}.")
            except Exception as exc:  # noqa: BLE001
                self.notify(str(exc), severity="error")

        self.push_screen(
            NewBenchScreen(  # type: ignore[arg-type]
                self._cfg, self._groups, self._selected_group, self._selected_block
            ),
            _handle,
        )

    def action_format_group(self) -> None:
        if not self._guard():
            return
        from gr4_modtool.commands.format import format_files
        groups = [self._selected_group] if self._selected_group else None
        try:
            rc = format_files(self._cfg, groups=groups)  # type: ignore[arg-type]
            label = self._selected_group or "all groups"
            if rc == 0:
                self.notify(f"Formatted {label}.")
            else:
                self.notify(f"clang-format exited with code {rc}.", severity="warning")
        except Exception as exc:  # noqa: BLE001
            self.notify(str(exc), severity="error")

    def action_check(self) -> None:
        if self._cfg is None:
            self.notify("No project loaded.", severity="error")
            return
        from gr4_modtool.commands.check import audit_project
        issues = audit_project(self._cfg)
        if not issues:
            self.notify("No issues found.")
            return
        errors = sum(1 for i in issues if i.severity == "error")
        warnings = sum(1 for i in issues if i.severity == "warning")
        lines = ["[bold]Check Results[/bold]", ""]
        for issue in issues:
            color = "red" if issue.severity == "error" else "yellow"
            lines.append(
                f"  [{color}]{issue.severity}[/{color}]  "
                f"[cyan]{issue.group}[/cyan]/{issue.block}  {issue.issue}"
            )
        self.query_one(DetailPanel).show_message("\n".join(lines))
        e_s = "s" if errors != 1 else ""
        w_s = "s" if warnings != 1 else ""
        self.notify(
            f"{errors} error{e_s}, {warnings} warning{w_s}",
            severity="error" if errors else "warning",
        )

    def action_build(self) -> None:
        if self._cfg is None:
            self.notify("No project loaded.", severity="error")
            return

        def _handle(opts: dict | None) -> None:
            if opts is None:
                return
            import os
            import shutil
            cfg = self._cfg  # type: ignore[assignment]
            root = cfg.root
            bd = root / opts["build_dir"]
            has_cmake = (root / "CMakeLists.txt").exists()
            parallel = str(opts["jobs"]) if opts["jobs"] else str(os.cpu_count() or 4)

            if opts["clean"] and bd.exists():
                shutil.rmtree(bd)

            cmds: list[list[str]] = []
            if has_cmake:
                if opts["reconfigure"] or not (bd / "CMakeCache.txt").exists():
                    cmds.append(["cmake", "-B", str(bd), "-S", str(root)])
                cmds.append(["cmake", "--build", str(bd), "--parallel", parallel])
                if opts["run_tests"]:
                    cmds.append(["ctest", "--test-dir", str(bd), "--output-on-failure"])
            else:
                if opts["reconfigure"] or not bd.exists():
                    cmds.append(["meson", "setup", str(bd), str(root)])
                cmds.append(["ninja", "-C", str(bd), "-j", parallel])
                if opts["run_tests"]:
                    cmds.append(["meson", "test", "-C", str(bd)])

            self.push_screen(BuildOutputScreen(cmds, root))

        self.push_screen(BuildScreen(), _handle)

    def action_run_test(self) -> None:
        if self._cfg is None:
            self.notify("No project loaded.", severity="error")
            return

        def _handle(opts: dict | None) -> None:
            if opts is None:
                return
            cfg = self._cfg  # type: ignore[assignment]
            root = cfg.root
            build_dir = root / opts["build_dir"]
            block_name = opts["block_name"]
            if not build_dir.exists():
                self.notify(f"Build dir not found: {build_dir}. Run Build first.", severity="error")
                return
            if (root / "CMakeLists.txt").exists():
                cmd = ["ctest", "--test-dir", str(build_dir), "-R", f"qa_{block_name}", "--output-on-failure"]
            else:
                cmd = ["meson", "test", "-C", str(build_dir), f"qa_{block_name}"]
            self.push_screen(BuildOutputScreen([cmd], root))

        self.push_screen(RunTestScreen(self._selected_block), _handle)
