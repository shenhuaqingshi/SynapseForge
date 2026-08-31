from pathlib import Path

from synapseforge.core.local_agent_cli import (
    DEFAULT_LOCAL_AGENTS,
    LocalAgentCLIManager,
    render_args,
    resolve_binary,
)


def test_default_grok_invocation_is_single_turn_not_build():
    grok = DEFAULT_LOCAL_AGENTS["grok"]
    assert grok["args_pattern"] == ["-p", "{instruction}"]
    assert grok["prompt_file_args"] == ["--prompt-file", "{prompt_file}"]
    assert "build" not in grok["args_pattern"]


def test_default_host_cli_templates():
    assert DEFAULT_LOCAL_AGENTS["antigravity"]["binary"] == "agy"
    assert DEFAULT_LOCAL_AGENTS["antigravity"]["args_pattern"][0] == "-p"
    assert DEFAULT_LOCAL_AGENTS["claude"]["args_pattern"][0] == "-p"
    assert DEFAULT_LOCAL_AGENTS["codex"]["args_pattern"][0] == "exec"


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
        description="User custom grok engine",
    )
    assert res["ok"] is True
    assert res["agent_name"] == "custom_grok"

    clis = mgr.detect_available_clis()
    found = [c for c in clis if c["agent_name"] == "custom_grok"]
    assert len(found) == 1
    assert found[0]["binary"] == "grok-custom"


def test_local_agent_cli_run_mock_binary(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    mock_cli = bin_dir / "mock_agent"
    mock_cli.write_text(
        """#!/bin/bash
echo "Mock Agent writing output"
echo "## Added by Mock Agent" >> sections/01_test.md
""",
        encoding="utf-8",
    )
    mock_cli.chmod(0o755)

    sec_dir = tmp_path / "sections"
    sec_dir.mkdir(parents=True)
    (sec_dir / "01_test.md").write_text("# 1. Test\nInitial content\n", encoding="utf-8")

    mgr = LocalAgentCLIManager(workspace_root=tmp_path)
    mgr.register_cli(
        name="mock_agent",
        binary=str(mock_cli),
        args_pattern=["{instruction}"],
        description="Mock test agent",
    )

    res = mgr.run_agent_cli(
        agent_name="mock_agent",
        section_id="01_test",
        user_instruction="Draft proof for Theorem 1",
    )
    assert res["ok"] is True
    assert res["lock_status"] == "auto_released"

    updated_content = (sec_dir / "01_test.md").read_text(encoding="utf-8")
    assert "Added by Mock Agent" in updated_content


def test_grok_build_command_uses_prompt_file(tmp_path):
    grok_bin = tmp_path / "bin"
    grok_bin.mkdir()
    fake = grok_bin / "grok"
    fake.write_text("#!/bin/bash\necho grok\n", encoding="utf-8")
    fake.chmod(0o755)

    mgr = LocalAgentCLIManager(workspace_root=tmp_path)
    mgr.register_cli(
        name="grok",
        binary=str(fake),
        args_pattern=["-p", "{instruction}"],
        prompt_file_args=["--prompt-file", "{prompt_file}"],
    )
    spec = {c["agent_name"]: c for c in mgr.detect_available_clis()}["grok"]
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("hello", encoding="utf-8")
    argv = mgr.build_command(spec, "hello " * 2000, prompt_file=prompt)
    assert argv[0] == str(fake)
    assert "--prompt-file" in argv
    assert "-p" not in argv


def test_render_args_and_resolve_missing():
    assert render_args(["-p", "{instruction}"], {"instruction": "hi"}) == ["-p", "hi"]
    assert resolve_binary("definitely-not-a-real-synapseforge-bin-xyz") is None
