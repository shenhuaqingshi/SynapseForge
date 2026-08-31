"""
Document Quality Scorecard & Academic Rigor Radar for SynapseForge.
Computes quantitative Anti-AI scores, citation density, mathematical formality index,
and structural compliance metrics across all document sections.
"""

from __future__ import annotations

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
        section_files = sorted(sec_dir.glob("*.md"))

        total_words = 0
        total_citations = 0
        total_math_blocks = 0
        total_inline_math = 0
        total_tables = 0
        anti_ai_penalties = 0

        section_scores = []

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
            report = self.linter.lint_text(content, filename=str(p))
            cliches_count = len([i for i in report.all_issues if i.linter_name == "Anti-AI"])

            total_words += words
            total_citations += len(citations)
            total_math_blocks += math_blocks
            total_inline_math += inline_math
            total_tables += tables
            anti_ai_penalties += cliches_count

            section_scores.append({
                "section": p.stem,
                "words": words,
                "citations": len(citations),
                "math_equations": math_blocks + inline_math,
                "tables": tables,
                "anti_ai_clean": cliches_count == 0,
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

        # 4. Overall Publication Readiness Grade
        overall_score = round((anti_ai_score * 0.35 + citation_score * 0.35 + math_score * 0.30), 1)

        grade = "A+" if overall_score >= 90 else "A" if overall_score >= 80 else "B"

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
            },
            "sections_breakdown": section_scores,
        }
