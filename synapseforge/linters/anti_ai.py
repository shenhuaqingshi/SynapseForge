"""
Anti-AI Flavor and Narrative Analytical Prose Linter.
Detects robotic boilerplate, cliché transitional phrases, formulaic bullet-point addiction,
and vacuous buzzwords to enforce publication-grade human/agent writing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from synapseforge.core.ast_parser import BlockType, DocBlock, MarkdownASTParser


@dataclass
class LintIssue:
    linter_name: str
    severity: str  # "error" | "warning" | "info"
    line_start: int
    line_end: int
    message: str
    snippet: str
    suggested_fix: Optional[str] = None


@dataclass
class LintResult:
    linter_name: str
    passed: bool
    issues: List[LintIssue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


# Cliché openings, transitions, and conclusion fluff
BANNED_CLICHES_ZH = [
    (r"在当今(数字化|科技|信息|快速发展|日新月异)的时代", "严禁套路化开头。请直击核心命题、背景演进或实证数据。"),
    (r"随着[^\n，。]{2,20}的(快速发展|飞速进步|不断演进|日益普及)", "严禁套路化开头。开篇应直接展开技术机制或问题背景。"),
    (r"在本文中，?我们将(探讨|介绍|分析|研究)", "严禁自述式机械宣教，直接进入正文论述。"),
    (r"总而言之", "严禁机械总结词，依靠段落内部因果推进自然收束。"),
    (r"综上所述", "严禁机械总结词，使用具体论点与数据进行收敛。"),
    (r"值得注意的是", "严禁机械过渡词，请直接阐述该项关键机理或反常发现。"),
    (r"不可否认的是", "严禁假意辩证套话，请直接列出限制条件或定量对比。"),
    (r"不言而喻", "避免空泛断言，请给出实证或理论推导。"),
    (r"赋能[^\n，。]{2,15}(业务|发展|创新|升级)", "严禁空泛宣教词'赋能'，请说明具体的提效机理或技术指标。"),
    (r"全方位(矩阵|布局|覆盖)", "避免夸大宣传用语，请采用精准技术架构描述。"),
    (r"展现出巨大(的)?潜力与广阔(的)?前景", "严禁空洞套话，请用定量指标与收敛边界说话。"),
    (r"打造[^\n，。]{2,15}闭环", "避免商业黑话'闭环'，使用具体反馈机制/循环流程描述。"),
    (r"打法|抓手|底座|顶层设计", "避免空泛黑话，使用学术/工程规范术语。"),
]

BANNED_CLICHES_EN = [
    (r"\bIn today's (fast-paced|rapidly changing|digital|modern) (world|era|landscape)\b", "Ban formulaic cliché opener. Start with core technical mechanism or empirical premise."),
    (r"\bWith the rapid (advancement|development|growth|evolution) of\b", "Ban formulaic opening. Dive straight into technical architecture."),
    (r"\bIn this paper, we will (explore|discuss|delve into)\b", "Avoid self-referential introductory fluff; state thesis directly."),
    (r"\bIn conclusion\b", "Ban formulaic transition; close with mechanistic synthesis or empirical convergence."),
    (r"\bIt is worth noting that\b", "Ban formulaic transition; present finding directly with rationale."),
    (r"\bDelve (into|deeper)\b", "Avoid AI-cliché verb 'delve'; use analyze, dissect, or evaluate."),
    (r"\bTapestry\b", "Avoid AI-cliché metaphor 'tapestry'."),
    (r"\bBeacon of\b", "Avoid hyperbolic AI-cliché 'beacon'."),
    (r"\bGame-changer\b", "Avoid promotional hype; specify exact performance gains."),
    (r"\bLeverage the power of\b", "Avoid vague AI marketing fluff; specify operational mechanism."),
    (r"\bSeamlessly integrated\b", "Avoid unsubstantiated claims; specify integration latency or API protocol."),
]


class AntiAILinter:
    """Enforces zero AI flavor, continuous narrative analytical prose, and bans formulaic lists."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.ban_cliches = self.config.get("ban_cliches", True)
        self.ban_formulaic_lists = self.config.get("ban_formulaic_lists", True)
        self.require_narrative_prose = self.config.get("require_narrative_prose", True)
        self.max_buzzword_density = self.config.get("max_buzzword_density", 0.015)

    def lint_text(self, text: str, filename: str = "document.md") -> LintResult:
        issues: List[LintIssue] = []
        blocks = MarkdownASTParser.parse_blocks(text)
        lines = text.splitlines()

        # 1. Cliché and Buzzword Check
        if self.ban_cliches:
            for idx, line in enumerate(lines, 1):
                # Chinese Clichés
                for pattern, advice in BANNED_CLICHES_ZH:
                    for m in re.finditer(pattern, line):
                        issues.append(LintIssue(
                            linter_name="AntiAI:ClichéFluff",
                            severity="error",
                            line_start=idx,
                            line_end=idx,
                            message=f"检测到典型 AI 套话/机械过渡词: '{m.group(0)}'。{advice}",
                            snippet=line.strip(),
                            suggested_fix="重写为紧凑的专业散文论述，直击机理与实证数据。",
                        ))
                # English Clichés
                for pattern, advice in BANNED_CLICHES_EN:
                    for m in re.finditer(pattern, line, re.IGNORECASE):
                        issues.append(LintIssue(
                            linter_name="AntiAI:ClichéFluff",
                            severity="error",
                            line_start=idx,
                            line_end=idx,
                            message=f"Detected AI boilerplate phrase: '{m.group(0)}'. {advice}",
                            snippet=line.strip(),
                            suggested_fix="Reformulate into rigorous analytical prose.",
                        ))

        # 2. Formulaic List Abuse Check
        if self.ban_formulaic_lists:
            list_blocks = [b for b in blocks if b.type == BlockType.LIST]
            
            # Count list item lines
            list_item_lines = sum(len([l for l in b.content.splitlines() if l.strip()]) for b in list_blocks)
            total_content_lines = sum(len([l for l in b.content.splitlines() if l.strip()]) for b in blocks if b.type != BlockType.CODE_BLOCK)

            if list_item_lines >= 4 and (list_item_lines / max(total_content_lines, 1)) > 0.35:
                issues.append(LintIssue(
                    linter_name="AntiAI:FormulaicLists",
                    severity="error",
                    line_start=list_blocks[0].line_start if list_blocks else 1,
                    line_end=list_blocks[-1].line_end if list_blocks else 1,
                    message="检测到严重的机械分点狂热症 (List Addiction)。分点行数占比过高，破坏了学术长文的有机叙事连贯性。",
                    snippet="Consecutive list items detected across document.",
                    suggested_fix="将碎裂的流水账列表重构成行云流水的专业散文体（Narrative Prose）或学术级三线表（booktabs）。",
                ))

        # 3. Paragraph Narrative Flow & Breathability
        if self.require_narrative_prose:
            for b in blocks:
                if b.type == BlockType.PARAGRAPH:
                    words = b.word_count
                    if words < 25 and not b.content.strip().startswith("!"):  # exclude image captions
                        issues.append(LintIssue(
                            linter_name="AntiAI:ParagraphFragmentation",
                            severity="warning",
                            line_start=b.line_start,
                            line_end=b.line_end,
                            message=f"段落过短（{words} 字/词），叙事呈现碎裂化倾向。标准学术段落应包含完整的主旨句、机理阐述与逻辑衔接。",
                            snippet=b.content[:100] + "...",
                            suggested_fix="将碎片观点与相邻上下文合并，构建深度论证段落（推荐 150～300 字）。",
                        ))
                    elif words > 500:
                        issues.append(LintIssue(
                            linter_name="AntiAI:RunOnWallOfText",
                            severity="warning",
                            line_start=b.line_start,
                            line_end=b.line_end,
                            message=f"段落过长（{words} 字/词），形成冗长文本墙。请根据逻辑微观转折适度分段保持通透感。",
                            snippet=b.content[:100] + "...",
                            suggested_fix="按微观论点自然切分，单段保持在 200~350 字区间。",
                        ))

        return LintResult(
            linter_name="AntiAILinter",
            passed=(len([i for i in issues if i.severity == "error"]) == 0),
            issues=issues,
        )
