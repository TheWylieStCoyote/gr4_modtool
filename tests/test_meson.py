"""Tests for meson.py helpers."""

from pathlib import Path

import pytest

from gr4_modtool.project.meson import (
    append_test_entry,
    remove_test_entry,
    rename_test_entry,
    add_subdir,
    append_bench_entry,
    remove_bench_entry,
    rename_bench_entry,
    add_bench_subdir,
)


@pytest.fixture()
def meson_file(tmp_path: Path) -> Path:
    f = tmp_path / "meson.build"
    f.write_text(
        "qa_Copy_exe = executable(\n"
        "  'qa_Copy',\n"
        "  'qa_Copy.cpp',\n"
        "  dependencies: [gr4_dep, ut_dep, gr4_basic_blocks_dep],\n"
        ")\n"
        "test('qa_Copy', qa_Copy_exe)\n"
    )
    return f


def test_append_test_entry(meson_file: Path) -> None:
    append_test_entry(meson_file, "MyBlock", extra_deps=["gr4_basic_blocks_dep"])
    text = meson_file.read_text()
    assert "qa_MyBlock" in text
    assert "test('qa_MyBlock'" in text


def test_remove_test_entry(meson_file: Path) -> None:
    append_test_entry(meson_file, "MyBlock", extra_deps=["gr4_basic_blocks_dep"])
    found = remove_test_entry(meson_file, "MyBlock")
    assert found
    text = meson_file.read_text()
    assert "qa_MyBlock" not in text
    assert "qa_Copy" in text


def test_remove_nonexistent(meson_file: Path) -> None:
    found = remove_test_entry(meson_file, "Ghost")
    assert not found


def test_rename_test_entry(meson_file: Path) -> None:
    append_test_entry(meson_file, "OldBlock")
    changed = rename_test_entry(meson_file, "OldBlock", "NewBlock")
    assert changed
    text = meson_file.read_text()
    assert "qa_NewBlock" in text
    assert "qa_OldBlock" not in text


def test_add_subdir(tmp_path: Path) -> None:
    f = tmp_path / "meson.build"
    f.write_text("subdir('basic')\n")
    add_subdir(f, "channel")
    text = f.read_text()
    assert "subdir('channel')" in text


def test_add_subdir_idempotent(tmp_path: Path) -> None:
    f = tmp_path / "meson.build"
    f.write_text("subdir('basic')\n")
    add_subdir(f, "basic")
    assert f.read_text().count("subdir('basic')") == 1


@pytest.fixture()
def bench_meson(tmp_path: Path) -> Path:
    f = tmp_path / "meson.build"
    f.write_text("# benchmarks\n")
    return f


def test_append_bench_entry(bench_meson: Path) -> None:
    append_bench_entry(bench_meson, "MyBlock", extra_deps=["gr4_basic_blocks_dep"])
    text = bench_meson.read_text()
    assert "bench_MyBlock" in text
    assert "benchmark('bench_MyBlock'" in text


def test_remove_bench_entry(bench_meson: Path) -> None:
    append_bench_entry(bench_meson, "MyBlock", extra_deps=["gr4_basic_blocks_dep"])
    found = remove_bench_entry(bench_meson, "MyBlock")
    assert found
    assert "bench_MyBlock" not in bench_meson.read_text()


def test_remove_bench_nonexistent(bench_meson: Path) -> None:
    found = remove_bench_entry(bench_meson, "Ghost")
    assert not found


def test_rename_bench_entry(bench_meson: Path) -> None:
    append_bench_entry(bench_meson, "OldBlock")
    changed = rename_bench_entry(bench_meson, "OldBlock", "NewBlock")
    assert changed
    text = bench_meson.read_text()
    assert "bench_NewBlock" in text
    assert "bench_OldBlock" not in text


def test_add_bench_subdir(tmp_path: Path) -> None:
    f = tmp_path / "meson.build"
    f.write_text("subdir('test')\n")
    add_bench_subdir(f)
    text = f.read_text()
    assert "enable_benchmarking" in text
    assert "subdir('benchmarks')" in text


def test_add_bench_subdir_idempotent(tmp_path: Path) -> None:
    f = tmp_path / "meson.build"
    f.write_text("subdir('test')\n")
    add_bench_subdir(f)
    add_bench_subdir(f)
    assert f.read_text().count("subdir('benchmarks')") == 1
