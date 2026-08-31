import pytest
from pathlib import Path
from synapseforge.core.exporter import MultiFormatExporter
from synapseforge.core.scorecard import QualityScorecard
from synapseforge.core.notifier import NotificationDispatcher


def test_quality_scorecard_metrics(tmp_path):
    sec_dir = tmp_path / "sections"
    sec_dir.mkdir(parents=True, exist_ok=True)
    sec_file = sec_dir / "01_test.md"
    sec_file.write_text("""
# 1. 引言

本文推导了形式化理论 @lamport1982byzantine，收敛界如下：

$$
\\mathbb{E}[\\tau] \\le \\frac{1}{\\mu - \\lambda}
$$

| 节点 | 时延 |
|---|---|
| A | 12ms |
""", encoding="utf-8")

    scorecard = QualityScorecard(workspace_root=tmp_path)
    res = scorecard.evaluate_document()
    assert res["ok"] is True
    assert res["overall_score"] > 70
    assert "publication_grade" in res
    assert res["metrics"]["total_words"] > 0
    assert res["metrics"]["total_citations"] == 1
    assert res["metrics"]["total_math_equations"] >= 1


def test_notification_dispatcher_fallback(tmp_path):
    dispatcher = NotificationDispatcher(user_email="test@example.com")
    res = dispatcher.send_notification(
        title="Milestone Complete",
        message="Section 4 has been drafted and audited.",
        channel="cli"
    )
    assert res["ok"] is True
    assert res["title"] == "Milestone Complete"


def test_multiformat_exporter_assemble(tmp_path):
    sec_dir = tmp_path / "sections"
    sec_dir.mkdir(parents=True, exist_ok=True)
    (sec_dir / "01_intro.md").write_text("# 1. Introduction\n\nContent 1", encoding="utf-8")
    (sec_dir / "02_theory.md").write_text("# 2. Theory\n\nContent 2", encoding="utf-8")

    exporter = MultiFormatExporter(workspace_root=tmp_path)
    full_doc = exporter.assemble_full_document()
    assert "Introduction" in full_doc
    assert "Theory" in full_doc
