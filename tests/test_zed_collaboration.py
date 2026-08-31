import pytest
from pathlib import Path
from synapseforge.core.agent_roles import AgentRoleManager


def test_agent_role_manager_all_roles():
    mgr = AgentRoleManager()
    roles = mgr.list_roles()
    assert len(roles) >= 5

    role_ids = [r["role_id"] for r in roles]
    assert "architect" in role_ids
    assert "drafter" in role_ids
    assert "critic" in role_ids
    assert "harmonizer" in role_ids
    assert "sci_plot" in role_ids


def test_agent_system_prompts_loading():
    mgr = AgentRoleManager()
    for r_id in ["architect", "drafter", "critic", "harmonizer", "sci_plot"]:
        prompt = mgr.get_system_prompt(r_id)
        assert len(prompt) > 50
        assert "Role:" in prompt
