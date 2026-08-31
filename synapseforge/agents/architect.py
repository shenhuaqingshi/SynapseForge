"""
Document Architect Agent: Synthesizes document schemas, chapter DAGs, and word count allocations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from synapseforge.agents.base import AgentRole, BaseAgent
from synapseforge.config import SectionSpec


class ArchitectAgent(BaseAgent):
    def __init__(self, name: str = "Architect-Prime", model: str = "inherit"):
        super().__init__(name=name, role=AgentRole.ARCHITECT, model=model)

    def _default_system_prompt(self) -> str:
        return (
            "You are the Lead Document Architect. Your job is to structure complex technical "
            "whitepapers, academic papers, and system specs into modular, non-overlapping section "
            "DAGs with explicit dependencies, word budgets, and role assignments."
        )

    def plan_document_dag(self, topic: str, target_total_words: int = 5000) -> List[SectionSpec]:
        """Creates a standard 6-stage topological DAG for a high-impact technical document."""
        return [
            SectionSpec(
                id="sec_01_abstract",
                title="Abstract & Problem Statement",
                file="sections/01_abstract_introduction.md",
                assigned_role="drafter",
                dependencies=[],
                word_count_target=int(target_total_words * 0.15),
                description="Core thesis, distributed consensus paradox, and mechanistic overview.",
            ),
            SectionSpec(
                id="sec_02_theory",
                title="Theoretical Foundations & Mathematical Formalism",
                file="sections/02_theoretical_foundations.md",
                assigned_role="drafter",
                dependencies=["sec_01_abstract"],
                word_count_target=int(target_total_words * 0.20),
                description="Formal definition of semantic AST conflict resolution and consensus theorems.",
            ),
            SectionSpec(
                id="sec_03_architecture",
                title="System Architecture & GitOps State Machine",
                file="sections/03_system_architecture.md",
                assigned_role="drafter",
                dependencies=["sec_02_theory"],
                word_count_target=int(target_total_words * 0.25),
                description="Decentralized coordination layer, lease manager, and GitHub Action bridges.",
            ),
            SectionSpec(
                id="sec_04_conflict_consensus",
                title="Cross-Regional Conflict Resolution Protocol",
                file="sections/04_conflict_resolution_and_consensus.md",
                assigned_role="drafter",
                dependencies=["sec_03_architecture"],
                word_count_target=int(target_total_words * 0.20),
                description="AST 3-way reconciliation algorithms and asynchronous human-in-the-loop review.",
            ),
            SectionSpec(
                id="sec_05_empirical_benchmarks",
                title="Empirical Validation & Benchmark Results",
                file="sections/05_empirical_benchmarks.md",
                assigned_role="drafter",
                dependencies=["sec_04_conflict_consensus"],
                word_count_target=int(target_total_words * 0.15),
                description="Quantitative metrics, merge latency, citation integrity, and reviewer workload reduction.",
            ),
            SectionSpec(
                id="sec_06_conclusion",
                title="Synthesis, Limitations & Open Directions",
                file="sections/06_conclusion_and_roadmap.md",
                assigned_role="harmonizer",
                dependencies=["sec_05_empirical_benchmarks"],
                word_count_target=int(target_total_words * 0.05),
                description="Concluding synthesis and forward-looking research roadmap.",
            ),
        ]
