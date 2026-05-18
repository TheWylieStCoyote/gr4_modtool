"""Textual TUI for gr4_modtool."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import (
    Footer,
    Header,
    Label,
    Button,
    Input,
    Select,
    Static,
    Tree,
)
from textual.widgets.tree import TreeNode

from gr4_modtool.project.discovery import load_config, discover_groups, ProjectConfig, GroupInfo


# --------------------------------------------------------------------------- #
# Project tree panel
# --------------------------------------------------------------------------- #

class ProjectTree(Tree):
    """Left-panel tree showing groups → blocks."""

    def populate(self, groups: list[GroupInfo]) -> None:
        self.clear()
        self.root.expand()
        for group in groups:
            node = self.root.add(group.name, expand=True)
            for block in group.blocks:
                node.add_leaf(block.name, data=block)
            if not group.blocks:
                node.add_leaf("(no blocks)", data=None)


# --------------------------------------------------------------------------- #
# Detail panel
# --------------------------------------------------------------------------- #

class DetailPanel(ScrollableContainer):
    """Right-panel showing block detail or command output."""

    DEFAULT_CSS = """
    DetailPanel {
        border: solid $primary;
        padding: 1 2;
    }
    """

    def show_welcome(self, cfg: ProjectConfig) -> None:
        self.remove_children()
        self.mount(
            Static(f"[bold]Project:[/bold] {cfg.name}  v{cfg.version}"),
            Static(f"[bold]Namespace:[/bold] {cfg.cpp_namespace}"),
            Static(f"[bold]Build:[/bold] cmake={cfg.build_cmake}  meson={cfg.build_meson}"),
            Static(""),
            Static("Select a block in the tree, or press Ctrl+P for commands."),
        )

    def show_block(self, block_name: str, header_path: Path) -> None:
        self.remove_children()
        self.mount(
            Static(f"[bold]{block_name}[/bold]"),
            Static(f"[dim]{header_path}[/dim]"),
            Static(""),
        )
        try:
            preview = header_path.read_text()[:2000]
            self.mount(Static(f"[dim]{preview}[/dim]"))
        except OSError:
            self.mount(Static("[red]Could not read file.[/red]"))

    def show_message(self, message: str) -> None:
        self.remove_children()
        self.mount(Static(message))


# --------------------------------------------------------------------------- #
# NewBlock modal form
# --------------------------------------------------------------------------- #

class NewBlockScreen(ModalScreen):
    """Modal form for the newblock command."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("escape", "dismiss", "Cancel"),
    ]

    def __init__(self, cfg: ProjectConfig, groups: list[GroupInfo]) -> None:
        super().__init__()
        self._cfg = cfg
        self._groups = groups

    def compose(self) -> ComposeResult:
        group_options = [(g.name, g.name) for g in self._groups]
        with Vertical(id="newblock-form"):
            yield Label("[bold]New Block[/bold]")
            yield Label("Group:")
            yield Select(options=group_options, id="group-select")
            yield Label("Block name (CamelCase):")
            yield Input(placeholder="MyFilter", id="block-name")
            yield Label("Description:")
            yield Input(placeholder="One-line description", id="description")
            yield Label("Type list (comma-separated):")
            yield Input(placeholder="float, double", id="type-list")
            yield Horizontal(
                Button("Create", variant="primary", id="create-btn"),
                Button("Cancel", variant="default", id="cancel-btn"),
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-btn":
            self.dismiss(None)
            return

        group = self.query_one("#group-select", Select).value
        block_name = self.query_one("#block-name", Input).value.strip()
        description = self.query_one("#description", Input).value.strip()
        type_list = self.query_one("#type-list", Input).value.strip() or "float, double"

        import re
        if not re.match(r"^[A-Z][A-Za-z0-9]*$", block_name):
            self.query_one("#block-name", Input).border_title = "Must be CamelCase!"
            return

        self.dismiss({
            "group_name": group,
            "block_name": block_name,
            "description": description,
            "template_params": ["T"],
            "in_ports": [{"name": "in", "type": "T"}],
            "out_ports": [{"name": "out", "type": "T"}],
            "processing_style": "processOne",
            "type_list": type_list,
            "gen_test": True,
        })


# --------------------------------------------------------------------------- #
# Main app
# --------------------------------------------------------------------------- #

class GR4ModtoolApp(App):
    """GNURadio 4 OOT module management TUI."""

    TITLE = "gr4_modtool"
    CSS = """
    Screen {
        layout: vertical;
    }
    #main-area {
        layout: horizontal;
        height: 1fr;
    }
    ProjectTree {
        width: 30;
        border: solid $primary;
    }
    DetailPanel {
        width: 1fr;
    }
    #newblock-form {
        width: 60;
        height: auto;
        border: solid $primary;
        background: $surface;
        padding: 2 4;
    }
    """

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("q", "quit", "Quit"),
        Binding("ctrl+p", "command_palette", "Commands"),
        Binding("n", "new_block", "New Block"),
        Binding("r", "refresh", "Refresh"),
    ]

    def __init__(self, project_dir: Path | None = None) -> None:
        super().__init__()
        self._project_dir = project_dir
        self._cfg: ProjectConfig | None = None
        self._groups: list[GroupInfo] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-area"):
            yield ProjectTree("Project", id="project-tree")
            yield DetailPanel(id="detail")
        yield Footer()

    def on_mount(self) -> None:
        self._load_project()

    def _load_project(self) -> None:
        try:
            self._cfg = load_config(self._project_dir)
            self._groups = discover_groups(self._cfg)
        except FileNotFoundError as exc:
            self.query_one(DetailPanel).show_message(f"[red]{exc}[/red]")
            return

        tree = self.query_one(ProjectTree)
        tree.populate(self._groups)
        self.query_one(DetailPanel).show_welcome(self._cfg)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:  # type: ignore[type-arg]
        node: TreeNode = event.node  # type: ignore[assignment]
        if node.data is None:
            return
        from gr4_modtool.project.discovery import BlockInfo
        if isinstance(node.data, BlockInfo):
            self.query_one(DetailPanel).show_block(node.data.name, node.data.path)

    def action_new_block(self) -> None:
        if self._cfg is None or not self._groups:
            self.query_one(DetailPanel).show_message("[red]No project loaded.[/red]")
            return

        def _handle_result(answers: dict | None) -> None:
            if answers is None:
                return
            from gr4_modtool.commands.newblock import write_block_files
            try:
                written = write_block_files(self._cfg, answers)  # type: ignore[arg-type]
                self._load_project()
                self.query_one(DetailPanel).show_message(
                    "[green]Created:[/green]\n" + "\n".join(str(p) for p in written)
                )
            except Exception as exc:  # noqa: BLE001
                self.query_one(DetailPanel).show_message(f"[red]Error: {exc}[/red]")

        self.push_screen(NewBlockScreen(self._cfg, self._groups), _handle_result)

    def action_refresh(self) -> None:
        self._load_project()
