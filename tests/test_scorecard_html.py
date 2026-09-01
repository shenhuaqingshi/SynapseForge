import pytest
from pathlib import Path
from synapseforge.core.scorecard import QualityScorecard


def test_scorecard_evaluate_and_html_generation(tmp_path):
    sec_dir = tmp_path / "sections"
    sec_dir.mkdir(parents=True)

    sec1 = sec_dir / "01_intro.md"
    sec1.write_text("""# Introduction

Distributed systems face fundamental limits under asynchronous network partitions.
We formulate the state machine replication problem following [@lamport1982].

$$
\\lim_{t \\to \\infty} P(\\text{Consensus}_t) = 1
$$

| Metric | Target | Baseline |
|---|---|---|
| Latency (ms) | 12.4 | 48.2 |
| Throughput (ops/sec) | 120,000 | 32,000 |
""", encoding="utf-8")

    scorecard = QualityScorecard(workspace_root=tmp_path)
    res = scorecard.evaluate_document()

    assert res["ok"] is True
    assert res["overall_score"] >= 80
    assert res["metrics"]["total_math_equations"] >= 1
    assert res["metrics"]["total_booktabs_tables"] == 1
    assert res["metrics"]["anti_ai_natural_flow_score"] == 100

    # Test HTML export
    html_file = tmp_path / "dist" / "quality_report.html"
    out_path = scorecard.generate_html_report(output_path=html_file)

    assert out_path.exists()
    html_text = out_path.read_text(encoding="utf-8")
    assert "<svg" in html_text
    assert "<polygon" in html_text
    assert "SynapseForge Document Quality Radar" in html_text
    assert "01_intro.md" in html_text
