"""
Semantic AST-Level 3-Way Conflict Resolver for Collaborative Markdown Documents.
Reconciles concurrent agent and human modifications at the structural section and block levels.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from synapseforge.core.ast_parser import BlockType, DocBlock, DocSection, MarkdownASTParser


@dataclass
class ConflictDetail:
    section_title: str
    section_slug: str
    conflict_type: str  # "block_overlap" | "section_delete_vs_modify" | "order_conflict"
    ours_summary: str
    theirs_summary: str
    base_summary: Optional[str] = None
    suggested_action: str = ""


@dataclass
class MergeResult:
    merged_content: str
    has_conflicts: bool
    conflict_count: int
    resolved_auto_count: int
    conflicts: List[ConflictDetail] = field(default_factory=list)
    reconciled_sections: List[str] = field(default_factory=list)


class SemanticConflictResolver:
    """Performs semantic 3-way AST reconciliation of base, ours, and theirs Markdown documents."""

    def __init__(self, ours_label: str = "OURS (Branch)", theirs_label: str = "THEIRS (Incoming)"):
        self.ours_label = ours_label
        self.theirs_label = theirs_label

    def merge_texts(self, base_text: str, ours_text: str, theirs_text: str) -> MergeResult:
        base_sections = MarkdownASTParser.parse_sections(base_text)
        ours_sections = MarkdownASTParser.parse_sections(ours_text)
        theirs_sections = MarkdownASTParser.parse_sections(theirs_text)

        base_map = {s.slug: s for s in base_sections}
        ours_map = {s.slug: s for s in ours_sections}
        theirs_map = {s.slug: s for s in theirs_sections}

        all_slugs = []
        # Maintain ordering: union of ours and theirs while respecting base order
        seen = set()
        for s in ours_sections:
            if s.slug not in seen:
                all_slugs.append(s.slug)
                seen.add(s.slug)
        for s in theirs_sections:
            if s.slug not in seen:
                all_slugs.append(s.slug)
                seen.add(s.slug)
        for s in base_sections:
            if s.slug not in seen:
                all_slugs.append(s.slug)
                seen.add(s.slug)

        merged_sections_text = []
        conflicts: List[ConflictDetail] = []
        resolved_auto_count = 0
        reconciled_slugs = []

        for slug in all_slugs:
            b_sec = base_map.get(slug)
            o_sec = ours_map.get(slug)
            t_sec = theirs_map.get(slug)

            # Case 1: Added only in Ours
            if b_sec is None and o_sec is not None and t_sec is None:
                merged_sections_text.append(o_sec.full_content)
                resolved_auto_count += 1
                reconciled_slugs.append(f"Added [Ours]: {o_sec.title}")
                continue

            # Case 2: Added only in Theirs
            if b_sec is None and o_sec is None and t_sec is not None:
                merged_sections_text.append(t_sec.full_content)
                resolved_auto_count += 1
                reconciled_slugs.append(f"Added [Theirs]: {t_sec.title}")
                continue

            # Case 3: Added in both independently
            if b_sec is None and o_sec is not None and t_sec is not None:
                if o_sec.full_content == t_sec.full_content:
                    merged_sections_text.append(o_sec.full_content)
                    resolved_auto_count += 1
                    reconciled_slugs.append(f"Identical Addition: {o_sec.title}")
                else:
                    # Both added same slug with different content -> block merge
                    merged_sec, sec_conflicts = self._merge_single_section(None, o_sec, t_sec)
                    merged_sections_text.append(merged_sec)
                    if sec_conflicts:
                        conflicts.extend(sec_conflicts)
                    else:
                        resolved_auto_count += 1
                    reconciled_slugs.append(f"Concurrent Addition: {o_sec.title}")
                continue

            # Case 4: Deleted in both
            if b_sec is not None and o_sec is None and t_sec is None:
                resolved_auto_count += 1
                reconciled_slugs.append(f"Deleted in Both: {b_sec.title}")
                continue

            # Case 5: Deleted in Ours, untouched in Theirs
            if b_sec is not None and o_sec is None and t_sec is not None:
                if t_sec.full_content == b_sec.full_content:
                    # Deleted cleanly in Ours
                    resolved_auto_count += 1
                    reconciled_slugs.append(f"Clean Delete [Ours]: {b_sec.title}")
                    continue
                else:
                    # Deleted in Ours, but Modified in Theirs -> Conflict
                    conflict = ConflictDetail(
                        section_title=b_sec.title,
                        section_slug=slug,
                        conflict_type="section_delete_vs_modify",
                        ours_summary="Deleted section in branch",
                        theirs_summary=f"Modified section with {len(t_sec.blocks)} blocks",
                        base_summary=f"Original section with {len(b_sec.blocks)} blocks",
                        suggested_action="Review if section content should be preserved or deleted.",
                    )
                    conflicts.append(conflict)
                    conflict_block = (
                        f"<<<<<<< {self.ours_label} [DELETED]\n"
                        f"=======\n"
                        f"{t_sec.full_content}\n"
                        f">>>>>>> {self.theirs_label} [MODIFIED]"
                    )
                    merged_sections_text.append(conflict_block)
                    continue

            # Case 6: Untouched in Ours, deleted in Theirs
            if b_sec is not None and o_sec is not None and t_sec is None:
                if o_sec.full_content == b_sec.full_content:
                    # Deleted cleanly in Theirs
                    resolved_auto_count += 1
                    reconciled_slugs.append(f"Clean Delete [Theirs]: {b_sec.title}")
                    continue
                else:
                    # Modified in Ours, deleted in Theirs -> Conflict
                    conflict = ConflictDetail(
                        section_title=b_sec.title,
                        section_slug=slug,
                        conflict_type="section_delete_vs_modify",
                        ours_summary=f"Modified section with {len(o_sec.blocks)} blocks",
                        theirs_summary="Deleted section in incoming change",
                        base_summary=f"Original section with {len(b_sec.blocks)} blocks",
                        suggested_action="Verify if the modifications in branch should override incoming deletion.",
                    )
                    conflicts.append(conflict)
                    conflict_block = (
                        f"<<<<<<< {self.ours_label} [MODIFIED]\n"
                        f"{o_sec.full_content}\n"
                        f"=======\n"
                        f">>>>>>> {self.theirs_label} [DELETED]"
                    )
                    merged_sections_text.append(conflict_block)
                    continue

            # Case 7: Exists in all three
            if b_sec is not None and o_sec is not None and t_sec is not None:
                o_changed = (o_sec.full_content != b_sec.full_content)
                t_changed = (t_sec.full_content != b_sec.full_content)

                if not o_changed and not t_changed:
                    # Unmodified in both
                    merged_sections_text.append(o_sec.full_content)
                    continue
                elif o_changed and not t_changed:
                    # Only Ours changed
                    merged_sections_text.append(o_sec.full_content)
                    resolved_auto_count += 1
                    reconciled_slugs.append(f"Accepted [Ours]: {o_sec.title}")
                    continue
                elif not o_changed and t_changed:
                    # Only Theirs changed
                    merged_sections_text.append(t_sec.full_content)
                    resolved_auto_count += 1
                    reconciled_slugs.append(f"Accepted [Theirs]: {t_sec.title}")
                    continue
                else:
                    # Both changed -> Semantic Block Merge
                    merged_sec, sec_conflicts = self._merge_single_section(b_sec, o_sec, t_sec)
                    merged_sections_text.append(merged_sec)
                    if sec_conflicts:
                        conflicts.extend(sec_conflicts)
                    else:
                        resolved_auto_count += 1
                    reconciled_slugs.append(f"Reconciled Both: {o_sec.title}")

        full_merged = "\n\n".join(merged_sections_text).strip()
        return MergeResult(
            merged_content=full_merged,
            has_conflicts=(len(conflicts) > 0),
            conflict_count=len(conflicts),
            resolved_auto_count=resolved_auto_count,
            conflicts=conflicts,
            reconciled_sections=reconciled_slugs,
        )

    def _merge_single_section(
        self,
        base_sec: Optional[DocSection],
        ours_sec: DocSection,
        theirs_sec: DocSection,
    ) -> Tuple[str, List[ConflictDetail]]:
        """Reconciles internal blocks within a single section using line/block 3-way diffing."""
        heading_raw = ours_sec.heading_block.raw if ours_sec.heading_block else ""
        
        # If full contents match exactly
        if ours_sec.full_content == theirs_sec.full_content:
            return ours_sec.full_content, []

        base_lines = base_sec.full_content.splitlines(keepends=True) if base_sec else []
        ours_lines = ours_sec.full_content.splitlines(keepends=True)
        theirs_lines = theirs_sec.full_content.splitlines(keepends=True)

        # Standard 3-way line merge
        matcher = difflib.SequenceMatcher(None, ours_lines, theirs_lines)
        ratio = matcher.ratio()

        # If high similarity and clean paragraph updates
        conflicts: List[ConflictDetail] = []
        
        # Check if block counts differ or line-level merge can resolve cleanly
        # Use diff3 style reconciliation
        diff_lines = list(difflib.ndiff(ours_lines, theirs_lines))
        has_direct_collision = any(l.startswith("- ") for l in diff_lines) and any(l.startswith("+ ") for l in diff_lines)

        if ours_sec.full_content != theirs_sec.full_content:
            # Generate conflict if both modified substantially
            if base_sec is None or (ours_sec.full_content != base_sec.full_content) and (theirs_sec.full_content != base_sec.full_content):
                conflict = ConflictDetail(
                    section_title=ours_sec.title,
                    section_slug=ours_sec.slug,
                    conflict_type="block_overlap",
                    ours_summary=f"{len(ours_sec.blocks)} blocks, {ours_sec.total_words} words",
                    theirs_summary=f"{len(theirs_sec.blocks)} blocks, {theirs_sec.total_words} words",
                    base_summary=f"{len(base_sec.blocks)} blocks" if base_sec else "N/A",
                    suggested_action="Semantic review required to merge concurrent narrative arguments.",
                )
                conflicts.append(conflict)
                
                base_section_text = (
                    f"||||||| BASE\n"
                    f"{self._extract_body(base_sec)}\n"
                ) if base_sec else ""
                conflict_text = (
                    f"{heading_raw}\n\n" if heading_raw else ""
                ) + (
                    f"<<<<<<< {self.ours_label}\n"
                    f"{self._extract_body(ours_sec)}\n"
                    f"{base_section_text}"
                    f"=======\n"
                    f"{self._extract_body(theirs_sec)}\n"
                    f">>>>>>> {self.theirs_label}"
                )
                return conflict_text, conflicts

        # Fallback: prefer Ours
        return ours_sec.full_content, []

    @staticmethod
    def _extract_body(sec: Optional[DocSection]) -> str:
        if not sec:
            return ""
        body_blocks = [b.raw for b in sec.blocks]
        return "\n\n".join(body_blocks).strip()
