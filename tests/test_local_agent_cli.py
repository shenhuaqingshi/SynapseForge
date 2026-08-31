import pytest
from pathlib import Path
from synapseforge.core.local_agent_cli import LocalAgentCLIManager


def test_local_agent_cli_detection(tmp_path):
    mgr = LocalAgentCLIManager(workspace_root=tmp_path)
    clis = mgr.detect_available_clis()
    assert len(clis) >= 5

    cli_names = [c["agent_name"] for c in clis]
    assert "antigravity" in cli_names
    assert "claude" in cli_names
    assert "codex" in cli_names
    assert "grok" in cli_names


def test_local_agent_cli_registration(tmp_path):
    mgr = LocalAgentCLIManager(workspace_root=tmp_path)
    res = mgr.register_cli(
        name="custom_grok",
        binary="grok-custom",
        args_pattern=["run", "--task", "{instruction}"],
        description="User custom grok engine"
    )
    assert res["ok"] is True
    assert res["agent_name"] == "custom_grok"

    clis = mgr.detect_available_clis()
    found = [c for c in clis if c["agent_name"] == "custom_grok"]
    assert len(found) == 1
    assert found[0]["binary"] == "grok-custom"


def test_local_agent_cli_run_mock_binary(tmp_path):
    # Create a mock CLI script
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    mock_cli = bin_dir / "mock_agent"
    mock_cli.write_text("""#!/bin/bash
echo "Mock Agent writing output to $1"
echo "## Added by Mock Agent" >> sections/01_test.md
""", encoding="utf-8")
    mock_cli.chmod(0o755)

    sec_dir = tmp_path / "sections"
    sec_dir.mkdir(parents=True)
    (sec_dir / "01_test.md").write_text("# 1. Test\nInitial content\n", encoding="utf-8")

    mgr = LocalAgentCLIManager(workspace_root=tmp_path)
    mgr.register_cli(
        name="mock_agent",
        binary=str(mock_cli),
        args_pattern=["{instruction}"],
        description="Mock test agent"
    )

    res = mgr.run_agent_cli(
        agent_name="mock_agent",
        section_id="01_test",
        user_instruction="Draft proof for Theorem 1"
    )
    assert res["ok"] is True
    assert res["lock_status"] == "auto_released"

    updated_content = (sec_dir / "01_test.md").read_text(encoding="utf-8")
    assert "Added by Mock Agent" in updated_content
