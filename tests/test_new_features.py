import json
import pytest
from pathlib import Path
from synapseforge.core.ingest import DocumentIngestor
from synapseforge.core.figure_linker import FigureLinker
from synapseforge.core.llm_router import LLMRouter


def test_document_ingestor_add_and_list(tmp_path):
    ingestor = DocumentIngestor(workspace_root=tmp_path)
    res = ingestor.ingest_text_or_note(
        source_id="paxos_notes",
        title="Paxos Formal Consensus Summary",
        content="Lamport's classical multi-decree Paxos algorithm guarantees safety under asynchronous network partitions.",
        tags=["consensus", "theory"]
    )
    assert res["ok"] is True
    assert res["source_id"] == "paxos_notes"

    sources = ingestor.list_ingested_sources()
    assert len(sources) == 1
    assert sources[0]["id"] == "paxos_notes"


def test_figure_linker_insert(tmp_path):
    sec_dir = tmp_path / "sections"
    sec_dir.mkdir(parents=True, exist_ok=True)
    sec_file = sec_dir / "05_benchmarks.md"
    sec_file.write_text("# 5. 基准测试\n\n本章节评估系统性能。", encoding="utf-8")

    linker = FigureLinker(workspace_root=tmp_path)
    res = linker.insert_figure(
        section_id="05_benchmarks",
        image_path="assets/nature_bench.png",
        caption="多智能体跨节点收敛时延对比",
        fig_num=2,
        discussion_bridge="如图 2 所示，随着并发节点数由 1 扩展至 64，AST 共识时延收敛于对数曲线。"
    )
    assert res["ok"] is True
    assert res["fig_num"] == 2

    content = sec_file.read_text(encoding="utf-8")
    assert "图 2：多智能体跨节点收敛时延对比" in content
    assert "如图 2 所示" in content


def test_llm_router_list_and_ping(monkeypatch):
    router = LLMRouter()
    providers = router.list_providers()
    assert len(providers) >= 3

    # Unreachable endpoint must be reported as offline, not faked as online
    import urllib.request

    def _fail(req, timeout=0):
        raise ConnectionError("endpoint unreachable")

    monkeypatch.setattr(urllib.request, "urlopen", _fail)
    res = router.ping_provider("deepseek")
    assert res["ok"] is False
    assert res["status"] == "unreachable"
    assert res["latency_ms"] is None
    assert router.providers["deepseek"].status == "unreachable"
