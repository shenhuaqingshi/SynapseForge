import json
import threading
import time
import urllib.request
import urllib.parse
import pytest
from synapseforge.server.app import start_server


@pytest.fixture(scope="module")
def remote_server():
    server = start_server(host="127.0.0.1", port=18765)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)
    yield "http://127.0.0.1:18765"
    server.shutdown()
    server.server_close()


def test_server_get_index(remote_server):
    with urllib.request.urlopen(f"{remote_server}/") as resp:
        assert resp.status == 200
        html = resp.read().decode("utf-8")
        assert "SynapseForge Studio" in html
        assert "KaTeX" in html


def test_server_get_status_api(remote_server):
    with urllib.request.urlopen(f"{remote_server}/api/status") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["ok"] is True
        assert "sections_count" in data


def test_server_get_sections_api(remote_server):
    with urllib.request.urlopen(f"{remote_server}/api/sections") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["ok"] is True
        assert "sec_01" in data["sections"]


def test_server_post_save_api(remote_server):
    payload = json.dumps({"section_id": "sec_01", "content": "# Updated Abstract\n\nContent..."}).encode("utf-8")
    req = urllib.request.Request(
        f"{remote_server}/api/doc/save",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["ok"] is True
        assert data["word_count"] > 0


def test_server_session_get_and_post(remote_server):
    # 1. GET session
    with urllib.request.urlopen(f"{remote_server}/api/session") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["ok"] is True
        assert "room_id" in data["session"]

    # 2. POST update session state
    payload = json.dumps({
        "room_id": "room-special-sync",
        "room_name": "Special AGI Swarm",
        "active_section": "sec_05",
        "draftContent": "# Testing draft state"
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{remote_server}/api/session",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200
        res_data = json.loads(resp.read().decode("utf-8"))
        assert res_data["ok"] is True
        assert res_data["session"]["room_id"] == "room-special-sync"
