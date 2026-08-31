"""
SynapseForge Command Line Interface (CLI).
The central toolkit for distributed multi-agent collaborative writing, quality gating, Tailscale mesh networking, and GitHub synchronization.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional

from synapseforge import __version__
from synapseforge.config import ProjectConfig, load_config
from synapseforge.core.conflict_resolver import SemanticConflictResolver
from synapseforge.core.engine import SwarmEngine
from synapseforge.github_bridge.ci_reporter import CIReporter
from synapseforge.github_bridge.issue_orchestrator import IssueTaskOrchestrator
from synapseforge.github_bridge.pr_reviewer import PRReviewRunner
from synapseforge.linters import LintSuite
from synapseforge.network.room_sync import DistributedRoomManager
from synapseforge.network.tailscale_mesh import TailscaleMeshManager
from synapseforge.renderers.pipeline import PublicationPipeline


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
    {Color.GRAY}GitOps & Tailscale Multi-Agent Distributed Collaborative Writing Engine v{__version__}{Color.RESET}
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
    print(f"\n{Color.CYAN}{Color.BOLD}Document Structure Plan (Topological Order):{Color.RESET}")
    print(f"{'Order':<6} | {'Section ID':<25} | {'Role':<12} | {'Target File':<35}")
    print("-" * 85)
    for idx, s in enumerate(sections, 1):
        print(f"{idx:<6} | {s.id:<25} | {s.assigned_role:<12} | {s.file:<35}")
    print(f"\n{Color.GREEN}✓ Document plan synced with {len(sections)} sections.{Color.RESET}\n")


def cmd_status(args):
    engine = SwarmEngine()
    tree = engine.get_document_tree()
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
        sec_dir = Path.cwd() / "sections"
        targets = list(sec_dir.glob("*.md")) if sec_dir.exists() else list(Path.cwd().glob("*.md"))

    if not targets:
        print(f"{Color.YELLOW}No markdown files found to lint.{Color.RESET}")
        return

    print(f"{Color.CYAN}{Color.BOLD}Running SynapseForge Document Quality Gates on {len(targets)} files...{Color.RESET}\n")
    all_passed = True

    for t in sorted(targets):
        report = suite.lint_file(t)
        status_str = f"{Color.GREEN}PASSED{Color.RESET}" if report.passed else f"{Color.RED}FAILED{Color.RESET}"
        print(f"[{status_str}] {t.name} (Errors: {report.total_errors}, Warnings: {report.total_warnings})")

        for issue in report.all_issues:
            icon = f"{Color.RED}✖ Error{Color.RESET}" if issue.severity == "error" else f"{Color.YELLOW}⚠ Warning{Color.RESET}"
            print(f"  {icon} [{issue.linter_name}] Line {issue.line_start}: {issue.message}")
            if issue.snippet:
                print(f"    {Color.GRAY}Context: {issue.snippet[:90]}{Color.RESET}")

        if not report.passed:
            all_passed = False

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

    print(f"\n{Color.CYAN}{Color.BOLD}Semantic AST 3-Way Merge Result:{Color.RESET}")
    print(f"  - Output: {out_path}")
    print(f"  - Auto-Resolved Sections: {res.resolved_auto_count}")
    print(f"  - Semantic Conflicts: {res.conflict_count}")


def cmd_review(args):
    runner = PRReviewRunner()
    print(f"{Color.CYAN}{Color.BOLD}Running SynapseForge Multi-Agent Peer Review...{Color.RESET}")
    res = runner.run_full_pr_review(base_ref=args.base, pr_number=args.pr)
    print("\n" + res["summary_markdown"] + "\n")
    if not res["all_passed"] and args.ci:
        sys.exit(1)


def cmd_build(args):
    engine = SwarmEngine()
    master_md = engine.compile_full_document()
    pipeline = PublicationPipeline(config=engine.config)
    res = pipeline.build_all(master_md)

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
        print(f"\n{Color.GREEN}{Color.BOLD}✓ Shared Room Successfully Created & Replicated across Tailscale Mesh!{Color.RESET}")
        print(f"  - Room Slug: {room.slug}")
        print(f"  - Room ID: {room.room_id}")
        print(f"  - Synchronized Nodes: {', '.join(room.synced_nodes)}")
        print(f"  - Members Enrolled: {len(room.members)}\n")

    elif args.room_action == "join":
        room = room_mgr.join_shared_room(args.room_id, member_name=args.user or "xb")
        if room:
            print(f"{Color.GREEN}✓ Node successfully joined shared room '{room.name}' (Version {room.state_version}){Color.RESET}")
        else:
            print(f"{Color.RED}✖ Room '{args.room_id}' not found.{Color.RESET}")


def main():
    parser = argparse.ArgumentParser(
        prog="synapseforge",
        description="SynapseForge: GitOps & Tailscale Mesh Framework for Distributed Multi-Agent Collaborative Writing",
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # init
    p_init = subparsers.add_parser("init", help="Initialize a new SynapseForge repository")
    p_init.add_argument("--force", action="store_true", help="Overwrite existing configuration")
    p_init.set_defaults(func=cmd_init)

    # plan
    p_plan = subparsers.add_parser("plan", help="Generate document structure DAG & scaffolds")
    p_plan.set_defaults(func=cmd_plan)

    # status
    p_status = subparsers.add_parser("status", help="Display document writing status ledger")
    p_status.set_defaults(func=cmd_status)

    # lint
    p_lint = subparsers.add_parser("lint", help="Run document quality gates & anti-AI linter")
    p_lint.add_argument("target", nargs="?", default=None, help="Target markdown file or directory")
    p_lint.add_argument("--ci", action="store_true", help="Exit with code 1 on quality gate failure")
    p_lint.set_defaults(func=cmd_lint)

    # merge
    p_merge = subparsers.add_parser("merge", help="Execute AST-level 3-way conflict resolution")
    p_merge.add_argument("--base", required=True, help="Path to base document")
    p_merge.add_argument("--ours", required=True, help="Path to branch (ours) document")
    p_merge.add_argument("--theirs", required=True, help="Path to incoming (theirs) document")
    p_merge.add_argument("-o", "--output", required=True, help="Path to write merged document")
    p_merge.add_argument("--ours-label", default="OURS (Branch)", help="Label for ours")
    p_merge.add_argument("--theirs-label", default="THEIRS (Incoming)", help="Label for theirs")
    p_merge.set_defaults(func=cmd_merge)

    # review
    p_review = subparsers.add_parser("review", help="Run automated Multi-Agent PR peer review bot")
    p_review.add_argument("--base", default="main", help="Base git ref to diff against")
    p_review.add_argument("--pr", type=int, default=None, help="Pull Request number to comment on")
    p_review.add_argument("--ci", action="store_true", help="Exit with non-zero on failure in CI")
    p_review.set_defaults(func=cmd_review)

    # build
    p_build = subparsers.add_parser("build", help="Build publication deliverables (HTML, Typst, PDF)")
    p_build.set_defaults(func=cmd_build)

    # mesh
    p_mesh = subparsers.add_parser("mesh", help="Inspect Tailscale WireGuard P2P mesh network status")
    p_mesh.set_defaults(func=cmd_mesh)

    # room
    p_room = subparsers.add_parser("room", help="Manage multi-node shared collaborative rooms")
    p_room.add_argument("room_action", nargs="?", default="list", choices=["list", "create", "join"], help="Action: list, create, join")
    p_room.add_argument("--name", default="Distributed Whitepaper Room", help="Room name for create")
    p_room.add_argument("--title", default=None, help="Document title")
    p_room.add_argument("--type", default="academic_whitepaper", help="Document type")
    p_room.add_argument("--room-id", default="", help="Room ID or slug to join")
    p_room.add_argument("--user", default="xb", help="User name joining")
    p_room.set_defaults(func=cmd_room)

    args = parser.parse_args()
    if not args.command:
        print_banner()
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
