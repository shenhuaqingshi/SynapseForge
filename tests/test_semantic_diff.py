import pytest
from pathlib import Path
from synapseforge.core.semantic_diff import BlockDiff, ChangeType, SemanticASTDiffer


def test_semantic_diff_identical_texts():
    differ = SemanticASTDiffer()
    text = "# Introduction\n\nThis is a baseline paragraph.\n\n$$\nE = mc^2\n$$\n"
    res = differ.diff_texts(text, text, "Base", "Target")

    assert res.similarity_ratio == 1.0
    assert res.blocks_added == 0
    assert res.blocks_removed == 0
    assert res.blocks_modified == 0
    assert res.blocks_unchanged == 3
    assert res.net_word_change == 0
    assert len(res.citations_added) == 0
    assert len(res.citations_removed) == 0


def test_semantic_diff_block_add_and_remove():
    differ = SemanticASTDiffer()
    base = "# Section 1\n\nOriginal paragraph to be removed [@oldcite2020].\n"
    target = "# Section 1\n\nBrand new analytical argument [@newcite2026].\n\n| Param | Value |\n|---|---|\n| Latency | 12ms |\n"

    res = differ.diff_texts(base, target, "Base", "Target")

    assert res.blocks_removed >= 1 or res.blocks_modified >= 1
    assert "newcite2026" in res.citations_added or any("newcite2026" in b.citations_added for b in res.blocks)
    assert res.total_target_words > 0

    term = res.render_terminal(use_color=False)
    assert "Semantic AST Diff" in term
    assert "Base ➔ Target" in term


def test_semantic_diff_modified_block():
    differ = SemanticASTDiffer()
    base = "## Theory\n\nWe define system convergence over $N$ distributed nodes.\n"
    target = "## Theory\n\nWe define strict convergence over $2N$ distributed nodes with fault tolerance.\n"

    res = differ.diff_texts(base, target, "Theory V1", "Theory V2")

    d_dict = res.to_dict()
    assert d_dict["base_title"] == "Theory V1"
    assert d_dict["target_title"] == "Theory V2"
    assert "summary" in d_dict
    assert isinstance(d_dict["block_diffs"], list)


def test_semantic_diff_files(tmp_path):
    differ = SemanticASTDiffer()
    f1 = tmp_path / "doc1.md"
    f2 = tmp_path / "doc2.md"

    f1.write_text("# Chapter A\n\nFirst draft content.\n", encoding="utf-8")
    f2.write_text("# Chapter A\n\nRevised draft content with further theoretical rigor.\n", encoding="utf-8")

    res = differ.diff_files(f1, f2)
    assert res.base_title == "doc1.md"
    assert res.target_title == "doc2.md"
    assert res.total_target_words > res.total_base_words
