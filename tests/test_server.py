import json
import shutil
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from synapseforge.server.app import start_server


def _free_port():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@pytest.fixture
def remote_server(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    src_sections = Path("sections")
    dest_sections = workspace / "sections"
    dest_sections.mkdir()
    if src_sections.exists():
        for path in list(src_sections.glob("*.md"))[:3]:
            shutil.copy(path, dest_sections / path.name)
    else:
        (dest_sections / "01_abstract.md").write_text("# Abstract\n\nHello.\n", encoding="utf-8")
    yaml_src = Path("synapseforge.yaml")
    if yaml_src.exists():
        shutil.copy(yaml_src, workspace / "synapseforge.yaml")
    subprocess.run(["git", "init"], cwd=workspace, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=workspace, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=test@example.com", "-c", "user.name=Test", "commit", "-m", "init"],
        cwd=workspace,
        capture_output=True,
    )
    port = _free_port()
    server = start_server(host="127.0.0.1", port=port, workspace=workspace)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    yield f"http://127.0.0.1:{port}", workspace
    server.shutdown()
    server.server_close()


def test_server_get_index(remote_server):
    base, _ = remote_server
    with urllib.request.urlopen(f"{base}/") as resp:
        assert resp.status == 200
        html = resp.read().decode("utf-8")
        assert "SynapseForge Studio" in html
        assert "KaTeX" in html


def test_server_get_status_api(remote_server):
    base, _ = remote_server
    with urllib.request.urlopen(f"{base}/api/status") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["ok"] is True
        assert "sections_count" in data


def test_server_get_sections_api(remote_server):
    base, _ = remote_server
    with urllib.request.urlopen(f"{base}/api/sections") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["ok"] is True
        assert data["sections"]


def test_server_post_save_api(remote_server):
    base, workspace = remote_server
    payload = json.dumps({"section_id": "sec_01", "content": "# Updated Abstract\n\nContent..."}).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/api/doc/save",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["ok"] is True
        assert data["word_count"] > 0
    saved = list((workspace / "sections").glob("01*.md"))
    assert saved
    assert "Updated Abstract" in saved[0].read_text(encoding="utf-8")


def test_server_session_get_and_post(remote_server):
    base, _ = remote_server
    with urllib.request.urlopen(f"{base}/api/session") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["ok"] is True
        assert "room_id" in data["session"]

    payload = json.dumps({
        "room_id": "room-special-sync",
        "room_name": "Special AGI Swarm",
        "active_section": "sec_05",
        "draftContent": "# Testing draft state"
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/api/session",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        res_data = json.loads(resp.read().decode("utf-8"))
        assert res_data["ok"] is True
        assert res_data["session"]["room_id"] == "room-special-sync"


def test_server_dispatch_rejects_unknown_agent(remote_server):
    base, _ = remote_server
    payload = json.dumps({
        "agent": "not-a-real-cli",
        "section_id": "sec_01",
        "prompt": "Draft the abstract",
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/api/agent/dispatch",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(req)
    assert exc.value.code == 400
    body = json.loads(exc.value.read().decode("utf-8"))
    assert body["ok"] is False
    assert "not recognized" in body["error"] or "not found" in body["error"]


def test_server_team_status_and_directive(remote_server):
    base, _ = remote_server
    with urllib.request.urlopen(f"{base}/api/team/status") as resp:
        data = json.loads(resp.read().decode("utf-8"))
    assert data["ok"] is True
    assert data["room"]["name"]
    payload = json.dumps({
        "agent": "human",
        "kind": "directive",
        "message": "Stop submitting",
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/api/team/say",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as resp:
        posted = json.loads(resp.read().decode("utf-8"))
    assert posted["ok"] is True
    assert posted["kind"] == "directive"
    with urllib.request.urlopen(f"{base}/api/team/messages") as resp:
        inbox = json.loads(resp.read().decode("utf-8"))
    assert any(m["body"] == "Stop submitting" for m in inbox["messages"])
