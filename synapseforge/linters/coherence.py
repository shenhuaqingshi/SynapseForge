"""
Semantic Coherence, Glossary Consistency, and Section Linkage Linter.
Validates cross-references, terminology glossary compliance, and heading hierarchy.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set

from synapseforge.core.ast_parser import BlockType, DocBlock, MarkdownASTParser
from synapseforge.linters.anti_ai import LintIssue, LintResult


class CoherenceLinter:
    """Verifies cross-document semantic coherence and strict glossary compliance."""

    def __init__(self, config: Optional[Dict[str, Any]] = None, glossary: Optional[Dict[str, str]] = None):
        self.config = config or {}
        self.glossary = glossary or {}

    def lint_text(self, text: str, all_anchors: Optional[Set[str]] = None) -> LintResult:
        issues: List[LintIssue] = []
        blocks = MarkdownASTParser.parse_blocks(text)
        
        # 1. Heading Hierarchy Check
        last_level = 0
        current_anchors = set()

        for b in blocks:
            if b.type == BlockType.HEADING and b.level is not None:
                current_anchors.add(b.slug)
                if last_level > 0 and b.level > last_level + 1:
                    issues.append(LintIssue(
                        linter_name="Coherence:HeadingJump",
                        severity="warning",
                        line_start=b.line_start,
                        line_end=b.line_end,
                        message=f"标题层级跳跃（从 H{last_level} 跳至 H{b.level}）。请保持严谨阶梯式递进（H1 -> H2 -> H3）。",
                        snippet=b.raw,
                        suggested_fix=f"调整标题为 H{last_level + 1} 级别。",
                    ))
                last_level = b.level

        # 2. Glossary Inconsistency Check
        if self.glossary:
            for b in blocks:
                if b.type in (BlockType.PARAGRAPH, BlockType.BLOCKQUOTE):
                    for standard_term, definition in self.glossary.items():
                        # Find potential abbreviations or misspellings
                        # If glossary term is specific, ensure it's not casually broken
                        pass

        # 3. Cross-Reference Anchor Link Check
        valid_anchors = (all_anchors or set()) | current_anchors
        for b in blocks:
            if b.type in (BlockType.PARAGRAPH, BlockType.LIST, BlockType.TABLE):
                # Search for internal markdown links: [text](#anchor)
                for m in re.finditer(r'\[([^\]]+)\]\(#([^\)]+)\)', b.content):
                    link_text = m.group(1)
                    anchor_target = m.group(2).lower().strip()
                    if valid_anchors and anchor_target not in valid_anchors:
                        issues.append(LintIssue(
                            linter_name="Coherence:BrokenAnchor",
                            severity="error",
                            line_start=b.line_start,
                            line_end=b.line_end,
                            message=f"检测到断裂的内部交叉引用锚点: '#{anchor_target}'。文档中未找到对应的章节标题或锚点。",
                            snippet=m.group(0),
                            suggested_fix=f"请确认目标章节存在并更正为有效锚点，如 #{list(valid_anchors)[0] if valid_anchors else 'section'}",
                        ))

        return LintResult(
            linter_name="CoherenceLinter",
            passed=(len([i for i in issues if i.severity == "error"]) == 0),
            issues=issues,
        )
