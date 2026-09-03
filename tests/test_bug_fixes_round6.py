"""Regression tests for path-safe ids, lock files, citation keys, and Typst titles."""

from pathlib import Path

from synapseforge.core.file_lock import AutoSectionLock, SectionLockedError
from synapseforge.core.section_paths import resolve_section_path
from synapseforge.core.user_prompts import UserPromptManager
from synapseforge.tools.cite_tool import CiteTool
from synapseforge.tools.pdf_tool import PDFTool


def test_resolve_section_path_rejects_traversal(tmp_path):
    outside = tmp_path.parent / f"escaped_{tmp_path.name}.md"
    path = resolve_section_path(tmp_path, f"../escaped_{tmp_path.name}", create_dir=True)
    assert path.parent.resolve() == (tmp_path / "sections").resolve()
    assert path.name == f"escaped_{tmp_path.name}.md"
    assert not outside.exists()


def test_file_lock_stays_inside_locks_dir(tmp_path):
    lock = AutoSectionLock("../outside", "Agent", tmp_path)
    assert lock.lock_file_path.parent == tmp_path / ".synapse" / "locks"
    assert lock.lock_file_path.name == "outside.lock"


def test_write_draft_rejects_path_escape(tmp_path):
    outside = tmp_path.parent / f"draft_escape_{tmp_path.name}.md"
    with AutoSectionLock("sec_01", "Agent", tmp_path) as lock:
        try:
            lock.write_draft("nope", target_file_path=outside)
            escaped = True
        except SectionLockedError:
            escaped = False
    assert escaped is False
    assert not outside.exists()


def test_user_prompt_rejects_path_role_id(tmp_path):
    mgr = UserPromptManager(tmp_path, auto_init_report_spec=False)
    res = mgr.set_prompt("../evil", "should not write")
    assert res.get("ok") is False
    assert not list(tmp_path.glob("evil.md"))
    assert not list((tmp_path / "prompts").glob("..*"))


def test_add_bibtex_rejects_injected_key(tmp_path):
    cite = CiteTool(workspace_root=tmp_path)
    bad = cite.add_bibtex_entry("bad}{@injected", "article", "T", "A", "2026")
    assert bad.get("ok") is False
    ok = cite.add_bibtex_entry("good2026", "article", "T", "A", "2026")
    assert ok.get("ok") is True
    text = (tmp_path / "bibliography.bib").read_text(encoding="utf-8")
    assert "@injected" not in text
    assert "good2026" in text


def test_pdf_header_title_escapes_typst_markup(tmp_path):
    md = tmp_path / "doc.md"
    md.write_text("hello\n", encoding="utf-8")
    out = tmp_path / "out.pdf"
    PDFTool(typst_bin="/nonexistent/typst").compile_markdown_to_pdf(
        md, out, title="Hack ] #title"
    )
    typ = out.with_suffix(".typ")
    body = typ.read_text(encoding="utf-8")
    assert "Hack \\ ] \\ #title".replace(" ", "") in body.replace(" ", "") or "Hack \\] \\#title" in body
