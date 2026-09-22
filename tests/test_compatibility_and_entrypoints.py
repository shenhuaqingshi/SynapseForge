import ast
import glob
import subprocess
import sys
from pathlib import Path
from synapseforge.core.variant_synthesizer import MultiDocumentSynthesizer


def test_all_python_files_are_valid_ast():
    root = Path(__file__).parent.parent
    py_files = list(root.glob("synapseforge/**/*.py")) + list(root.glob("tests/**/*.py"))
    assert len(py_files) > 20
    for py_file in py_files:
        content = py_file.read_text(encoding="utf-8")
        parsed = ast.parse(content, filename=str(py_file))
        assert parsed is not None


def test_module_main_entrypoint_execution():
    root = Path(__file__).parent.parent
    res1 = subprocess.run(
        [sys.executable, "-m", "synapseforge", "--version"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert res1.returncode == 0
    assert "synapseforge" in res1.stdout or "0.1.0" in res1.stdout

    res2 = subprocess.run(
        [sys.executable, "-m", "synapseforge.cli", "--version"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    assert res2.returncode == 0


def test_variant_synthesizer_ast_union_and_deduplication(tmp_path):
    v1 = tmp_path / "v1.md"
    v2 = tmp_path / "v2.md"
    out = tmp_path / "merged.md"

    v1.write_text("# Chapter 1\n\nInitial paragraph on swarm consensus [@lamport1982].\n", encoding="utf-8")
    v2.write_text("# Chapter 1\n\nInitial paragraph on swarm consensus [@lamport1982].\n\nNovel theorem block.\n", encoding="utf-8")

    synthesizer = MultiDocumentSynthesizer(workspace_root=tmp_path)
    res = synthesizer.merge_variants([v1, v2], output_file=out, strategy="ast_union")

    assert res["ok"] is True
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert content.count("# Chapter 1") == 1
    assert "Initial paragraph on swarm consensus [@lamport1982]." in content
    assert "Novel theorem block." in content
    assert "lamport1982" in res["citations_preserved"]
