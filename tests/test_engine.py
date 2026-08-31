from pathlib import Path
import pytest
from synapseforge.config import ProjectConfig, SectionSpec
from synapseforge.core.engine import SwarmEngine
from synapseforge.core.state import SectionStatus, StateManager


def test_state_manager_dag_topological_sort(tmp_path):
    config = ProjectConfig(
        name="test-project",
        sections=[
            SectionSpec(id="sec_01", title="Intro", file="sec1.md", assigned_role="drafter", dependencies=[]),
            SectionSpec(id="sec_02", title="Theory", file="sec2.md", assigned_role="drafter", dependencies=["sec_01"]),
            SectionSpec(id="sec_03", title="Eval", file="sec3.md", assigned_role="drafter", dependencies=["sec_02"]),
        ],
        root_dir=tmp_path,
    )
    mgr = StateManager(tmp_path)
    mgr.sync_from_config(config)
    order = mgr.get_topological_order()
    assert order == ["sec_01", "sec_02", "sec_03"]


def test_section_claim_and_release(tmp_path):
    config = ProjectConfig(
        name="test-project",
        sections=[
            SectionSpec(id="sec_01", title="Intro", file="sec1.md", assigned_role="drafter"),
        ],
        root_dir=tmp_path,
    )
    mgr = StateManager(tmp_path)
    mgr.sync_from_config(config)
    assert mgr.claim_section("sec_01", actor="Agent-A")
    assert not mgr.claim_section("sec_01", actor="Agent-B")
    assert mgr.release_section("sec_01", actor="Agent-A")
    assert mgr.claim_section("sec_01", actor="Agent-B")
