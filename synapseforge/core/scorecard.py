"""
Document Quality Scorecard & Academic Rigor Radar for SynapseForge.
Computes quantitative Anti-AI scores, citation density, mathematical formality index,
and structural compliance metrics across all document sections, with visual HTML report export.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from synapseforge.core.ast_parser import BlockType, MarkdownASTParser
from synapseforge.linters import LintSuite


class QualityScorecard:
    """Evaluates document rigor and produces academic radar scorecard metrics."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or Path.cwd()
        self.parser = MarkdownASTParser()
        self.linter = LintSuite()

    def evaluate_document(self) -> Dict[str, Any]:
        """Evaluates all sections and outputs quantitative scorecard."""
        sec_dir = self.workspace_root / "sections"
        section_files = sorted(sec_dir.glob("*.md")) if sec_dir.exists() else []

        total_words = 0
        total_citations = 0
        total_math_blocks = 0
        total_inline_math = 0
        total_tables = 0
        anti_ai_penalties = 0

        section_scores = []
        all_issues = []

        for p in section_files:
            content = p.read_text(encoding="utf-8")
            words = self.parser.count_words(content)
            blocks = self.parser.parse_blocks(content)
            citations = self.parser.extract_citations(content)

            # Count math
            math_blocks = len([b for b in blocks if b.type == BlockType.MATH_BLOCK])
            inline_math = len(re.findall(r'\$[^$\n]+\$', content))
            tables = len([b for b in blocks if b.type == BlockType.TABLE])

            # Lint issues
            report = self.linter.lint_text(content, filename=str(p.name))
            cliches_count = len([i for i in report.all_issues if i.linter_name == "Anti-AI"])

            for iss in report.all_issues:
                all_issues.append({
                    "file": p.name,
                    "linter": iss.linter_name,
                    "severity": iss.severity.value if hasattr(iss.severity, "value") else str(iss.severity),
                    "line": getattr(iss, "line_start", getattr(iss, "line", 1)),
                    "message": iss.message,
                })

            total_words += words
            total_citations += len(citations)
            total_math_blocks += math_blocks
            total_inline_math += inline_math
            total_tables += tables
            anti_ai_penalties += cliches_count

            section_scores.append({
                "section": p.stem,
                "file": p.name,
                "words": words,
                "citations": len(citations),
                "math_equations": math_blocks + inline_math,
                "tables": tables,
                "anti_ai_clean": cliches_count == 0,
                "issues_count": len(report.all_issues),
            })

        # Calculate Academic Radar Scores (0 - 100)
        # 1. Anti-AI Natural Flow Index (100 - penalties)
        anti_ai_score = max(60, min(100, 100 - (anti_ai_penalties * 5)))

        # 2. Citation Density (per 1,000 words, optimal ~ 5-10)
        cite_density = (total_citations / max(1, total_words)) * 1000
        citation_score = min(100, int(cite_density * 12)) if total_citations > 0 else 70

        # 3. Mathematical Formality Index
        math_count = total_math_blocks + total_inline_math
        math_score = min(100, max(50, 60 + math_count * 4))

        # 4. Structural Coherence (Tables and block distribution)
        structure_score = min(100, max(60, 70 + total_tables * 10))

        # 5. Overall Publication Readiness Grade
        overall_score = round((anti_ai_score * 0.35 + citation_score * 0.30 + math_score * 0.20 + structure_score * 0.15), 1)

        grade = "A+" if overall_score >= 90 else "A" if overall_score >= 80 else "B" if overall_score >= 70 else "C"

        return {
            "ok": True,
            "overall_score": overall_score,
            "publication_grade": grade,
            "metrics": {
                "total_words": total_words,
                "total_citations": total_citations,
                "citation_density_per_k_words": round(cite_density, 2),
                "total_math_equations": math_count,
                "total_booktabs_tables": total_tables,
                "anti_ai_natural_flow_score": anti_ai_score,
                "citation_richness_score": citation_score,
                "mathematical_rigor_score": math_score,
                "structural_coherence_score": structure_score,
            },
            "sections_breakdown": section_scores,
            "issues": all_issues,
        }

    def generate_html_report(self, output_path: Optional[Path | str] = None) -> Path:
        """Generates a standalone dark-themed HTML quality audit report with SVG radar chart."""
        data = self.evaluate_document()
        metrics = data["metrics"]
        score = data["overall_score"]
        grade = data["publication_grade"]

        out_p = Path(output_path) if output_path else self.workspace_root / "dist" / "quality_audit_report.html"
        out_p.parent.mkdir(parents=True, exist_ok=True)

        # Generate SVG radar polygon coordinates
        # Center: 150, 150, Radius: 100
        cx, cy, r = 150, 150, 100
        axes = [
            ("Anti-AI Flow", metrics["anti_ai_natural_flow_score"]),
            ("Citations", metrics["citation_richness_score"]),
            ("Math Rigor", metrics["mathematical_rigor_score"]),
            ("Structure", metrics["structural_coherence_score"]),
        ]
        
        polygon_pts = []
        grid_circles = []
        for level in [0.25, 0.5, 0.75, 1.0]:
            grid_circles.append(f'<circle cx="{cx}" cy="{cy}" r="{r * level}" fill="none" stroke="#2a2e39" stroke-dasharray="2,2"/>')

        axis_lines = []
        axis_labels = []
        num_axes = len(axes)
        for i, (label, val) in enumerate(axes):
            angle = (2 * math.pi / num_axes) * i - (math.pi / 2)
            # Outer line
            lx = cx + r * math.cos(angle)
            ly = cy + r * math.sin(angle)
            axis_lines.append(f'<line x1="{cx}" y1="{cy}" x2="{lx}" y2="{ly}" stroke="#333842"/>')
            
            # Label
            lbl_x = cx + (r + 20) * math.cos(angle)
            lbl_y = cy + (r + 20) * math.sin(angle) + 4
            axis_labels.append(f'<text x="{lbl_x}" y="{lbl_y}" text-anchor="middle" font-size="11" fill="#8b949e">{label}</text>')

            # Value point
            val_ratio = min(1.0, max(0.0, val / 100.0))
            px = cx + (r * val_ratio) * math.cos(angle)
            py = cy + (r * val_ratio) * math.sin(angle)
            polygon_pts.append(f"{px:.1f},{py:.1f}")

        polygon_str = " ".join(polygon_pts)

        # Build sections table HTML
        sec_rows = []
        for s in data["sections_breakdown"]:
            clean_badge = '<span class="badge green">Pass</span>' if s["anti_ai_clean"] else '<span class="badge red">Warning</span>'
            sec_rows.append(f"""
            <tr>
              <td><strong>{s['file']}</strong></td>
              <td>{s['words']:,}</td>
              <td>{s['citations']}</td>
              <td>{s['math_equations']}</td>
              <td>{s['tables']}</td>
              <td>{clean_badge}</td>
            </tr>
            """)

        # Build issues list HTML
        issues_html = []
        if not data["issues"]:
            issues_html.append('<div class="empty-state">🎉 All automated quality and anti-AI gates passed with zero violations!</div>')
        else:
            for iss in data["issues"]:
                sev_cls = "red" if iss["severity"] == "error" else "yellow"
                issues_html.append(f"""
                <div class="issue-item">
                  <span class="badge {sev_cls}">{iss['severity'].upper()}</span>
                  <span class="issue-file">{iss['file']}:{iss['line']}</span>
                  <span class="issue-linter">[{iss['linter']}]</span>
                  <span class="issue-msg">{iss['message']}</span>
                </div>
                """)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>SynapseForge Quality Audit Scorecard</title>
  <style>
    :root {{
      --bg: #0d1117;
      --card-bg: #161b22;
      --border: #30363d;
      --text: #c9d1d9;
      --text-muted: #8b949e;
      --accent: #58a6ff;
      --green: #238636;
      --yellow: #d29922;
      --red: #da3633;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      padding: 32px;
      line-height: 1.6;
    }}
    .container {{ max-width: 1000px; margin: 0 auto; }}
    header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 20px; margin-bottom: 28px; }}
    h1 {{ font-size: 24px; font-weight: 600; color: #f0f6fc; display: flex; align-items: center; gap: 8px; }}
    .badge {{ display: inline-block; padding: 2px 8px; font-size: 11px; font-weight: 600; border-radius: 12px; }}
    .badge.green {{ background: #23863622; color: #3fb950; border: 1px solid #23863666; }}
    .badge.yellow {{ background: #d2992222; color: #e3b341; border: 1px solid #d2992266; }}
    .badge.red {{ background: #da363322; color: #f85149; border: 1px solid #da363366; }}
    .grid {{ display: grid; grid-template-columns: 320px 1fr; gap: 24px; margin-bottom: 28px; }}
    .card {{ background: var(--card-bg); border: 1px solid var(--border); border-radius: 8px; padding: 20px; }}
    .score-banner {{ text-align: center; margin-bottom: 16px; }}
    .score-val {{ font-size: 48px; font-weight: 700; color: var(--accent); }}
    .score-grade {{ font-size: 20px; font-weight: 600; color: #f0f6fc; margin-left: 8px; }}
    .metrics-list {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }}
    .metric-card {{ background: #0d1117; border: 1px solid var(--border); border-radius: 6px; padding: 12px; }}
    .metric-title {{ font-size: 12px; color: var(--text-muted); }}
    .metric-val {{ font-size: 20px; font-weight: 600; color: #f0f6fc; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid var(--border); font-size: 13px; }}
    th {{ color: var(--text-muted); font-weight: 600; background: #0d1117; }}
    .issue-item {{ display: flex; align-items: center; gap: 12px; padding: 8px 12px; background: #0d1117; border: 1px solid var(--border); border-radius: 6px; margin-bottom: 8px; font-size: 13px; }}
    .issue-file {{ color: var(--accent); font-family: monospace; }}
    .issue-linter {{ color: var(--text-muted); }}
    .issue-msg {{ color: #f0f6fc; }}
    .empty-state {{ padding: 24px; text-align: center; color: #3fb950; background: #23863611; border: 1px solid #23863644; border-radius: 6px; }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>⚡ SynapseForge Document Quality Radar</h1>
      <div><span class="badge green">Report-Spec Standard</span></div>
    </header>

    <div class="grid">
      <div class="card">
        <div class="score-banner">
          <div class="score-val">{score}<span class="score-grade">[{grade}]</span></div>
          <div style="font-size: 12px; color: var(--text-muted)">Publication Readiness Score</div>
        </div>
        <div style="text-align: center;">
          <svg width="300" height="300" viewBox="0 0 300 300">
            {''.join(grid_circles)}
            {''.join(axis_lines)}
            <polygon points="{polygon_str}" fill="#58a6ff33" stroke="#58a6ff" stroke-width="2"/>
            {''.join(axis_labels)}
          </svg>
        </div>
      </div>

      <div class="card">
        <h2 style="font-size: 16px; margin-bottom: 16px; color: #f0f6fc;">Quantitative Rigor Metrics</h2>
        <div class="metrics-list">
          <div class="metric-card">
            <div class="metric-title">Total Words</div>
            <div class="metric-val">{metrics['total_words']:,}</div>
          </div>
          <div class="metric-card">
            <div class="metric-title">Total Citations</div>
            <div class="metric-val">{metrics['total_citations']}</div>
          </div>
          <div class="metric-card">
            <div class="metric-title">Citation Density (per 1k)</div>
            <div class="metric-val">{metrics['citation_density_per_k_words']}</div>
          </div>
          <div class="metric-card">
            <div class="metric-title">Math Equations</div>
            <div class="metric-val">{metrics['total_math_equations']}</div>
          </div>
          <div class="metric-card">
            <div class="metric-title">Anti-AI Natural Flow</div>
            <div class="metric-val">{metrics['anti_ai_natural_flow_score']} / 100</div>
          </div>
          <div class="metric-card">
            <div class="metric-title">Booktabs Tables</div>
            <div class="metric-val">{metrics['total_booktabs_tables']}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="card" style="margin-bottom: 24px;">
      <h2 style="font-size: 16px; color: #f0f6fc; margin-bottom: 8px;">Sections Audit Breakdown</h2>
      <table>
        <thead>
          <tr>
            <th>Section File</th>
            <th>Word Count</th>
            <th>Citations</th>
            <th>Math Blocks</th>
            <th>Tables</th>
            <th>Anti-AI Gate</th>
          </tr>
        </thead>
        <tbody>
          {''.join(sec_rows)}
        </tbody>
      </table>
    </div>

    <div class="card">
      <h2 style="font-size: 16px; color: #f0f6fc; margin-bottom: 12px;">Quality Gate Findings</h2>
      {''.join(issues_html)}
    </div>
  </div>
</body>
</html>
"""
        out_p.write_text(html_content, encoding="utf-8")
        return out_p
