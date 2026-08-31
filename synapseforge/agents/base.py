"""
Base Agent Protocols and Structured Feedback Schemas for SynapseForge.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentRole(str, Enum):
    ARCHITECT = "architect"
    DRAFTER = "drafter"
    CRITIC = "critic"
    HARMONIZER = "harmonizer"
    VISUALIZER = "visualizer"


@dataclass
class ReviewFeedback:
    agent_name: str
    agent_role: str
    section_id: str
    line_number: Optional[int]
    category: str  # "fact_check" | "logic_flaw" | "tone_harmonization" | "structure" | "citation"
    severity: str  # "blocking" | "suggestion" | "praise"
    comment: str
    suggested_diff: Optional[str] = None

    def to_github_pr_comment(self) -> Dict[str, Any]:
        """Formats into GitHub PR Review Comment payload."""
        body = f"**[{self.agent_role.upper()}: {self.agent_name}]** ({self.category})\n\n{self.comment}"
        if self.suggested_diff:
            body += f"\n\n```suggestion\n{self.suggested_diff}\n```"
        
        return {
            "body": body,
            "line": self.line_number,
        }


class BaseAgent:
    """Base class for all collaborative writing and reviewing agents in the swarm."""

    def __init__(self, name: str, role: AgentRole, model: str = "inherit", system_prompt: Optional[str] = None):
        self.name = name
        self.role = role
        self.model = model
        self.system_prompt = system_prompt or self._default_system_prompt()

    def _default_system_prompt(self) -> str:
        return f"You are {self.name}, acting as {self.role.value} in SynapseForge."

    def execute_task(self, task_input: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Subclasses must implement execute_task")
