import pytest
from pathlib import Path
from synapseforge.core.vault import WorkspaceVault, VAULT_STRUCTURE


def test_vault_structure_initialization(tmp_path):
    vault = WorkspaceVault(workspace_root=tmp_path)
    vault.ensure_vault_structure()
    for folder in VAULT_STRUCTURE.keys():
        assert (tmp_path / folder).exists()
        assert (tmp_path / folder).is_dir()


def test_vault_auto_import_external_file(tmp_path):
    # Create external file outside workspace
    external_dir = tmp_path / "outside_downloads"
    external_dir.mkdir()
    external_file = external_dir / "external_literature.md"
    external_file.write_text("# External Research Note\nImportant data points here.", encoding="utf-8")

    workspace = tmp_path / "my_project"
    workspace.mkdir()

    vault = WorkspaceVault(workspace_root=workspace)
    res = vault.import_external_file(external_path=external_file)

    assert res["ok"] is True
    assert res["status"] == "copied"
    assert res["category"] == "imports"
    assert (workspace / "imports" / "external_literature.md").exists()

    # Verify content preserved
    copied_text = (workspace / "imports" / "external_literature.md").read_text(encoding="utf-8")
    assert "Important data points here." in copied_text

    # Re-importing same file should return already_imported status
    re_res = vault.import_external_file(external_path=external_file)
    assert re_res["ok"] is True
    assert re_res["status"] == "already_imported"


def test_vault_categorized_list(tmp_path):
    vault = WorkspaceVault(workspace_root=tmp_path)
    (tmp_path / "sections" / "01_intro.md").write_text("# Intro", encoding="utf-8")
    (tmp_path / "figures" / "plot_loss.png").write_bytes(b"\x89PNG\r\n\x1a\n")

    res = vault.list_vault_files()
    assert res["ok"] is True
    assert res["categories"]["sections"]["file_count"] >= 1
    assert res["categories"]["figures"]["file_count"] >= 1
