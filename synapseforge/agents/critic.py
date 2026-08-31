"""
Adversarial Critic and Fact-Checking Agent.
Scrutinizes claims, checks logical consistency, verifies citations, and produces PR inline suggestions.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from synapseforge.agents.base import AgentRole, BaseAgent, ReviewFeedback
from synapseforge.core.ast_parser import BlockType, DocBlock, MarkdownASTParser


class CriticAgent(BaseAgent):
    def __init__(self, name: str = "Critic-Adversarial", model: str = "inherit"):
        super().__init__(name=name, role=AgentRole.CRITIC, model=model)

    def _default_system_prompt(self) -> str:
        return (
            "You are an Adversarial Academic Peer Reviewer and Fact-Checker. Your mission is to "
            "find unsupported claims, hand-waving logic, missing mathematical derivations, and "
            "unverified citations. Provide precise inline suggestions for corrections."
        )

    def review_section(self, section_text: str, section_id: str = "section") -> List[ReviewFeedback]:
        feedbacks: List[ReviewFeedback] = []
        blocks = MarkdownASTParser.parse_blocks(section_text)

        for b in blocks:
            if b.type == BlockType.PARAGRAPH:
                # Check for unsupported quantitative claims (e.g. "improves performance by 50%" without citation)
                match = re.search(r'(提升了?\s*\d+[\.%]|improved by \d+%)', b.content, re.IGNORECASE)
                if match and "@" not in b.content and "[" not in b.content:
                    feedbacks.append(ReviewFeedback(
                        agent_name=self.name,
                        agent_role=self.role.value,
                        section_id=section_id,
                        line_number=b.line_start,
                        category="fact_check",
                        severity="suggestion",
                        comment=f"定量性能结论 '{match.group(0)}' 缺少具体基准测试引用或数学推导支撑。建议补充实验对照基准或文献引用。",
                    ))

                # Check for absolute hand-waving words
                vague_matches = re.findall(r'(完美解决|完全消除|毫无疑问|flawlessly solved|completely eliminated)', b.content, re.IGNORECASE)
                for vm in vague_matches:
                    feedbacks.append(ReviewFeedback(
                        agent_name=self.name,
                        agent_role=self.role.value,
                        section_id=section_id,
                        line_number=b.line_start,
                        category="logic_flaw",
                        severity="suggestion",
                        comment=f"词句 '{vm}' 过于绝对，缺乏工程边界界定。建议明确系统适用场景与理论边界条件。",
                    ))

        return feedbacks
