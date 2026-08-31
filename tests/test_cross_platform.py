import os
import sys
import pytest
from pathlib import Path
from synapseforge.core.file_lock import AutoSectionLock, HAS_FCNTL, HAS_MSVCRT
from synapseforge.core.local_agent_cli import LocalAgentCLIManager
from synapseforge.network.tailscale_mesh import TailscaleMeshManager
from synapseforge.tools.pdf_tool import PDFTool


def test_cross_platform_lock_metadata(tmp_path):
    with AutoSectionLock("sec_plat", "CrossPlatAgent", workspace_root=tmp_path) as lock:
        lock.write_draft("# Cross Platform Draft", tmp_path / "sec_plat.md")
        lock_file = tmp_path / ".synapse" / "locks" / "sec_plat.lock"
        assert lock_file.exists()
        content = lock_file.read_text(encoding="utf-8")
        assert "CrossPlatAgent" in content
        assert "platform" in content


def test_cross_platform_tailscale_finder():
    mgr = TailscaleMeshManager()
    # Should resolve without raising exception
    bin_path = mgr._find_tailscale_bin()
    assert bin_path is None or isinstance(bin_path, str)


def test_cross_platform_pdf_typst_finder():
    tool = PDFTool()
    bin_path = tool._find_typst_bin()
    assert isinstance(bin_path, str)
    assert len(bin_path) > 0


def test_cross_platform_cli_detection(tmp_path):
    mgr = LocalAgentCLIManager(workspace_root=tmp_path)
    clis = mgr.detect_available_clis()
    assert len(clis) > 0
    for c in clis:
        assert "platform" in c
