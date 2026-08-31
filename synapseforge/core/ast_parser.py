"""
Markdown AST Parser and Structural Chunker for Collaborative Document Processing.
Provides section-aware and block-level decomposition of Markdown documents.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class BlockType(str, Enum):
    FRONTMATTER = "frontmatter"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    CODE_BLOCK = "code_block"
    BLOCKQUOTE = "blockquote"
    MATH_BLOCK = "math_block"
    LIST = "list"
    THEMATIC_BREAK = "thematic_break"
    RAW = "raw"


@dataclass
class DocBlock:
    type: BlockType
    content: str
    raw: str
    line_start: int
    line_end: int
    level: Optional[int] = None  # for headings (1..6)
    title: Optional[str] = None  # for headings
    slug: Optional[str] = None   # for headings
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def word_count(self) -> int:
        if self.type in (BlockType.CODE_BLOCK, BlockType.FRONTMATTER):
            return 0
        # Count words (CJK characters + Western words)
        cjk_chars = len(re.findall(r'[\u4e00-\u9fff]', self.content))
        latin_words = len(re.findall(r'[a-zA-Z0-9_\-]+', self.content))
        return cjk_chars + latin_words


@dataclass
class DocSection:
    heading_block: Optional[DocBlock]
    blocks: List[DocBlock] = field(default_factory=list)
    subsections: List[DocSection] = field(default_factory=list)

    @property
    def title(self) -> str:
        return self.heading_block.title if self.heading_block else "Preamble"

    @property
    def level(self) -> int:
        return self.heading_block.level if self.heading_block else 0

    @property
    def slug(self) -> str:
        return self.heading_block.slug if self.heading_block else "preamble"

    @property
    def full_content(self) -> str:
        res = []
        if self.heading_block:
            res.append(self.heading_block.raw)
        for b in self.blocks:
            res.append(b.raw)
        for s in self.subsections:
            res.append(s.full_content)
        return "\n\n".join([x for x in res if x.strip()])

    @property
    def total_words(self) -> int:
        w = sum(b.word_count for b in self.blocks)
        w += sum(s.total_words for s in self.subsections)
        return w


def slugify(text: str) -> str:
    s = text.lower().strip()
    s = re.sub(r'[^\w\s\u4e00-\u9fff-]', '', s)
    s = re.sub(r'[\s_-]+', '-', s)
    return s.strip('-') or 'section'


def is_markdown_table_row(line: str) -> bool:
    s = line.strip()
    if not s or s.startswith("$$") or s.startswith(">"):
        return False
    return bool(re.match(r'^\|.*\|\s*$', s)) or (s.startswith("|") and s.count("|") >= 2)


class MarkdownASTParser:
    """Parses a Markdown string or file into structured AST blocks and hierarchical sections."""

    @staticmethod
    def count_words(text: str) -> int:
        if not text:
            return 0
        cjk_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        latin_words = len(re.findall(r'[a-zA-Z0-9_\-]+', text))
        return cjk_chars + latin_words

    @staticmethod
    def parse_blocks(text: str) -> List[DocBlock]:
        lines = text.splitlines()
        blocks: List[DocBlock] = []
        i = 0
        n = len(lines)

        # 1. Frontmatter check
        if n > 0 and lines[0].strip() == "---":
            end_fm = -1
            for j in range(1, n):
                if lines[j].strip() == "---":
                    end_fm = j
                    break
            if end_fm != -1:
                fm_raw = "\n".join(lines[0:end_fm + 1])
                fm_content = "\n".join(lines[1:end_fm])
                blocks.append(DocBlock(
                    type=BlockType.FRONTMATTER,
                    content=fm_content,
                    raw=fm_raw,
                    line_start=1,
                    line_end=end_fm + 1,
                ))
                i = end_fm + 1

        while i < n:
            line = lines[i]
            stripped = line.strip()

            if not stripped:
                i += 1
                continue

            # 2. Heading
            heading_match = re.match(r'^(#{1,6})\s+(.*)$', line)
            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                slug = slugify(title)
                blocks.append(DocBlock(
                    type=BlockType.HEADING,
                    content=title,
                    raw=line,
                    line_start=i + 1,
                    line_end=i + 1,
                    level=level,
                    title=title,
                    slug=slug,
                ))
                i += 1
                continue

            # 3. Code block
            if stripped.startswith("```") or stripped.startswith("~~~"):
                fence = stripped[:3]
                lang = stripped[3:].strip()
                code_lines = [line]
                start_line = i + 1
                i += 1
                while i < n and not lines[i].strip().startswith(fence):
                    code_lines.append(lines[i])
                    i += 1
                if i < n:
                    code_lines.append(lines[i])
                    i += 1
                raw_code = "\n".join(code_lines)
                blocks.append(DocBlock(
                    type=BlockType.CODE_BLOCK,
                    content="\n".join(code_lines[1:-1] if len(code_lines) > 2 else []),
                    raw=raw_code,
                    line_start=start_line,
                    line_end=i,
                    metadata={"lang": lang},
                ))
                continue

            # 4. Math block ($$...$$)
            if stripped.startswith("$$"):
                math_lines = [line]
                start_line = i + 1
                i += 1
                if not (stripped.endswith("$$") and len(stripped) > 2):
                    while i < n and not lines[i].strip().endswith("$$"):
                        math_lines.append(lines[i])
                        i += 1
                    if i < n:
                        math_lines.append(lines[i])
                        i += 1
                raw_math = "\n".join(math_lines)
                blocks.append(DocBlock(
                    type=BlockType.MATH_BLOCK,
                    content=raw_math.strip("$").strip(),
                    raw=raw_math,
                    line_start=start_line,
                    line_end=i,
                ))
                continue

            # 5. Table (pipe markdown table)
            if is_markdown_table_row(line):
                table_lines = [line]
                start_line = i + 1
                i += 1
                while i < n and is_markdown_table_row(lines[i]):
                    table_lines.append(lines[i])
                    i += 1
                raw_table = "\n".join(table_lines)
                blocks.append(DocBlock(
                    type=BlockType.TABLE,
                    content=raw_table,
                    raw=raw_table,
                    line_start=start_line,
                    line_end=i,
                ))
                continue

            # 6. Blockquote
            if stripped.startswith(">"):
                quote_lines = [line]
                start_line = i + 1
                i += 1
                while i < n and (lines[i].strip().startswith(">") or (lines[i].strip() and not lines[i].startswith("#"))):
                    if not lines[i].strip():
                        break
                    quote_lines.append(lines[i])
                    i += 1
                raw_quote = "\n".join(quote_lines)
                blocks.append(DocBlock(
                    type=BlockType.BLOCKQUOTE,
                    content="\n".join(l.lstrip("> ").strip() for l in quote_lines),
                    raw=raw_quote,
                    line_start=start_line,
                    line_end=i,
                ))
                continue

            # 7. List item
            if re.match(r'^(\*|-|\+|\d+\.)\s+', stripped):
                list_lines = [line]
                start_line = i + 1
                i += 1
                while i < n:
                    if not lines[i].strip():
                        break
                    if re.match(r'^(#{1,6})\s+', lines[i]):
                        break
                    list_lines.append(lines[i])
                    i += 1
                raw_list = "\n".join(list_lines)
                blocks.append(DocBlock(
                    type=BlockType.LIST,
                    content=raw_list,
                    raw=raw_list,
                    line_start=start_line,
                    line_end=i,
                ))
                continue

            # 8. Regular paragraph
            p_lines = [line]
            start_line = i + 1
            i += 1
            while i < n:
                curr = lines[i]
                c_strip = curr.strip()
                if not c_strip:
                    break
                if (
                    re.match(r'^(#{1,6})\s+', curr)
                    or c_strip.startswith("```")
                    or c_strip.startswith("$$")
                    or is_markdown_table_row(curr)
                    or c_strip.startswith(">")
                    or re.match(r'^(\*|-|\+|\d+\.)\s+', c_strip)
                ):
                    break
                p_lines.append(curr)
                i += 1
            raw_p = "\n".join(p_lines)
            blocks.append(DocBlock(
                type=BlockType.PARAGRAPH,
                content=raw_p,
                raw=raw_p,
                line_start=start_line,
                line_end=i,
            ))

        return blocks

    @staticmethod
    def parse_sections(text: str) -> List[DocSection]:
        """Hierarchically groups parsed blocks into document sections based on H1-H6 headers."""
        blocks = MarkdownASTParser.parse_blocks(text)
        sections: List[DocSection] = []
        curr_section: Optional[DocSection] = None

        for b in blocks:
            if b.type == BlockType.HEADING:
                if curr_section is not None:
                    sections.append(curr_section)
                curr_section = DocSection(heading_block=b, blocks=[])
            else:
                if curr_section is None:
                    curr_section = DocSection(heading_block=None, blocks=[])
                curr_section.blocks.append(b)

        if curr_section is not None:
            sections.append(curr_section)

        return sections

    @staticmethod
    def extract_citations(text: str) -> List[str]:
        """Extract citation keys in @citationKey or [^citationKey] formats."""
        keys = set()
        for match in re.finditer(r'@([a-zA-Z0-9_:\-]+)', text):
            keys.add(match.group(1))
        for match in re.finditer(r'\[\^([a-zA-Z0-9_:\-]+)\]', text):
            keys.add(match.group(1))
        return sorted(list(keys))
