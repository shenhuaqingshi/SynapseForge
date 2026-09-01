import io
import json
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from synapseforge.tools.cite_tool import CiteTool


def test_cite_tool_clean_doi():
    tool = CiteTool()
    assert tool.clean_doi("https://doi.org/10.1145/3372278.3390678") == "10.1145/3372278.3390678"
    assert tool.clean_doi("doi:10.1038/s41586-020-2649-2") == "10.1038/s41586-020-2649-2"
    assert tool.clean_doi("10.1000/182") == "10.1000/182"


def test_cite_tool_lookup_doi_mocked(tmp_path):
    tool = CiteTool(bib_path=tmp_path / "bibliography.bib", workspace_root=tmp_path)

    mock_resp_data = {
        "message": {
            "title": ["Distributed Consensus under Byzantine Faults"],
            "author": [
                {"given": "Leslie", "family": "Lamport"},
                {"given": "Robert", "family": "Shostak"},
            ],
            "published-print": {"date-parts": [[1982]]},
            "container-title": ["ACM Transactions on Programming Languages and Systems"],
            "DOI": "10.1145/357172.357176",
            "URL": "https://doi.org/10.1145/357172.357176",
            "type": "journal-article",
        }
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_resp_data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = tool.lookup_doi("10.1145/357172.357176")

    assert res["ok"] is True
    assert res["key"] == "lamport1982distributed"
    assert "Leslie Lamport" in res["author"]
    assert res["year"] == "1982"
    assert "ACM Transactions" in res["journal"]


def test_cite_tool_search_crossref_mocked(tmp_path):
    tool = CiteTool(bib_path=tmp_path / "bibliography.bib", workspace_root=tmp_path)

    mock_resp_data = {
        "message": {
            "items": [
                {
                    "title": ["Raft: In Search of an Understandable Consensus Algorithm"],
                    "author": [{"given": "Diego", "family": "Ongaro"}, {"given": "John", "family": "Ousterhout"}],
                    "published-print": {"date-parts": [[2014]]},
                    "container-title": ["USENIX ATC '14"],
                    "DOI": "10.5555/2643634.2643666",
                    "URL": "https://doi.org/10.5555/2643634.2643666",
                }
            ]
        }
    }

    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(mock_resp_data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        res = tool.search_crossref("Raft consensus", limit=1)

    assert res["ok"] is True
    assert res["count"] == 1
    assert res["results"][0]["key"] == "ongaro2014raft"
    assert "Ongaro" in res["results"][0]["author"]


def test_cite_tool_validate_citations(tmp_path):
    bib_file = tmp_path / "bibliography.bib"
    bib_content = """@article{lamport1982,
  author = {Lamport, Leslie},
  title  = {The Byzantine Generals Problem},
  year   = {1982},
  journal= {TOPLAS}
}

@article{unused2020,
  author = {Smith, John},
  title  = {Some Unused Paper},
  year   = {2020}
}
"""
    bib_file.write_text(bib_content, encoding="utf-8")

    sec_dir = tmp_path / "sections"
    sec_dir.mkdir(parents=True)
    sec_file = sec_dir / "01_intro.md"
    sec_file.write_text("# Intro\n\nConsensus is critical [@lamport1982] and also [@missing2025].\n", encoding="utf-8")

    tool = CiteTool(bib_path=bib_file, workspace_root=tmp_path)
    res = tool.validate_citations(sections_dir=sec_dir)

    assert res["ok"] is True
    assert res["valid"] is False  # Because missing2025 is missing
    assert "missing2025" in res["unresolved_citations"]
    assert "unused2020" in res["unused_in_bibliography"]
    assert len(res["incomplete_entries"]) == 0
