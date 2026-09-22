"""
Local team collaboration CLI.

``synapseforge team`` is the host-side bus for Codex, Grok Build, Antigravity
and humans sharing one writing workspace. It does not replace Tailscale mesh
rooms; it coordinates several Agent CLIs on the same machine.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from synapseforge.core.team_bus import open_bus
from synapseforge.core.team_launch import (
    CANONICAL_SEATS,
    doctor as run_doctor,
    launch_room,
    paste_prompt,
)


def _json_mode(args) -> bool:
    return bool(getattr(args, "json", False))


def emit(args, payload: Dict[str, Any], ok: bool = True, text: Optional[str] = None) -> None:
    if _json_mode(args):
        body = dict(payload)
        body.setdefault("ok", ok)
        print(json.dumps(body, indent=2, ensure_ascii=False, default=str))
        return
    if text:
        print(text)
        return
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def fail(args, message: str, extra: Optional[Dict[str, Any]] = None) -> None:
    payload = {"ok": False, "error": message}
    if extra:
        payload.update(extra)
    if _json_mode(args):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"✖ {message}")
    sys.exit(1)


def default_room(args) -> str:
    room = getattr(args, "room", None) or os.environ.get("SYNAPSEFORGE_ROOM") or os.environ.get("AGENT_TEAM_ROOM")
    if room:
        return room
    fail(args, "room is required (pass --room or set SYNAPSEFORGE_ROOM)")
    raise AssertionError("unreachable")


def default_workspace(args) -> str:
    raw = getattr(args, "cwd", None) or os.environ.get("SYNAPSEFORGE_WORKSPACE") or str(Path.cwd())
    return str(Path(raw).expanduser().resolve())


def default_agent(args) -> str:
    agent = getattr(args, "agent", None)
    if agent:
        return agent
    fail(args, "agent is required (codex, grok, antigravity, claude, or human)")
    raise AssertionError("unreachable")


def open_store(args):
    workspace = default_workspace(args)
    return open_bus(workspace=workspace), workspace


def handle_team(args):
    action = getattr(args, "team_action", None)
    dispatch = {
        "join": cmd_join,
        "status": cmd_status,
        "say": cmd_say,
        "messages": cmd_messages,
        "tasks": cmd_tasks,
        "create-task": cmd_create_task,
        "claim-task": cmd_claim_task,
        "update-task": cmd_update_task,
        "lock": cmd_lock,
        "unlock": cmd_unlock,
        "reclaim": cmd_reclaim,
        "claim-action": cmd_claim_action,
        "rooms": cmd_rooms,
        "docs": cmd_docs,
        "share": cmd_share,
        "open": cmd_open,
        "paste-prompts": cmd_paste_prompts,
        "mcp": cmd_mcp,
        "wait": cmd_wait,
        "leave": cmd_leave,
        "doctor": cmd_doctor,
    }
    if action not in dispatch:
        fail(args, f"unknown team action: {action}")
    try:
        dispatch[action](args)
    except ValueError as exc:
        fail(args, str(exc))


def cmd_join(args):
    store, workspace = open_store(args)
    result = store.join(
        default_room(args),
        default_agent(args),
        role=getattr(args, "role", "") or "",
        objective=getattr(args, "objective", "") or "",
        workspace=workspace,
    )
    emit(args, result, text=_format_join(result))


def _format_join(result: Dict[str, Any]) -> str:
    lines = [
        f"Joined room '{result['room']}' as {result['agent']}"
        + (" (observer — seat taken)" if result.get("already_online") else ""),
        f"session={result.get('session_id')}",
        f"documents={len(result.get('documents') or [])} active_tasks={len(result.get('active_tasks') or [])}",
    ]
    return "\n".join(lines)


def cmd_status(args):
    store, _ = open_store(args)
    result = store.status(default_room(args))
    if _json_mode(args):
        emit(args, result)
        return
    room = result["room"]
    print(f"Room: {room['name']}")
    print(f"Objective: {room.get('objective') or '-'}")
    print(f"Workspace: {room.get('workspace') or '-'}")
    print(f"Live: {', '.join(result['live_agents']) or '-'}")
    print(f"Silent: {', '.join(result['silent_agents']) or '-'}")
    print(f"Coordinator silent: {result['coordinator_silent']}")
    print("Participants:")
    for p in result["participants"]:
        flag = "online" if p.get("online") else "offline"
        print(f"  - {p['agent']} ({p.get('role') or 'n/a'}) {flag} last_seen={p.get('last_seen')}")
    print("Tasks:")
    for t in result["tasks"]:
        print(f"  #{t['id']} [{t['status']}] {t['title']} assignee={t.get('assignee') or '-'}")
    print("Locks:")
    for lock in result["file_locks"]:
        stale = " stale" if lock.get("holder_stale") else ""
        print(f"  - {lock['path']} holder={lock['agent']}{stale}")


def cmd_say(args):
    store, _ = open_store(args)
    message = getattr(args, "message", None) or ""
    result = store.post_message(
        default_room(args),
        default_agent(args),
        message,
        kind=getattr(args, "kind", None) or "discussion",
        to_agent=getattr(args, "to_agent", None) or None,
    )
    emit(args, result, text=f"#{result['id']} {result['kind']} from {result['sender']}")


def cmd_messages(args):
    store, _ = open_store(args)
    rows = store.read_messages(
        default_room(args),
        default_agent(args),
        after_id=getattr(args, "after_id", 0) or 0,
        limit=getattr(args, "limit", 50) or 50,
    )
    emit(args, {"messages": rows}, text="\n".join(
        f"#{m['id']} [{m['kind']}] {m['sender']}: {m['body']}" for m in rows
    ) or "(no messages)")


def cmd_tasks(args):
    store, _ = open_store(args)
    rows = store.list_tasks(default_room(args), status=getattr(args, "status", None) or None)
    emit(args, {"tasks": rows}, text="\n".join(
        f"#{t['id']} [{t['status']}] {t['title']} assignee={t.get('assignee') or '-'}"
        for t in rows
    ) or "(no tasks)")


def cmd_create_task(args):
    store, _ = open_store(args)
    files = _split_files(getattr(args, "files", None))
    result = store.create_task(
        default_room(args),
        default_agent(args),
        args.title,
        description=getattr(args, "description", "") or "",
        priority=getattr(args, "priority", 2) or 2,
        files=files,
    )
    note = " (deduplicated)" if result.get("deduplicated") else ""
    emit(args, result, text=f"Task #{result['id']}{note}: {result['title']}")


def cmd_claim_task(args):
    store, _ = open_store(args)
    result = store.claim_task(
        default_room(args),
        default_agent(args),
        args.task_id,
        lock_minutes=getattr(args, "lock_minutes", 30) or 30,
    )
    emit(args, result, text=f"Claimed task #{result['id']} ({result['title']})")


def cmd_update_task(args):
    store, _ = open_store(args)
    result = store.update_task(
        default_room(args),
        default_agent(args),
        args.task_id,
        args.status,
        result=getattr(args, "result", "") or "",
    )
    emit(args, result, text=f"Task #{result['id']} -> {result['status']}")


def cmd_lock(args):
    store, _ = open_store(args)
    paths = _split_files(getattr(args, "files", None) or getattr(args, "path", None))
    if not paths:
        fail(args, "pass --files with one or more paths")
    result = store.lock_files(
        default_room(args),
        default_agent(args),
        paths,
        task_id=getattr(args, "task_id", None),
        lock_minutes=getattr(args, "lock_minutes", 30) or 30,
    )
    emit(args, result, text="Locked:\n" + "\n".join(result["paths"]))


def cmd_unlock(args):
    store, _ = open_store(args)
    paths = _split_files(getattr(args, "files", None))
    result = store.unlock_files(default_room(args), default_agent(args), paths or None)
    emit(args, result, text=f"Unlocked {result['unlocked']} lock(s)")


def cmd_reclaim(args):
    store, _ = open_store(args)
    result = store.reclaim_stale_locks(default_room(args), default_agent(args))
    emit(args, result, text=f"Reclaimed {result['reclaimed']} stale lock(s)")


def cmd_claim_action(args):
    store, _ = open_store(args)
    result = store.claim_action(
        default_room(args),
        default_agent(args),
        args.action_key,
        ttl_seconds=getattr(args, "ttl", 600) or 600,
    )
    emit(args, result, text=f"Claimed action {result['action_key']} as {result['agent']}")


def cmd_rooms(args):
    store, _ = open_store(args)
    result = store.list_rooms()
    emit(args, result, text="\n".join(
        f"{r['name']} online={r['online_agents']} ws={r.get('workspace') or '-'}"
        for r in result["rooms"]
    ) or "(no rooms)")


def cmd_docs(args):
    store, _ = open_store(args)
    rows = store.list_documents(default_room(args))
    emit(args, {"documents": rows}, text="\n".join(
        f"#{d['id']} {d['title']} {d['path']}" for d in rows
    ) or "(no documents)")


def cmd_share(args):
    store, _ = open_store(args)
    result = store.share_document(
        default_room(args),
        default_agent(args),
        args.path,
        title=getattr(args, "title", "") or "",
    )
    emit(args, result, text=f"Shared #{result['id']} {result['path']}")


def _split_files(raw) -> List[str]:
    if not raw:
        return []
    if isinstance(raw, list):
        items = raw
    else:
        items = [part.strip() for part in str(raw).split(",")]
    return [item for item in items if item]


def cmd_open(args):
    document = getattr(args, "document", None)
    if not document:
        fail(args, "pass --document /path/to/brief.md")
    workspace = default_workspace(args) if getattr(args, "cwd", None) else str(Path(document).expanduser().resolve().parent)
    skip_raw = getattr(args, "skip_agents", None) or ""
    skip_agents = [part.strip() for part in skip_raw.split(",") if part.strip()]
    try:
        payload = launch_room(
            document=document,
            workspace=workspace,
            room=getattr(args, "room", None) or os.environ.get("SYNAPSEFORGE_ROOM"),
            objective=getattr(args, "objective", "") or "",
            new_room=bool(getattr(args, "new_room", False)),
            skip_agents=skip_agents,
            wait_join_seconds=int(getattr(args, "wait_join_seconds", 0) or 0),
            open_terminal=bool(getattr(args, "launch", False)),
        )
    except FileNotFoundError as exc:
        fail(args, str(exc))
    emit(args, payload, text=_format_open(payload))


def _format_open(payload: Dict[str, Any]) -> str:
    lines = [
        f"Room: {payload['room']}" + (" (resumed)" if payload.get("resumed") else ""),
        f"Workspace: {payload['workspace']}",
        f"Document: {payload['document']}",
        f"Skipped host seats: {', '.join(payload.get('skipped_host_agents') or []) or '-'}",
        f"Launched terminals: {', '.join(payload.get('terminals') or []) or '-'}",
        f"Joined: {', '.join(payload.get('joined') or []) or '-'}",
        f"Not joined: {', '.join(payload.get('not_joined') or []) or '-'}",
        "Paste the matching prompt into each Agent CLI that did not join (or point MCP at `synapseforge team mcp`).",
    ]
    for agent, path in (payload.get("prompt_files") or {}).items():
        lines.append(f"  {agent}: {path}")
    if payload.get("missing_binaries"):
        missing = ", ".join(f"{m['agent']} ({m['binary']})" for m in payload["missing_binaries"])
        lines.append(f"Missing binaries: {missing}")
    if payload.get("launch_errors"):
        lines.append("Launch errors: " + " | ".join(payload["launch_errors"]))
    return "\n".join(lines)


def cmd_paste_prompts(args):
    store, workspace = open_store(args)
    room = default_room(args)
    try:
        status = store.status(room)
        document = (status.get("documents") or [{}])[0].get("path") or ""
        objective = (status.get("room") or {}).get("objective") or ""
        workspace = (status.get("room") or {}).get("workspace") or workspace
    except ValueError:
        document = ""
        objective = ""
    prompts = {
        agent: paste_prompt(room, agent, role, document, workspace, objective)
        for agent, (role, _) in CANONICAL_SEATS.items()
    }
    emit(args, {"room": room, "paste_prompts": prompts}, text="\n\n".join(
        f"===== {agent} =====\n{text}" for agent, text in prompts.items()
    ))


def cmd_mcp(args):
    os.environ.setdefault("SYNAPSEFORGE_WORKSPACE", default_workspace(args))
    if getattr(args, "room", None):
        os.environ["SYNAPSEFORGE_ROOM"] = args.room
    from synapseforge.mcp.server import main as mcp_main

    mcp_main()


def cmd_wait(args):
    store, _ = open_store(args)
    result = store.wait_for_activity(
        default_room(args),
        default_agent(args),
        after_message_id=getattr(args, "after_id", 0) or 0,
        timeout_seconds=getattr(args, "timeout", 20) or 0,
    )
    emit(
        args,
        result,
        text=(
            f"timed_out={result['timed_out']} coordinator_silent={result['coordinator_silent']} "
            f"messages={len(result['messages'])} stale_locks={len(result['stale_locks'])}"
        ),
    )


def cmd_leave(args):
    store, _ = open_store(args)
    result = store.leave(default_room(args), default_agent(args))
    emit(args, result, text=f"{result['agent']} left {result['room']} (unlocked {result['unlocked']})")


def cmd_doctor(args):
    result = run_doctor(workspace=default_workspace(args))
    ok = bool(result.get("ok"))
    emit(args, result, ok=ok, text=_format_doctor(result))
    if not ok:
        sys.exit(1)


def _format_doctor(result: Dict[str, Any]) -> str:
    agents = result.get("agents") or {}
    installed = ", ".join(f"{name}={'yes' if path else 'no'}" for name, path in agents.items())
    return "\n".join(
        [
            f"ok={result.get('ok')}",
            f"database={result.get('database')}",
            f"mcp_ndjson={bool((result.get('mcp_ndjson') or {}).get('ok'))}",
            f"mcp_content_length={bool((result.get('mcp_content_length') or {}).get('ok'))}",
            f"agents: {installed or '-'}",
        ]
    )



