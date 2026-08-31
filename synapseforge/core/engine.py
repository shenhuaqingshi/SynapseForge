"""
Swarm Orchestration Engine for Distributed Multi-Agent & Multi-Human Collaborative Workflows.
Coordinates planning, drafting, linting, peer review, conflict reconciliation, and document synthesis.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from synapseforge.config import ProjectConfig, load_config
from synapseforge.core.ast_parser import MarkdownASTParser
from synapseforge.core.conflict_resolver import MergeResult, SemanticConflictResolver
from synapseforge.core.state import SectionState, SectionStatus, StateManager


@dataclass
class SwarmExecutionReport:
    project_name: str
    total_sections: int
    completed_sections: int
    active_sections: int
    total_words: int
    linter_passed: bool
    linter_errors: int
    linter_warnings: int
    reviews_count: int
    ready_for_merge: bool
    details: Dict[str, Any] = field(default_factory=dict)


class SwarmEngine:
    """The central orchestrator driving distributed collaborative writing on Git and GitHub."""

    def __init__(self, project_root: Optional[Path | str] = None, config: Optional[ProjectConfig] = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.config = config or load_config(self.project_root / "synapseforge.yaml")
        self.state_manager = StateManager(self.project_root)
        self.state_manager.sync_from_config(self.config)
        self.conflict_resolver = SemanticConflictResolver(
            ours_label="Branch (Swarm/Agent)",
            theirs_label="Main (Upstream)"
        )

    def plan_document(self) -> List[SectionState]:
        """Generates section stubs, verifies DAG topological order, and prepares workspace files."""
        topo_order = self.state_manager.get_topological_order()
        created_sections = []

        for sec_id in topo_order:
            sec_state = self.state_manager.state.sections[sec_id]
            target_path = self.project_root / sec_state.file
            target_path.parent.mkdir(parents=True, exist_ok=True)

            if not target_path.exists():
                # Create initial scaffold
                initial_content = (
                    f"# {sec_state.title}\n\n"
                    f"<!-- SynapseForge Section ID: {sec_state.id} -->\n"
                    f"<!-- Assigned Role: {sec_state.assigned_role} -->\n"
                    f"<!-- Target Words: {getattr(sec_state, 'word_count', 1000)} -->\n\n"
                    f"<!-- Drafting in progress by {sec_state.assigned_actor}... -->\n"
                )
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(initial_content)
                sec_state.status = SectionStatus.IDLE
            created_sections.append(sec_state)

        self.state_manager.save()
        return created_sections

    def get_document_tree(self) -> List[Dict[str, Any]]:
        """Returns structured hierarchy and status of all document sections."""
        res = []
        for s_id, s in self.state_manager.state.sections.items():
            f_path = self.project_root / s.file
            word_count = 0
            if f_path.exists():
                text = f_path.read_text(encoding="utf-8")
                blocks = MarkdownASTParser.parse_blocks(text)
                word_count = sum(b.word_count for b in blocks)

            res.append({
                "id": s.id,
                "title": s.title,
                "file": s.file,
                "status": s.status,
                "assigned_role": s.assigned_role,
                "assigned_actor": s.assigned_actor,
                "word_count": word_count,
                "dependencies": s.dependencies,
            })
        return res

    def compile_full_document(self) -> str:
        """Assembles all sections into a single coherent master document ordered by DAG."""
        topo_order = self.state_manager.get_topological_order()
        full_parts = []

        # Document Header / Frontmatter
        full_parts.append(f"# {self.config.document_title}\n")
        if self.config.authors:
            full_parts.append(f"**Authors**: {', '.join(self.config.authors)}\n")

        for sec_id in topo_order:
            sec_state = self.state_manager.state.sections[sec_id]
            f_path = self.project_root / sec_state.file
            if f_path.exists():
                content = f_path.read_text(encoding="utf-8")
                # Strip initial metadata comments for clean master compilation
                clean_lines = [l for l in content.splitlines() if not l.startswith("<!-- SynapseForge")]
                full_parts.append("\n".join(clean_lines).strip())

        return "\n\n".join(full_parts)

    def reconcile_3way(self, base_file: Path, ours_file: Path, theirs_file: Path) -> MergeResult:
        """Executes AST-level 3-way conflict resolution between file variants."""
        base_text = base_file.read_text(encoding="utf-8") if base_file.exists() else ""
        ours_text = ours_file.read_text(encoding="utf-8") if ours_file.exists() else ""
        theirs_text = theirs_file.read_text(encoding="utf-8") if theirs_file.exists() else ""

        return self.conflict_resolver.merge_texts(base_text, ours_text, theirs_text)
