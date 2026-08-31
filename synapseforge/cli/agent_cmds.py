"""
Agent-specific CLI command handlers.
Enables programmatic execution for AI Agents (Drafter, Critic, Harmonizer, Architect, Visualizer).
Supports structured JSON output (--json) for seamless LLM agent tool-use.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from synapseforge.config import load_config
from synapseforge.core.ast_parser import MarkdownASTParser
from synapseforge.core.state import SectionStatus, StateManager
from synapseforge.linters import LintSuite


def handle_agent_list(args):
    """Lists all configured swarm agents, their model configs, and assigned roles."""
    config = load_config()
    state_mgr = StateManager()
    state_mgr.sync_from_config(config)

    agents_data = []
    for a in config.swarm:
        # Find active leases held by this agent
        held_leases = [
            sec_id for sec_id, holder in state_mgr.state.active_locks.items()
            if holder == a.name or holder == a.role
        ]
        agents_data.append({
            "role": a.role,
            "name": a.name,
            "model": a.model,
            "responsibilities": a.responsibilities,
            "active_leases": held_leases,
            "status": "busy" if held_leases else "idle",
        })

    if getattr(args, "json", False):
        print(json.dumps({"ok": True, "agents": agents_data}, indent=2, ensure_ascii=False))
    else:
        print(f"\nSwarm Agents Fleet ({len(agents_data)} Agents):")
        print(f"{'Role':<15} | {'Name':<20} | {'Status':<10} | {'Active Leases'}")
        print("-" * 65)
        for ag in agents_data:
            leases_str = ", ".join(ag["active_leases"]) if ag["active_leases"] else "-"
            print(f"{ag['role']:<15} | {ag['name']:<20} | {ag['status']:<10} | {leases_str}")
        print()


def handle_agent_claim(args):
    """Atomically acquires an exclusive writing lease on a section for an agent."""
    config = load_config()
    state_mgr = StateManager()
    state_mgr.sync_from_config(config)

    try:
        success = state_mgr.claim_section(
            section_id=args.section,
            actor=args.agent,
            lease_duration_seconds=args.lease,
        )
        msg = "Lease acquired" if success else "Section currently locked by another actor"
    except KeyError as e:
        success = False
        msg = str(e)

    res = {
        "ok": success,
        "section_id": args.section,
        "agent": args.agent,
        "lease_seconds": args.lease,
        "message": msg,
    }

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        if success:
            print(f"✓ Successfully acquired lease on '{args.section}' for agent '{args.agent}' ({args.lease}s)")
        else:
            print(f"✖ Failed to acquire lease: {msg}")
            sys.exit(1)


def handle_agent_release(args):
    """Releases an exclusive section lease."""
    config = load_config()
    state_mgr = StateManager()
    state_mgr.sync_from_config(config)

    success = state_mgr.release_section(section_id=args.section, actor=args.agent)
    res = {
        "ok": success,
        "section_id": args.section,
        "agent": args.agent,
        "message": "Lease released" if success else "Failed to release lease (not owner or not found)",
    }

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        if success:
            print(f"✓ Released lease on '{args.section}' for agent '{args.agent}'")
        else:
            print(f"✖ Could not release lease on '{args.section}'")
            sys.exit(1)


def handle_agent_draft(args):
    """Writes drafted content to a section file, parses AST blocks, and updates state hash."""
    config = load_config()
    state_mgr = StateManager()
    state_mgr.sync_from_config(config)

    # Find section file
    sec_file = None
    for s in config.sections:
        if s.id == args.section:
            sec_file = Path.cwd() / s.file
            break

    if not sec_file:
        sec_file = Path.cwd() / "sections" / f"{args.section}.md"

    content = args.content
    if args.content_file:
        content = Path(args.content_file).read_text(encoding="utf-8")

    sec_file.parent.mkdir(parents=True, exist_ok=True)
    sec_file.write_text(content, encoding="utf-8")

    # Parse AST and word count
    parser = MarkdownASTParser()
    blocks = parser.parse_blocks(content)
    words = parser.count_words(content)

    state_mgr.update_section(
        section_id=args.section,
        status=SectionStatus.DRAFTING,
        assigned_actor=args.agent,
        word_count=words,
    )

    res = {
        "ok": True,
        "section_id": args.section,
        "agent": args.agent,
        "file": str(sec_file.relative_to(Path.cwd())),
        "word_count": words,
        "ast_block_count": len(blocks),
        "citations": parser.extract_citations(content),
    }

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(f"✓ Draft saved to '{sec_file.name}' ({words} words, {len(blocks)} AST blocks, {len(res['citations'])} citations)")


def handle_agent_audit(args):
    """Runs quality gates (Anti-AI, citations, style, coherence) and outputs structured line-by-line issues."""
    config = load_config()
    bib_file = Path.cwd() / config.quality_gates.citations.get("bib_file", "bibliography.bib")
    suite = LintSuite(quality_gates=config.quality_gates, bib_file=bib_file, glossary=config.glossary)

    target_path = Path(args.target)
    if not target_path.exists():
        res = {"ok": False, "error": f"Target file not found: {target_path}"}
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2))
        else:
            print(f"✖ Error: {target_path} not found")
        sys.exit(1)

    report = suite.lint_file(target_path)

    issues_json = [
        {
            "linter": i.linter_name,
            "severity": i.severity,
            "line": i.line_start,
            "message": i.message,
            "snippet": i.snippet,
            "suggestion": i.suggestion,
        }
        for i in report.all_issues
    ]

    res = {
        "ok": True,
        "target": str(target_path),
        "passed": report.passed,
        "total_errors": report.total_errors,
        "total_warnings": report.total_warnings,
        "issues": issues_json,
    }

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        status_str = "PASSED" if report.passed else "FAILED"
        print(f"\nAudit Report for '{target_path.name}': [{status_str}] (Errors: {report.total_errors}, Warnings: {report.total_warnings})")
        for i in report.all_issues:
            icon = "✖" if i.severity == "error" else "⚠"
            print(f"  {icon} [{i.linter_name}] Line {i.line_start}: {i.message}")
            if i.suggestion:
                print(f"    Suggested Patch: {i.suggestion}")
        print()
        if not report.passed:
            sys.exit(1)


def handle_agent_patch(args):
    """Applies an agent's suggested patch to a specific line in a markdown file."""
    target_path = Path(args.file)
    if not target_path.exists():
        res = {"ok": False, "error": f"File not found: {target_path}"}
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2))
        else:
            print(f"✖ File not found: {target_path}")
        sys.exit(1)

    lines = target_path.read_text(encoding="utf-8").splitlines()
    line_idx = args.line - 1

    if line_idx < 0 or line_idx >= len(lines):
        res = {"ok": False, "error": f"Line {args.line} out of range (total lines: {len(lines)})"}
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2))
        else:
            print(f"✖ Line {args.line} out of range")
        sys.exit(1)

    original_line = lines[line_idx]
    lines[line_idx] = args.replace

    new_content = "\n".join(lines) + "\n"
    target_path.write_text(new_content, encoding="utf-8")

    res = {
        "ok": True,
        "file": str(target_path),
        "line": args.line,
        "original": original_line,
        "replaced": args.replace,
    }

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(f"✓ Applied patch to '{target_path.name}' at line {args.line}")
        print(f"  - Original: {original_line}")
        print(f"  + Replaced: {args.replace}")
