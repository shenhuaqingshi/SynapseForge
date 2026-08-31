import pytest
from pathlib import Path
from synapseforge.core.variant_synthesizer import MultiDocumentSynthesizer, VariantManager


def test_variant_manager_lifecycle(tmp_path):
    vm = VariantManager(workspace_root=tmp_path)
    
    # 1. Create variants
    res1 = vm.create_variant(
        variant_id="var_theory_a",
        name="Variant Theory A",
        target_section="sec_02",
        author="Agent-Math"
    )
    assert res1["ok"] is True
    assert res1["variant_id"] == "var_theory_a"

    res2 = vm.create_variant(
        variant_id="var_theory_b",
        name="Variant Theory B",
        target_section="sec_02",
        author="Agent-Empirical"
    )
    assert res2["ok"] is True

    # 2. List variants
    variants = vm.list_variants(target_section="sec_02")
    assert len(variants) == 2


def test_multi_document_synthesizer_merge(tmp_path):
    doc1 = tmp_path / "doc1.md"
    doc1.write_text("""# 2. 理论分析\n\n这是第一份文档的论述，给出了形式化证明 @lamport1982byzantine。\n""", encoding="utf-8")

    doc2 = tmp_path / "doc2.md"
    doc2.write_text("""# 2. 理论分析\n\n这是第二份文档的论述，补充了实验数据 @vaswani2017attention。\n""", encoding="utf-8")

    synthesizer = MultiDocumentSynthesizer(workspace_root=tmp_path)
    merged_output = tmp_path / "master_merged.md"

    res = synthesizer.merge_variants(
        variant_files=[doc1, doc2],
        output_file=merged_output,
        strategy="harmonize"
    )
    assert res["ok"] is True
    assert merged_output.exists()
    
    merged_content = merged_output.read_text(encoding="utf-8")
    assert "第一份文档" in merged_content
    assert "第二份文档" in merged_content
    assert "lamport1982byzantine" in res["citations_preserved"]
    assert "vaswani2017attention" in res["citations_preserved"]
