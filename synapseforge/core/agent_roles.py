"""
Pre-Designed Agent Roles and System Prompt Library for SynapseForge.
Provides standardized, top-tier personas for Drafter, Critic, Architect, Harmonizer, and SciPlotter.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class AgentRoleSpec:
    role_id: str
    name: str
    description: str
    prompt_file: str
    recommended_model: str
    color_accent: str


class AgentRoleManager:
    """Manages pre-designed system prompts and role specifications."""

    def __init__(self, workspace_root: Optional[Path] = None):
        self.workspace_root = workspace_root or Path.cwd()
        self.prompts_dir = self.workspace_root / "synapseforge" / "prompts"
        self.roles: Dict[str, AgentRoleSpec] = {
            "architect": AgentRoleSpec(
                role_id="architect",
                name="Architect Agent (总架构师)",
                description="Decomposes research themes into orthogonal DAG sections and sets word budgets.",
                prompt_file="architect.md",
                recommended_model="deepseek-reasoner / claude-3-7-sonnet",
                color_accent="#0a84ff",
            ),
            "drafter": AgentRoleSpec(
                role_id="drafter",
                name="Drafter Agent (学术起草专家)",
                description="Writes dense academic narrative prose, LaTeX formulas, and Booktabs tables with zero AI flavor.",
                prompt_file="drafter.md",
                recommended_model="deepseek-v3 / gemini-2.0-flash",
                color_accent="#af52de",
            ),
            "critic": AgentRoleSpec(
                role_id="critic",
                name="Critic Agent (严苛审稿专家)",
                description="Audits manuscripts, runs Anti-AI quality gates, checks citations, and finds proof gaps.",
                prompt_file="critic.md",
                recommended_model="deepseek-reasoner / local-ollama",
                color_accent="#ff9f0a",
            ),
            "harmonizer": AgentRoleSpec(
                role_id="harmonizer",
                name="Harmonizer Agent (多方案调和官)",
                description="Fuses multi-document candidate drafts into unified master chapters.",
                prompt_file="harmonizer.md",
                recommended_model="deepseek-v3 / gpt-4o",
                color_accent="#30d158",
            ),
            "sci_plot": AgentRoleSpec(
                role_id="sci_plot",
                name="SciPlot Artist (顶刊科研绘图专家)",
                description="Generates Nature/Science 300+ DPI figures and injects figure discussion bridges.",
                prompt_file="sci_plot.md",
                recommended_model="gemini-2.0-flash / python-runtime",
                color_accent="#64d2ff",
            ),
        }

    def list_roles(self) -> List[Dict[str, Any]]:
        """Lists all available pre-designed agent roles."""
        res = []
        for r in self.roles.values():
            res.append({
                "role_id": r.role_id,
                "name": r.name,
                "description": r.description,
                "recommended_model": r.recommended_model,
                "color_accent": r.color_accent,
                "prompt_file": f"synapseforge/prompts/{r.prompt_file}",
            })
        return res

    def get_system_prompt(self, role_id: str) -> str:
        """Loads the full markdown system prompt for a designated agent role."""
        if role_id not in self.roles:
            raise KeyError(f"Role '{role_id}' not found in pre-designed roles.")

        p_file = self.prompts_dir / self.roles[role_id].prompt_file
        if p_file.exists():
            return p_file.read_text(encoding="utf-8")
        return f"# Role: {self.roles[role_id].name}\n\n{self.roles[role_id].description}"
