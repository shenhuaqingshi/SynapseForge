from pathlib import Path

from synapseforge.core.team_bus import TeamBus
from synapseforge.core.team_launch import (
    doctor,
    launch_argv,
    launch_room,
    paste_prompt,
    wait_for_joins,
    write_launch_bundle,
)


def test_paste_prompt_submitter_split():
    grok = paste_prompt("r", "grok", "review", "/tmp/a.md", "/tmp", "goal")
    agy = paste_prompt("r", "antigravity", "impl", "/tmp/a.md", "/tmp", "goal")
    assert "not the submitter" in grok
    assert "only submitter" in agy
    assert "synapseforge team join" in grok


def test_launch_argv_uses_real_host_flags(tmp_path):
    prompt = tmp_path / "p.txt"
    prompt.write_text("join", encoding="utf-8")
    assert "--prompt-file" in launch_argv("grok", "/bin/grok", prompt)
    assert "--prompt-interactive" in launch_argv("antigravity", "/bin/agy", prompt)
    assert "exec" in launch_argv("codex", "/bin/codex", prompt)


def test_write_launch_bundle_keeps_script_short(tmp_path):
    fake = tmp_path / "fake-grok"
    fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    bundle = write_launch_bundle(
        workspace=str(tmp_path),
        room="paper",
        agent="grok",
        role="review",
        document=str(tmp_path / "brief.md"),
        objective="draft",
        binary=str(fake),
    )
    script = Path(bundle["script_path"]).read_text(encoding="utf-8")
    prompt = Path(bundle["prompt_path"]).read_text(encoding="utf-8")
    assert "SYNAPSEFORGE_ROOM=paper" in script
    assert "do script" not in script
    assert "You occupy this identity exclusively" in prompt
    assert len(script) < 1200


def test_wait_for_joins_reports_live_seats(tmp_path):
    store = TeamBus(tmp_path / "team.db")
    store.join("demo", "codex", "lead")
    joined, pending = wait_for_joins(store, "demo", ["codex", "grok"], timeout_seconds=0)
    assert joined == ["codex"]
    assert pending == ["grok"]


def test_launch_room_without_terminal_prints_prompts(tmp_path):
    doc = tmp_path / "brief.md"
    doc.write_text("# Brief\n", encoding="utf-8")
    payload = launch_room(
        document=str(doc),
        workspace=str(tmp_path),
        room="paper",
        open_terminal=False,
        wait_join_seconds=0,
    )
    assert payload["ok"] is True
    assert payload["room"] == "paper"
    assert "grok" in payload["paste_prompts"]
    assert "codex" in payload["paste_prompts"]
    assert "antigravity" in payload["paste_prompts"]
    assert payload["terminals"] == [] or isinstance(payload["terminals"], list)


def test_doctor_mcp_handshake(tmp_path, monkeypatch):
    monkeypatch.setenv("SYNAPSEFORGE_TEAM_DB", str(tmp_path / "team.db"))
    monkeypatch.setenv("SYNAPSEFORGE_WORKSPACE", str(tmp_path))
    result = doctor(workspace=str(tmp_path))
    assert result["mcp_ndjson"]["ok"] is True
    assert result["mcp_content_length"]["ok"] is True
    assert result["ok"] is True
