"""
Regression and verification test suite for SynapseForge bug fixes (Round 3).
Tests:
- CitationLinter & ASTParser code block decorator isolation
- StyleLinter CJK-Latin spacing with inline code & LaTeX math
- SnapshotManager reason parameter and hash/commit_hash compatibility
- ConfidentialityRedactor multi-line secret scanning (SSH private keys)
- MultiDocumentSynthesizer structural block deduplication (code, lists, quotes)
- SciPlotTool run_plot_script cwd output directory propagation
- PDFTool LaTeX math to Typst conversion (fractions, roots, Greek letters, operators)
- FigureLinker robust section file resolution
- MultiFormatExporter HTMLRenderer publication output
"""

import sys
import tempfile
from pathlib import Path

import pytest

from synapseforge.core.ast_parser import BlockType, MarkdownASTParser
from synapseforge.core.exporter import MultiFormatExporter
from synapseforge.core.figure_linker import FigureLinker
from synapseforge.core.snapshot import SnapshotManager
from synapseforge.core.variant_synthesizer import MultiDocumentSynthesizer
from synapseforge.linters.citations import CitationLinter
from synapseforge.linters.style import StyleLinter
from synapseforge.security.redactor import ConfidentialityRedactor
from synapseforge.tools.pdf_tool import PDFTool
from synapseforge.tools.sci_plot_tool import SciPlotTool


def test_citation_linter_and_ast_ignore_code_blocks_and_decorators(tmp_path):
    bib_file = tmp_path / "bibliography.bib"
    bib_file.write_text(
        """@article{vaswani2017,
  author = {Ashish Vaswani},
  title = {Attention Is All You Need},
  year = {2017},
  journal = {NeurIPS}
}
""",
        encoding="utf-8",
    )

    doc_text = """# Section with Code and Real Citations

In our implementation, we cite @vaswani2017 for the transformer architecture.

```python
@dataclass
@pytest.fixture
def sample_fixture():
    @app.get("/api")
    def endpoint():
        pass
```

Inline code like `@classmethod` and comment <!-- Assigned to @Drafter --> should not be citations.
"""
    # 1. AST parser citation extraction
    citations = MarkdownASTParser.extract_citations(doc_text)
    assert "vaswani2017" in citations
    assert "dataclass" not in citations
    assert "pytest" not in citations
    assert "app" not in citations
    assert "classmethod" not in citations

    # 2. CitationLinter execution
    linter = CitationLinter(bib_path=bib_file)
    res = linter.lint_text(doc_text)
    assert res.passed is True
    assert res.error_count == 0


def test_style_linter_ignores_inline_code_and_latex_math():
    linter = StyleLinter()
    # Mixed Chinese and Western text containing inline code, LaTeX math, and links
    text = """# 算法性能评估

本节分析 $E=mc^2$ 与 $O(n\\log n)$ 复杂度，以及使用 `SyncEngine` 时的通信开销。
详见文档 [系统架构](#system-architecture) 说明。
"""
    res = linter.lint_text(text)
    assert res.passed is True


def test_snapshot_create_checkpoint_reason_and_hash_compat(tmp_path):
    snap = SnapshotManager(tmp_path)
    # create_checkpoint with reason kwarg (and empty git fallback)
    res = snap.create_checkpoint(reason="Automated test checkpoint", author="Tester")
    assert isinstance(res, dict)
    assert "commit_hash" in res
    assert "hash" in res
    assert res["commit_hash"] == res["hash"]


def test_confidentiality_redactor_scans_multiline_ssh_key(tmp_path):
    redactor = ConfidentialityRedactor(tmp_path)
    multiline_text = """# Confidential Node Deployment
Here is the deployment key:
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEA0Y7V5lW9n7p...
...ABCDEF1234567890...
-----END RSA PRIVATE KEY-----
"""
    issues = redactor.scan_for_secrets(multiline_text)
    assert len(issues) >= 1
    assert any(iss.matched_type == "SSH_PRIVATE_KEY" for iss in issues)

    # Verify redaction and unredaction roundtrip
    sanitized, token_map = redactor.redact(multiline_text)
    assert "BEGIN RSA PRIVATE KEY" not in sanitized
    assert "⟦SEC_SSH_PRIVATE_KEY_" in sanitized
    rehydrated = redactor.unredact(sanitized, token_map)
    assert rehydrated == multiline_text


def test_variant_synthesizer_deduplicates_all_blocks(tmp_path):
    var1 = tmp_path / "var1.md"
    var2 = tmp_path / "var2.md"

    var1.write_text("""# Section Title

Here is common paragraph A.

```python
def shared_code():
    return 42
```

- Shared bullet point 1
- Shared bullet point 2
""", encoding="utf-8")

    var2.write_text("""# Section Title

Here is common paragraph A.

```python
def shared_code():
    return 42
```

- Shared bullet point 1
- Shared bullet point 2

Here is unique paragraph B from variant 2.
""", encoding="utf-8")

    synth = MultiDocumentSynthesizer(tmp_path)
    out_file = tmp_path / "merged.md"
    res = synth.merge_variants([var1, var2], out_file, strategy="harmonize")
    assert res["ok"] is True

    merged_content = out_file.read_text(encoding="utf-8")
    assert merged_content.count("def shared_code():") == 1
    assert merged_content.count("Shared bullet point 1") == 1
    assert "Here is unique paragraph B" in merged_content


def test_sci_plot_run_plot_script_cwd(tmp_path):
    tool = SciPlotTool()
    script = tmp_path / "test_plot.py"
    output_dir = tmp_path / "plot_out"
    script.write_text("""
from pathlib import Path
(Path.cwd() / "generated_plot.txt").write_text("plot generated")
""", encoding="utf-8")

    res = tool.run_plot_script(script, output_dir=output_dir)
    assert res["ok"] is True
    assert (output_dir / "generated_plot.txt").exists()
    assert (output_dir / "generated_plot.txt").read_text() == "plot generated"


def test_pdf_tool_latex_to_typst_math_conversion():
    tool = PDFTool()
    latex_md = "We evaluate $\\frac{1}{\\mu - \\lambda}$ and $\\sqrt{x^2 + y^2}$ with $\\alpha \\le \\beta \\to \\infty$."
    typst_md = tool._convert_latex_math_to_typst(latex_md)
    assert "(1) / (mu - lambda)" in typst_md
    assert "sqrt(x^2 + y^2)" in typst_md
    assert "<=" in typst_md
    assert "->" in typst_md
    assert "oo" in typst_md


def test_figure_linker_exact_and_prefixed_lookup(tmp_path):
    sec_dir = tmp_path / "sections"
    sec_dir.mkdir(parents=True, exist_ok=True)

    sec1 = sec_dir / "01_intro.md"
    sec10 = sec_dir / "10_conclusion.md"
    sec1.write_text("# Introduction\n\nIntro text.", encoding="utf-8")
    sec10.write_text("# Conclusion\n\nConclusion text.", encoding="utf-8")

    linker = FigureLinker(tmp_path)
    res = linker.insert_figure(
        section_id="sec_01",
        image_path="figures/fig1.png",
        caption="Architecture Diagram",
        fig_num=1,
    )
    assert res["ok"] is True
    assert "01_intro.md" in res["section_file"]
    assert "![图 1：Architecture Diagram]" in sec1.read_text(encoding="utf-8")
    assert "![图 1" not in sec10.read_text(encoding="utf-8")


def test_multi_format_exporter_html_rendering(tmp_path):
    sec_dir = tmp_path / "sections"
    sec_dir.mkdir(parents=True, exist_ok=True)
    sec1 = sec_dir / "01_intro.md"
    sec1.write_text("# Research Overview\n\nContinuous prose paragraph regarding decentralized consensus.", encoding="utf-8")

    exporter = MultiFormatExporter(tmp_path)
    res = exporter.export_all(title="Publication Test Paper")
    assert res["ok"] is True

    html_file = tmp_path / "dist" / "publication_standalone.html"
    assert html_file.exists()
    html_content = html_file.read_text(encoding="utf-8")
    assert "<h1" in html_content
    assert "Research Overview" in html_content
    assert "Continuous prose paragraph" in html_content
