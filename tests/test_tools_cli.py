import json
import pytest
from pathlib import Path
from synapseforge.tools.office_tool import OfficeTool
from synapseforge.tools.sci_plot_tool import SciPlotTool
from synapseforge.tools.pdf_tool import PDFTool


def test_office_tool_inspect(tmp_path):
    tool = OfficeTool()
    dummy = tmp_path / "test.docx"
    dummy.write_text("dummy docx content", encoding="utf-8")
    
    res = tool.inspect_file(dummy)
    assert res["ok"] is True
    assert res["extension"] == ".docx"
    assert res["size_bytes"] > 0


def test_sci_plot_tool_nature_curve(tmp_path):
    pytest.importorskip("matplotlib")
    tool = SciPlotTool(default_style="nature", dpi=150)
    out_png = tmp_path / "curve.png"
    
    res = tool.plot_benchmark_curve(
        data={},
        output_path=out_png,
        title="Test Multi-Agent Performance",
        style="nature",
    )
    assert res["ok"] is True
    assert out_png.exists()
    assert out_png.with_suffix(".svg").exists()
    assert res["curves_rendered"] == 3


def test_pdf_tool_typst_compilation(tmp_path):
    tool = PDFTool()
    if not tool.is_available():
        pytest.skip("Typst binary not installed on host")
    md_file = tmp_path / "doc.md"
    md_file.write_text("# 摘要与方法\n\n本文提出了全新的分布式智能体共识机制。\n", encoding="utf-8")
    out_pdf = tmp_path / "doc.pdf"

    res = tool.compile_markdown_to_pdf(md_file, out_pdf, title="测试文档")
    assert res["ok"] is True
    assert out_pdf.exists()
    assert res["file_size"] > 0
