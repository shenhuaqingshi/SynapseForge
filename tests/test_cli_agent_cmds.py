import json
import pytest
from pathlib import Path
from synapseforge.cli.agent_cmds import handle_agent_list, handle_agent_claim, handle_agent_release, handle_agent_patch
from synapseforge.cli.doc_cmds import handle_doc_get, handle_doc_stats


class MockArgs:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_cli_agent_list_json(capsys):
    args = MockArgs(json=True)
    handle_agent_list(args)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["ok"] is True
    assert len(data["agents"]) >= 4


def test_cli_agent_claim_and_release(capsys):
    args_claim = MockArgs(agent="Drafter-Narrative", section="sec_01_abstract", lease=1800, json=True)
    handle_agent_claim(args_claim)
    captured = capsys.readouterr()
    res = json.loads(captured.out)
    assert res["ok"] is True
    assert res["section_id"] == "sec_01_abstract"

    args_rel = MockArgs(agent="Drafter-Narrative", section="sec_01_abstract", json=True)
    handle_agent_release(args_rel)
    captured = capsys.readouterr()
    res2 = json.loads(captured.out)
    assert res2["ok"] is True


def test_cli_doc_stats_json(capsys):
    args = MockArgs(json=True)
    handle_doc_stats(args)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["ok"] is True
    assert data["total_words"] > 1000
    assert len(data["sections"]) >= 5


def test_cli_doc_get_json(capsys):
    args = MockArgs(section="sec_01_abstract", json=True)
    handle_doc_get(args)
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["ok"] is True
    assert data["section_id"] == "sec_01_abstract"
    assert len(data["ast_blocks"]) > 0
