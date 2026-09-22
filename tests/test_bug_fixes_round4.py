"""Regression tests for PDF heading conversion, BibTeX field parsing, and snapshot commit status."""

import subprocess
from pathlib import Path

from synapseforge.core.scorecard import QualityScorecard
from synapseforge.core.snapshot import SnapshotManager
from synapseforge.tools.cite_tool import CiteTool
from synapseforge.tools.pdf_tool import PDFTool


def test_pdf_headings_do_not_rewrite_csharp_or_issue_hashes():
    tool = PDFTool()
    md = (
        "C# programming and issue # 12 are not headings.\n\n"
        "# Real Title\n\n"
        "## Subsection\n\n"
        "```python\n"
        "# keep this comment\n"
        "print(1)\n"
        "```\n"
    )
    out = tool._convert_markdown_headings_to_typst(md)
    assert "C# programming and issue # 12" in out
    assert out.splitlines()[2].startswith("= Real Title")
    assert "== Subsection" in out
    assert "# keep this comment" in out
    assert "= keep this comment" not in out


def test_pdf_finds_bibliography_next_to_workspace_not_only_cwd(tmp_path, monkeypatch):
    workspace = tmp_path / "paper"
    dist = workspace / "dist"
    dist.mkdir(parents=True)
    (workspace / "bibliography.bib").write_text("@article{a2020, title={A}, author={A}, year={2020}}\n", encoding="utf-8")
    md = dist / "full_manuscript.md"
    md.write_text("See @a2020 for the protocol.\n", encoding="utf-8")
    other = tmp_path / "unrelated"
    other.mkdir()
    monkeypatch.chdir(other)
    found = PDFTool._find_bibliography(md)
    assert found == workspace / "bibliography.bib"


def test_cite_tool_keeps_quoted_titles_and_nested_braces(tmp_path):
    bib = tmp_path / "bibliography.bib"
    bib.write_text(
        """@article{li2023camel,
  title={CAMEL: Communicative Agents for "Mind" Exploration of Large Language Model Society},
  author={Li, Guohao and Hammoud, Hasan Abed Al Kader},
  year={2023},
  journal={NeurIPS}
}

@article{shapiro2011crdt,
  title={Conflict-free Replicated Data Types},
  author={Shapiro, Marc and Pregui{\\c{c}}a, Nuno},
  year={2011}
}
""",
        encoding="utf-8",
    )
    tool = CiteTool(bib_path=bib, workspace_root=tmp_path)
    entries = {e["key"]: e for e in tool.list_citations()}
    assert "Mind" in entries["li2023camel"]["title"]
    assert entries["li2023camel"]["title"].startswith("CAMEL:")
    assert "Shapiro" in entries["shapiro2011crdt"]["author"]
    assert entries["shapiro2011crdt"]["year"] == "2011"


def test_snapshot_failed_commit_is_not_marked_created(tmp_path):
    snap = SnapshotManager(tmp_path)
    (tmp_path / "sections").mkdir()
    (tmp_path / "sections" / "01.md").write_text("hello\n", encoding="utf-8")
    res = snap.create_checkpoint(message="no git repository")
    assert res.get("created") is not True
    assert res.get("ok") is not True


def test_snapshot_checkpoint_in_isolated_repo(tmp_path):
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "sections").mkdir()
    (tmp_path / "sections" / "01.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    snap = SnapshotManager(tmp_path)
    first = snap.create_checkpoint(message="initial", author="TestRunner")
    assert first["ok"] is True
    (tmp_path / "sections" / "01.md").write_text("hello world\n", encoding="utf-8")
    second = snap.create_checkpoint(message="edit", author="TestRunner")
    assert second["ok"] is True
    assert second["created"] is True
    hist = snap.list_history(limit=5)
    assert len(hist) >= 1


def test_scorecard_html_escapes_issue_text(tmp_path):
    sec = tmp_path / "sections"
    sec.mkdir()
    nasty = sec / "01_<script>.md"
    nasty.write_text("# Intro\n\nShort paragraph.\n", encoding="utf-8")
    out = QualityScorecard(tmp_path).generate_html_report(tmp_path / "dist" / "audit.html")
    text = out.read_text(encoding="utf-8")
    assert "<script>" not in text
    assert "01_&lt;script&gt;.md" in text
