import json
import pytest
from pathlib import Path
from synapseforge.core.snapshot import SnapshotManager
from synapseforge.tools.cite_tool import CiteTool


def test_snapshot_manager_checkpoint_and_history():
    snap = SnapshotManager()
    res = snap.create_checkpoint(message="Unit test checkpoint", section_id="sec_01", author="TestRunner")
    assert res["ok"] is True
    assert "commit_hash" in res

    hist = snap.list_history(limit=5)
    assert isinstance(hist, list)
    assert len(hist) > 0


def test_cite_tool_list_and_add(tmp_path):
    bib_file = tmp_path / "test.bib"
    bib_file.write_text("""
@article{lamport1998paxos,
  author = {Leslie Lamport},
  title = {The Part-Time Parliament},
  year = {1998},
  journal = {ACM TOCS}
}
""", encoding="utf-8")

    tool = CiteTool(bib_path=bib_file)
    citations = tool.list_citations()
    assert len(citations) == 1
    assert citations[0]["key"] == "lamport1998paxos"

    # Add a new citation
    res = tool.add_bibtex_entry(
        key="shapiro2011crdt",
        entry_type="inproceedings",
        title="Conflict-free Replicated Data Types",
        author="Marc Shapiro et al.",
        year="2011",
        journal_or_book="SSS 2011"
    )
    assert res["ok"] is True
    assert res["key"] == "shapiro2011crdt"

    updated = tool.list_citations()
    assert len(updated) == 2
