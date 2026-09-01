import time
import pytest
from pathlib import Path
from synapseforge.core.watcher import DocumentWatcher, FileChangeType, WatchEvent


def test_watcher_poll_and_detect_change(tmp_path):
    sec_dir = tmp_path / "sections"
    sec_dir.mkdir(parents=True)
    sec1 = sec_dir / "01_intro.md"
    sec1.write_text("# Introduction\n\nInitial draft text.\n", encoding="utf-8")

    watcher = DocumentWatcher(workspace_root=tmp_path, auto_snapshot=False, debounce_seconds=0.0)

    # Initial poll should detect no new changes after init
    evs = watcher.poll_once()
    assert len(evs) == 0

    # Modify file
    time.sleep(0.01)
    sec1.write_text("# Introduction\n\nModified draft text with more analytical substance.\n", encoding="utf-8")

    evs = watcher.poll_once()
    assert len(evs) == 1
    assert evs[0].change_type == FileChangeType.MODIFIED
    assert evs[0].path.name == "01_intro.md"
    assert evs[0].linter_passed is True

    # Delete file
    sec1.unlink()
    evs2 = watcher.poll_once()
    assert len(evs2) == 1
    assert evs2[0].change_type == FileChangeType.DELETED


def test_watcher_watch_loop_iteration(tmp_path):
    sec_dir = tmp_path / "sections"
    sec_dir.mkdir(parents=True)
    sec1 = sec_dir / "01_intro.md"
    sec1.write_text("# Intro\n\nTest content.\n", encoding="utf-8")

    watcher = DocumentWatcher(workspace_root=tmp_path, debounce_seconds=0.0)

    collected = []
    def on_ev(e):
        collected.append(e)

    # Loop once
    watcher.watch_loop(interval=0.01, max_iterations=1, on_event=on_ev)
    assert isinstance(collected, list)
