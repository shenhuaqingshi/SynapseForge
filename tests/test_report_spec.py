"""
Unit and Integration Tests for SynapseForge Report Specification (Report-Spec) Engine.
"""

import json
from pathlib import Path
import pytest

from synapseforge.report.spec import ReportSpecification, ReportStandard, ReportType
from synapseforge.report.generator import ReportGenerator
from synapseforge.report.prompts import REPORT_SPEC_PROMPTS
from synapseforge.core.user_prompts import UserPromptManager
from synapseforge.linters.anti_ai import AntiAILinter


def test_report_spec_seven_prohibitions_detection():
    # 1. Cliché Opening
    bad_doc_1 = "# 测试报告\n\n在当今数字化快速发展的时代，人工智能技术正在颠覆传统模式。\n\n这表明机制非常重要。"
    audit_1 = ReportSpecification.audit_document(bad_doc_1)
    assert audit_1.passed is False
    assert any(v["type"] == "cliche_opening" for v in audit_1.violations)

    # 2. Mechanical Transitions
    bad_doc_2 = "# 深度调研\n\n首先我们分析算力瓶颈。其次我们分析通信延迟。值得注意的是，这是关键指标。"
    audit_2 = ReportSpecification.audit_document(bad_doc_2)
    assert audit_2.passed is False
    assert any(v["type"] == "mechanical_transitions" for v in audit_2.violations)

    # 3. Vacuous Buzzwords
    bad_doc_3 = "# 架构设计\n\n我们将打造底座并赋能业务增长，构建全方位矩阵并形成闭环。"
    audit_3 = ReportSpecification.audit_document(bad_doc_3)
    assert audit_3.passed is False
    assert any(v["type"] == "vacuous_buzzwords" for v in audit_3.violations)

    # 4. Formulaic Bullet Point Addiction
    bad_doc_4 = "# 方案分析\n\n针对该问题有以下几点：\n- 性能瓶颈\n- 延迟过高\n- 内存占用过大\n- 通信抖动\n- 缺乏冗余备份\n- 调度不均\n"
    audit_4 = ReportSpecification.audit_document(bad_doc_4)
    assert any(v["type"] == "formulaic_bullet_points" for v in audit_4.violations)


def test_report_generator_template_generation_and_audit(tmp_path):
    gen = ReportGenerator(workspace_root=tmp_path)
    res = gen.generate_report_template(
        title="分布式认知智能体协同架构白皮书",
        topic="异步状态机与共识网络",
        report_type=ReportType.WHITEPAPER,
    )
    assert res["title"] == "分布式认知智能体协同架构白皮书"
    assert res["audit"]["passed"] is True
    assert res["audit"]["total_score"] >= 90.0
    assert "Booktabs" in res["content"]
    assert "|---|" in res["content"]  # Contains comparative table


def test_report_generator_pdf_compilation(tmp_path):
    gen = ReportGenerator(workspace_root=tmp_path)
    res_template = gen.generate_report_template(
        title="测试学术报告",
        topic="拜占庭容错与异步状态机",
        report_type=ReportType.ACADEMIC_REVIEW,
    )
    md_file = tmp_path / "academic_report.md"
    md_file.write_text(res_template["content"], encoding="utf-8")
    
    out_pdf = tmp_path / "academic_report.pdf"
    res = gen.compile_report_to_pdf(markdown_path=md_file, output_pdf=out_pdf, title="测试学术报告")
    
    assert res.get("ok") is True, f"PDF compilation failed: {res.get('error')}"
    assert out_pdf.exists()
    assert out_pdf.stat().st_size > 0
    assert res["audit_passed"] is True


def test_user_prompts_report_spec_auto_initialization(tmp_path):
    manager = UserPromptManager(workspace_root=tmp_path, auto_init_report_spec=True)
    prompts = manager.list_prompts()
    
    role_ids = [p["role_id"] for p in prompts]
    assert "architect" in role_ids
    assert "drafter" in role_ids
    assert "critic" in role_ids
    assert "harmonizer" in role_ids
    assert "visualizer" in role_ids
    
    drafter_prompt = manager.get_prompt("drafter")
    assert drafter_prompt is not None
    assert "彻底祛除 AI 味" in drafter_prompt
    assert "三位一体结构" in drafter_prompt


def test_report_spec_prompts_dictionary():
    assert "architect" in REPORT_SPEC_PROMPTS
    assert "drafter" in REPORT_SPEC_PROMPTS
    assert "critic" in REPORT_SPEC_PROMPTS
    assert "harmonizer" in REPORT_SPEC_PROMPTS
    assert "visualizer" in REPORT_SPEC_PROMPTS
    
    for role, data in REPORT_SPEC_PROMPTS.items():
        assert "display_name" in data
        assert "desc" in data
        assert "prompt" in data
        assert len(data["prompt"]) > 50
