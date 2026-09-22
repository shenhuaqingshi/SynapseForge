"""
Report Specification and Publication Standard Rules for SynapseForge.
Encapsulates zero AI flavor, narrative analytical prose, scientific plotting,
and publication-grade PDF typography.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ReportType(str, Enum):
    WHITEPAPER = "whitepaper"
    ACADEMIC_REVIEW = "academic_review"
    INDUSTRY_ANALYSIS = "industry_analysis"
    TECH_SURVEY = "tech_survey"
    EMPIRICAL_STUDY = "empirical_study"


class ReportStandard:
    """The gold-standard specification rules for publication-grade documents."""

    # Seven Banned AI Clichés (The 7 Major Prohibitions)
    SEVEN_PROHIBITIONS = [
        {
            "id": "cliche_opening",
            "name": "严禁套路化开头",
            "banned": ["在当今数字化时代", "随着人工智能的快速发展", "在本文中我们将探讨", "In today's fast-paced world", "With the rapid advancement of"],
            "patterns": [
                r"在当今[^\n，。]{0,15}(时代|浪潮|背景)",
                r"随着[^\n，。]{2,20}的(快速发展|飞速进步|不断演进|日益普及)",
                r"在本文中，?我们将(探讨|介绍|分析|研究)",
                r"\bIn today's (fast-paced|rapidly changing|digital|modern) (world|era|landscape)\b",
                r"\bWith the rapid (advancement|development|growth|evolution) of\b",
            ],
            "rule": "开篇必须直击核心命题、背景演进或实证数据，严禁宏观套话与自我介绍。",
        },
        {
            "id": "mechanical_transitions",
            "name": "严禁机械过渡词与流水账",
            "banned": ["首先、其次、再次、最后", "第一点是、第二点是", "一方面、另一方面", "值得注意的是", "不可否认的是", "It is worth noting that", "Firstly, secondly"],
            "patterns": [
                r"首先[^\n，。]{0,10}其次",
                r"值得注意的是",
                r"不可否认的是",
                r"不言而喻",
                r"\bIt is worth noting that\b",
                r"\bFirstly\b|\bSecondly\b",
            ],
            "rule": "依靠段落内部的因果逻辑与语意推进自然衔接，以矛盾揭示与机理推演组织行文。",
        },
        {
            "id": "cliche_conclusions",
            "name": "严禁机械套路结尾",
            "banned": ["总而言之", "综上所述", "展望未来充满挑战与机遇", "In conclusion", "To sum up"],
            "patterns": [
                r"总而言之",
                r"综上所述",
                r"充满挑战与机遇",
                r"\bIn conclusion\b",
                r"\bTo sum up\b",
            ],
            "rule": "结尾必须进行深层机理升华或前瞻性洞见，直接完成论证收敛，严禁套路式复述。",
        },
        {
            "id": "vacuous_buzzwords",
            "name": "严禁空泛口号与废话堆砌",
            "banned": ["赋能业务增长", "构建全方位矩阵", "展现出巨大潜力与广阔前景", "打造底座", "形成闭环", "Tapestry", "Beacon", "Leverage the power"],
            "patterns": [
                r"赋能[^\n，。]{2,15}(业务|发展|创新|升级|增长)",
                r"全方位(矩阵|布局|覆盖)",
                r"展现出巨大(的)?潜力与广阔(的)?前景",
                r"打造[^\n，。]{0,10}底座",
                r"形成[^\n，。]{0,10}闭环",
                r"\bTapestry\b",
                r"\bBeacon of\b",
                r"\bLeverage the power of\b",
            ],
            "rule": "必须用扎实数据、微观机理与定量对比说话，给出精确收敛边界与工程指标。",
        },
        {
            "id": "section_tail_summary",
            "name": "严禁章节末尾车轱辘总结",
            "banned": ["本节主要分析了", "为下节打下基础", "This section analyzed"],
            "patterns": [
                r"本节主要(分析|阐述|探讨)了",
                r"为(下一节|下文|后续章节)打下(了)?基础",
                r"\bThis section analyzed\b",
            ],
            "rule": "段末直接完成论证闭环，下一节通过内在逻辑关联自然开启，无需机械自述。",
        },
        {
            "id": "false_balance",
            "name": "严禁虚假平衡与端水废话",
            "banned": ["各有优劣，要根据实际情况决定", "Both have pros and cons"],
            "patterns": [
                r"各有(其)?优劣",
                r"根据实际情况(而定|决定)",
                r"\bBoth have pros and cons\b",
            ],
            "rule": "清晰剖析各方案在吞吐量、显存开销与工程复杂度上的权衡代价与适用临界点。",
        },
        {
            "id": "robot_self_reference",
            "name": "严禁机器人自说自话",
            "banned": ["作为您的 AI 助手", "我为您准备了以下报告", "As an AI assistant"],
            "patterns": [
                r"作为(您(的)?)?AI(助手)?",
                r"(我|本系统)为您(准备|生成)了",
                r"\bAs an AI assistant\b",
            ],
            "rule": "采用完全客观、权威的第三方专家/学术叙述视角。",
        },
    ]

    # Narrative Analytical Prose Rules
    PARAGRAPH_TRIAD_RULE = (
        "每个正文段落必须遵循「主旨句引领 (Topic Sentence) → 机理/数据/实证展开 (Elaboration & Evidence) "
        "→ 辩证推论与逻辑桥 (Synthesis & Bridge)」三位一体结构，单段推荐字数 150～300 字。"
    )

    # Booktabs Rules
    BOOKTABS_RULE = (
        "多维性能指标或方案对比严禁分点罗列，必须转化为学术出版级三线表 (Booktabs)，"
        "无竖线，粗顶线 (1.5pt)、粗底线 (1.5pt)、细表头线 (0.75pt)，并在正文中深度解读机理。"
    )

    # Scientific Plot Rules
    SCIENTIFIC_PLOT_RULES = (
        "所有数据图表必须遵循 Nature/Science 顶刊级规范：Panel 标识（a, b 8.5-10pt Bold）、"
        "物理量斜体、单位正体、300+ DPI PNG + 矢量 PDF/SVG、正文必须显式引用并深度解读，严禁孤儿图表。"
    )

    # Publication PDF Layout Rules
    PUBLICATION_PDF_LAYOUT_RULES = (
        "交付 PDF 时遵循官方高精楷体规范：Times New Roman 西文、各级标题全阶梯加黑加粗、"
        "正文仅重要字词句及核心数据加黑加粗（常规正文适度通透）、14~16px 出版级舒适字号、"
        "1.48 倍行距、中西文分治、首行缩进 2em、无竖线三线表。"
    )


@dataclass
class ReportQualityAudit:
    """Audit result for a document against report-spec standards."""
    anti_ai_score: float  # 0.0 to 100.0
    narrative_score: float  # 0.0 to 100.0
    structure_score: float  # 0.0 to 100.0
    total_score: float  # 0.0 to 100.0
    passed: bool
    violations: List[Dict[str, Any]] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


class ReportSpecification:
    """Evaluates and enforces Report Specification standards across documents."""

    @classmethod
    def audit_document(cls, text: str) -> ReportQualityAudit:
        violations: List[Dict[str, Any]] = []
        suggestions: List[str] = []
        lines = text.splitlines()

        # 1. Check AI Prohibitions via regex patterns
        for prohib in ReportStandard.SEVEN_PROHIBITIONS:
            for pattern_str in prohib.get("patterns", prohib["banned"]):
                try:
                    pattern = re.compile(pattern_str, re.IGNORECASE)
                except Exception:
                    pattern = re.compile(re.escape(pattern_str), re.IGNORECASE)
                for idx, line in enumerate(lines, 1):
                    m = pattern.search(line)
                    if m:
                        violations.append({
                            "type": prohib["id"],
                            "rule_name": prohib["name"],
                            "line": idx,
                            "match": m.group(0),
                            "snippet": line.strip()[:100],
                            "advice": prohib["rule"],
                        })

        # 2. Check Formulaic Bullet Points in narrative body
        # Count consecutive list items
        list_streak = 0
        max_streak = 0
        for idx, line in enumerate(lines, 1):
            if re.match(r"^\s*([*\-+]|\d+\.)\s+", line):
                list_streak += 1
                if list_streak > max_streak:
                    max_streak = list_streak
                if list_streak >= 5:
                    violations.append({
                        "type": "formulaic_bullet_points",
                        "rule_name": "彻底摒弃机械分点狂热症",
                        "line": idx,
                        "match": "长篇列表分点枚举",
                        "snippet": line.strip()[:100],
                        "advice": "正文论证必须采用行云流水的专业散文长文叙事；多维指标对比请提炼为学术三线表 (booktabs)。",
                    })
            else:
                list_streak = 0

        # 3. Check for Short / Fragmented Paragraphs
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip() and not p.strip().startswith("#")]
        short_paras = [p for p in paragraphs if 0 < len(p) < 40 and not p.startswith("|") and not p.startswith("```")]
        if len(short_paras) > 3:
            suggestions.append("检测到多处碎片化短段落，建议遵循「主旨句 → 实证展开 → 辩证逻辑桥」三位一体结构，单段扩充至 150～300 字。")

        # 4. Check for Booktabs Table syntax if tables exist
        has_tables = any("|" in line for line in lines)
        if has_tables:
            suggestions.append("文档包含对比表格：导出 PDF 时将自动应用 Publication-Grade Booktabs（无竖线三线表）排版。")

        # Compute Scores
        anti_ai_deductions = len([v for v in violations if v["type"] != "formulaic_bullet_points"]) * 12.0
        anti_ai_score = max(0.0, 100.0 - anti_ai_deductions)

        narrative_deductions = len([v for v in violations if v["type"] == "formulaic_bullet_points"]) * 15.0 + len(short_paras) * 2.0
        narrative_score = max(0.0, 100.0 - narrative_deductions)

        structure_score = 95.0 if has_tables else 90.0

        total_score = round(anti_ai_score * 0.45 + narrative_score * 0.35 + structure_score * 0.20, 1)
        passed = (total_score >= 85.0 and len(violations) == 0)

        return ReportQualityAudit(
            anti_ai_score=round(anti_ai_score, 1),
            narrative_score=round(narrative_score, 1),
            structure_score=round(structure_score, 1),
            total_score=total_score,
            passed=passed,
            violations=violations,
            suggestions=suggestions,
        )
