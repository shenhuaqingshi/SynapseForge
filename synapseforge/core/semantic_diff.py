"""
Semantic AST Differ for Markdown and Typst documents in SynapseForge.
Compares documents at the structural block level (headings, paragraphs, equations, tables, code blocks)
and provides detailed change analysis, word count deltas, citation changes, and terminal/JSON rendering.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from synapseforge.core.ast_parser import BlockType, DocBlock, MarkdownASTParser


class ChangeType(str, Enum):
    UNCHANGED = "unchanged"
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"


@dataclass
class BlockDiff:
    change_type: ChangeType
    block_type: BlockType
    base_block: Optional[DocBlock] = None
    target_block: Optional[DocBlock] = None
    similarity: float = 1.0
    word_delta: int = 0
    citations_added: List[str] = field(default_factory=list)
    citations_removed: List[str] = field(default_factory=list)
    line_diff: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "change_type": self.change_type.value,
            "block_type": self.block_type.value,
            "similarity": round(self.similarity, 3),
            "word_delta": self.word_delta,
            "base_lines": [self.base_block.line_start, self.base_block.line_end] if self.base_block else None,
            "target_lines": [self.target_block.line_start, self.target_block.line_end] if self.target_block else None,
            "base_preview": (self.base_block.content[:100] + "...") if self.base_block and len(self.base_block.content) > 100 else (self.base_block.content if self.base_block else None),
            "target_preview": (self.target_block.content[:100] + "...") if self.target_block and len(self.target_block.content) > 100 else (self.target_block.content if self.target_block else None),
            "citations_added": self.citations_added,
            "citations_removed": self.citations_removed,
        }


@dataclass
class SemanticDiffResult:
    base_title: str
    target_title: str
    blocks: List[BlockDiff] = field(default_factory=list)
    similarity_ratio: float = 1.0
    total_base_words: int = 0
    total_target_words: int = 0
    net_word_change: int = 0
    blocks_added: int = 0
    blocks_removed: int = 0
    blocks_modified: int = 0
    blocks_unchanged: int = 0
    citations_added: List[str] = field(default_factory=list)
    citations_removed: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_title": self.base_title,
            "target_title": self.target_title,
            "similarity_ratio": round(self.similarity_ratio, 3),
            "total_base_words": self.total_base_words,
            "total_target_words": self.total_target_words,
            "net_word_change": self.net_word_change,
            "summary": {
                "added": self.blocks_added,
                "removed": self.blocks_removed,
                "modified": self.blocks_modified,
                "unchanged": self.blocks_unchanged,
            },
            "citations_added": sorted(list(set(self.citations_added))),
            "citations_removed": sorted(list(set(self.citations_removed))),
            "block_diffs": [b.to_dict() for b in self.blocks],
        }

    def render_terminal(self, use_color: bool = True) -> str:
        c_green = "\033[32m" if use_color else ""
        c_red = "\033[31m" if use_color else ""
        c_yellow = "\033[33m" if use_color else ""
        c_cyan = "\033[36m" if use_color else ""
        c_bold = "\033[1m" if use_color else ""
        c_reset = "\033[0m" if use_color else ""

        lines = [
            f"{c_bold}⚡ Semantic AST Diff: {c_cyan}{self.base_title}{c_reset} ➔ {c_cyan}{self.target_title}{c_reset}",
            f"Similarity: {c_bold}{int(self.similarity_ratio * 100)}%{c_reset} | Base Words: {self.total_base_words} | Target Words: {self.total_target_words} ({'+' if self.net_word_change >= 0 else ''}{self.net_word_change})",
            f"Blocks: {c_green}+{self.blocks_added} added{c_reset}, {c_red}-{self.blocks_removed} removed{c_reset}, {c_yellow}~{self.blocks_modified} modified{c_reset}, {self.blocks_unchanged} unchanged",
            "─" * 70,
        ]

        for b in self.blocks:
            if b.change_type == ChangeType.UNCHANGED:
                continue
            elif b.change_type == ChangeType.ADDED:
                lines.append(f"{c_green}[+ ADDED {b.block_type.value.upper()}]{c_reset} (+{b.word_delta} words)")
                for l in (b.target_block.raw if b.target_block else "").splitlines()[:5]:
                    lines.append(f"{c_green}+ {l}{c_reset}")
            elif b.change_type == ChangeType.REMOVED:
                lines.append(f"{c_red}[- REMOVED {b.block_type.value.upper()}]{c_reset} (-{abs(b.word_delta)} words)")
                for l in (b.base_block.raw if b.base_block else "").splitlines()[:5]:
                    lines.append(f"{c_red}- {l}{c_reset}")
            elif b.change_type == ChangeType.MODIFIED:
                lines.append(f"{c_yellow}[~ MODIFIED {b.block_type.value.upper()}]{c_reset} (sim: {int(b.similarity * 100)}%, {'+' if b.word_delta >= 0 else ''}{b.word_delta} words)")
                if b.line_diff:
                    for d in b.line_diff:
                        if d.startswith("+"):
                            lines.append(f"{c_green}{d}{c_reset}")
                        elif d.startswith("-"):
                            lines.append(f"{c_red}{d}{c_reset}")
                        elif d.startswith("?"):
                            lines.append(f"{c_cyan}{d}{c_reset}")
                        else:
                            lines.append(f"  {d}")

        if self.citations_added:
            lines.append(f"{c_green}Citations added:{c_reset} {', '.join(sorted(set(self.citations_added)))}")
        if self.citations_removed:
            lines.append(f"{c_red}Citations removed:{c_reset} {', '.join(sorted(set(self.citations_removed)))}")

        return "\n".join(lines)


class SemanticASTDiffer:
    """Computes semantic block-level differences between two Markdown documents."""

    def __init__(self):
        self.parser = MarkdownASTParser()

    def diff_texts(self, base_text: str, target_text: str, base_title: str = "Base", target_title: str = "Target") -> SemanticDiffResult:
        base_blocks = self.parser.parse_blocks(base_text)
        target_blocks = self.parser.parse_blocks(target_text)

        base_citations = set(self.parser.extract_citations(base_text))
        target_citations = set(self.parser.extract_citations(target_text))

        citations_added = list(target_citations - base_citations)
        citations_removed = list(base_citations - target_citations)

        base_words = sum(b.word_count for b in base_blocks)
        target_words = sum(b.word_count for b in target_blocks)

        # Match blocks using SequenceMatcher on block signatures
        matcher = difflib.SequenceMatcher(
            None,
            [f"{b.type.value}:{b.content.strip()}" for b in base_blocks],
            [f"{b.type.value}:{b.content.strip()}" for b in target_blocks],
        )

        overall_sim = matcher.ratio()

        diff_blocks: List[BlockDiff] = []
        blocks_added = 0
        blocks_removed = 0
        blocks_modified = 0
        blocks_unchanged = 0

        # Detailed block pairing
        opcodes = matcher.get_opcodes()
        for tag, i1, i2, j1, j2 in opcodes:
            if tag == "equal":
                for idx in range(i1, i2):
                    b_b = base_blocks[idx]
                    t_b = target_blocks[j1 + (idx - i1)]
                    diff_blocks.append(BlockDiff(
                        change_type=ChangeType.UNCHANGED,
                        block_type=b_b.type,
                        base_block=b_b,
                        target_block=t_b,
                        similarity=1.0,
                        word_delta=0,
                    ))
                    blocks_unchanged += 1
            elif tag == "delete":
                for idx in range(i1, i2):
                    b_b = base_blocks[idx]
                    diff_blocks.append(BlockDiff(
                        change_type=ChangeType.REMOVED,
                        block_type=b_b.type,
                        base_block=b_b,
                        target_block=None,
                        similarity=0.0,
                        word_delta=-b_b.word_count,
                        citations_removed=self.parser.extract_citations(b_b.content),
                    ))
                    blocks_removed += 1
            elif tag == "insert":
                for idx in range(j1, j2):
                    t_b = target_blocks[idx]
                    diff_blocks.append(BlockDiff(
                        change_type=ChangeType.ADDED,
                        block_type=t_b.type,
                        base_block=None,
                        target_block=t_b,
                        similarity=0.0,
                        word_delta=t_b.word_count,
                        citations_added=self.parser.extract_citations(t_b.content),
                    ))
                    blocks_added += 1
            elif tag == "replace":
                base_slice = base_blocks[i1:i2]
                target_slice = target_blocks[j1:j2]
                
                # If slice counts match, treat as modified pairs
                if len(base_slice) == len(target_slice):
                    for b_b, t_b in zip(base_slice, target_slice):
                        sim = difflib.SequenceMatcher(None, b_b.content, t_b.content).ratio()
                        line_diff = list(difflib.ndiff(b_b.content.splitlines(), t_b.content.splitlines()))
                        b_cits = set(self.parser.extract_citations(b_b.content))
                        t_cits = set(self.parser.extract_citations(t_b.content))
                        diff_blocks.append(BlockDiff(
                            change_type=ChangeType.MODIFIED,
                            block_type=t_b.type,
                            base_block=b_b,
                            target_block=t_b,
                            similarity=sim,
                            word_delta=t_b.word_count - b_b.word_count,
                            citations_added=list(t_cits - b_cits),
                            citations_removed=list(b_cits - t_cits),
                            line_diff=[d for d in line_diff if d.startswith(("+", "-", "?"))],
                        ))
                        blocks_modified += 1
                else:
                    for b_b in base_slice:
                        diff_blocks.append(BlockDiff(
                            change_type=ChangeType.REMOVED,
                            block_type=b_b.type,
                            base_block=b_b,
                            target_block=None,
                            similarity=0.0,
                            word_delta=-b_b.word_count,
                            citations_removed=self.parser.extract_citations(b_b.content),
                        ))
                        blocks_removed += 1
                    for t_b in target_slice:
                        diff_blocks.append(BlockDiff(
                            change_type=ChangeType.ADDED,
                            block_type=t_b.type,
                            base_block=None,
                            target_block=t_b,
                            similarity=0.0,
                            word_delta=t_b.word_count,
                            citations_added=self.parser.extract_citations(t_b.content),
                        ))
                        blocks_added += 1

        return SemanticDiffResult(
            base_title=base_title,
            target_title=target_title,
            blocks=diff_blocks,
            similarity_ratio=overall_sim,
            total_base_words=base_words,
            total_target_words=target_words,
            net_word_change=target_words - base_words,
            blocks_added=blocks_added,
            blocks_removed=blocks_removed,
            blocks_modified=blocks_modified,
            blocks_unchanged=blocks_unchanged,
            citations_added=citations_added,
            citations_removed=citations_removed,
        )

    def diff_files(self, base_file: Path | str, target_file: Path | str) -> SemanticDiffResult:
        b_p = Path(base_file)
        t_p = Path(target_file)
        if not b_p.exists():
            raise FileNotFoundError(f"Base file not found: {b_p}")
        if not t_p.exists():
            raise FileNotFoundError(f"Target file not found: {t_p}")

        return self.diff_texts(
            b_p.read_text(encoding="utf-8"),
            t_p.read_text(encoding="utf-8"),
            base_title=str(b_p.name),
            target_title=str(t_p.name),
        )
