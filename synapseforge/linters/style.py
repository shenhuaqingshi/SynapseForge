"""
Typography and Publication Style Linter.
Checks CJK-Latin spacing, academic booktabs table standards, and typographical correctness.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from synapseforge.core.ast_parser import BlockType, DocBlock, MarkdownASTParser
from synapseforge.linters.anti_ai import LintIssue, LintResult


class StyleLinter:
    """Enforces publication-grade typography, CJK-Latin spacing, and booktabs table structure."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.enforce_cjk_spacing = self.config.get("enforce_cjk_latin_spacing", True)
        self.enforce_booktabs_tables = self.config.get("enforce_booktabs_tables", True)

    def lint_text(self, text: str) -> LintResult:
        issues: List[LintIssue] = []
        blocks = MarkdownASTParser.parse_blocks(text)

        for b in blocks:
            # 1. CJK-Latin Spacing Check (Pangu Spacing)
            if self.enforce_cjk_spacing and b.type in (BlockType.PARAGRAPH, BlockType.HEADING, BlockType.BLOCKQUOTE):
                lines = b.content.splitlines()
                for idx, line in enumerate(lines, b.line_start):
                    # Mask code, inline math, html tags, and markdown links
                    masked_line = re.sub(r'`[^`\n]+`', lambda m: ' ' * len(m.group(0)), line)
                    masked_line = re.sub(r'\$[^\$\n]+\$', lambda m: ' ' * len(m.group(0)), masked_line)
                    masked_line = re.sub(r'<[^>\n]+>', lambda m: ' ' * len(m.group(0)), masked_line)
                    masked_line = re.sub(r'\[([^\]]+)\]\([^\)\n]+\)', r'\1', masked_line)

                    # Chinese immediately followed by English/Number without space
                    zh_to_en = re.finditer(r'([\u4e00-\u9fff])([a-zA-Z0-9])', masked_line)
                    for m in zh_to_en:
                        snippet_pos = m.start()
                        sub = line[max(0, snippet_pos - 10):min(len(line), snippet_pos + 10)]
                        if "@" in sub or "http" in sub or "](#" in sub:
                            continue
                        issues.append(LintIssue(
                            linter_name="Style:CJKLatinSpacing",
                            severity="warning",
                            line_start=idx,
                            line_end=idx,
                            message=f"中西文混排缺少空格间隙: '{m.group(1)}{m.group(2)}'。出版级排版要求中文字符与西文/数字之间保留半角空格。",
                            snippet=sub,
                            suggested_fix=f"{m.group(1)} {m.group(2)}",
                        ))
                    
                    # English/Number immediately followed by Chinese without space
                    en_to_zh = re.finditer(r'([a-zA-Z0-9])([\u4e00-\u9fff])', masked_line)
                    for m in en_to_zh:
                        snippet_pos = m.start()
                        sub = line[max(0, snippet_pos - 10):min(len(line), snippet_pos + 10)]
                        if "@" in sub or "http" in sub or "](#" in sub:
                            continue
                        issues.append(LintIssue(
                            linter_name="Style:CJKLatinSpacing",
                            severity="warning",
                            line_start=idx,
                            line_end=idx,
                            message=f"西文中文字符混排缺少空格: '{m.group(1)}{m.group(2)}'。出版级规范要求保留半角空格以确保视觉呼吸感。",
                            snippet=sub,
                            suggested_fix=f"{m.group(1)} {m.group(2)}",
                        ))

            # 2. Booktabs Table Standard Check
            if self.enforce_booktabs_tables and b.type == BlockType.TABLE:
                t_lines = [l.strip() for l in b.content.splitlines() if l.strip()]
                if len(t_lines) < 3:
                    issues.append(LintIssue(
                        linter_name="Style:MalformedTable",
                        severity="error",
                        line_start=b.line_start,
                        line_end=b.line_end,
                        message="表格结构不完整。学术出版三线表必须包含表头行、分隔行与数据行。",
                        snippet=b.content[:100],
                        suggested_fix="补充标准 Markdown 表头与分隔行 |---|---|",
                    ))
                else:
                    # Check delimiter line
                    delim = t_lines[1]
                    if not re.match(r'^\|?(\s*:?-+:?\s*\|?)+$', delim):
                        issues.append(LintIssue(
                            linter_name="Style:TableDelimiter",
                            severity="error",
                            line_start=b.line_start + 1,
                            line_end=b.line_start + 1,
                            message="表格第二行非有效分隔符。请使用标准 `|---|---|` 格式。",
                            snippet=delim,
                            suggested_fix="|---|---|",
                        ))

        return LintResult(
            linter_name="StyleLinter",
            passed=(len([i for i in issues if i.severity == "error"]) == 0),
            issues=issues,
        )
