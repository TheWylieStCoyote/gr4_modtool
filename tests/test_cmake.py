"""Tests for cmake.py helpers."""

from pathlib import Path

import pytest

from gr4_modtool.project.cmake import (
    append_test_entry,
    remove_test_entry,
    rename_test_entry,
    add_subdirectory,
)


@pytest.fixture()
def cmake_file(tmp_path: Path) -> Path:
    f = tmp_path / "CMakeLists.txt"
    f.write_text(
        "gr4_incubator_add_ut_test(qa_Copy qa_Copy.cpp)\n"
        "target_link_libraries(qa_Copy PRIVATE gr4_testmod::blocks_basic_headers)\n"
    )
    return f


def test_append_test_entry(cmake_file: Path) -> None:
    append_test_entry(cmake_file, "MyBlock", "gr4_testmod::blocks_basic_headers")
    text = cmake_file.read_text()
    assert "qa_MyBlock" in text
    assert "target_link_libraries(qa_MyBlock" in text


def test_remove_test_entry(cmake_file: Path) -> None:
    append_test_entry(cmake_file, "MyBlock", "gr4_testmod::blocks_basic_headers")
    found = remove_test_entry(cmake_file, "MyBlock")
    assert found
    text = cmake_file.read_text()
    assert "qa_MyBlock" not in text
    # Original entry should still be present
    assert "qa_Copy" in text


def test_remove_nonexistent(cmake_file: Path) -> None:
    found = remove_test_entry(cmake_file, "DoesNotExist")
    assert not found


def test_rename_test_entry(cmake_file: Path) -> None:
    append_test_entry(cmake_file, "OldBlock", "gr4_testmod::blocks_basic_headers")
    changed = rename_test_entry(cmake_file, "OldBlock", "NewBlock")
    assert changed
    text = cmake_file.read_text()
    assert "qa_NewBlock" in text
    assert "qa_OldBlock" not in text


def test_add_subdirectory(tmp_path: Path) -> None:
    f = tmp_path / "CMakeLists.txt"
    f.write_text("add_subdirectory(basic)\n")
    add_subdirectory(f, "channel")
    text = f.read_text()
    assert "add_subdirectory(channel)" in text


def test_add_subdirectory_idempotent(tmp_path: Path) -> None:
    f = tmp_path / "CMakeLists.txt"
    f.write_text("add_subdirectory(basic)\n")
    add_subdirectory(f, "basic")
    assert f.read_text().count("add_subdirectory(basic)") == 1
