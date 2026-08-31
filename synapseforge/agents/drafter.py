"""
Narrative Analytical Drafter Agent: Generates in-depth publication-grade prose with zero AI flavor.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from synapseforge.agents.base import AgentRole, BaseAgent


class DrafterAgent(BaseAgent):
    def __init__(self, name: str = "Drafter-Narrative", model: str = "inherit"):
        super().__init__(name=name, role=AgentRole.DRAFTER, model=model)

    def _default_system_prompt(self) -> str:
        return (
            "You are a Senior Technical Drafter. Write in rigorous, continuous narrative prose. "
            "Eliminate all robotic transitions ('In today's fast-paced world', 'It is worth noting'), "
            "ban formulaic bullet-point addiction, and support every thesis with quantitative mechanisms, "
            "formal mathematics, booktabs comparative tables, and verified academic citations."
        )

    def execute_task(self, task_input: Dict[str, Any]) -> Dict[str, Any]:
        section_spec = task_input.get("section_spec")
        context_docs = task_input.get("context_docs", {})
        # Returns drafted content structure
        return {
            "status": "drafted",
            "section_id": section_spec.id if section_spec else "unknown",
            "agent": self.name,
        }
