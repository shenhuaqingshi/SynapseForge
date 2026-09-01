"""
Academic Citation and BibTeX Integrity Linter.
Validates @citation keys in Markdown against verified bibliography databases (.bib).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from synapseforge.core.ast_parser import BlockType, MarkdownASTParser
from synapseforge.linters.anti_ai import LintIssue, LintResult


class CitationLinter:
    """Verifies that all academic citation keys referenced in text are present in the BibTeX library."""

    def __init__(self, bib_path: Optional[Path | str] = None, config: Optional[Dict[str, Any]] = None):
        self.bib_path = Path(bib_path) if bib_path else None
        self.config = config or {}
        self.bib_keys: Set[str] = self._load_bib_keys() if self.bib_path and self.bib_path.exists() else set()

    def _load_bib_keys(self) -> Set[str]:
        if not self.bib_path or not self.bib_path.exists():
            return set()
        text = self.bib_path.read_text(encoding="utf-8")
        # Match @type{cite_key,
        matches = re.findall(r'@\w+\s*\{\s*([a-zA-Z0-9_:\-]+)\s*,', text)
        return set(matches)

    def lint_text(self, text: str, extra_bib_keys: Optional[Set[str]] = None) -> LintResult:
        issues: List[LintIssue] = []
        known_keys = self.bib_keys | (extra_bib_keys or set())
        
        blocks = MarkdownASTParser.parse_blocks(text)

        if self.bib_path and self.bib_path.exists() and len(known_keys) > 0:
            for b in blocks:
                if b.type in (BlockType.CODE_BLOCK, BlockType.FRONTMATTER):
                    continue
                # Strip inline code and comments from content before checking citations
                clean_content = re.sub(r'`[^`\n]+`', '', b.content)
                clean_content = re.sub(r'<!--[\s\S]*?-->', '', clean_content)
                
                # Find all @key matches with word boundaries
                for m in re.finditer(r'(?<![\w.@])@([a-zA-Z0-9_:\-]+)', clean_content):
                    key = m.group(1)
                    # Ignore programming decorators or directives
                    if key.lower() in ("import", "export", "param", "return", "returns", "note", "see", "example", "type", "raises"):
                        continue
                    if key not in known_keys:
                        issues.append(LintIssue(
                            linter_name="Citation:MissingBibEntry",
                            severity="error",
                            line_start=b.line_start,
                            line_end=b.line_end,
                            message=f"引用键 '@{key}' 在参考文献库 ({self.bib_path.name}) 中未找到定义。",
                            snippet=m.group(0),
                            suggested_fix=f"请在 {self.bib_path.name} 中补充 @article 或 @misc 条目，或修正引用键拼写。",
                        ))

        return LintResult(
            linter_name="CitationLinter",
            passed=(len([i for i in issues if i.severity == "error"]) == 0),
            issues=issues,
        )
