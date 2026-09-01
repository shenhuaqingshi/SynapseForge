"""
SynapseForge Command Line Interface (CLI).
Comprehensive, programmatic toolkit for Solo Humans, Multi-Agent Swarms, Quality Gating, Tailscale Mesh, and GitOps workflows.
Supports machine-readable JSON output (--json) across all subcommands.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

from synapseforge import __version__
from synapseforge.cli.agent_cmds import (
    handle_agent_audit,
    handle_agent_claim,
    handle_agent_detect_clis,
    handle_agent_draft,
    handle_agent_list,
    handle_agent_patch,
    handle_agent_prompt,
    handle_agent_register_cli,
    handle_agent_release,
    handle_agent_roles,
    handle_agent_run_cli,
)
from synapseforge.cli.team_cmds import handle_team
from synapseforge.cli.doc_cmds import handle_doc_get, handle_doc_stats
from synapseforge.config import ProjectConfig, load_config
from synapseforge.core.conflict_resolver import SemanticConflictResolver
from synapseforge.core.engine import SwarmEngine
from synapseforge.github_bridge.ci_reporter import CIReporter
from synapseforge.github_bridge.issue_orchestrator import IssueTaskOrchestrator
from synapseforge.github_bridge.pr_reviewer import PRReviewRunner
from synapseforge.linters import LintSuite
from synapseforge.core.exporter import MultiFormatExporter
from synapseforge.core.figure_linker import FigureLinker
from synapseforge.core.ingest import DocumentIngestor
from synapseforge.core.llm_router import LLMRouter
from synapseforge.core.notifier import NotificationDispatcher
from synapseforge.core.scorecard import QualityScorecard
from synapseforge.core.semantic_diff import SemanticASTDiffer
from synapseforge.core.snapshot import SnapshotManager
from synapseforge.core.user_prompts import UserPromptManager
from synapseforge.core.vault import WorkspaceVault
from synapseforge.core.variant_synthesizer import MultiDocumentSynthesizer, VariantManager
from synapseforge.core.watcher import DocumentWatcher
from synapseforge.network.room_sync import DistributedRoomManager
from synapseforge.network.tailscale_mesh import TailscaleMeshManager
from synapseforge.renderers.pipeline import PublicationPipeline
from synapseforge.security.acl import NodeAccessController
from synapseforge.security.crypto_vault import CryptoVault
from synapseforge.security.redactor import ConfidentialityRedactor
from synapseforge.tools import CiteTool, OfficeTool, PDFTool, SciPlotTool
import time


# ANSI Terminal Colors
class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"


def print_banner():
    banner = fr"""{Color.CYAN}{Color.BOLD}
  ___                             ___                 
 / __|_  _ _ _  __ _ _ __  ___ ___| __|__ _ _ __ _ ___ 
 \__ \ || | ' \/ _` | '_ \(_-</ -_) _/ _ \ '_/ _` / -_)
 |___/\_, |_||_\__,_| .__/__/\___|_| \___/_| \__, \___|
      |__/          |_|                      |___/     
    {Color.GRAY}Solo-Human & Multi-Agent Swarm Collaborative Writing Engine v{__version__}{Color.RESET}
"""
    print(banner)


def cmd_init(args):
    """Initializes a new SynapseForge collaborative project in the current directory."""
    root = Path.cwd()
    config_file = root / "synapseforge.yaml"
    if config_file.exists() and not args.force:
        print(f"{Color.YELLOW}Warning: synapseforge.yaml already exists. Use --force to overwrite.{Color.RESET}")
        return

    (root / "sections").mkdir(parents=True, exist_ok=True)
    (root / "assets").mkdir(parents=True, exist_ok=True)
    (root / "dist").mkdir(parents=True, exist_ok=True)
    (root / ".synapse" / "rooms").mkdir(parents=True, exist_ok=True)

    print(f"{Color.GREEN}✓ Initialized SynapseForge project at: {root}{Color.RESET}")


def cmd_plan(args):
    engine = SwarmEngine()
    sections = engine.plan_document()
    
    if getattr(args, "json", False):
        data = [
            {
                "order": idx,
                "id": s.id,
                "title": s.title,
                "file": s.file,
                "role": s.assigned_role,
                "word_count_target": s.word_count_target,
                "dependencies": s.dependencies,
            }
            for idx, s in enumerate(sections, 1)
        ]
        print(json.dumps({"ok": True, "plan": data}, indent=2, ensure_ascii=False))
        return

    print(f"\n{Color.CYAN}{Color.BOLD}Document Structure Plan (Topological Order):{Color.RESET}")
    print(f"{'Order':<6} | {'Section ID':<25} | {'Role':<12} | {'Target File':<35}")
    print("-" * 85)
    for idx, s in enumerate(sections, 1):
        print(f"{idx:<6} | {s.id:<25} | {s.assigned_role:<12} | {s.file:<35}")
    print(f"\n{Color.GREEN}✓ Document plan synced with {len(sections)} sections.{Color.RESET}\n")


def cmd_status(args):
    engine = SwarmEngine()
    tree = engine.get_document_tree()

    if getattr(args, "json", False):
        print(json.dumps({"ok": True, "status_ledger": tree}, indent=2, ensure_ascii=False))
        return

    print(f"\n{Color.CYAN}{Color.BOLD}SynapseForge Swarm Status:{Color.RESET}")
    print(f"{'Section ID':<25} | {'Status':<15} | {'Words':<8} | {'Actor':<18} | {'File'}")
    print("-" * 90)
    total_words = 0
    for item in tree:
        total_words += item["word_count"]
        status_color = Color.GREEN if item["status"] == "merged" else (Color.YELLOW if item["status"] == "drafting" else Color.GRAY)
        print(f"{item['id']:<25} | {status_color}{item['status']:<15}{Color.RESET} | {item['word_count']:<8} | {item['assigned_actor']:<18} | {item['file']}")
    print("-" * 90)
    print(f"{Color.BOLD}Total Document Words: {total_words}{Color.RESET}\n")


def cmd_lint(args):
    config = load_config()
    bib_file = Path.cwd() / config.quality_gates.citations.get("bib_file", "bibliography.bib")
    suite = LintSuite(quality_gates=config.quality_gates, bib_file=bib_file, glossary=config.glossary)

    targets: List[Path] = []
    if args.target:
        p = Path(args.target)
        if p.is_dir():
            targets = list(p.glob("**/*.md"))
        elif p.exists():
            targets = [p]
        else:
            if getattr(args, "json", False):
                print(json.dumps({"ok": False, "error": f"Target path not found: {args.target}"}))
            else:
                print(f"{Color.RED}✖ Target path not found: {args.target}{Color.RESET}")
            sys.exit(1)
    else:
        sec_dir = Path.cwd() / "sections"
        targets = list(sec_dir.glob("*.md")) if sec_dir.exists() else list(Path.cwd().glob("*.md"))

    if not targets:
        if getattr(args, "json", False):
            print(json.dumps({"ok": True, "files_scanned": 0, "passed": True}))
        else:
            print(f"{Color.YELLOW}No markdown files found to lint.{Color.RESET}")
        return

    all_passed = True
    reports_data = []

    for t in sorted(targets):
        report = suite.lint_file(t)
        if not report.passed:
            all_passed = False
        reports_data.append({
            "file": os.path.relpath(t, Path.cwd()),
            "passed": report.passed,
            "errors": report.total_errors,
            "warnings": report.total_warnings,
            "issues": [
                {
                    "linter": i.linter_name,
                    "severity": i.severity,
                    "line": i.line_start,
                    "message": i.message,
                    "suggestion": i.suggested_fix,
                }
                for i in report.all_issues
            ]
        })

    if getattr(args, "json", False):
        print(json.dumps({"ok": True, "all_passed": all_passed, "reports": reports_data}, indent=2, ensure_ascii=False))
        if not all_passed and args.ci:
            sys.exit(1)
        return

    print(f"{Color.CYAN}{Color.BOLD}Running SynapseForge Document Quality Gates on {len(targets)} files...{Color.RESET}\n")
    for r in reports_data:
        status_str = f"{Color.GREEN}PASSED{Color.RESET}" if r["passed"] else f"{Color.RED}FAILED{Color.RESET}"
        print(f"[{status_str}] {r['file']} (Errors: {r['errors']}, Warnings: {r['warnings']})")
        for issue in r["issues"]:
            icon = f"{Color.RED}✖ Error{Color.RESET}" if issue["severity"] == "error" else f"{Color.YELLOW}⚠ Warning{Color.RESET}"
            print(f"  {icon} [{issue['linter']}] Line {issue['line']}: {issue['message']}")

    print("\n" + "=" * 60)
    if all_passed:
        print(f"{Color.GREEN}{Color.BOLD}✓ All Document Quality Gates Passed! Publication-Grade Tone Verified.{Color.RESET}")
    else:
        print(f"{Color.RED}{Color.BOLD}✖ Quality Gates Failed. Please resolve errors before merging.{Color.RESET}")
        if args.ci:
            sys.exit(1)


def cmd_merge(args):
    resolver = SemanticConflictResolver(ours_label=args.ours_label, theirs_label=args.theirs_label)
    base_text = Path(args.base).read_text(encoding="utf-8") if Path(args.base).exists() else ""
    ours_text = Path(args.ours).read_text(encoding="utf-8") if Path(args.ours).exists() else ""
    theirs_text = Path(args.theirs).read_text(encoding="utf-8") if Path(args.theirs).exists() else ""

    res = resolver.merge_texts(base_text, ours_text, theirs_text)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(res.merged_content, encoding="utf-8")

    if getattr(args, "json", False):
        print(json.dumps({
            "ok": True,
            "output": str(out_path),
            "auto_resolved": res.resolved_auto_count,
            "conflicts": res.conflict_count,
        }, indent=2))
        return

    print(f"\n{Color.CYAN}{Color.BOLD}Semantic AST 3-Way Merge Result:{Color.RESET}")
    print(f"  - Output: {out_path}")
    print(f"  - Auto-Resolved Sections: {res.resolved_auto_count}")
    print(f"  - Semantic Conflicts: {res.conflict_count}")


def cmd_review(args):
    runner = PRReviewRunner()
    res = runner.run_full_pr_review(base_ref=args.base, pr_number=args.pr)
    
    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
        if not res["all_passed"] and args.ci:
            sys.exit(1)
        return

    print(f"{Color.CYAN}{Color.BOLD}Running SynapseForge Multi-Agent Peer Review...{Color.RESET}")
    print("\n" + res["summary_markdown"] + "\n")
    if not res["all_passed"] and args.ci:
        sys.exit(1)


def cmd_build(args):
    engine = SwarmEngine()
    master_md = engine.compile_full_document()
    pipeline = PublicationPipeline(config=engine.config)
    res = pipeline.build_all(master_md)

    if getattr(args, "json", False):
        print(json.dumps({
            "ok": True,
            "document_title": res.document_title,
            "output_dir": res.output_dir,
            "total_words": res.total_words,
            "files": res.generated_files,
        }, indent=2, ensure_ascii=False))
        return

    print(f"\n{Color.GREEN}{Color.BOLD}✓ Publication Artifacts Successfully Generated!{Color.RESET}")
    print(f"  - Document: {res.document_title}")
    print(f"  - Output Directory: {res.output_dir}")
    print(f"  - Total Words: {res.total_words}")
    for f in res.generated_files:
        print(f"    • {f}")


def cmd_mesh(args):
    """Inspects Tailscale P2P WireGuard mesh network status and cross-regional latency."""
    config = load_config()
    mesh = TailscaleMeshManager(tailnet_name=config.tailscale.tailnet, port=config.tailscale.mesh_port)
    topo = mesh.get_mesh_status()

    if getattr(args, "json", False):
        data = {
            "ok": True,
            "tailnet": topo.tailnet_name,
            "local_node": topo.local_node_id,
            "local_ip": topo.local_ip,
            "total_nodes": topo.total_nodes,
            "direct_p2p_ratio": topo.direct_p2p_ratio,
            "average_latency_ms": topo.average_latency_ms,
            "nodes": [
                {
                    "hostname": n.hostname,
                    "tailscale_ip": n.tailscale_ip,
                    "region": n.region,
                    "role": n.role,
                    "latency_ms": n.latency_ms,
                    "direct_p2p": n.direct_p2p,
                }
                for n in topo.connected_nodes
            ]
        }
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return

    print(f"\n{Color.CYAN}{Color.BOLD}🔒 Tailscale Mesh Topology ({topo.tailnet_name}):{Color.RESET}")
    print(f"  - Local Node: {topo.local_node_id} ({topo.local_ip})")
    print(f"  - Total Swarm Nodes: {topo.total_nodes} | Direct P2P Ratio: {topo.direct_p2p_ratio * 100:.0f}% | Avg Latency: {topo.average_latency_ms}ms\n")
    
    print(f"{'Node ID':<22} | {'Tailscale IP':<15} | {'Region':<22} | {'Role':<16} | {'RTT':<8} | {'P2P'}")
    print("-" * 98)
    for n in topo.connected_nodes:
        p2p_str = f"{Color.GREEN}Direct UDP{Color.RESET}" if n.direct_p2p else f"{Color.YELLOW}DERP Relay{Color.RESET}"
        print(f"{n.hostname:<22} | {n.tailscale_ip:<15} | {n.region:<22} | {n.role:<16} | {n.latency_ms:>5.1f}ms | {p2p_str}")
    print("-" * 98 + "\n")


def cmd_room(args):
    """Manages distributed shared rooms across Tailscale mesh nodes."""
    room_mgr = DistributedRoomManager()
    
    if args.room_action == "list" or not args.room_action:
        rooms = room_mgr.list_rooms()
        if getattr(args, "json", False):
            print(json.dumps({"ok": True, "rooms": [r.to_dict() for r in rooms]}, indent=2, ensure_ascii=False))
            return
        print(f"\n{Color.CYAN}{Color.BOLD}🏢 Decentralized Shared Rooms across Tailscale Mesh:{Color.RESET}")
        print(f"{'Slug / ID':<30} | {'Room Name':<28} | {'Synced Nodes':<14} | {'Members':<8} | {'Owner'}")
        print("-" * 96)
        for r in rooms:
            nodes_str = f"{len(r.synced_nodes)} Nodes [✓]"
            print(f"{r.slug:<30} | {r.name:<28} | {Color.GREEN}{nodes_str:<14}{Color.RESET} | {len(r.members):<8} | @{r.owner_name}")
        print("-" * 96 + "\n")

    elif args.room_action == "create":
        name = args.name
        title = args.title or name
        doc_type = args.type or "academic_whitepaper"
        room = room_mgr.create_shared_room(name=name, document_title=title, document_type=doc_type)
        if getattr(args, "json", False):
            print(json.dumps({"ok": True, "room": room.to_dict()}, indent=2, ensure_ascii=False))
            return
        print(f"\n{Color.GREEN}{Color.BOLD}✓ Shared Room Successfully Created & Replicated across Tailscale Mesh!{Color.RESET}")
        print(f"  - Room Slug: {room.slug}")
        print(f"  - Room ID: {room.room_id}")
        print(f"  - Synchronized Nodes: {', '.join(room.synced_nodes)}")
        print(f"  - Members Enrolled: {len(room.members)}\n")

    elif args.room_action == "join":
        room = room_mgr.join_shared_room(args.room_id, member_name=args.user or "xb")
        if getattr(args, "json", False):
            print(json.dumps({"ok": room is not None, "room": room.to_dict() if room else None}, indent=2))
            return
        if room:
            print(f"{Color.GREEN}✓ Node successfully joined shared room '{room.name}' (Version {room.state_version}){Color.RESET}")
        else:
            print(f"{Color.RED}✖ Room '{args.room_id}' not found.{Color.RESET}")


def cmd_office(args):
    tool = OfficeTool()
    if args.office_action == "create-docx":
        input_path = Path(args.input)
        output_path = Path(args.output)
        res = tool.create_docx_from_markdown(input_path, output_path, title=args.title)
    elif args.office_action == "inspect":
        res = tool.inspect_file(Path(args.file))
    elif args.office_action == "run":
        res = tool.run_raw(args.extra_args)
    else:
        res = {"ok": tool.is_available(), "officecli_bin": tool.officecli_bin}
    
    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        if res.get("ok"):
            print(f"{Color.GREEN}✓ Office operation completed successfully:{Color.RESET}")
            for k, v in res.items():
                print(f"  - {k}: {v}")
        else:
            print(f"{Color.RED}✖ Office operation failed: {res.get('error', res)}{Color.RESET}")


def cmd_plot(args):
    tool = SciPlotTool(default_style=getattr(args, "style", "nature"), dpi=getattr(args, "dpi", 300))
    if args.plot_action == "curve":
        data = {}
        if args.data:
            p = Path(args.data)
            load_error = None
            if not p.exists():
                load_error = f"Data file not found: {args.data}"
            else:
                try:
                    data = json.loads(p.read_text(encoding="utf-8"))
                except (ValueError, OSError) as e:
                    load_error = f"Failed to parse data file '{args.data}': {e}"
            if load_error:
                res = {"ok": False, "error": load_error}
                if getattr(args, "json", False):
                    print(json.dumps(res, indent=2, ensure_ascii=False))
                else:
                    print(f"{Color.RED}✖ Plot failed: {load_error}{Color.RESET}")
                sys.exit(1)
        res = tool.plot_benchmark_curve(
            data=data,
            output_path=Path(args.output),
            title=getattr(args, "title", ""),
            x_label=getattr(args, "xlabel", "Concurrency (Agents)"),
            y_label=getattr(args, "ylabel", "Reconciliation Latency (ms)"),
            style=getattr(args, "style", "nature"),
        )
    elif args.plot_action == "run":
        res = tool.run_plot_script(Path(args.script))
    else:
        res = {"ok": True, "styles": ["nature", "science", "ieee"], "dpi": 300}

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        if res.get("ok"):
            print(f"{Color.GREEN}✓ Scientific figure generated:{Color.RESET}")
            for k, v in res.items():
                print(f"  - {k}: {v}")
        else:
            print(f"{Color.RED}✖ Plot failed: {res.get('error', res)}{Color.RESET}")


def cmd_pdf(args):
    tool = PDFTool()
    if getattr(args, "pdf_action", None) is None:
        available = tool.is_available()
        usage = "synapseforge pdf compile --input <markdown> [--output <pdf>] [--title <title>]"
        if getattr(args, "json", False):
            print(json.dumps({"ok": True, "engine": "typst", "available": available, "usage": usage}, indent=2, ensure_ascii=False))
        else:
            print(f"{Color.CYAN}Publication PDF engine: typst (available: {'yes' if available else 'no'}){Color.RESET}")
            print(f"Usage: {usage}")
        return
    input_path = Path(args.input)
    output_path = Path(args.output)
    res = tool.compile_markdown_to_pdf(input_path, output_path, title=getattr(args, "title", "SynapseForge Document"))

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        if res.get("ok"):
            print(f"{Color.GREEN}✓ Publication PDF generated successfully:{Color.RESET}")
            print(f"  - PDF File: {res['output_pdf']}")
            print(f"  - Engine: {res['engine']}")
            print(f"  - Standards: {res.get('page_standard')}")
        else:
            print(f"{Color.RED}✖ PDF generation failed: {res.get('error')}{Color.RESET}")


def cmd_serve(args):
    """Starts the remote web studio and REST API daemon for remote human control."""
    from synapseforge.server.app import start_server
    host = args.host
    port = args.port
    print(f"\n{Color.CYAN}{Color.BOLD}🚀 Starting SynapseForge Remote Web Studio Daemon...{Color.RESET}")
    print(f"  - Local Access:     http://127.0.0.1:{port}")
    print(f"  - Tailscale Access: http://0.0.0.0:{port} (accessible via your Tailscale node IP / MagicDNS)")
    print(f"  - REST API:         http://127.0.0.1:{port}/api/status")
    print(f"{Color.GREEN}✓ Remote Web Daemon active. Open in browser from any remote device.{Color.RESET}\n")

    httpd = start_server(host=host, port=port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{Color.YELLOW}Shutting down server...{Color.RESET}")
        httpd.server_close()


def cmd_cite(args):
    cite = CiteTool()
    if args.cite_action == "list" or not args.cite_action:
        res = {"ok": True, "citations": cite.list_citations()}
    elif args.cite_action == "add":
        res = cite.add_bibtex_entry(
            key=args.key,
            entry_type=getattr(args, "type", "article") or "article",
            title=args.title,
            author=args.author,
            year=getattr(args, "year", "2026") or "2026",
            journal_or_book=getattr(args, "journal", "") or "",
            doi=getattr(args, "doi", "") or "",
        )
    elif args.cite_action == "lookup":
        res = cite.lookup_doi(args.doi)
        if res.get("ok") and getattr(args, "add", False):
            add_res = cite.add_bibtex_entry(
                key=res["key"],
                entry_type=res.get("type", "article"),
                title=res["title"],
                author=res["author"],
                year=res["year"],
                journal_or_book=res.get("journal", ""),
                doi=res.get("doi", ""),
            )
            res["added_to_bibliography"] = add_res.get("ok", False)
    elif args.cite_action == "search":
        res = cite.search_crossref(args.query, limit=getattr(args, "limit", 5) or 5)
    elif args.cite_action == "validate":
        res = cite.validate_citations()
    else:
        res = {"ok": False, "error": f"Unknown cite action: {args.cite_action}"}

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        if args.cite_action == "add":
            if res.get("ok"):
                print(f"{Color.GREEN}✓ Added citation '@{args.key}' to bibliography.bib{Color.RESET}")
            else:
                print(f"{Color.RED}✖ Error: {res.get('error')}{Color.RESET}")
        elif args.cite_action == "lookup":
            if res.get("ok"):
                print(f"{Color.GREEN}✓ Found DOI metadata: @{res['key']}{Color.RESET}")
                print(f"  • Title:   {res['title']}")
                print(f"  • Author:  {res['author']}")
                print(f"  • Year:    {res['year']}")
                print(f"  • Journal: {res.get('journal', 'N/A')}")
                if res.get("added_to_bibliography"):
                    print(f"{Color.GREEN}✓ Added automatically to bibliography.bib{Color.RESET}")
            else:
                print(f"{Color.RED}✖ Lookup error: {res.get('error')}{Color.RESET}")
        elif args.cite_action == "search":
            if res.get("ok"):
                print(f"\n{Color.CYAN}{Color.BOLD}CrossRef Search Results ({res.get('count', 0)} found):{Color.RESET}")
                for r in res.get("results", []):
                    print(f"  • @{r['key']:<22} | {r['author'][:25]:<25} | {r['year']} | {r['title']}")
                    if r.get("doi"):
                        print(f"    DOI: https://doi.org/{r['doi']}")
            else:
                print(f"{Color.RED}✖ Search error: {res.get('error')}{Color.RESET}")
        elif args.cite_action == "validate":
            if res.get("valid"):
                print(f"{Color.GREEN}✓ All {res['total_cited_in_document']} citations in document are valid and resolved in bibliography.bib!{Color.RESET}")
            else:
                print(f"{Color.YELLOW}⚠ Citation Validation Issues Detected:{Color.RESET}")
                if res.get("unresolved_citations"):
                    print(f"  {Color.RED}✖ Unresolved in document: {', '.join(res['unresolved_citations'])}{Color.RESET}")
                if res.get("unused_in_bibliography"):
                    print(f"  {Color.GRAY}• Unused in bibliography: {', '.join(res['unused_in_bibliography'])}{Color.RESET}")
                if res.get("incomplete_entries"):
                    print(f"  {Color.YELLOW}• Incomplete entries: {res['incomplete_entries']}{Color.RESET}")
        else:
            print(f"\n{Color.CYAN}{Color.BOLD}BibTeX Bibliography Citations ({len(res['citations'])} entries):{Color.RESET}")
            for c in res["citations"]:
                print(f"  • @{c['key']:<22} | {c['author']:<20} | {c['year']} | {c['title']}")
            print()


def cmd_snapshot(args):
    snap = SnapshotManager()
    if args.snap_action == "create":
        res = snap.create_checkpoint(message=args.message, section_id=args.section, author=args.author or "Human")
    elif args.snap_action == "list" or not args.snap_action:
        res = {"ok": True, "history": snap.list_history(section_id=args.section, limit=args.limit or 10)}
    elif args.snap_action == "rollback":
        res = snap.rollback(commit_hash=args.commit, file_path=args.file)
    else:
        res = {"ok": False, "error": f"Unknown snapshot action: {args.snap_action}"}

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        if args.snap_action == "create":
            if res.get("ok"):
                print(f"{Color.GREEN}✓ Checkpoint created: {res.get('commit_hash')} - {res.get('message')}{Color.RESET}")
            else:
                print(f"{Color.RED}✖ Failed to create checkpoint: {res.get('error')}{Color.RESET}")
        elif args.snap_action == "rollback":
            if res.get("ok"):
                print(f"{Color.GREEN}✓ Rollback to {args.commit} successful for {res.get('target')}{Color.RESET}")
            else:
                print(f"{Color.RED}✖ Rollback failed: {res.get('error')}{Color.RESET}")
        else:
            print(f"\n{Color.CYAN}{Color.BOLD}Git Snapshot Checkpoints History:{Color.RESET}")
            for h in res.get("history", []):
                print(f"  • [{h['commit_hash']}] {h['author']:<15} | {h['message']}")
            print()


def cmd_ingest(args):
    ingestor = DocumentIngestor()
    if args.ingest_action == "add":
        content = args.content
        if args.file:
            file_path = Path(args.file)
            if not file_path.exists():
                res = {"ok": False, "error": f"File not found: {args.file}"}
                if getattr(args, "json", False):
                    print(json.dumps(res, indent=2, ensure_ascii=False))
                else:
                    print(f"{Color.RED}✖ Ingest failed: {res['error']}{Color.RESET}")
                sys.exit(1)
            content = file_path.read_text(encoding="utf-8")
        res = ingestor.ingest_text_or_note(
            source_id=args.id,
            title=args.title,
            content=content,
            tags=args.tags.split(",") if args.tags else [],
        )
    elif args.ingest_action == "list" or not args.ingest_action:
        res = {"ok": True, "sources": ingestor.list_ingested_sources()}
    else:
        res = {"ok": False, "error": f"Unknown ingest action: {args.ingest_action}"}

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        if args.ingest_action == "add":
            if res.get("ok"):
                print(f"{Color.GREEN}✓ Ingested research source: '{args.title}' ({res['file']}){Color.RESET}")
            else:
                print(f"{Color.RED}✖ Ingest failed: {res.get('error')}{Color.RESET}")
        else:
            print(f"\n{Color.CYAN}{Color.BOLD}Ingested Knowledge Context ({len(res.get('sources', []))} sources):{Color.RESET}")
            for s in res.get("sources", []):
                print(f"  • [{s['id']}] {s['title']} ({s['file']})")
            print()


def cmd_figure(args):
    linker = FigureLinker()
    if args.figure_action == "insert":
        res = linker.insert_figure(
            section_id=args.section,
            image_path=args.image,
            caption=args.caption,
            fig_num=args.num or 1,
            discussion_bridge=args.bridge,
        )
    else:
        res = {"ok": False, "error": f"Unknown figure action: {args.figure_action}"}

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        if res.get("ok"):
            print(f"{Color.GREEN}✓ Bound figure to {res['section_file']}:{Color.RESET}")
            print(f"  - Caption: 图 {res['fig_num']}：{res['caption']}")
            print(f"  - Discussion Bridge: {res['bridge_injected']}")
        else:
            print(f"{Color.RED}✖ Figure insertion failed: {res.get('error')}{Color.RESET}")


def cmd_provider(args):
    router = LLMRouter()
    if args.provider_action == "list" or not args.provider_action:
        res = {"ok": True, "providers": router.list_providers()}
    elif args.provider_action == "ping":
        res = router.ping_provider(args.provider_id)
    else:
        res = {"ok": False, "error": f"Unknown provider action: {args.provider_action}"}

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        if args.provider_action == "ping":
            if res.get("ok"):
                print(f"{Color.GREEN}✓ Provider '{res['provider']}' online (RTT: {res['latency_ms']}ms){Color.RESET}")
            else:
                print(f"{Color.RED}✖ Ping failed: {res.get('error')}{Color.RESET}")
        else:
            print(f"\n{Color.CYAN}{Color.BOLD}LLM Model Provider Mesh Routing:{Color.RESET}")
            for p in res.get("providers", []):
                print(f"  • {p['name']:<25} | {p['type']:<10} | {p['model']:<25} | {p['endpoint']}")
            print()


def cmd_variant(args):
    vm = VariantManager()
    syn = MultiDocumentSynthesizer()

    if args.variant_action == "create":
        res = vm.create_variant(
            variant_id=args.id,
            name=args.name,
            target_section=args.section,
            base_file=Path(args.base) if args.base else None,
            author=args.author or "Drafter",
        )
    elif args.variant_action == "list" or not args.variant_action:
        res = {"ok": True, "variants": vm.list_variants(target_section=args.section)}
    elif args.variant_action == "merge":
        input_files = [Path(p.strip()) for p in args.inputs.split(",") if p.strip()]
        res = syn.merge_variants(
            variant_files=input_files,
            output_file=Path(args.output),
            strategy=args.strategy or "harmonize",
        )
    else:
        res = {"ok": False, "error": f"Unknown variant action: {args.variant_action}"}

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        if args.variant_action == "create":
            if res.get("ok"):
                print(f"{Color.GREEN}✓ Document variant created: '{res['name']}' ({res['file']}){Color.RESET}")
            else:
                print(f"{Color.RED}✖ Failed: {res.get('error')}{Color.RESET}")
        elif args.variant_action == "merge":
            if res.get("ok"):
                print(f"{Color.GREEN}✓ Successfully synthesized {len(res['source_variants'])} variants into '{res['output_file']}':{Color.RESET}")
                print(f"  - Strategy: {res['strategy']}")
                print(f"  - Word count: {res['total_words']}")
                print(f"  - Citations preserved: {len(res['citations_preserved'])}")
            else:
                print(f"{Color.RED}✖ Merge failed: {res.get('error')}{Color.RESET}")
            print()


def cmd_export(args):
    exporter = MultiFormatExporter()
    res = exporter.export_all(title=getattr(args, "title", None))

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        if res.get("ok"):
            print(f"\n{Color.GREEN}{Color.BOLD}✓ Publication Package Exported Successfully:{Color.RESET}")
            print(f"  - Document Title: {res['title']}")
            print(f"  - Total Words:    {res['total_words']} words ({res['sections_count']} sections)")
            print(f"  - PDF Paper:      {res['artifacts'].get('pdf')}")
            print(f"  - Word Doc:       {res['artifacts'].get('docx')}")
            print(f"  - Web HTML:       {res['artifacts'].get('html')}")
            print(f"  - Zip Bundle:     {res['artifacts'].get('zip_package')}\n")
        else:
            print(f"{Color.RED}✖ Export failed: {res.get('error')}{Color.RESET}")


def cmd_diff(args):
    differ = SemanticASTDiffer()
    file1 = getattr(args, "file1", None)
    file2 = getattr(args, "file2", None)
    variant = getattr(args, "variant", None)

    if variant and file1:
        var_path = Path.cwd() / "variants" / f"{variant}.md"
        if not var_path.exists():
            res = {"ok": False, "error": f"Variant file not found: {var_path}"}
            if getattr(args, "json", False):
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                print(f"{Color.RED}✖ Variant not found: {var_path}{Color.RESET}")
            return
        file2 = str(var_path)

    if not file1 or not file2:
        res = {"ok": False, "error": "Two files or a file and --variant must be specified"}
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"{Color.RED}✖ Error: Please specify two files to diff.{Color.RESET}")
        return

    try:
        diff_res = differ.diff_files(file1, file2)
        if getattr(args, "json", False):
            print(json.dumps({"ok": True, "diff": diff_res.to_dict()}, indent=2, ensure_ascii=False))
        else:
            print(diff_res.render_terminal(use_color=True))
    except Exception as e:
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "error": str(e)}, indent=2, ensure_ascii=False))
        else:
            print(f"{Color.RED}✖ Diff error: {e}{Color.RESET}")


def cmd_watch(args):
    watcher = DocumentWatcher(
        auto_snapshot=getattr(args, "auto_snapshot", False),
        debounce_seconds=getattr(args, "debounce", 0.5),
    )
    interval = getattr(args, "interval", 1.0)
    once = getattr(args, "once", False)

    if once:
        events = watcher.poll_once()
        res = {"ok": True, "events": [e.to_dict() for e in events]}
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"{Color.CYAN}Polled once: {len(events)} change events detected.{Color.RESET}")
            for ev in events:
                print(f"  • {ev.change_type.value.upper()} {ev.path.name} (lint: {'PASS' if ev.linter_passed else 'FAIL'})")
        return

    print(f"{Color.CYAN}{Color.BOLD}⚡ SynapseForge Watch Daemon active (interval: {interval}s, auto-snapshot: {getattr(args, 'auto_snapshot', False)})...{Color.RESET}")
    print(f"{Color.GRAY}Press Ctrl+C to stop watching.{Color.RESET}\n")

    def handle_ev(ev):
        status_icon = f"{Color.GREEN}✓{Color.RESET}" if ev.linter_passed else f"{Color.RED}✖{Color.RESET}"
        snap_msg = f" | {Color.MAGENTA}snapshot {ev.snapshot_hash[:7]}{Color.RESET}" if ev.snapshot_created else ""
        print(f"[{time.strftime('%H:%M:%S')}] {status_icon} {ev.change_type.value.upper()}: {Color.BOLD}{ev.path.name}{Color.RESET} (issues: {ev.linter_issues_count}){snap_msg}")

    try:
        watcher.watch_loop(interval=interval, on_event=handle_ev)
    except KeyboardInterrupt:
        print(f"\n{Color.YELLOW}Stopped watcher daemon.{Color.RESET}")


def cmd_scorecard(args):
    scorecard = QualityScorecard()
    html_out = getattr(args, "html", None)
    if html_out:
        p = scorecard.generate_html_report(output_path=html_out)
        res = {"ok": True, "html_report": str(p)}
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"{Color.GREEN}✓ Quality audit HTML report generated at: {p}{Color.RESET}")
        return

    res = scorecard.evaluate_document()
    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        m = res["metrics"]
        print(f"\n{Color.CYAN}{Color.BOLD}📊 SynapseForge Document Academic Scorecard:{Color.RESET}")
        print(f"  • Publication Grade:         {Color.BOLD}{res['publication_grade']} ({res['overall_score']}/100){Color.RESET}")
        print(f"  • Anti-AI Natural Flow:      {m['anti_ai_natural_flow_score']}/100")
        print(f"  • Citation Richness Score:   {m['citation_richness_score']}/100 ({m['total_citations']} citations, {m['citation_density_per_k_words']}/k words)")
        print(f"  • Mathematical Rigor Score:  {m['mathematical_rigor_score']}/100 ({m['total_math_equations']} KaTeX equations)")
        print(f"  • Booktabs Tables:           {m['total_booktabs_tables']} tables (100% no-vertical-line compliance)")
        print(f"  • Total Word Count:          {m['total_words']} words\n")


def cmd_notify(args):
    dispatcher = NotificationDispatcher(user_email=getattr(args, "email", "361487867@qq.com"))
    res = dispatcher.send_notification(
        title=args.title,
        message=args.message,
        channel=args.channel or "email",
    )

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        if res.get("ok"):
            print(f"{Color.GREEN}✓ Notification sent via {res['channel']} to {res.get('recipient', 'local')}{Color.RESET}")
        else:
            print(f"{Color.RED}✖ Notification failed: {res.get('error')}{Color.RESET}")


def cmd_user_prompts(args):
    mgr = UserPromptManager()
    action = getattr(args, "prompt_action", "list")

    if action == "list":
        prompts = mgr.list_prompts()
        if getattr(args, "json", False):
            print(json.dumps({"ok": True, "prompts": prompts}, indent=2, ensure_ascii=False))
        else:
            print(f"\n{Color.CYAN}{Color.BOLD}User-Defined Custom Agent Prompts ({len(prompts)} Personas):{Color.RESET}")
            print(f"{'Role ID':<15} | {'Display Name':<25} | {'File Path':<30} | {'Model':<15}")
            print("-" * 90)
            for p in prompts:
                print(f"{p['role_id']:<15} | {p['display_name']:<25} | {p['prompt_file']:<30} | {p.get('model', 'default'):<15}")
            print()

    elif action == "set":
        prompt_content = ""
        if args.file:
            p_path = Path(args.file)
            if not p_path.exists():
                print(json.dumps({"ok": False, "error": f"File not found: {args.file}"}))
                return
            prompt_content = p_path.read_text(encoding="utf-8")
        elif args.prompt:
            prompt_content = args.prompt
        else:
            print(json.dumps({"ok": False, "error": "Either --file or --prompt must be provided"}))
            return

        res = mgr.set_prompt(
            role_id=args.role,
            prompt_content=prompt_content,
            display_name=getattr(args, "name", None),
            description=getattr(args, "desc", None),
            model=getattr(args, "model", None),
        )
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"{Color.GREEN}✓ Successfully saved user custom prompt for role '{res['role_id']}' at '{res['prompt_file']}' ({res['length_characters']} chars){Color.RESET}")

    elif action == "get":
        prompt = mgr.get_prompt(args.role)
        if prompt is not None:
            if getattr(args, "json", False):
                print(json.dumps({"ok": True, "role_id": args.role, "prompt": prompt}, indent=2, ensure_ascii=False))
            else:
                print(f"\n{Color.CYAN}--- Custom Prompt for '{args.role}' ---{Color.RESET}\n")
                print(prompt)
        else:
            if getattr(args, "json", False):
                print(json.dumps({"ok": False, "error": f"Prompt for role '{args.role}' not found"}, indent=2))
            else:
                print(f"{Color.RED}✖ No custom prompt found for role '{args.role}'. Create one with 'synapseforge prompt set --role {args.role} --file <path>'{Color.RESET}")

    elif action == "delete":
        deleted = mgr.delete_prompt(args.role)
        if getattr(args, "json", False):
            print(json.dumps({"ok": deleted, "role_id": args.role}, indent=2))
        else:
            if deleted:
                print(f"{Color.GREEN}✓ Deleted custom prompt for role '{args.role}'{Color.RESET}")
            else:
                print(f"{Color.RED}✖ Role '{args.role}' did not exist{Color.RESET}")


def cmd_vault(args):
    vault = WorkspaceVault()
    action = getattr(args, "vault_action", "list")

    if action == "list":
        res = vault.list_vault_files()
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"\n{Color.CYAN}{Color.BOLD}📁 SynapseForge Centralized Workspace Vault:{Color.RESET}")
            print(f"  Root: {res['workspace_root']}\n")
            for cat, data in res["categories"].items():
                print(f"  📂 {Color.BOLD}{cat:<14}{Color.RESET} ({data['file_count']} files) — {data['description']}")
                for f in data["files"][:4]:
                    print(f"     • {f['relative_path']} ({f['size_bytes']} bytes)")
                if len(data["files"]) > 4:
                    print(f"     • ... and {len(data['files']) - 4} more files")
            print()

    elif action == "import":
        res = vault.import_external_file(
            external_path=args.file,
            target_category=getattr(args, "category", None),
            overwrite=getattr(args, "overwrite", False),
        )
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            if res.get("ok"):
                print(f"{Color.GREEN}✓ Successfully imported external file into dedicated vault:{Color.RESET}")
                print(f"  - Source:      {res['original_path']}")
                print(f"  - Vault Path:  {res['vault_path']} ({res.get('file_size', 0)} bytes)")
                print(f"  - Category:    {res['category']}")
                print(f"  - SHA-256:     {res['sha256'][:16]}...")
            else:
                print(f"{Color.RED}✖ Import failed: {res.get('error')}{Color.RESET}")

    elif action == "init":
        vault.ensure_vault_structure()
        res = {"ok": True, "workspace_root": str(vault.workspace_root), "status": "all_dedicated_folders_created"}
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"{Color.GREEN}✓ Initialized all 10 dedicated vault directories at '{vault.workspace_root}'{Color.RESET}")


def cmd_security(args):
    action = getattr(args, "sec_action", "audit")

    if action == "audit":
        redactor = ConfidentialityRedactor()
        target_path = Path(args.path) if getattr(args, "path", None) else (Path.cwd() / "sections")
        
        all_issues = []
        if target_path.is_file():
            text = target_path.read_text(encoding="utf-8")
            issues = redactor.scan_for_secrets(text)
            for iss in issues:
                all_issues.append({"file": str(target_path), "line": iss.line_number, "type": iss.matched_type, "preview": iss.redacted_preview})
        elif target_path.is_dir():
            for p in sorted(target_path.glob("**/*.md")):
                text = p.read_text(encoding="utf-8")
                issues = redactor.scan_for_secrets(text)
                for iss in issues:
                    all_issues.append({"file": str(p), "line": iss.line_number, "type": iss.matched_type, "preview": iss.redacted_preview})

        if getattr(args, "json", False):
            print(json.dumps({"ok": True, "total_secrets_detected": len(all_issues), "issues": all_issues}, indent=2, ensure_ascii=False))
        else:
            if all_issues:
                print(f"\n{Color.RED}{Color.BOLD}⚠️  Confidentiality Audit: Found {len(all_issues)} Sensitive Secrets / Terms:{Color.RESET}")
                for iss in all_issues:
                    print(f"  • {iss['file']}:{iss['line']} [{iss['type']}] -> {iss['preview']}")
                print()
            else:
                print(f"\n{Color.GREEN}{Color.BOLD}✓ Confidentiality Audit Clean:{Color.RESET} No secrets, tokens, PII, or classified terms detected.\n")

    elif action == "redact":
        redactor = ConfidentialityRedactor()
        inp = Path(args.input)
        if not inp.exists():
            print(json.dumps({"ok": False, "error": f"Input file not found: {args.input}"}))
            return
        text = inp.read_text(encoding="utf-8")
        sanitized, token_map = redactor.redact(text)
        
        out = Path(args.output) if getattr(args, "output", None) else inp.with_suffix(".redacted.md")
        out.write_text(sanitized, encoding="utf-8")
        
        map_out = out.with_suffix(".map.json")
        map_out.write_text(json.dumps(token_map, indent=2, ensure_ascii=False), encoding="utf-8")

        res = {
            "ok": True,
            "input_file": str(inp),
            "sanitized_file": str(out),
            "token_map_file": str(map_out),
            "redacted_count": len(token_map),
        }
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"{Color.GREEN}✓ Masked {len(token_map)} secrets -> '{out}' (mapping saved to '{map_out}'){Color.RESET}")

    elif action == "encrypt":
        crypto = CryptoVault()
        inp = Path(args.file)
        if not inp.exists():
            print(json.dumps({"ok": False, "error": f"File not found: {args.file}"}))
            return
        out = Path(args.output) if getattr(args, "output", None) else inp.with_suffix(".enc.json")
        res = crypto.encrypt_file(inp, out, passphrase=args.passphrase)
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"{Color.GREEN}✓ At-Rest Encrypted '{inp.name}' -> '{out.name}' ({res['encrypted_bytes']} bytes){Color.RESET}")

    elif action == "decrypt":
        crypto = CryptoVault()
        inp = Path(args.file)
        if not inp.exists():
            print(json.dumps({"ok": False, "error": f"File not found: {args.file}"}))
            return
        out = Path(args.output) if getattr(args, "output", None) else inp.with_suffix(".dec.md")
        try:
            res = crypto.decrypt_file(inp, out, passphrase=args.passphrase)
            if getattr(args, "json", False):
                print(json.dumps(res, indent=2, ensure_ascii=False))
            else:
                print(f"{Color.GREEN}✓ Successfully Decrypted '{inp.name}' -> '{out.name}' ({res['decrypted_chars']} chars){Color.RESET}")
        except Exception as e:
            if getattr(args, "json", False):
                print(json.dumps({"ok": False, "error": str(e)}))
            else:
                print(f"{Color.RED}✖ Decryption failed: {e}{Color.RESET}")

    elif action == "add-term":
        redactor = ConfidentialityRedactor()
        redactor.add_classified_term(args.term)
        res = {"ok": True, "classified_terms": redactor.list_classified_terms()}
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"{Color.GREEN}✓ Added confidential keyword '{args.term}' to redaction registry{Color.RESET}")


def cmd_report(args):
    action = getattr(args, "report_action", "spec")

    if action == "new":
        from synapseforge.report import ReportGenerator
        from synapseforge.report.spec import ReportType
        gen = ReportGenerator()
        rep_type = ReportType(getattr(args, "type", "whitepaper"))
        res = gen.generate_report_template(
            title=args.title,
            topic=args.topic,
            report_type=rep_type,
            author=getattr(args, "author", "SynapseForge Swarm Contributors"),
        )
        out_path = Path(args.output) if getattr(args, "output", None) else (Path.cwd() / "sections" / "01_report_spec.md")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(res["content"], encoding="utf-8")
        res["output_file"] = str(out_path)
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"{Color.GREEN}{Color.BOLD}✓ Report-Spec Publication Document Created:{Color.RESET} {out_path}")
            print(f"  • Title: {res['title']}")
            print(f"  • Quality Score: {res['audit']['total_score']}/100 (Anti-AI: {res['audit']['anti_ai_score']}, Narrative: {res['audit']['narrative_score']})")

    elif action == "lint":
        from synapseforge.report.spec import ReportSpecification
        file_path = Path(args.file)
        if not file_path.exists():
            print(json.dumps({"ok": False, "error": f"File not found: {args.file}"}))
            return
        text = file_path.read_text(encoding="utf-8")
        audit = ReportSpecification.audit_document(text)
        res = {
            "ok": True,
            "file": str(file_path),
            "passed": audit.passed,
            "total_score": audit.total_score,
            "anti_ai_score": audit.anti_ai_score,
            "narrative_score": audit.narrative_score,
            "structure_score": audit.structure_score,
            "violations": audit.violations,
            "suggestions": audit.suggestions,
        }
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            status_color = Color.GREEN if audit.passed else Color.RED
            print(f"\n{status_color}{Color.BOLD}Report-Spec Quality Gate: {'PASSED' if audit.passed else 'FAILED'} (Score: {audit.total_score}/100){Color.RESET}")
            print(f"  • Anti-AI Score: {audit.anti_ai_score}/100")
            print(f"  • Narrative Prose Score: {audit.narrative_score}/100")
            print(f"  • Structure Score: {audit.structure_score}/100")
            if audit.violations:
                print(f"\n{Color.YELLOW}Violations ({len(audit.violations)}):{Color.RESET}")
                for v in audit.violations:
                    print(f"  • Line {v['line']}: [{v['rule_name']}] {v['snippet']} -> {v['advice']}")
            print()

    elif action == "build":
        from synapseforge.report import ReportGenerator
        gen = ReportGenerator()
        inp = Path(args.file)
        if not inp.exists():
            print(json.dumps({"ok": False, "error": f"File not found: {args.file}"}))
            return
        out = Path(args.output) if getattr(args, "output", None) else (Path.cwd() / "dist" / f"{inp.stem}.pdf")
        res = gen.compile_report_to_pdf(markdown_path=inp, output_pdf=out, title=getattr(args, "title", None))
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            if res.get("ok"):
                print(f"{Color.GREEN}{Color.BOLD}✓ Publication-Grade PDF Compiled:{Color.RESET} {res['output_pdf']}")
                print(f"  • Standard: {res.get('page_standard')}")
                print(f"  • Audit Score: {res.get('audit_score')}/100 (Passed: {res.get('audit_passed')})")
            else:
                print(f"{Color.RED}✖ PDF Compilation Failed: {res.get('error')}{Color.RESET}")

    elif action == "spec":
        from synapseforge.report.spec import ReportStandard
        res = {
            "standard_name": "Report Specification (Report-Spec)",
            "seven_prohibitions": ReportStandard.SEVEN_PROHIBITIONS,
            "paragraph_triad_rule": ReportStandard.PARAGRAPH_TRIAD_RULE,
            "booktabs_rule": ReportStandard.BOOKTABS_RULE,
            "scientific_plot_rules": ReportStandard.SCIENTIFIC_PLOT_RULES,
            "publication_pdf_layout_rules": ReportStandard.PUBLICATION_PDF_LAYOUT_RULES,
        }
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2, ensure_ascii=False))
        else:
            print(f"\n{Color.CYAN}{Color.BOLD}📋 SynapseForge Report Specification (Report-Spec) Standards:{Color.RESET}\n")
            for p in ReportStandard.SEVEN_PROHIBITIONS:
                print(f"  {Color.BOLD}• {p['name']}:{Color.RESET} {p['rule']}")
            print(f"\n  {Color.BOLD}• 散文段落三位一体法:{Color.RESET} {ReportStandard.PARAGRAPH_TRIAD_RULE}")
            print(f"  {Color.BOLD}• 出版级三线表规范:{Color.RESET} {ReportStandard.BOOKTABS_RULE}")
            print(f"  {Color.BOLD}• 顶刊科研绘图联动:{Color.RESET} {ReportStandard.SCIENTIFIC_PLOT_RULES}")
            print(f"  {Color.BOLD}• 出版级 PDF 排版:{Color.RESET} {ReportStandard.PUBLICATION_PDF_LAYOUT_RULES}\n")

    elif action == "prompts":
        from synapseforge.report.prompts import REPORT_SPEC_PROMPTS
        if getattr(args, "json", False):
            print(json.dumps(REPORT_SPEC_PROMPTS, indent=2, ensure_ascii=False))
        else:
            print(f"\n{Color.CYAN}{Color.BOLD}🤖 Report-Spec Built-in Multi-Agent Prompts:{Color.RESET}\n")
            for role, info in REPORT_SPEC_PROMPTS.items():
                print(f"  {Color.BOLD}[{role.upper()}] {info['display_name']}{Color.RESET}: {info['desc']}")
            print()


def main():
    parser = argparse.ArgumentParser(
        prog="synapseforge",
        description="SynapseForge: GitOps & Tailscale Mesh Framework for Distributed Multi-Agent Collaborative Writing",
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--json", dest="json_global", action=argparse.BooleanOptionalAction, default=False, help="Output machine-readable JSON format for AI agents")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # serve
    p_serve = subparsers.add_parser("serve", help="Start remote web studio & REST control daemon")
    p_serve.add_argument("--port", type=int, default=8765, help="HTTP port (default 8765)")
    p_serve.add_argument("--host", default="0.0.0.0", help="Binding host (default 0.0.0.0)")
    p_serve.set_defaults(func=cmd_serve)

    # init
    p_init = subparsers.add_parser("init", help="Initialize a new SynapseForge repository")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing configuration")
    p_init.set_defaults(func=cmd_init)

    # plan
    p_plan = subparsers.add_parser("plan", help="Generate document structure DAG & scaffolds")
    p_plan.add_argument("--json", action="store_true", help="Output JSON")
    p_plan.set_defaults(func=cmd_plan)

    # status
    p_status = subparsers.add_parser("status", help="Display document writing status ledger")
    p_status.add_argument("--json", action="store_true", help="Output JSON")
    p_status.set_defaults(func=cmd_status)

    # lint
    p_lint = subparsers.add_parser("lint", help="Run document quality gates & anti-AI linter")
    p_lint.add_argument("target", nargs="?", default=None, help="Target markdown file or directory")
    p_lint.add_argument("--ci", action="store_true", help="Exit with code 1 on quality gate failure")
    p_lint.add_argument("--json", action="store_true", help="Output JSON")
    p_lint.set_defaults(func=cmd_lint)

    # merge
    p_merge = subparsers.add_parser("merge", help="Execute AST-level 3-way conflict resolution")
    p_merge.add_argument("--base", required=True, help="Path to base document")
    p_merge.add_argument("--ours", required=True, help="Path to branch (ours) document")
    p_merge.add_argument("--theirs", required=True, help="Path to incoming (theirs) document")
    p_merge.add_argument("-o", "--output", required=True, help="Path to write merged document")
    p_merge.add_argument("--ours-label", default="OURS (Branch)", help="Label for ours")
    p_merge.add_argument("--theirs-label", default="THEIRS (Incoming)", help="Label for theirs")
    p_merge.add_argument("--json", action="store_true", help="Output JSON")
    p_merge.set_defaults(func=cmd_merge)

    # review
    p_review = subparsers.add_parser("review", help="Run automated Multi-Agent PR peer review bot")
    p_review.add_argument("--base", default="main", help="Base git ref to diff against")
    p_review.add_argument("--pr", type=int, default=None, help="Pull Request number to comment on")
    p_review.add_argument("--ci", action="store_true", help="Exit with non-zero on failure in CI")
    p_review.add_argument("--json", action="store_true", help="Output JSON")
    p_review.set_defaults(func=cmd_review)

    # diff
    p_diff = subparsers.add_parser("diff", help="Semantic AST block difference analysis between documents or variants")
    p_diff.add_argument("file1", nargs="?", default=None, help="Base document file path")
    p_diff.add_argument("file2", nargs="?", default=None, help="Target document file path")
    p_diff.add_argument("--variant", default=None, help="Compare file1 against a variant in variants/")
    p_diff.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_diff.set_defaults(func=cmd_diff)

    # watch
    p_watch = subparsers.add_parser("watch", help="Continuous quality gate daemon watching sections for changes")
    p_watch.add_argument("--interval", type=float, default=1.0, help="Polling interval in seconds")
    p_watch.add_argument("--once", action="store_true", help="Poll once and exit immediately")
    p_watch.add_argument("--auto-snapshot", action="store_true", help="Create an atomic checkpoint snapshot on each save")
    p_watch.add_argument("--debounce", type=float, default=0.5, help="Debounce window in seconds")
    p_watch.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_watch.set_defaults(func=cmd_watch)

    # build
    p_build = subparsers.add_parser("build", help="Build publication deliverables (HTML, Typst, PDF)")
    p_build.add_argument("--json", action="store_true", help="Output JSON")
    p_build.set_defaults(func=cmd_build)

    # mesh
    p_mesh = subparsers.add_parser("mesh", help="Inspect Tailscale WireGuard P2P mesh network status")
    p_mesh.add_argument("--json", action="store_true", help="Output JSON")
    p_mesh.set_defaults(func=cmd_mesh)

    # room
    p_room = subparsers.add_parser("room", help="Manage multi-node shared collaborative rooms")
    p_room.add_argument("room_action", nargs="?", default="list", choices=["list", "create", "join"], help="Action: list, create, join")
    p_room.add_argument("--name", default="Distributed Whitepaper Room", help="Room name for create")
    p_room.add_argument("--title", default=None, help="Document title")
    p_room.add_argument("--type", default="academic_whitepaper", help="Document type")
    p_room.add_argument("--room-id", default="", help="Room ID or slug to join")
    p_room.add_argument("--user", default="xb", help="User name joining")
    p_room.add_argument("--json", action="store_true", help="Output JSON")
    p_room.set_defaults(func=cmd_room)

    # ==========================================
    # LOCAL TEAM BUS (host Agent CLI collaboration)
    # ==========================================
    p_team = subparsers.add_parser(
        "team",
        help="Local collaboration bus for Codex / Grok / Antigravity on one machine",
    )
    p_team.set_defaults(func=handle_team)
    team_subs = p_team.add_subparsers(dest="team_action", help="Team action")

    def _team_common(p, agent=False, room=True):
        p.add_argument("--cwd", default=None, help="Workspace root (default: cwd)")
        p.add_argument("--json", action="store_true", help="Machine-readable JSON")
        if room:
            p.add_argument("--room", default=None, help="Room name (or SYNAPSEFORGE_ROOM)")
        if agent:
            p.add_argument("--agent", required=True, help="Seat name: codex, grok, antigravity, claude, human")
        p.set_defaults(func=handle_team)
        return p

    p_team_join = team_subs.add_parser("join", help="Join or create a local team room")
    _team_common(p_team_join, agent=True)
    p_team_join.add_argument("--role", default="", help="Role label")
    p_team_join.add_argument("--objective", default="", help="Room objective")

    _team_common(team_subs.add_parser("status", help="Room dashboard: seats, tasks, locks, coordinator_silent"))
    p_team_say = team_subs.add_parser("say", help="Post a message or human directive")
    _team_common(p_team_say, agent=True)
    p_team_say.add_argument("-m", "--message", required=True, help="Message body")
    p_team_say.add_argument("--kind", default="discussion", help="discussion, proposal, directive, ...")
    p_team_say.add_argument("--to-agent", dest="to_agent", default=None)

    p_team_msg = team_subs.add_parser("messages", help="Read room messages (heartbeat)")
    _team_common(p_team_msg, agent=True)
    p_team_msg.add_argument("--after-id", dest="after_id", type=int, default=0)
    p_team_msg.add_argument("--limit", type=int, default=50)

    p_team_tasks = team_subs.add_parser("tasks", help="List the shared task board")
    _team_common(p_team_tasks)
    p_team_tasks.add_argument("--status", default=None, choices=["open", "in_progress", "blocked", "done"])

    p_team_ct = team_subs.add_parser("create-task", help="Create a task (dedupes same files/title)")
    _team_common(p_team_ct, agent=True)
    p_team_ct.add_argument("--title", required=True)
    p_team_ct.add_argument("--description", default="")
    p_team_ct.add_argument("--files", default="", help="Comma-separated workspace paths")
    p_team_ct.add_argument("--priority", type=int, default=2)

    p_team_claim = team_subs.add_parser("claim-task", help="Claim a task and lock its files")
    _team_common(p_team_claim, agent=True)
    p_team_claim.add_argument("--task-id", dest="task_id", type=int, required=True)
    p_team_claim.add_argument("--lock-minutes", dest="lock_minutes", type=int, default=30)

    p_team_up = team_subs.add_parser("update-task", help="Update task status")
    _team_common(p_team_up, agent=True)
    p_team_up.add_argument("--task-id", dest="task_id", type=int, required=True)
    p_team_up.add_argument("--status", required=True, choices=["open", "in_progress", "blocked", "done"])
    p_team_up.add_argument("--result", default="")

    p_team_lock = team_subs.add_parser("lock", help="Lock workspace files")
    _team_common(p_team_lock, agent=True)
    p_team_lock.add_argument("--files", required=True, help="Comma-separated paths")
    p_team_lock.add_argument("--task-id", dest="task_id", type=int, default=None)
    p_team_lock.add_argument("--lock-minutes", dest="lock_minutes", type=int, default=30)

    p_team_unlock = team_subs.add_parser("unlock", help="Release this agent's file locks")
    _team_common(p_team_unlock, agent=True)
    p_team_unlock.add_argument("--files", default="", help="Optional subset of paths")

    p_team_reclaim = team_subs.add_parser("reclaim", help="Drop locks whose holder went silent")
    _team_common(p_team_reclaim, agent=True)

    p_team_act = team_subs.add_parser("claim-action", help="Claim a one-shot push/submit/deploy action")
    _team_common(p_team_act, agent=True)
    p_team_act.add_argument("--action-key", dest="action_key", required=True)
    p_team_act.add_argument("--ttl", type=int, default=600)

    _team_common(team_subs.add_parser("rooms", help="List local rooms"), room=False)
    _team_common(team_subs.add_parser("docs", help="List shared documents"))

    p_team_share = team_subs.add_parser("share", help="Share a local document into the room")
    _team_common(p_team_share, agent=True)
    p_team_share.add_argument("--path", required=True)
    p_team_share.add_argument("--title", default="")

    p_team_open = team_subs.add_parser("open", help="Create/resume a room and print paste prompts for host CLIs")
    _team_common(p_team_open, room=False)
    p_team_open.add_argument("--document", required=True, help="Shared brief / section markdown")
    p_team_open.add_argument("--room", default=None, help="Room name (resumes live workspace room if omitted)")
    p_team_open.add_argument("--objective", default="")
    p_team_open.add_argument("--new-room", dest="new_room", action="store_true", help="Do not resume an existing live room")

    p_team_paste = team_subs.add_parser("paste-prompts", help="Print join prompts for Codex/Grok/Antigravity")
    _team_common(p_team_paste)

    p_team_mcp = team_subs.add_parser("mcp", help="Run the stdio MCP server for host Agent CLIs")
    _team_common(p_team_mcp)

    # ==========================================
    # AGENT TOOLKIT COMMANDS (For AI Subagents)
    # ==========================================
    p_agent = subparsers.add_parser("agent", help="AI Agent atomic action toolkit (list, claim, draft, audit, patch)")
    agent_subs = p_agent.add_subparsers(dest="agent_action", help="Agent action")

    # agent list
    p_ag_list = agent_subs.add_parser("list", help="List all swarm agents and their active leases")
    p_ag_list.add_argument("--json", action=argparse.BooleanOptionalAction, default=True, help="Output JSON (default true for agents)")
    p_ag_list.set_defaults(func=handle_agent_list)

    # agent claim
    p_ag_claim = agent_subs.add_parser("claim", help="Acquire an exclusive writing lease on a section")
    p_ag_claim.add_argument("--agent", required=True, help="Agent name (e.g. Drafter-Narrative)")
    p_ag_claim.add_argument("--section", required=True, help="Section ID to claim (e.g. sec_04_consensus)")
    p_ag_claim.add_argument("--lease", type=int, default=3600, help="Lease duration in seconds")
    p_ag_claim.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_ag_claim.set_defaults(func=handle_agent_claim)

    # agent release
    p_ag_release = agent_subs.add_parser("release", help="Release a section lease")
    p_ag_release.add_argument("--agent", required=True, help="Agent name")
    p_ag_release.add_argument("--section", required=True, help="Section ID to release")
    p_ag_release.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_ag_release.set_defaults(func=handle_agent_release)

    # agent draft
    p_ag_draft = agent_subs.add_parser("draft", help="Atomically write drafted content to a section file")
    p_ag_draft.add_argument("--agent", required=True, help="Agent name")
    p_ag_draft.add_argument("--section", required=True, help="Section ID")
    p_ag_draft.add_argument("--content", default="", help="Markdown text content")
    p_ag_draft.add_argument("--content-file", default=None, help="File containing markdown text")
    p_ag_draft.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_ag_draft.set_defaults(func=handle_agent_draft)

    # agent audit
    p_ag_audit = agent_subs.add_parser("audit", help="Run quality gates audit with structured line issues")
    p_ag_audit.add_argument("--target", required=True, help="Target markdown file to audit")
    p_ag_audit.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_ag_audit.set_defaults(func=handle_agent_audit)

    # agent patch
    p_ag_patch = agent_subs.add_parser("patch", help="Apply line-level patch to markdown document")
    p_ag_patch.add_argument("--file", required=True, help="Path to markdown file")
    p_ag_patch.add_argument("--line", type=int, required=True, help="1-indexed line number to replace")
    p_ag_patch.add_argument("--replace", required=True, help="New line content")
    p_ag_patch.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_ag_patch.set_defaults(func=handle_agent_patch)

    # agent roles
    p_ag_roles = agent_subs.add_parser("roles", help="List all pre-designed agent roles & personas")
    p_ag_roles.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_ag_roles.set_defaults(func=handle_agent_roles)

    # agent prompt
    p_ag_prompt = agent_subs.add_parser("prompt", help="Get pre-designed system prompt for an agent role")
    p_ag_prompt.add_argument("--role", required=True, choices=["drafter", "critic", "architect", "harmonizer", "sci_plot"], help="Role ID")
    p_ag_prompt.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_ag_prompt.set_defaults(func=handle_agent_prompt)

    # agent detect
    p_ag_detect = agent_subs.add_parser("detect", help="Detect installed local Agent CLIs (Antigravity, Claude Code, Codex, Grok, Aider)")
    p_ag_detect.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_ag_detect.set_defaults(func=handle_agent_detect_clis)

    # agent run-cli
    p_ag_run = agent_subs.add_parser("run-cli", help="Dispatch section writing task to a local Agent CLI tool")
    p_ag_run.add_argument("--agent", required=True, help="Agent CLI name (e.g. antigravity, claude, codex, grok)")
    p_ag_run.add_argument("--section", required=True, help="Section ID to edit/draft")
    p_ag_run.add_argument("--instruction", required=True, help="Task instruction prompt")
    p_ag_run.add_argument("--preset", default=None, help="Optional user prompt preset role (e.g. drafter, critic)")
    p_ag_run.add_argument("--timeout", type=int, default=120, help="Execution timeout in seconds")
    p_ag_run.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_ag_run.set_defaults(func=handle_agent_run_cli)

    # agent register-cli
    p_ag_reg = agent_subs.add_parser("register-cli", help="Register or customize a local Agent CLI command template")
    p_ag_reg.add_argument("--name", required=True, help="Agent identifier")
    p_ag_reg.add_argument("--cmd", required=True, help="Command executable (e.g. agy, claude, cursor-agent)")
    p_ag_reg.add_argument("--pattern", required=True, help="Args pattern (e.g. '-p {instruction}')")
    p_ag_reg.add_argument("--desc", default=None, help="Agent description")
    p_ag_reg.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_ag_reg.set_defaults(func=handle_agent_register_cli)

    # ==========================================
    # DOCUMENT TOOLKIT COMMANDS (For AI Agents)
    # ==========================================
    p_doc = subparsers.add_parser("doc", help="Document inspection & AST queries for AI Agents")
    doc_subs = p_doc.add_subparsers(dest="doc_action", help="Document action")

    # doc get
    p_doc_get = doc_subs.add_parser("get", help="Get section content and AST blocks in JSON")
    p_doc_get.add_argument("--section", required=True, help="Section ID or filename")
    p_doc_get.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_doc_get.set_defaults(func=handle_doc_get)

    # doc stats
    p_doc_stats = doc_subs.add_parser("stats", help="Get full document metrics, word counts, and citations")
    p_doc_stats.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_doc_stats.set_defaults(func=handle_doc_stats)

    # doc scorecard
    p_doc_sc = doc_subs.add_parser("scorecard", help="Get academic quality scorecard & radar metrics")
    p_doc_sc.add_argument("--html", default=None, help="Export quality audit scorecard to standalone HTML report")
    p_doc_sc.add_argument("--json", action=argparse.BooleanOptionalAction, default=None)
    p_doc_sc.set_defaults(func=cmd_scorecard)

    # ==========================================
    # OFFICE CLI TOOLKIT (Word .docx, Excel, PPT)
    # ==========================================
    p_office = subparsers.add_parser("office", help="Office document creation and inspection toolkit")
    p_office.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_office.set_defaults(func=cmd_office)
    p_office_subs = p_office.add_subparsers(dest="office_action", help="Office action")
    
    p_off_docx = p_office_subs.add_parser("create-docx", help="Convert Markdown or template to styled Word .docx")
    p_off_docx.add_argument("--input", required=True, help="Input markdown file path")
    p_off_docx.add_argument("--output", required=True, help="Output docx file path")
    p_off_docx.add_argument("--title", default="Document", help="Document title")
    p_off_docx.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_off_docx.set_defaults(func=cmd_office)

    p_off_insp = p_office_subs.add_parser("inspect", help="Inspect Office document structure and metadata")
    p_off_insp.add_argument("--file", required=True, help="Path to .docx, .xlsx, or .pptx file")
    p_off_insp.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_off_insp.set_defaults(func=cmd_office)

    p_off_run = p_office_subs.add_parser("run", help="Run raw officecli command")
    p_off_run.add_argument("extra_args", nargs=argparse.REMAINDER, help="Arguments passed to officecli")
    p_off_run.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_off_run.set_defaults(func=cmd_office)

    # ==========================================
    # SCIENTIFIC PLOT TOOLKIT (Nature/Science/IEEE)
    # ==========================================
    p_plot = subparsers.add_parser("plot", help="Publication-grade scientific figure generator (Nature/Science/IEEE)")
    p_plot.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_plot.set_defaults(func=cmd_plot)
    p_plot_subs = p_plot.add_subparsers(dest="plot_action", help="Plot action")

    p_plt_curve = p_plot_subs.add_parser("curve", help="Plot multi-series benchmark or experimental curve")
    p_plt_curve.add_argument("--data", default=None, help="JSON or CSV file with series data")
    p_plt_curve.add_argument("--output", default="assets/benchmark_curve.png", help="Output PNG path")
    p_plt_curve.add_argument("--title", default="", help="Chart title")
    p_plt_curve.add_argument("--xlabel", default="Concurrency (Agents)", help="X-axis label")
    p_plt_curve.add_argument("--ylabel", default="Reconciliation Latency (ms)", help="Y-axis label")
    p_plt_curve.add_argument("--style", default="nature", choices=["nature", "science", "ieee"], help="Publication style palette")
    p_plt_curve.add_argument("--dpi", type=int, default=300, help="Resolution DPI")
    p_plt_curve.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_plt_curve.set_defaults(func=cmd_plot)

    p_plt_run = p_plot_subs.add_parser("run", help="Execute custom Python scientific plotting script")
    p_plt_run.add_argument("--script", required=True, help="Path to python script")
    p_plt_run.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_plt_run.set_defaults(func=cmd_plot)

    # ==========================================
    # PUBLICATION PDF TOOLKIT (KaiTi + Times, 14pt)
    # ==========================================
    p_pdf = subparsers.add_parser("pdf", help="Publication-grade PDF compilation engine")
    p_pdf.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_pdf.set_defaults(func=cmd_pdf)
    p_pdf_subs = p_pdf.add_subparsers(dest="pdf_action", help="PDF action")

    p_pdf_compile = p_pdf_subs.add_parser("compile", help="Compile Markdown to publication PDF")
    p_pdf_compile.add_argument("--input", required=True, help="Input Markdown file path")
    p_pdf_compile.add_argument("--output", default="dist/publication_report.pdf", help="Output PDF path")
    p_pdf_compile.add_argument("--title", default="SynapseForge Publication Report", help="Document Header Title")
    p_pdf_compile.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_pdf_compile.set_defaults(func=cmd_pdf)

    # ==========================================
    # CITE & BIBLIOGRAPHY TOOLKIT
    # ==========================================
    p_cite = subparsers.add_parser("cite", help="BibTeX citations lookup and management")
    p_cite.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_cite.set_defaults(func=cmd_cite)
    p_cite_subs = p_cite.add_subparsers(dest="cite_action", help="Cite action")

    p_ct_list = p_cite_subs.add_parser("list", help="List all BibTeX entries in bibliography.bib")
    p_ct_list.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_ct_list.set_defaults(func=cmd_cite)

    p_ct_add = p_cite_subs.add_parser("add", help="Add new citation to bibliography.bib")
    p_ct_add.add_argument("--key", required=True, help="Citation key (e.g. lamport1998)")
    p_ct_add.add_argument("--title", required=True, help="Paper or book title")
    p_ct_add.add_argument("--author", required=True, help="Author names")
    p_ct_add.add_argument("--year", default="2026", help="Publication year")
    p_ct_add.add_argument("--journal", default="", help="Journal or venue name")
    p_ct_add.add_argument("--type", default="article", help="Entry type")
    p_ct_add.add_argument("--doi", default="", help="Optional DOI")
    p_ct_add.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_ct_add.set_defaults(func=cmd_cite)

    p_ct_lookup = p_cite_subs.add_parser("lookup", help="Query CrossRef API for a given DOI")
    p_ct_lookup.add_argument("doi", help="Digital Object Identifier (DOI)")
    p_ct_lookup.add_argument("--add", action="store_true", help="Automatically append to bibliography.bib")
    p_ct_lookup.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_ct_lookup.set_defaults(func=cmd_cite)

    p_ct_search = p_cite_subs.add_parser("search", help="Search CrossRef literature by keyword/title")
    p_ct_search.add_argument("query", help="Search query string")
    p_ct_search.add_argument("--limit", type=int, default=5, help="Maximum search results")
    p_ct_search.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_ct_search.set_defaults(func=cmd_cite)

    p_ct_val = p_cite_subs.add_parser("validate", help="Validate document citation graph against bibliography.bib")
    p_ct_val.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_ct_val.set_defaults(func=cmd_cite)

    # ==========================================
    # SNAPSHOT & ROLLBACK TOOLKIT
    # ==========================================
    p_snap = subparsers.add_parser("snapshot", help="Git-backed document checkpointing and rollback")
    p_snap.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_snap.set_defaults(func=cmd_snapshot)
    p_snap_subs = p_snap.add_subparsers(dest="snap_action", help="Snapshot action")

    p_sn_create = p_snap_subs.add_parser("create", help="Create an atomic checkpoint commit")
    p_sn_create.add_argument("--message", "-m", required=True, help="Commit description")
    p_sn_create.add_argument("--section", default=None, help="Specific section ID")
    p_sn_create.add_argument("--author", default="Human", help="Author name")
    p_sn_create.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_sn_create.set_defaults(func=cmd_snapshot)

    p_sn_list = p_snap_subs.add_parser("list", help="List checkpoint history")
    p_sn_list.add_argument("--section", default=None, help="Filter by section ID")
    p_sn_list.add_argument("--limit", type=int, default=10, help="Max entries")
    p_sn_list.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_sn_list.set_defaults(func=cmd_snapshot)

    p_sn_roll = p_snap_subs.add_parser("rollback", help="Roll back document or section to a checkpoint hash")
    p_sn_roll.add_argument("--commit", required=True, help="Commit hash (e.g. a1b2c3d or HEAD~1)")
    p_sn_roll.add_argument("--file", default=None, help="Optional specific file path")
    p_sn_roll.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_sn_roll.set_defaults(func=cmd_snapshot)

    # ==========================================
    # RESEARCH INGESTION TOOLKIT
    # ==========================================
    p_ing = subparsers.add_parser("ingest", help="Ingest research literature, ArXiv, notes into context")
    p_ing.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_ing.set_defaults(func=cmd_ingest)
    p_ing_subs = p_ing.add_subparsers(dest="ingest_action", help="Ingest action")

    p_in_add = p_ing_subs.add_parser("add", help="Add text note or file into project context")
    p_in_add.add_argument("--id", required=True, help="Source identifier")
    p_in_add.add_argument("--title", required=True, help="Source title")
    p_in_add.add_argument("--content", default="", help="Note content")
    p_in_add.add_argument("--file", default=None, help="File to ingest")
    p_in_add.add_argument("--tags", default="", help="Comma-separated tags")
    p_in_add.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_in_add.set_defaults(func=cmd_ingest)

    p_in_list = p_ing_subs.add_parser("list", help="List all ingested research sources")
    p_in_list.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_in_list.set_defaults(func=cmd_ingest)

    # ==========================================
    # SCIENTIFIC FIGURE LINKER
    # ==========================================
    p_fig = subparsers.add_parser("figure", help="Bind scientific figures with narrative discussion bridges")
    p_fig.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_fig.set_defaults(func=cmd_figure)
    p_fig_subs = p_fig.add_subparsers(dest="figure_action", help="Figure action")

    p_fg_ins = p_fig_subs.add_parser("insert", help="Insert figure into section with caption and bridge")
    p_fg_ins.add_argument("--section", required=True, help="Target section ID")
    p_fg_ins.add_argument("--image", required=True, help="Image file path")
    p_fg_ins.add_argument("--caption", required=True, help="Figure caption")
    p_fg_ins.add_argument("--num", type=int, default=1, help="Figure number")
    p_fg_ins.add_argument("--bridge", default=None, help="Discussion bridge sentence")
    p_fg_ins.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_fg_ins.set_defaults(func=cmd_figure)

    # ==========================================
    # LLM MODEL PROVIDER MESH ROUTER
    # ==========================================
    p_prov = subparsers.add_parser("provider", help="Multi-model LLM routing and GPU node latency ping")
    p_prov.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_prov.set_defaults(func=cmd_provider)
    p_prov_subs = p_prov.add_subparsers(dest="provider_action", help="Provider action")

    p_pr_list = p_prov_subs.add_parser("list", help="List all configured LLM providers and models")
    p_pr_list.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_pr_list.set_defaults(func=cmd_provider)

    p_pr_ping = p_prov_subs.add_parser("ping", help="Ping LLM provider endpoint latency")
    p_pr_ping.add_argument("--provider-id", required=True, help="Provider ID (e.g. deepseek, ollama_local)")
    p_pr_ping.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_pr_ping.set_defaults(func=cmd_provider)

    # ==========================================
    # MULTI-DOCUMENT VARIANTS & SYNTHESIS
    # ==========================================
    p_var = subparsers.add_parser("variant", help="Create independent candidate drafts and synthesize/merge them")
    p_var.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_var.set_defaults(func=cmd_variant)
    p_var_subs = p_var.add_subparsers(dest="variant_action", help="Variant action")

    p_vr_create = p_var_subs.add_parser("create", help="Create an independent document variant draft")
    p_vr_create.add_argument("--id", required=True, help="Variant ID (e.g. var_theory_proofs)")
    p_vr_create.add_argument("--name", required=True, help="Variant human readable name")
    p_vr_create.add_argument("--section", required=True, help="Target section ID")
    p_vr_create.add_argument("--base", default=None, help="Optional base file to branch from")
    p_vr_create.add_argument("--author", default="Drafter", help="Author agent name")
    p_vr_create.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_vr_create.set_defaults(func=cmd_variant)

    p_vr_list = p_var_subs.add_parser("list", help="List all candidate document variants")
    p_vr_list.add_argument("--section", default=None, help="Filter by section ID")
    p_vr_list.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_vr_list.set_defaults(func=cmd_variant)

    p_vr_merge = p_var_subs.add_parser("merge", help="Synthesize multiple candidate variants into master document")
    p_vr_merge.add_argument("--inputs", required=True, help="Comma-separated variant files to merge")
    p_vr_merge.add_argument("--output", required=True, help="Target merged master document path")
    p_vr_merge.add_argument("--strategy", default="harmonize", choices=["harmonize", "union", "concatenate"], help="Synthesis strategy")
    p_vr_merge.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_vr_merge.set_defaults(func=cmd_variant)

    # ==========================================
    # MULTI-FORMAT PUBLICATION EXPORTER
    # ==========================================
    p_exp = subparsers.add_parser("export", help="Compile and export project to PDF, Word docx, HTML, and ZIP package")
    p_exp.add_argument("--title", default=None, help="Document Title")
    p_exp.add_argument("--json", action=argparse.BooleanOptionalAction, default=None)
    p_exp.set_defaults(func=cmd_export)

    # ==========================================
    # ACADEMIC QUALITY SCORECARD & RADAR
    # ==========================================
    p_sc = subparsers.add_parser("scorecard", help="Compute quantitative Anti-AI, citation, and mathematical rigor scorecard")
    p_sc.add_argument("--html", default=None, help="Export quality audit scorecard to standalone HTML report")
    p_sc.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_sc.set_defaults(func=cmd_scorecard)

    # ==========================================
    # NOTIFICATION DISPATCHER
    # ==========================================
    p_notif = subparsers.add_parser("notify", help="Dispatch milestone notifications to human author via Email/Webhook")
    p_notif.add_argument("--title", required=True, help="Notification title")
    p_notif.add_argument("--message", required=True, help="Notification body message")
    p_notif.add_argument("--channel", default="email", choices=["email", "webhook", "cli"], help="Notification channel")
    p_notif.add_argument("--email", default="361487867@qq.com", help="Recipient email")
    p_notif.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_notif.set_defaults(func=cmd_notify)

    # ==========================================
    # USER-DEFINED CUSTOM PROMPT & PERSONA MANAGER
    # ==========================================
    p_pmt = subparsers.add_parser("prompt", help="User-defined custom agent prompts & personas manager")
    p_pmt.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_pmt.set_defaults(func=cmd_user_prompts)
    pmt_subs = p_pmt.add_subparsers(dest="prompt_action", help="Prompt actions")

    p_pmt_list = pmt_subs.add_parser("list", help="List all user-defined custom agent prompts")
    p_pmt_list.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_pmt_list.set_defaults(func=cmd_user_prompts)

    p_pmt_set = pmt_subs.add_parser("set", help="Create or update user custom agent prompt")
    p_pmt_set.add_argument("--role", required=True, help="Custom role identifier (e.g. quantum_theorist)")
    p_pmt_set.add_argument("--file", default=None, help="Path to markdown prompt file")
    p_pmt_set.add_argument("--prompt", default=None, help="Prompt text string")
    p_pmt_set.add_argument("--name", default=None, help="Display name")
    p_pmt_set.add_argument("--desc", default=None, help="Role description")
    p_pmt_set.add_argument("--model", default=None, help="Preferred LLM model")
    p_pmt_set.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_pmt_set.set_defaults(func=cmd_user_prompts)

    p_pmt_get = pmt_subs.add_parser("get", help="Get user custom agent prompt")
    p_pmt_get.add_argument("--role", required=True, help="Role ID")
    p_pmt_get.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_pmt_get.set_defaults(func=cmd_user_prompts)

    p_pmt_del = pmt_subs.add_parser("delete", help="Delete a user custom agent prompt")
    p_pmt_del.add_argument("--role", required=True, help="Role ID")
    p_pmt_del.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_pmt_del.set_defaults(func=cmd_user_prompts)

    # ==========================================
    # CENTRALIZED WORKSPACE VAULT & FILE MANAGER
    # ==========================================
    p_vlt = subparsers.add_parser("vault", help="Centralized workspace vault & auto-copy external files manager")
    p_vlt.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_vlt.set_defaults(func=cmd_vault)
    vlt_subs = p_vlt.add_subparsers(dest="vault_action", help="Vault action")

    p_vlt_list = vlt_subs.add_parser("list", help="List all workspace files categorized by dedicated directories")
    p_vlt_list.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_vlt_list.set_defaults(func=cmd_vault)

    p_vlt_import = vlt_subs.add_parser("import", help="Auto-copy an external file into the dedicated vault")
    p_vlt_import.add_argument("--file", required=True, help="Path to external file")
    p_vlt_import.add_argument("--category", default=None, help="Target dedicated directory (sections, imports, references, figures...)")
    p_vlt_import.add_argument("--overwrite", action="store_true", default=False)
    p_vlt_import.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_vlt_import.set_defaults(func=cmd_vault)

    p_vlt_init = vlt_subs.add_parser("init", help="Ensure all dedicated vault folders are initialized")
    p_vlt_init.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_vlt_init.set_defaults(func=cmd_vault)

    # ==========================================
    # CONFIDENTIALITY & CRYPTOGRAPHIC SECURITY
    # ==========================================
    p_sec = subparsers.add_parser("secure", help="Confidentiality audit, secret redaction, and at-rest AES encryption")
    p_sec.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_sec.set_defaults(func=cmd_security)
    sec_subs = p_sec.add_subparsers(dest="sec_action", help="Security action")

    p_sc_audit = sec_subs.add_parser("audit", help="Audit sections or file for exposed API keys, secrets, PII, and classified terms")
    p_sc_audit.add_argument("--path", default=None, help="Target file or folder to audit")
    p_sc_audit.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_sc_audit.set_defaults(func=cmd_security)

    p_sc_redact = sec_subs.add_parser("redact", help="Mask sensitive secrets with cryptographic tokens")
    p_sc_redact.add_argument("--input", required=True, help="Input markdown file")
    p_sc_redact.add_argument("--output", default=None, help="Output sanitized markdown file")
    p_sc_redact.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_sc_redact.set_defaults(func=cmd_security)

    p_sc_enc = sec_subs.add_parser("encrypt", help="At-rest AES-GCM stream encrypt a document with passphrase")
    p_sc_enc.add_argument("--file", required=True, help="Path to markdown document to encrypt")
    p_sc_enc.add_argument("--passphrase", required=True, help="User secret passphrase")
    p_sc_enc.add_argument("--output", default=None, help="Output .enc.json path")
    p_sc_enc.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_sc_enc.set_defaults(func=cmd_security)

    p_sc_dec = sec_subs.add_parser("decrypt", help="Decrypt an encrypted .enc.json document")
    p_sc_dec.add_argument("--file", required=True, help="Path to encrypted .enc.json document")
    p_sc_dec.add_argument("--passphrase", required=True, help="User secret passphrase")
    p_sc_dec.add_argument("--output", default=None, help="Output decrypted .md path")
    p_sc_dec.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_sc_dec.set_defaults(func=cmd_security)

    p_sc_term = sec_subs.add_parser("add-term", help="Register a confidential keyword or project codename")
    p_sc_term.add_argument("--term", required=True, help="Classified term or project codename")
    p_sc_term.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_sc_term.set_defaults(func=cmd_security)

    # ==========================================
    # REPORT SPECIFICATION & PUBLICATION ENGINE
    # ==========================================
    p_rep = subparsers.add_parser("report", help="Report Specification engine (Zero AI flavor, narrative prose, publication PDF)")
    p_rep.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_rep.set_defaults(func=cmd_report)
    rep_subs = p_rep.add_subparsers(dest="report_action", help="Report action")

    p_rp_new = rep_subs.add_parser("new", help="Generate a publication-grade report template adhering to Report-Spec")
    p_rp_new.add_argument("--title", required=True, help="Report title")
    p_rp_new.add_argument("--topic", required=True, help="Core subject or research topic")
    p_rp_new.add_argument("--type", default="whitepaper", choices=["whitepaper", "academic_review", "industry_analysis", "tech_survey", "empirical_study"], help="Report type")
    p_rp_new.add_argument("--output", default=None, help="Output markdown path")
    p_rp_new.add_argument("--author", default="SynapseForge Swarm Contributors", help="Author name")
    p_rp_new.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_rp_new.set_defaults(func=cmd_report)

    p_rp_lint = rep_subs.add_parser("lint", help="Audit a report against Report-Spec seven prohibitions and narrative prose")
    p_rp_lint.add_argument("--file", required=True, help="Path to markdown document to audit")
    p_rp_lint.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_rp_lint.set_defaults(func=cmd_report)

    p_rp_build = rep_subs.add_parser("build", help="Compile a Report-Spec markdown document to a publication-grade PDF")
    p_rp_build.add_argument("--file", required=True, help="Path to markdown document")
    p_rp_build.add_argument("--output", default=None, help="Output PDF path")
    p_rp_build.add_argument("--title", default=None, help="Document header title")
    p_rp_build.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_rp_build.set_defaults(func=cmd_report)

    p_rp_spec = rep_subs.add_parser("spec", help="Display the complete Report-Spec standards and seven prohibitions")
    p_rp_spec.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_rp_spec.set_defaults(func=cmd_report)

    p_rp_prompts = rep_subs.add_parser("prompts", help="Display or export built-in Report-Spec multi-agent system prompts")
    p_rp_prompts.add_argument("--json", action=argparse.BooleanOptionalAction, default=True)
    p_rp_prompts.set_defaults(func=cmd_report)

    args = parser.parse_args()
    if not args.command:
        print_banner()
        parser.print_help()
        return

    if not hasattr(args, "func"):
        # Subcommand groups (e.g. `agent`, `doc`) require a child action; show help instead of crashing.
        sub_parser = subparsers.choices.get(args.command)
        if sub_parser is not None:
            sub_parser.print_help()
        else:
            parser.print_help()
        sys.exit(1)

    if getattr(args, "json", None) is None:
        args.json = getattr(args, "json_global", False)

    args.func(args)


if __name__ == "__main__":
    main()
