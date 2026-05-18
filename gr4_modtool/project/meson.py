"""meson.build line-based reader/writer."""

from __future__ import annotations

import re
from pathlib import Path


def append_test_entry(meson_path: Path, block_name: str, extra_deps: list[str] | None = None) -> None:
    """Add a test executable entry to a test meson.build."""
    deps_str = ", ".join(["gr4_dep", "ut_dep"] + (extra_deps or []))
    text = meson_path.read_text()
    simple_entry = (
        f"\nqa_{block_name}_exe = executable(\n"
        f"  'qa_{block_name}',\n"
        f"  'qa_{block_name}.cpp',\n"
        f"  dependencies: [{deps_str}],\n"
        f")\n"
        f"test('qa_{block_name}', qa_{block_name}_exe)\n"
    )
    meson_path.write_text(text.rstrip() + simple_entry)


def remove_test_entry(meson_path: Path, block_name: str) -> bool:
    """Remove the executable + test lines for block_name."""
    text = meson_path.read_text()
    # Match the executable(...) block and test() call
    pattern = (
        rf"\nqa_{re.escape(block_name)}_exe\s*=\s*executable\([^)]*\)[^\n]*\n"
        rf"test\('qa_{re.escape(block_name)}'[^\n]*\)\n?"
    )
    new_text, count = re.subn(pattern, "\n", text, flags=re.DOTALL)
    if count:
        meson_path.write_text(new_text)
    return count > 0


def rename_test_entry(meson_path: Path, old_name: str, new_name: str) -> bool:
    """Rename old_name → new_name in meson test entries."""
    text = meson_path.read_text()
    # No trailing \b: pattern must also rename the qa_<name>_exe variable
    new_text = re.sub(
        rf"\bqa_{re.escape(old_name)}",
        f"qa_{new_name}",
        text,
    )
    changed = new_text != text
    if changed:
        meson_path.write_text(new_text)
    return changed


def append_bench_entry(meson_path: Path, block_name: str, extra_deps: list[str] | None = None) -> None:
    """Add a benchmark executable entry to a benchmarks meson.build."""
    deps_str = ", ".join(["gr4_dep"] + (extra_deps or []))
    text = meson_path.read_text()
    simple_entry = (
        f"\nbench_{block_name}_exe = executable(\n"
        f"  'bench_{block_name}',\n"
        f"  'bench_{block_name}.cpp',\n"
        f"  dependencies: [{deps_str}],\n"
        f")\n"
        f"benchmark('bench_{block_name}', bench_{block_name}_exe)\n"
    )
    meson_path.write_text(text.rstrip() + simple_entry)


def remove_bench_entry(meson_path: Path, block_name: str) -> bool:
    """Remove the executable + benchmark lines for block_name."""
    text = meson_path.read_text()
    pattern = (
        rf"\nbench_{re.escape(block_name)}_exe\s*=\s*executable\([^)]*\)[^\n]*\n"
        rf"benchmark\('bench_{re.escape(block_name)}'[^\n]*\)\n?"
    )
    new_text, count = re.subn(pattern, "\n", text, flags=re.DOTALL)
    if count:
        meson_path.write_text(new_text)
    return count > 0


def rename_bench_entry(meson_path: Path, old_name: str, new_name: str) -> bool:
    """Rename old_name → new_name in meson benchmark entries."""
    text = meson_path.read_text()
    # No trailing \b: also renames bench_<name>_exe variable
    new_text = re.sub(
        rf"\bbench_{re.escape(old_name)}",
        f"bench_{new_name}",
        text,
    )
    changed = new_text != text
    if changed:
        meson_path.write_text(new_text)
    return changed


def add_bench_subdir(meson_path: Path) -> None:
    """Append enable_benchmarking-guarded benchmarks subdir to a group meson.build."""
    text = meson_path.read_text()
    if "subdir('benchmarks')" not in text:
        block = "\nif get_option('enable_benchmarking')\n  subdir('benchmarks')\nendif\n"
        meson_path.write_text(text.rstrip() + block)


def add_subdir(meson_path: Path, subdir: str) -> None:
    """Append subdir('subdir') if not already present."""
    text = meson_path.read_text()
    entry = f"subdir('{subdir}')"
    if entry not in text:
        meson_path.write_text(text.rstrip() + f"\n{entry}\n")


def add_group_to_blocks_meson(blocks_meson: Path, group_name: str) -> None:
    """Add subdir(group_name) to blocks/meson.build if not present."""
    add_subdir(blocks_meson, group_name)
