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
        content_path = Path(args.content_file)
        if not content_path.exists():
            if getattr(args, "json", False):
                print(json.dumps({"ok": False, "error": f"Content file not found: {args.content_file}"}))
            else:
                print(f"✖ Content file not found: {args.content_file}")
            sys.exit(1)
        content = content_path.read_text(encoding="utf-8")

    from synapseforge.core.file_lock import AutoSectionLock, SectionLockedError

    try:
        with AutoSectionLock(section_id=args.section, agent_name=args.agent) as lock:
            # File is strictly locked while writing
            lock.write_draft(content, target_file_path=sec_file)
            
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

            try:
                sec_file_display = str(sec_file.relative_to(Path.cwd()))
            except ValueError:
                sec_file_display = str(sec_file)

            res = {
                "ok": True,
                "section_id": args.section,
                "agent": args.agent,
                "file": sec_file_display,
                "word_count": words,
                "ast_block_count": len(blocks),
                "citations": parser.extract_citations(content),
                "lock_status": "auto_released",
            }
    except SectionLockedError as e:
        res = {"ok": False, "error": str(e), "section_id": args.section}
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2))
        else:
            print(f"✖ Lock Error: {e}")
        sys.exit(1)

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(f"✓ Draft saved to '{sec_file.name}' ({words} words, {len(blocks)} AST blocks, lock auto-released)")


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

    from synapseforge.core.file_lock import AutoSectionLock, SectionLockedError

    agent_name = getattr(args, "agent", "Critic-Adversarial")
    section_id = target_path.stem

    try:
        with AutoSectionLock(section_id=section_id, agent_name=agent_name) as lock:
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
                "lock_status": "auto_released",
            }
    except SectionLockedError as e:
        res = {"ok": False, "error": str(e), "file": str(target_path)}
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2))
        else:
            print(f"✖ Lock Error: {e}")
        sys.exit(1)

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(f"✓ Applied patch to '{target_path.name}' at line {args.line} (lock auto-released)")
        print(f"  - Original: {original_line}")
        print(f"  + Replaced: {args.replace}")


def handle_agent_roles(args):
    """Lists all pre-designed agent roles and their descriptions."""
    from synapseforge.core.agent_roles import AgentRoleManager
    mgr = AgentRoleManager()
    roles = mgr.list_roles()

    if getattr(args, "json", False):
        print(json.dumps({"ok": True, "roles": roles}, indent=2, ensure_ascii=False))
    else:
        print(f"\nPre-Designed Swarm Agent Roles ({len(roles)} Personas):")
        print(f"{'Role ID':<12} | {'Name':<32} | {'Recommended Model':<30}")
        print("-" * 80)
        for r in roles:
            print(f"{r['role_id']:<12} | {r['name']:<32} | {r['recommended_model']:<30}")
        print()


def handle_agent_prompt(args):
    """Fetches the full pre-designed system prompt markdown for an agent role."""
    from synapseforge.core.agent_roles import AgentRoleManager
    mgr = AgentRoleManager()
    try:
        prompt_text = mgr.get_system_prompt(args.role)
        if getattr(args, "json", False):
            print(json.dumps({"ok": True, "role": args.role, "system_prompt": prompt_text}, indent=2, ensure_ascii=False))
        else:
            print(prompt_text)
    except KeyError as e:
        res = {"ok": False, "error": str(e)}
        if getattr(args, "json", False):
            print(json.dumps(res, indent=2))
        else:
            print(f"✖ Error: {e}")
        sys.exit(1)


def handle_agent_detect_clis(args):
    """Scans and lists local Agent CLI tools installed on the user's host machine."""
    from synapseforge.core.local_agent_cli import LocalAgentCLIManager
    mgr = LocalAgentCLIManager()
    clis = mgr.detect_available_clis()

    if getattr(args, "json", False):
        print(json.dumps({"ok": True, "local_agent_clis": clis}, indent=2, ensure_ascii=False))
    else:
        print(f"\nLocal Agent CLI Fleet Detected ({len(clis)} registered engines):")
        print(f"{'Agent Name':<15} | {'Installed':<10} | {'Binary / Executable Path':<40}")
        print("-" * 75)
        for c in clis:
            status = "✓ READY" if c["installed"] else "✖ Missing"
            path_str = c["executable_path"] or f"({c['binary']} not in PATH)"
            print(f"{c['agent_name']:<15} | {status:<10} | {path_str:<40}")
        print()


def handle_agent_run_cli(args):
    """Executes a section writing task by dispatching directly to a local Agent CLI tool."""
    from synapseforge.core.local_agent_cli import LocalAgentCLIManager
    mgr = LocalAgentCLIManager()
    res = mgr.run_agent_cli(
        agent_name=args.agent,
        section_id=args.section,
        user_instruction=args.instruction,
        role_preset=getattr(args, "preset", None),
        timeout=getattr(args, "timeout", 120),
    )

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        if res.get("ok"):
            print(f"✓ Local Agent CLI '{args.agent}' completed task on section '{args.section}'")
            print(f"  - Executable: {res.get('binary')}")
            print(f"  - Target file: {res.get('target_file')}")
            print(f"  - Lock status: {res.get('lock_status')}")
            if res.get("stdout"):
                print(f"  - Output:\n{res['stdout'][:500]}")
        else:
            print(f"✖ Local Agent CLI execution failed: {res.get('error')}")
            sys.exit(1)


def handle_agent_register_cli(args):
    """Registers or customizes a local Agent CLI template."""
    from synapseforge.core.local_agent_cli import LocalAgentCLIManager
    mgr = LocalAgentCLIManager()
    pattern = args.pattern.split() if isinstance(args.pattern, str) else args.pattern
    res = mgr.register_cli(
        name=args.name,
        binary=args.cmd,
        args_pattern=pattern,
        description=getattr(args, "desc", None),
    )

    if getattr(args, "json", False):
        print(json.dumps(res, indent=2, ensure_ascii=False))
    else:
        print(f"✓ Registered local agent CLI '{args.name}' using command '{args.cmd}'")
