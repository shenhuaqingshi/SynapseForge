from pathlib import Path
import pytest
from synapseforge.linters.anti_ai import AntiAILinter
from synapseforge.linters.coherence import CoherenceLinter
from synapseforge.linters.style import StyleLinter
from synapseforge.linters.citations import CitationLinter
from synapseforge.linters import LintSuite


def test_anti_ai_linter_detects_cliches():
    linter = AntiAILinter()
    bad_text = "在当今数字化时代，随着人工智能的快速发展，总而言之，它展现出巨大的潜力与广阔的前景。"
    res = linter.lint_text(bad_text)
    assert not res.passed
    assert res.error_count >= 3
    issues = [i.message for i in res.issues]
    assert any("套路化开头" in msg for msg in issues)


def test_anti_ai_linter_detects_formulaic_lists():
    linter = AntiAILinter()
    bad_list = """# Overview
- Item 1: First fragmented point.
- Item 2: Second fragmented point.
- Item 3: Third fragmented point.
- Item 4: Fourth fragmented point.
- Item 5: Fifth fragmented point.
- Item 6: Sixth fragmented point.
- Item 7: Seventh fragmented point.
- Item 8: Eighth fragmented point.
- Item 9: Ninth fragmented point.
- Item 10: Tenth fragmented point.
"""
    res = linter.lint_text(bad_list)
    assert not res.passed
    assert any("机械分点狂热症" in i.message for i in res.issues)


def test_style_linter_checks_booktabs():
    linter = StyleLinter()
    bad_table = """| Col 1 | Col 2 |
| Cell 1 | Cell 2 |
"""
    res = linter.lint_text(bad_table)
    assert not res.passed
    assert any("表格结构不完整" in i.message or "分隔符" in i.message for i in res.issues)


def test_citations_linter(tmp_path):
    bib = tmp_path / "test.bib"
    bib.write_text("""@article{smith2023,
  author={Smith, John},
  title={Agent Theory},
  year={2023}
}""", encoding="utf-8")

    linter = CitationLinter(bib_path=bib)
    good_text = "According to @smith2023, multi-agent swarms scale logarithmically."
    res = linter.lint_text(good_text)
    assert res.passed

    bad_text = "According to @nonexistent2099, systems fail."
    res_bad = linter.lint_text(bad_text)
    assert not res_bad.passed
    assert res_bad.error_count == 1
