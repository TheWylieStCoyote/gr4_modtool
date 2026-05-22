"""gr4_modtool public API.

Stable re-exports for use as a library.  Import from here rather than from
internal command modules — the paths below are the supported surface.

Example usage::

    from gr4_modtool.api import load_config, load_spec, write_block_files

    cfg = load_config(Path("/path/to/mymod"))
    entries = load_spec(Path("blocks.yaml"))
    for entry in entries:
        write_block_files(cfg, entry)
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Audit / check
# ---------------------------------------------------------------------------
from gr4_modtool.commands.check import (
    BlockIssue,
    audit_project,
)

# ---------------------------------------------------------------------------
# Header inspection
# ---------------------------------------------------------------------------
from gr4_modtool.commands.export_spec import (
    export_spec,
    header_to_spec_entry,
    infer_archetype,
)
from gr4_modtool.commands.lint_headers import (
    LintIssue,
    lint_header,
    lint_headers,
)

# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------
from gr4_modtool.commands.ls import collect_inventory

# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------
from gr4_modtool.commands.migrate import (
    Gr3BlockInfo,
    MigrationReport,
    MigrationResult,
    detect_gr3_project,
    migrate_project,
    parse_gr3_block,
)

# ---------------------------------------------------------------------------
# Block scaffolding
# ---------------------------------------------------------------------------
from gr4_modtool.commands.newblock import (
    ARCHETYPES,
    load_spec,
    validate_spec_entry,
    write_block_files,
)

# ---------------------------------------------------------------------------
# Group scaffolding
# ---------------------------------------------------------------------------
from gr4_modtool.commands.newgroup import write_group_skeleton

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
from gr4_modtool.commands.validate import (
    ValidationIssue,
    validate_project,
)

# ---------------------------------------------------------------------------
# Version management
# ---------------------------------------------------------------------------
from gr4_modtool.commands.version_bump import apply_version_bump

# ---------------------------------------------------------------------------
# Project config
# ---------------------------------------------------------------------------
from gr4_modtool.project.discovery import (
    BlockInfo,
    GroupInfo,
    ProjectConfig,
    discover_groups,
    find_project_root,
    load_config,
    save_config,
)

# ---------------------------------------------------------------------------
# Public surface declaration
# ---------------------------------------------------------------------------
__all__ = [
    # config
    "BlockInfo",
    "GroupInfo",
    "ProjectConfig",
    "discover_groups",
    "find_project_root",
    "load_config",
    "save_config",
    # block scaffolding
    "ARCHETYPES",
    "load_spec",
    "validate_spec_entry",
    "write_block_files",
    # group scaffolding
    "write_group_skeleton",
    # header inspection
    "export_spec",
    "header_to_spec_entry",
    "infer_archetype",
    "LintIssue",
    "lint_header",
    "lint_headers",
    # audit
    "BlockIssue",
    "audit_project",
    # migration
    "Gr3BlockInfo",
    "MigrationReport",
    "MigrationResult",
    "detect_gr3_project",
    "migrate_project",
    "parse_gr3_block",
    # inventory
    "collect_inventory",
    # validation
    "ValidationIssue",
    "validate_project",
    # versioning
    "apply_version_bump",
]
