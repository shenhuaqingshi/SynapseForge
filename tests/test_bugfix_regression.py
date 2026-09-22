"""
Regression tests for the cross-module bug-fix batch.

Each test reproduces a concrete defect that previously raised an exception,
silently dropped collaborator content, or produced non-monotonic metrics:

  1. `plan --json` crashed: SectionState has no `word_count_target` attribute.
  2. `lint` / `agent audit` crashed whenever an issue was found: LintIssue has
     no `suggestion` attribute (the field is `suggested_fix`).
  3. `agent draft` crashed after writing the file: StateManager has no
     `update_section` method, so state/actor/word-count were never persisted.
  4. Two sides independently adding the same section with different content
     (add/add conflict) silently kept "ours" and dropped "theirs" with zero
     conflicts reported.
  5. Citation richness score was non-monotonic: a document with a few
     citations scored below a document with no citations at all.
  6. MultiFormatExporter ignored workspace_root when loading config, did not
     HTML-escape manuscript/title content, and leaked internal comments.
  7. On Windows the msvcrt byte-range lock was taken on a 0-byte file, which
     always fails; the lock file must contain metadata (>= 1 byte) first.
"""

import io
import json
import os
import sys
from pathlib import Path

import pytest

from synapseforge.cli.agent_cmds import handle_agent_audit, handle_agent_draft
from synapseforge.cli.main import cmd_lint, cmd_plan
from synapseforge.core.conflict_resolver import SemanticConflictResolver
from synapseforge.core.exporter import MultiFormatExporter
from synapseforge.core.file_lock import AutoSectionLock
from synapseforge.core.scorecard import QualityScorecard


class MockArgs:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


MIN_CONFIG = """\
name: regression-project
document_title: Regression Test
sections:
  - id: sec_01
    title: Introduction
    file: sections/01_intro.md
    assigned_role: drafter
    word_count_target: 650
"""

# Deliberately fragmented prose that triggers Anti-AI paragraph-fragmentation
# warnings, so the lint/audit code paths that build issue payloads are exercised.
FRAGMENTED_MD = "# Intro\n\nThis is a very short fragmented line.\n\nAnother tiny fragment.\n"


def _make_project(root: Path) -> Path:
    (root / "sections").mkdir(parents=True, exist_ok=True)
    (root / "assets").mkdir(parents=True, exist_ok=True)
    (root / "synapseforge.yaml").write_text(MIN_CONFIG, encoding="utf-8")
    return root


def _run_cli(func, args):
    """Runs a CLI handler, capturing its --json stdout and returning parsed JSON."""
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        func(args)
    except SystemExit:
        # Some handlers exit(1) on failed gates; the JSON payload is printed first.
        pass
    finally:
        sys.stdout = old_stdout
    return json.loads(buf.getvalue())


# --- 1. plan --json ---------------------------------------------------------

def test_cmd_plan_json_includes_word_count_target(tmp_path, monkeypatch):
    _make_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    data = _run_cli(cmd_plan, MockArgs(json=True))

    assert data["ok"] is True
    assert len(data["plan"]) == 1
    assert data["plan"][0]["id"] == "sec_01"
    assert data["plan"][0]["word_count_target"] == 650


# --- 2. lint / agent audit issue serialization ------------------------------

def test_cmd_lint_json_serializes_issues(tmp_path, monkeypatch):
    _make_project(tmp_path)
    (tmp_path / "sections" / "01_intro.md").write_text(FRAGMENTED_MD, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    data = _run_cli(cmd_lint, MockArgs(json=True, target=None, ci=False))

    assert data["ok"] is True
    assert sum(len(r["issues"]) for r in data["reports"]) > 0
    for report in data["reports"]:
        for issue in report["issues"]:
            # The "suggestion" key must be populated from LintIssue.suggested_fix
            assert "suggestion" in issue


def test_agent_audit_json_serializes_issues(tmp_path, monkeypatch):
    _make_project(tmp_path)
    target = tmp_path / "sections" / "01_intro.md"
    target.write_text(FRAGMENTED_MD, encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    data = _run_cli(handle_agent_audit, MockArgs(target=str(target), json=True))

    assert "issues" in data
    assert len(data["issues"]) > 0


# --- 3. agent draft persists state ------------------------------------------

def test_agent_draft_persists_status_actor_and_word_count(tmp_path, monkeypatch):
    _make_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    content = "这是一段足够长的草稿内容，用于验证 draft 命令能够正确写入章节文件并同步更新项目状态台账中的状态、作者与字数。"
    data = _run_cli(
        handle_agent_draft,
        MockArgs(agent="Test-Agent", section="sec_01", content=content, content_file=None, json=True),
    )

    assert data["ok"] is True
    assert data["word_count"] > 0

    state = json.loads((tmp_path / ".synapse" / "state.json").read_text(encoding="utf-8"))
    sec = state["sections"]["sec_01"]
    assert sec["status"] == "drafting"
    assert sec["assigned_actor"] == "Test-Agent"
    assert sec["word_count"] == data["word_count"]


# --- 4. add/add conflict must preserve both sides --------------------------

def test_concurrent_addition_conflict_preserves_both_sides():
    resolver = SemanticConflictResolver()
    base = "# Existing\n\nBase body.\n"

    def addition(body):
        return f"\n<!-- SECTION:new_sec -->\n# New Section\n\n{body}\n<!-- END_SECTION:new_sec -->\n"

    result = resolver.merge_texts(
        base,
        base + addition("OURS independently drafted content"),
        base + addition("THEIRS independently drafted content"),
    )

    assert result.conflict_count >= 1
    assert "OURS independently drafted content" in result.merged_content
    assert "THEIRS independently drafted content" in result.merged_content
    assert "<<<<<<<" in result.merged_content and ">>>>>>>" in result.merged_content


def test_identical_concurrent_addition_auto_merges():
    resolver = SemanticConflictResolver()
    base = "# Existing\n\nBase body.\n"
    addition = "\n<!-- SECTION:new_sec -->\n# New Section\n\nIdentical body.\n<!-- END_SECTION:new_sec -->\n"

    result = resolver.merge_texts(base, base + addition, base + addition)
    assert result.conflict_count == 0
    assert "Identical body" in result.merged_content


# --- 5. citation score monotonicity -----------------------------------------

def _scorecard_with_text(root: Path, text: str):
    (root / "sections").mkdir(parents=True, exist_ok=True)
    (root / "sections" / "01.md").write_text("# 引言\n\n" + text + "\n", encoding="utf-8")
    return QualityScorecard(workspace_root=root).evaluate_document()


def test_citation_richness_score_is_monotonic(tmp_path):
    paragraph = (
        "本文围绕分布式多智能体协同写作中的状态一致性与冲突消解问题展开讨论，系统梳理了"
        "租约机制、文件加锁、三方合并以及拓扑排序等关键技术路径，并结合工程实践分析了各"
        "方案在并发场景下的适用边界与权衡取舍。"
    ) * 3

    no_cite = _scorecard_with_text(tmp_path / "no_cite", paragraph)
    with_cite = _scorecard_with_text(
        tmp_path / "with_cite",
        paragraph + " 相关结论可参见 @lamport1998paxos 的经典论述。",
    )

    score_no = no_cite["metrics"]["citation_richness_score"]
    score_yes = with_cite["metrics"]["citation_richness_score"]
    assert no_cite["metrics"]["total_citations"] == 0
    assert with_cite["metrics"]["total_citations"] >= 1
    # A document carrying citations must never score below one without any.
    assert score_yes >= score_no


# --- 6. exporter escaping, config scoping and comment stripping ------------

def test_exporter_escapes_html_and_strips_internal_comments(tmp_path):
    (tmp_path / "sections").mkdir(parents=True, exist_ok=True)
    (tmp_path / "sections" / "01.md").write_text(
        "# T <script>alert(1)</script>\n\n"
        "<!-- SynapseForge Section ID: sec_x -->\n"
        "Body containing <b> tags and an & ampersand.\n",
        encoding="utf-8",
    )

    exporter = MultiFormatExporter(workspace_root=tmp_path)
    assembled = exporter.assemble_full_document()
    assert "SynapseForge Section ID" not in assembled

    # No synapseforge.yaml exists here; export must fall back to defaults, not crash.
    result = exporter.export_all(title="A <b> B & C")
    assert result["ok"] is True

    html = (tmp_path / "dist" / "publication_standalone.html").read_text(encoding="utf-8")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "A &lt;b&gt; B &amp; C" in html


# --- 7. lock file non-empty (required for Windows msvcrt byte locking) ------

def test_lock_file_contains_metadata_while_held(tmp_path):
    with AutoSectionLock("sec_lock", "LockAgent", workspace_root=tmp_path) as lock:
        lock_file = tmp_path / ".synapse" / "locks" / "sec_lock.lock"
        assert lock_file.exists()
        # msvcrt.locking() on Windows can only lock bytes already present in the
        # file, so the lock file must be non-empty before the OS lock is taken.
        assert lock_file.stat().st_size > 0
        metadata = json.loads(lock_file.read_text(encoding="utf-8"))
        assert metadata["agent_name"] == "LockAgent"
        assert metadata["platform"]
