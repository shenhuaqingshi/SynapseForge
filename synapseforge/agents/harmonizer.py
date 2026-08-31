"""
Cross-Regional Tone and Style Harmonizer Agent.
Merges disparate writing styles from different human co-authors and agents into a unified, elegant voice.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from synapseforge.agents.base import AgentRole, BaseAgent, ReviewFeedback
from synapseforge.core.ast_parser import BlockType, MarkdownASTParser


class HarmonizerAgent(BaseAgent):
    def __init__(self, name: str = "Harmonizer-Voice", model: str = "inherit"):
        super().__init__(name=name, role=AgentRole.HARMONIZER, model=model)

    def _default_system_prompt(self) -> str:
        return (
            "You are the Swarm Lead Editor and Voice Harmonizer. Your responsibility is ensuring "
            "seamless narrative transitions between chapters written across different time zones, "
            "human co-authors, and specialized agents, maintaining a publication-grade academic tone."
        )

    def review_transitions(self, prev_section_text: str, curr_section_text: str, curr_section_id: str) -> List[ReviewFeedback]:
        feedbacks: List[ReviewFeedback] = []
        curr_blocks = MarkdownASTParser.parse_blocks(curr_section_text)
        
        # Check first paragraph of new section
        first_p = next((b for b in curr_blocks if b.type == BlockType.PARAGRAPH), None)
        if first_p:
            # Check if it connects to prior topic
            if len(first_p.content) < 40:
                feedbacks.append(ReviewFeedback(
                    agent_name=self.name,
                    agent_role=self.role.value,
                    section_id=curr_section_id,
                    line_number=first_p.line_start,
                    category="tone_harmonization",
                    severity="suggestion",
                    comment="章节开篇过渡较生硬。建议增加与前序章节核心结论衔接的有机逻辑过渡句。",
                ))

        return feedbacks
