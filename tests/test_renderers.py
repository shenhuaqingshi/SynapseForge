from pathlib import Path
import pytest
from synapseforge.config import ProjectConfig
from synapseforge.renderers.html_renderer import HTMLRenderer
from synapseforge.renderers.typst_renderer import TypstRenderer
from synapseforge.renderers.pipeline import PublicationPipeline


def test_html_renderer():
    md = """# Test Title
This is paragraph one.

## Subsection
This is paragraph two.
"""
    html = HTMLRenderer.render(md, title="Test Doc", authors=["Author A"])
    assert "<!DOCTYPE html>" in html
    assert "Test Doc" in html
    assert "Author A" in html
    assert "Subsection" in html


def test_typst_renderer():
    md = """# Introduction
Formal math: $\\mathcal{O}(N)$

## Details
Content details.
"""
    typ = TypstRenderer.render(md, title="Academic Paper", authors=["Swarm"])
    assert "#set document(title: \"Academic Paper\"" in typ
    assert "= Introduction" in typ
    assert "== Details" in typ


def test_publication_pipeline(tmp_path):
    config = ProjectConfig(
        document_title="Pipeline Output",
        authors=["Alice", "Bob"],
        root_dir=tmp_path,
    )
    pipeline = PublicationPipeline(project_root=tmp_path, config=config)
    res = pipeline.build_all("# Chapter 1\nHello World.")
    assert res.success
    assert (tmp_path / "dist" / "index.html").exists()
    assert (tmp_path / "dist" / "document.typ").exists()
    assert (tmp_path / "dist" / "document.md").exists()
