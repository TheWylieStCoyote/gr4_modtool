"""Tests for the migrate command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from rich.console import Console

import gr4_modtool.api as api
from gr4_modtool.commands.migrate import (
    Gr3BlockInfo,
    Gr3Property,
    MigrationReport,
    MigrationResult,
    _gr3_to_answers,
    _inject_properties,
    _render_json,
    _render_table,
    _to_camel,
    cmd,
    detect_gr3_project,
    migrate_project,
    parse_gr3_block,
)
from gr4_modtool.project.discovery import ProjectConfig

# ---------------------------------------------------------------------------
# GR3 fixture helpers
# ---------------------------------------------------------------------------

_CMAKE_TMPL = """\
cmake_minimum_required(VERSION 3.8)
project(gr-{name} VERSION {version} LANGUAGES CXX)
find_package(Gnuradio "3.10" REQUIRED)
GR_REGISTER_COMPONENT("{name}" ENABLE_{NAME})
"""

_HEADER_TMPL = """\
#ifndef INCLUDED_{NAME}_{BLOCK}_H
#define INCLUDED_{NAME}_{BLOCK}_H
#include <gnuradio/{base}.h>
namespace gr {{
  namespace {name} {{
    class {block} : public gr::{base}
    {{
     public:
      typedef std::shared_ptr<{block}> sptr;
      static sptr make({ctor_params});
{setters}\
    }};
  }}
}}
#endif
"""

_IMPL_CC_TMPL = """\
#include "{block}_impl.h"
namespace gr {{
  namespace {name} {{
    {block}::sptr {block}::make({ctor_params}) {{
      return gnuradio::make_block_sptr<{block}_impl>({ctor_args});
    }}
    {block}_impl::{block}_impl({ctor_params})
      : gr::{base}("{block}",
          gr::io_signature::make({in_min}, {in_max}, sizeof({in_type})),
          gr::io_signature::make({out_min}, {out_max}, sizeof({out_type}))){member_inits}
    {{}}
    int {block}_impl::work(int noutput_items,
        gr_vector_const_void_star &input_items,
        gr_vector_void_star &output_items)
    {{
{work_body}
      return noutput_items;
    }}
  }}
}}
"""


def _make_gr3_module(
    tmp_path: Path,
    name: str = "testmod",
    version: str = "0.9.0",
) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "CMakeLists.txt").write_text(
        _CMAKE_TMPL.format(name=name, version=version, NAME=name.upper())
    )
    inc = tmp_path / "include" / name
    inc.mkdir(parents=True)
    (inc / "api.h").write_text(f"// {name} api\n")
    (tmp_path / "lib").mkdir()
    return tmp_path


def _add_sync_block(
    gr3_dir: Path,
    mod: str,
    block: str,
    base: str = "sync_block",
    in_type: str = "float",
    out_type: str = "float",
    in_count: int = 1,
    out_count: int = 1,
    setters: str = "",
    ctor_params: str = "",
    ctor_args: str = "",
    member_inits: str = "",
    work_body: str = "      // identity",
) -> None:
    inc = gr3_dir / "include" / mod
    (inc / f"{block}.h").write_text(
        _HEADER_TMPL.format(
            NAME=mod.upper(),
            BLOCK=block.upper(),
            name=mod,
            block=block,
            base=base,
            ctor_params=ctor_params,
            setters=setters,
        )
    )
    lib = gr3_dir / "lib"
    (lib / f"{block}_impl.h").write_text(f"// {block} impl header\n")
    (lib / f"{block}_impl.cc").write_text(
        _IMPL_CC_TMPL.format(
            name=mod,
            block=block,
            base=base,
            ctor_params=ctor_params,
            ctor_args=ctor_args,
            in_min=in_count,
            in_max=in_count,
            in_type=in_type,
            out_min=out_count,
            out_max=out_count,
            out_type=out_type,
            member_inits=member_inits,
            work_body=work_body,
        )
    )


def _add_hier_block(gr3_dir: Path, mod: str, block: str) -> None:
    inc = gr3_dir / "include" / mod
    (inc / f"{block}.h").write_text(
        f"#ifndef INCLUDED_{mod.upper()}_{block.upper()}_H\n"
        f"#include <gnuradio/hier_block2.h>\n"
        f"namespace gr {{ namespace {mod} {{\n"
        f"  class {block} : public gr::hier_block2 {{}};\n"
        f"}} }}\n#endif\n"
    )
    lib = gr3_dir / "lib"
    (lib / f"{block}_impl.h").write_text("// hier impl\n")
    (lib / f"{block}_impl.cc").write_text("// hier impl\n")


def _add_varport_block(gr3_dir: Path, mod: str, block: str) -> None:
    inc = gr3_dir / "include" / mod
    (inc / f"{block}.h").write_text(
        f"#ifndef INCLUDED_{mod.upper()}_{block.upper()}_H\n"
        f"#include <gnuradio/block.h>\n"
        f"namespace gr {{ namespace {mod} {{\n"
        f"  class {block} : public gr::block {{}};\n"
        f"}} }}\n#endif\n"
    )
    lib = gr3_dir / "lib"
    (lib / f"{block}_impl.cc").write_text(
        "io_signature::makev(1, 4, sizeof_vector);\nio_signature::make(1, 1, sizeof(float));\n"
    )


# ---------------------------------------------------------------------------
# Detection tests
# ---------------------------------------------------------------------------


def test_detect_valid_gr3_module(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path)
    assert detect_gr3_project(tmp_path) is not None


def test_detect_extracts_name(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path, name="mymod")
    meta = detect_gr3_project(tmp_path)
    assert meta is not None
    assert meta.name == "mymod"


def test_detect_extracts_version(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path, version="1.2.3")
    meta = detect_gr3_project(tmp_path)
    assert meta is not None
    assert meta.version == "1.2.3"


def test_detect_finds_block_stems(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path)
    _add_sync_block(tmp_path, "testmod", "my_block")
    meta = detect_gr3_project(tmp_path)
    assert meta is not None
    assert "my_block" in meta.block_stems


def test_detect_excludes_api_stem(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path)
    meta = detect_gr3_project(tmp_path)
    assert meta is not None
    assert "api" not in meta.block_stems


def test_detect_returns_none_no_lib(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path)
    (tmp_path / "lib").rmdir()
    assert detect_gr3_project(tmp_path) is None


def test_detect_returns_none_no_cmake(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path)
    (tmp_path / "CMakeLists.txt").unlink()
    assert detect_gr3_project(tmp_path) is None


def test_detect_returns_none_for_empty_dir(tmp_path: Path) -> None:
    assert detect_gr3_project(tmp_path) is None


def test_detect_returns_none_no_api_header(tmp_path: Path) -> None:
    (tmp_path / "CMakeLists.txt").write_text(_CMAKE_TMPL.format(name="x", version="1.0", NAME="X"))
    (tmp_path / "lib").mkdir()
    # include dir exists but no api.h
    (tmp_path / "include" / "x").mkdir(parents=True)
    assert detect_gr3_project(tmp_path) is None


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------


def _parsed_sync(tmp_path: Path) -> Gr3BlockInfo:
    _make_gr3_module(tmp_path)
    _add_sync_block(tmp_path, "testmod", "my_block")
    h = tmp_path / "include" / "testmod" / "my_block.h"
    impl_h = tmp_path / "lib" / "my_block_impl.h"
    impl_cc = tmp_path / "lib" / "my_block_impl.cc"
    return parse_gr3_block("my_block", h, impl_h, impl_cc)


def test_parse_sync_block_base_class(tmp_path: Path) -> None:
    assert _parsed_sync(tmp_path).base_class == "sync_block"


def test_parse_block_base_class(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path)
    _add_sync_block(tmp_path, "testmod", "bulk_blk", base="block")
    h = tmp_path / "include" / "testmod" / "bulk_blk.h"
    b = parse_gr3_block("bulk_blk", h, None, tmp_path / "lib" / "bulk_blk_impl.cc")
    assert b.base_class == "block"


def test_parse_decim_block_base_class(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path)
    inc = tmp_path / "include" / "testmod"
    (inc / "dblk.h").write_text("class dblk : public gr::decim_block<4> {};")
    b = parse_gr3_block("dblk", inc / "dblk.h", None, None)
    assert b.base_class == "decim_block"


def test_parse_hier_block_base_class(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path)
    _add_hier_block(tmp_path, "testmod", "hblk")
    h = tmp_path / "include" / "testmod" / "hblk.h"
    b = parse_gr3_block("hblk", h, None, None)
    assert b.base_class == "hier_block2"


def test_parse_sync_block_port_counts(tmp_path: Path) -> None:
    b = _parsed_sync(tmp_path)
    assert b.in_port_count == 1
    assert b.out_port_count == 1


def test_parse_source_port_counts(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path)
    _add_sync_block(
        tmp_path, "testmod", "src", in_count=0, in_type="float", out_count=1, out_type="float"
    )
    h = tmp_path / "include" / "testmod" / "src.h"
    impl_cc = tmp_path / "lib" / "src_impl.cc"
    b = parse_gr3_block("src", h, None, impl_cc)
    assert b.in_port_count == 0
    assert b.out_port_count == 1


def test_parse_sink_port_counts(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path)
    _add_sync_block(
        tmp_path, "testmod", "snk", in_count=1, in_type="float", out_count=0, out_type="float"
    )
    h = tmp_path / "include" / "testmod" / "snk.h"
    impl_cc = tmp_path / "lib" / "snk_impl.cc"
    b = parse_gr3_block("snk", h, None, impl_cc)
    assert b.in_port_count == 1
    assert b.out_port_count == 0


def test_parse_port_type_float(tmp_path: Path) -> None:
    b = _parsed_sync(tmp_path)
    assert b.in_types == ["float"]
    assert b.out_types == ["float"]


def test_parse_port_type_gr_complex(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path)
    _add_sync_block(tmp_path, "testmod", "cblk", in_type="gr_complex", out_type="gr_complex")
    impl_cc = tmp_path / "lib" / "cblk_impl.cc"
    b = parse_gr3_block("cblk", tmp_path / "include" / "testmod" / "cblk.h", None, impl_cc)
    assert b.in_types == ["std::complex<float>"]


def test_parse_varport_none_count(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path)
    _add_varport_block(tmp_path, "testmod", "vblk")
    h = tmp_path / "include" / "testmod" / "vblk.h"
    impl_cc = tmp_path / "lib" / "vblk_impl.cc"
    b = parse_gr3_block("vblk", h, None, impl_cc)
    assert b.in_port_count is None


def test_parse_property_extracted(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path)
    setters = (
        "      virtual void set_alpha(float val) = 0;\n      virtual float alpha() const = 0;\n"
    )
    _add_sync_block(
        tmp_path, "testmod", "pblk", setters=setters, member_inits=",\n        d_alpha(0.5f)"
    )
    h = tmp_path / "include" / "testmod" / "pblk.h"
    impl_cc = tmp_path / "lib" / "pblk_impl.cc"
    b = parse_gr3_block("pblk", h, None, impl_cc)
    assert any(p.name == "alpha" for p in b.properties)


def test_parse_property_type(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path)
    setters = (
        "      virtual void set_alpha(float val) = 0;\n      virtual float alpha() const = 0;\n"
    )
    _add_sync_block(tmp_path, "testmod", "pblk", setters=setters)
    h = tmp_path / "include" / "testmod" / "pblk.h"
    b = parse_gr3_block("pblk", h, None, None)
    prop = next(p for p in b.properties if p.name == "alpha")
    assert prop.type == "float"


def test_parse_property_default(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path)
    setters = (
        "      virtual void set_alpha(float val) = 0;\n      virtual float alpha() const = 0;\n"
    )
    _add_sync_block(
        tmp_path, "testmod", "pblk", setters=setters, member_inits=",\n        d_alpha(0.5f)"
    )
    h = tmp_path / "include" / "testmod" / "pblk.h"
    impl_cc = tmp_path / "lib" / "pblk_impl.cc"
    b = parse_gr3_block("pblk", h, None, impl_cc)
    prop = next(p for p in b.properties if p.name == "alpha")
    assert prop.default == "0.5"


def test_parse_work_body_extracted(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path)
    _add_sync_block(
        tmp_path,
        "testmod",
        "wblk",
        work_body="      float *out0 = (float*)output_items[0];\n      out0[0] = 1.0f;",
    )
    impl_cc = tmp_path / "lib" / "wblk_impl.cc"
    b = parse_gr3_block("wblk", tmp_path / "include" / "testmod" / "wblk.h", None, impl_cc)
    assert b.work_body is not None
    assert "out0" in b.work_body


def test_parse_missing_impl_graceful(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path)
    inc = tmp_path / "include" / "testmod"
    (inc / "noimpl.h").write_text("class noimpl : public gr::sync_block {};")
    b = parse_gr3_block("noimpl", inc / "noimpl.h", None, None)
    assert b.work_body is None
    assert b.properties == []


def test_parse_message_ports_flag(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path)
    inc = tmp_path / "include" / "testmod"
    (inc / "mblk.h").write_text("class mblk : public gr::sync_block {};")
    lib = tmp_path / "lib"
    (lib / "mblk_impl.cc").write_text(
        "message_port_register_in(pmt::mp('in'));\n"
        "gr::io_signature::make(1,1,sizeof(float));\n"
        "gr::io_signature::make(1,1,sizeof(float));\n"
    )
    b = parse_gr3_block("mblk", inc / "mblk.h", None, lib / "mblk_impl.cc")
    assert b.has_message_ports is True


# ---------------------------------------------------------------------------
# Multi-port parsing and migration
# ---------------------------------------------------------------------------


def test_parse_multi_input_port_count(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path)
    _add_sync_block(tmp_path, "testmod", "add_blk", in_count=2, out_count=1)
    impl_cc = tmp_path / "lib" / "add_blk_impl.cc"
    h = tmp_path / "include" / "testmod" / "add_blk.h"
    b = parse_gr3_block("add_blk", h, None, impl_cc)
    assert b.in_port_count == 2
    assert b.out_port_count == 1


def test_parse_multi_output_port_count(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path)
    _add_sync_block(tmp_path, "testmod", "split_blk", in_count=1, out_count=2)
    impl_cc = tmp_path / "lib" / "split_blk_impl.cc"
    h = tmp_path / "include" / "testmod" / "split_blk.h"
    b = parse_gr3_block("split_blk", h, None, impl_cc)
    assert b.in_port_count == 1
    assert b.out_port_count == 2


def test_transform_multi_in_generates_correct_ports(tmp_path: Path) -> None:
    b = _minimal_block(in_count=2, out_count=1)
    answers, result = _gr3_to_answers(b, _dummy_cfg(tmp_path), "basic")
    assert len(answers["in_ports"]) == 2
    assert answers["in_ports"][0]["name"] == "in0"
    assert answers["in_ports"][1]["name"] == "in1"
    assert len(answers["out_ports"]) == 1
    assert answers["out_ports"][0]["name"] == "out"


def test_transform_multi_out_generates_correct_ports(tmp_path: Path) -> None:
    b = _minimal_block(in_count=1, out_count=2)
    answers, result = _gr3_to_answers(b, _dummy_cfg(tmp_path), "basic")
    assert len(answers["out_ports"]) == 2
    assert answers["out_ports"][0]["name"] == "out0"
    assert answers["out_ports"][1]["name"] == "out1"


def test_transform_multi_port_status_partial(tmp_path: Path) -> None:
    b = _minimal_block(in_count=2, out_count=1)
    _, result = _gr3_to_answers(b, _dummy_cfg(tmp_path), "basic")
    assert result.status == "partial"
    assert any("multi-port" in t for t in result.todos)


def test_transform_multi_port_uses_process_bulk(tmp_path: Path) -> None:
    b = _minimal_block(in_count=2, out_count=1)
    answers, _ = _gr3_to_answers(b, _dummy_cfg(tmp_path), "basic")
    assert answers["processing_style"] == "processBulk"


def test_migrate_multi_in_creates_hpp(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _make_gr3_module(src)
    _add_sync_block(
        src, "testmod", "add_blk", in_count=2, out_count=1, work_body="  out0[i] = in0[i] + in1[i];"
    )
    out = tmp_path / "out"
    migrate_project(src, out)
    hpp = out / "blocks" / "testmod" / "include" / "gnuradio-4.0" / "testmod" / "AddBlk.hpp"
    assert hpp.exists()


def test_migrate_multi_in_hpp_has_two_port_in(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _make_gr3_module(src)
    _add_sync_block(src, "testmod", "add_blk", in_count=2, out_count=1)
    out = tmp_path / "out"
    migrate_project(src, out)
    hpp = out / "blocks" / "testmod" / "include" / "gnuradio-4.0" / "testmod" / "AddBlk.hpp"
    text = hpp.read_text()
    assert text.count("PortIn<T>") == 2


def test_migrate_multi_in_hpp_bulk_params_include_all_spans(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _make_gr3_module(src)
    _add_sync_block(src, "testmod", "add_blk", in_count=2, out_count=1)
    out = tmp_path / "out"
    migrate_project(src, out)
    hpp = out / "blocks" / "testmod" / "include" / "gnuradio-4.0" / "testmod" / "AddBlk.hpp"
    text = hpp.read_text()
    assert "in0" in text
    assert "in1" in text
    assert "processBulk" in text


def test_migrate_multi_in_reflectable_has_all_ports(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _make_gr3_module(src)
    _add_sync_block(src, "testmod", "add_blk", in_count=2, out_count=1)
    out = tmp_path / "out"
    migrate_project(src, out)
    hpp = out / "blocks" / "testmod" / "include" / "gnuradio-4.0" / "testmod" / "AddBlk.hpp"
    text = hpp.read_text()
    assert "GR_MAKE_REFLECTABLE(AddBlk, in0, in1, out)" in text


# ---------------------------------------------------------------------------
# _to_camel
# ---------------------------------------------------------------------------


def test_to_camel_simple() -> None:
    assert _to_camel("my_block") == "MyBlock"


def test_to_camel_single_word() -> None:
    assert _to_camel("filter") == "Filter"


def test_to_camel_three_words() -> None:
    assert _to_camel("fir_filter_cc") == "FirFilterCc"


# ---------------------------------------------------------------------------
# Transformer tests
# ---------------------------------------------------------------------------


def _minimal_block(
    base: str = "sync_block",
    in_count: int = 1,
    out_count: int = 1,
    in_type: str = "float",
    out_type: str = "float",
    work_body: str = "  return n;",
    properties: list | None = None,
    has_message_ports: bool = False,
) -> Gr3BlockInfo:
    return Gr3BlockInfo(
        name="my_block",
        header_path=Path("/fake/my_block.h"),
        impl_header_path=None,
        impl_source_path=None,
        base_class=base,
        in_port_count=in_count,
        out_port_count=out_count,
        in_types=[in_type] if in_count > 0 else [],
        out_types=[out_type] if out_count > 0 else [],
        properties=properties or [],
        constructor_params=[],
        has_message_ports=has_message_ports,
        has_set_history=False,
        has_output_multiple=False,
        work_body=work_body,
    )


def _dummy_cfg(tmp_path: Path) -> ProjectConfig:
    from gr4_modtool.project.discovery import save_config

    cfg = ProjectConfig(
        root=tmp_path,
        name="testmod",
        version="0.1.0",
        cpp_namespace="gr::testmod",
        cmake_prefix="gr4_testmod",
        gr4_include_prefix="gnuradio-4.0",
        build_cmake=False,
        build_meson=False,
        groups={"basic": "blocks/basic"},
    )
    save_config(cfg)
    return cfg


def test_transform_sync_processing_style(tmp_path: Path) -> None:
    answers, _ = _gr3_to_answers(_minimal_block(), _dummy_cfg(tmp_path), "basic")
    assert answers["processing_style"] == "processOne"


def test_transform_block_base_processing_style(tmp_path: Path) -> None:
    answers, _ = _gr3_to_answers(_minimal_block(base="block"), _dummy_cfg(tmp_path), "basic")
    assert answers["processing_style"] == "processBulk"


def test_transform_source_no_in_ports(tmp_path: Path) -> None:
    answers, _ = _gr3_to_answers(
        _minimal_block(in_count=0, out_count=1), _dummy_cfg(tmp_path), "basic"
    )
    assert answers["in_ports"] == []


def test_transform_sink_no_out_ports(tmp_path: Path) -> None:
    answers, _ = _gr3_to_answers(
        _minimal_block(in_count=1, out_count=0), _dummy_cfg(tmp_path), "basic"
    )
    assert answers["out_ports"] == []


def test_transform_name_camel_case(tmp_path: Path) -> None:
    answers, _ = _gr3_to_answers(_minimal_block(), _dummy_cfg(tmp_path), "basic")
    assert answers["block_name"] == "MyBlock"


def test_transform_type_list_from_float(tmp_path: Path) -> None:
    answers, _ = _gr3_to_answers(_minimal_block(in_type="float"), _dummy_cfg(tmp_path), "basic")
    assert "float" in answers["type_list"]
    assert "double" in answers["type_list"]


def test_transform_type_list_from_gr_complex(tmp_path: Path) -> None:
    answers, _ = _gr3_to_answers(
        _minimal_block(in_type="std::complex<float>", out_type="std::complex<float>"),
        _dummy_cfg(tmp_path),
        "basic",
    )
    assert "std::complex" in answers["type_list"]


def test_transform_hier_block_manual(tmp_path: Path) -> None:
    b = _minimal_block(base="hier_block2")
    _, result = _gr3_to_answers(b, _dummy_cfg(tmp_path), "basic")
    assert result.status == "manual"


def test_transform_varport_manual(tmp_path: Path) -> None:
    b = Gr3BlockInfo(
        name="vblk",
        header_path=Path("/fake/vblk.h"),
        impl_header_path=None,
        impl_source_path=None,
        base_class="block",
        in_port_count=None,
        out_port_count=1,
        in_types=[],
        out_types=["float"],
        properties=[],
        constructor_params=[],
        has_message_ports=False,
        has_set_history=False,
        has_output_multiple=False,
        work_body=None,
    )
    _, result = _gr3_to_answers(b, _dummy_cfg(tmp_path), "basic")
    assert result.status == "manual"


def test_transform_message_ports_partial(tmp_path: Path) -> None:
    b = _minimal_block(has_message_ports=True)
    _, result = _gr3_to_answers(b, _dummy_cfg(tmp_path), "basic")
    assert result.status == "partial"
    assert any("message" in t.lower() for t in result.todos)


def test_transform_work_body_in_comment(tmp_path: Path) -> None:
    answers, _ = _gr3_to_answers(
        _minimal_block(work_body="  out[0] = in[0];"), _dummy_cfg(tmp_path), "basic"
    )
    assert "// TODO: translate" in answers["work_body_comment"]
    assert "out[0]" in answers["work_body_comment"]


def test_transform_properties_in_answers(tmp_path: Path) -> None:
    props = [Gr3Property("alpha", "float", "0.5")]
    b = _minimal_block(properties=props)
    answers, _ = _gr3_to_answers(b, _dummy_cfg(tmp_path), "basic")
    assert answers["properties"] == props


# ---------------------------------------------------------------------------
# _inject_properties tests
# ---------------------------------------------------------------------------

_SAMPLE_HPP = """\
#pragma once
namespace gr::testmod::basic {
template<typename T>
struct MyBlock : Block<MyBlock<T>> {
    PortIn<T> in;
    PortOut<T> out;
    GR_MAKE_REFLECTABLE(MyBlock, in, out);
    [[nodiscard]] T processOne(T x) const noexcept { return x; }
};
}
"""


def test_inject_properties_adds_annotated() -> None:
    props = [Gr3Property("alpha", "float", "0.5")]
    result = _inject_properties(_SAMPLE_HPP, props)
    assert "Annotated<float" in result


def test_inject_properties_empty_list_unchanged() -> None:
    result = _inject_properties(_SAMPLE_HPP, [])
    assert result == _SAMPLE_HPP


def test_inject_properties_default_value() -> None:
    props = [Gr3Property("alpha", "float", "0.5")]
    result = _inject_properties(_SAMPLE_HPP, props)
    assert "= 0.5" in result


def test_inject_properties_inserted_after_reflectable() -> None:
    props = [Gr3Property("alpha", "float", "")]
    result = _inject_properties(_SAMPLE_HPP, props)
    refl_pos = result.index("GR_MAKE_REFLECTABLE")
    annotated_pos = result.index("Annotated<float")
    assert annotated_pos > refl_pos


# ---------------------------------------------------------------------------
# Report / renderer tests
# ---------------------------------------------------------------------------


def test_migration_result_is_dataclass() -> None:
    assert hasattr(MigrationResult, "__dataclass_fields__")
    for f in ("block_name", "gr3_name", "status", "written_files", "todos", "detail"):
        assert f in MigrationResult.__dataclass_fields__


def test_migration_report_is_dataclass() -> None:
    assert hasattr(MigrationReport, "__dataclass_fields__")


def test_migration_report_counts() -> None:
    results = [
        MigrationResult("A", "a", "auto"),
        MigrationResult("B", "b", "auto"),
        MigrationResult("C", "c", "partial"),
        MigrationResult("D", "d", "manual"),
    ]
    report = MigrationReport(Path("."), Path("."), "mod", "gr::mod", results)
    assert report.auto_count == 2
    assert report.partial_count == 1
    assert report.manual_count == 1
    assert report.skipped_count == 0


def test_render_table_contains_block_name() -> None:
    results = [MigrationResult("MyBlock", "my_block", "auto", detail="test")]
    report = MigrationReport(Path("/src"), Path("/out"), "mod", "gr::mod", results)
    console = Console(record=True, no_color=True)
    _render_table(report, console)
    assert "MyBlock" in console.export_text()


def test_render_table_auto_tick() -> None:
    results = [MigrationResult("MyBlock", "my_block", "auto")]
    report = MigrationReport(Path("/src"), Path("/out"), "mod", "gr::mod", results)
    console = Console(record=True, no_color=True)
    _render_table(report, console)
    assert "✓" in console.export_text()


def test_render_table_manual_cross() -> None:
    results = [MigrationResult("HierBlk", "hier_blk", "manual")]
    report = MigrationReport(Path("/src"), Path("/out"), "mod", "gr::mod", results)
    console = Console(record=True, no_color=True)
    _render_table(report, console)
    assert "✗" in console.export_text()


def test_render_json_parses() -> None:
    results = [MigrationResult("MyBlock", "my_block", "auto")]
    report = MigrationReport(Path("/src"), Path("/out"), "mod", "gr::mod", results)
    parsed = json.loads(_render_json(report))
    assert "results" in parsed
    assert parsed["results"][0]["block_name"] == "MyBlock"


def test_render_json_has_summary() -> None:
    results = [
        MigrationResult("A", "a", "auto"),
        MigrationResult("B", "b", "manual"),
    ]
    report = MigrationReport(Path("/src"), Path("/out"), "mod", "gr::mod", results)
    parsed = json.loads(_render_json(report))
    assert parsed["summary"]["auto"] == 1
    assert parsed["summary"]["manual"] == 1


# ---------------------------------------------------------------------------
# migrate_project orchestrator tests
# ---------------------------------------------------------------------------


def test_migrate_project_raises_on_non_gr3(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="GNURadio 3"):
        migrate_project(tmp_path, tmp_path / "out")


def test_migrate_project_returns_report(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _make_gr3_module(src)
    _add_sync_block(src, "testmod", "my_block")
    report = migrate_project(src, tmp_path / "out")
    assert isinstance(report, MigrationReport)


def test_migrate_project_creates_toml(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _make_gr3_module(src)
    out = tmp_path / "out"
    migrate_project(src, out)
    assert (out / ".gr4modtool.toml").exists()


def test_migrate_project_creates_hpp(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _make_gr3_module(src)
    _add_sync_block(src, "testmod", "my_block")
    out = tmp_path / "out"
    migrate_project(src, out)
    hpp = out / "blocks" / "testmod" / "include" / "gnuradio-4.0" / "testmod" / "MyBlock.hpp"
    assert hpp.exists()


def test_migrate_project_creates_test(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _make_gr3_module(src)
    _add_sync_block(src, "testmod", "my_block")
    out = tmp_path / "out"
    migrate_project(src, out)
    test = out / "blocks" / "testmod" / "test" / "qa_MyBlock.cpp"
    assert test.exists()


def test_migrate_project_hpp_has_pragma_once(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _make_gr3_module(src)
    _add_sync_block(src, "testmod", "my_block")
    out = tmp_path / "out"
    migrate_project(src, out)
    hpp = out / "blocks" / "testmod" / "include" / "gnuradio-4.0" / "testmod" / "MyBlock.hpp"
    assert hpp.read_text().startswith("#pragma once")


def test_migrate_project_hpp_has_register_block(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _make_gr3_module(src)
    _add_sync_block(src, "testmod", "my_block")
    out = tmp_path / "out"
    migrate_project(src, out)
    hpp = out / "blocks" / "testmod" / "include" / "gnuradio-4.0" / "testmod" / "MyBlock.hpp"
    assert "GR_REGISTER_BLOCK" in hpp.read_text()


def test_migrate_project_hpp_has_work_body_comment(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _make_gr3_module(src)
    _add_sync_block(
        src, "testmod", "my_block", work_body="      float *out0 = (float *)output_items[0];"
    )
    out = tmp_path / "out"
    migrate_project(src, out)
    hpp = out / "blocks" / "testmod" / "include" / "gnuradio-4.0" / "testmod" / "MyBlock.hpp"
    assert "TODO: translate" in hpp.read_text()


def test_migrate_project_manual_creates_md(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _make_gr3_module(src)
    _add_hier_block(src, "testmod", "hier_blk")
    out = tmp_path / "out"
    migrate_project(src, out)
    assert (out / "HierBlk_MANUAL.md").exists()


def test_migrate_project_dry_run_no_output_dir(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _make_gr3_module(src)
    _add_sync_block(src, "testmod", "my_block")
    out = tmp_path / "out"
    migrate_project(src, out, dry_run=True)
    assert not out.exists()


def test_migrate_project_report_module_name(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _make_gr3_module(src, name="mymod")
    out = tmp_path / "out"
    report = migrate_project(src, out)
    assert report.module_name == "mymod"


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


def test_cli_valid_source_exits_0(tmp_path: Path, runner: CliRunner) -> None:
    src = tmp_path / "src"
    _make_gr3_module(src)
    _add_sync_block(src, "testmod", "my_block")
    out = tmp_path / "out"
    result = runner.invoke(cmd, [str(src), "--output", str(out)])
    assert result.exit_code == 0, result.output


def test_cli_invalid_source_exits_1(tmp_path: Path, runner: CliRunner) -> None:
    result = runner.invoke(cmd, [str(tmp_path)])
    assert result.exit_code == 1


def test_cli_dry_run_no_output(tmp_path: Path, runner: CliRunner) -> None:
    src = tmp_path / "src"
    _make_gr3_module(src)
    _add_sync_block(src, "testmod", "my_block")
    out = tmp_path / "out"
    runner.invoke(cmd, [str(src), "--output", str(out), "--dry-run"])
    assert not out.exists()


def test_cli_force_overwrites_existing(tmp_path: Path, runner: CliRunner) -> None:
    src = tmp_path / "src"
    _make_gr3_module(src)
    _add_sync_block(src, "testmod", "my_block")
    out = tmp_path / "out"
    out.mkdir()
    result = runner.invoke(cmd, [str(src), "--output", str(out), "--force"])
    assert result.exit_code == 0, result.output


def test_cli_no_force_existing_fails(tmp_path: Path, runner: CliRunner) -> None:
    src = tmp_path / "src"
    _make_gr3_module(src)
    out = tmp_path / "out"
    out.mkdir()
    result = runner.invoke(cmd, [str(src), "--output", str(out)])
    assert result.exit_code == 1


def test_cli_json_output_valid(tmp_path: Path, runner: CliRunner) -> None:
    src = tmp_path / "src"
    _make_gr3_module(src)
    _add_sync_block(src, "testmod", "my_block")
    out = tmp_path / "out"
    result = runner.invoke(cmd, [str(src), "--output", str(out), "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert "results" in parsed
    assert "summary" in parsed


def test_cli_default_output_dir_name(
    tmp_path: Path, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "src"
    _make_gr3_module(src, name="mymod")
    monkeypatch.chdir(tmp_path)
    runner.invoke(cmd, [str(src)])
    assert (tmp_path / "gr4-mymod").exists()


# ---------------------------------------------------------------------------
# api.py regression
# ---------------------------------------------------------------------------


def test_api_detect_gr3_project(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path)
    assert api.detect_gr3_project(tmp_path) is not None


def test_api_migrate_project(tmp_path: Path) -> None:
    src = tmp_path / "src"
    _make_gr3_module(src)
    _add_sync_block(src, "testmod", "my_block")
    report = api.migrate_project(src, tmp_path / "out")
    assert isinstance(report, api.MigrationReport)


def test_api_parse_gr3_block(tmp_path: Path) -> None:
    _make_gr3_module(tmp_path)
    _add_sync_block(tmp_path, "testmod", "my_block")
    h = tmp_path / "include" / "testmod" / "my_block.h"
    b = api.parse_gr3_block("my_block", h, None, None)
    assert isinstance(b, api.Gr3BlockInfo)
