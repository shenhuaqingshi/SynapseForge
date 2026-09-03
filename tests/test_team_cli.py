import json
import os
import subprocess
import sys
from pathlib import Path

from synapseforge.cli.team_cmds import paste_prompt
from synapseforge.core.team_bus import TeamBus


def _run(workspace: Path, extra: list, env=None):
    cmd = [sys.executable, "-m", "synapseforge.cli.main", "team", *extra, "--cwd", str(workspace), "--json"]
    merged = dict(os.environ)
    merged["PYTHONPATH"] = str(Path(__file__).resolve().parents[1]) + os.pathsep + merged.get("PYTHONPATH", "")
    if env:
        merged.update(env)
    proc = subprocess.run(cmd, text=True, capture_output=True, cwd=str(workspace), env=merged)
    return proc


def test_team_open_join_status_and_directive(tmp_path):
    doc = tmp_path / "brief.md"
    doc.write_text("# Brief\nWrite section 01.\n", encoding="utf-8")
    opened = _run(tmp_path, ["open", "--document", str(doc), "--room", "paper"])
    assert opened.returncode == 0, opened.stderr
    data = json.loads(opened.stdout)
    assert data["ok"] is True
    assert data["room"] == "paper"
    assert "grok" in data["paste_prompts"]
    assert "codex" in data["paste_prompts"]
    assert "synapseforge team join" in data["paste_prompts"]["antigravity"]

    joined = _run(tmp_path, ["join", "--room", "paper", "--agent", "grok", "--role", "reviewer"])
    assert joined.returncode == 0, joined.stderr
    seat = json.loads(joined.stdout)
    assert seat["already_online"] is False
    assert seat["agent"] == "grok"

    said = _run(
        tmp_path,
        ["say", "--room", "paper", "--agent", "human", "-m", "Stop submitting", "--kind", "directive"],
    )
    assert said.returncode == 0, said.stderr
    msg = json.loads(said.stdout)
    assert msg["kind"] == "directive"

    created = _run(
        tmp_path,
        ["create-task", "--room", "paper", "--agent", "grok", "--title", "Draft sec_01", "--files", str(doc)],
    )
    assert created.returncode == 0, created.stderr
    task = json.loads(created.stdout)
    assert task["deduplicated"] is False

    claimed = _run(
        tmp_path,
        ["claim-task", "--room", "paper", "--agent", "grok", "--task-id", str(task["id"])],
    )
    assert claimed.returncode == 0, claimed.stderr

    status = _run(tmp_path, ["status", "--room", "paper"])
    assert status.returncode == 0, status.stderr
    dash = json.loads(status.stdout)
    assert "grok" in dash["live_agents"]
    assert dash["coordinator_silent"] is True  # codex never joined


def test_paste_prompt_submitter_split():
    grok = paste_prompt("r", "grok", "review", "/tmp/a.md", "/tmp", "goal")
    agy = paste_prompt("r", "antigravity", "impl", "/tmp/a.md", "/tmp", "goal")
    assert "not the submitter" in grok
    assert "only submitter" in agy


def test_team_wait_and_leave(tmp_path):
    doc = tmp_path / "brief.md"
    doc.write_text("# Brief\nWrite section 01.\n", encoding="utf-8")
    opened = _run(tmp_path, ["open", "--document", str(doc), "--room", "paper"])
    assert opened.returncode == 0, opened.stderr
    joined = _run(tmp_path, ["join", "--room", "paper", "--agent", "grok"])
    assert joined.returncode == 0, joined.stderr
    waited = _run(
        tmp_path,
        ["wait", "--room", "paper", "--agent", "grok", "--timeout", "0"],
    )
    assert waited.returncode == 0, waited.stderr
    wait_data = json.loads(waited.stdout)
    assert "coordinator_silent" in wait_data
    left = _run(tmp_path, ["leave", "--room", "paper", "--agent", "grok"])
    assert left.returncode == 0, left.stderr


def test_mcp_handshake_and_join(tmp_path):
    env = dict(os.environ)
    env["SYNAPSEFORGE_TEAM_DB"] = str(tmp_path / "team.db")
    env["SYNAPSEFORGE_WORKSPACE"] = str(tmp_path)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1]) + os.pathsep + env.get("PYTHONPATH", "")
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}},
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "team_join", "arguments": {"room": "demo", "agent": "codex"}},
        },
    ]
    proc = subprocess.run(
        [sys.executable, "-m", "synapseforge.mcp.server"],
        input="".join(json.dumps(item) + "\n" for item in requests),
        text=True,
        capture_output=True,
        env=env,
        cwd=str(tmp_path),
    )
    assert proc.returncode == 0, proc.stderr
    responses = [json.loads(line) for line in proc.stdout.splitlines()]
    assert [item["id"] for item in responses] == [1, 2, 3]
    names = {tool["name"] for tool in responses[1]["result"]["tools"]}
    assert "team_join" in names
    assert "team_claim_action" in names
    assert "team_reclaim_stale_locks" in names
    assert "team_leave" in names
    assert responses[2]["result"]["isError"] is False
    joined = json.loads(responses[2]["result"]["content"][0]["text"])
    assert joined["agent"] == "codex"
    assert joined["already_online"] is False


def test_claim_action_cli_mutex(tmp_path):
    doc = tmp_path / "brief.md"
    doc.write_text("x\n", encoding="utf-8")
    _run(tmp_path, ["open", "--document", str(doc), "--room", "mutex"])
    _run(tmp_path, ["join", "--room", "mutex", "--agent", "antigravity"])
    first = _run(
        tmp_path,
        ["claim-action", "--room", "mutex", "--agent", "antigravity", "--action-key", "push:main"],
    )
    assert first.returncode == 0, first.stderr
    # Same session_id (each CLI invocation is a new process / session) can renew.
    # A different agent in a different process must not steal a live claim.
    _run(tmp_path, ["join", "--room", "mutex", "--agent", "grok"])
    second = _run(
        tmp_path,
        ["claim-action", "--room", "mutex", "--agent", "grok", "--action-key", "push:main"],
    )
    assert second.returncode != 0
    assert "already claimed" in (second.stdout + second.stderr)
