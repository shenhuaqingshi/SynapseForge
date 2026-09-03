"""Launch host Agent CLIs into a SynapseForge team room.

Writes a short per-seat ``.command`` wrapper (never embed the join prompt in
AppleScript), opens macOS Terminal.app, waits for ``team_join``, and can
install/doctor the stdio MCP server for Grok / Codex / Antigravity.
"""

from __future__ import annotations

import json
import os
import select
import shlex
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from synapseforge.core.local_agent_cli import resolve_binary
from synapseforge.core.team_bus import TEAM_PROTOCOL, open_bus

CANONICAL_SEATS = {
    "codex": ("coordinator and integration owner", "codex"),
    "grok": ("independent analyst and critical reviewer", "grok"),
    "antigravity": ("implementation and test specialist", "agy"),
}

SUBMITTER = "antigravity"


def paste_prompt(room: str, agent: str, role: str, document: str, workspace: str, objective: str = "") -> str:
    submitter = (
        "You are the only submitter: git push / deploy / send may only be called by you. "
        "Call team_claim_action first; if you do not get the claim, stop."
        if agent == SUBMITTER
        else "You are not the submitter. Do not push, deploy, or send even if you think others went silent."
    )
    return "\n".join(
        line
        for line in [
            "We are running a SynapseForge local Agent CLI collaboration. First call: team_join (MCP) or `synapseforge team join`.",
            f"room={room!r}",
            f"agent={agent!r}",
            f"role={role!r}",
            f"workspace={workspace}",
            f"shared document: {document}",
            f"objective: {objective}" if objective else "",
            "You occupy this identity exclusively. If join returns already_online=true you are a duplicate observer: do not claim, lock, post, or submit.",
            "kind=directive from human, and anything the user says in your own session, is a live instruction. Act immediately.",
            "Lock paths must sit inside the room workspace (or be a shared document).",
            "If a lock holder is silent, call team_reclaim_stale_locks. Do not wait forever.",
            "If coordinator (codex) is silent after one wait_for_activity timeout, freeze the plan and continue. A live OS process is not a heartbeat.",
            "Before create_task, list tasks. If an open card already covers the same files or work, claim it.",
            submitter,
            "Heartbeat by reading or waiting at least every 60 seconds while working.",
            "Protocol:",
            *["- " + item for item in TEAM_PROTOCOL],
        ]
        if line
    )


def run_dir(workspace: str) -> Path:
    path = Path(workspace) / ".synapse" / "run"
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_room_name(room: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in room) or "team"


def launch_argv(agent: str, binary: str, prompt_path: Path) -> str:
    """Shell fragment executed after PROMPT=$(cat file). Never interpolates the prompt body."""
    quoted = shlex.quote(binary)
    prompt_quoted = shlex.quote(str(prompt_path))
    if agent == "grok":
        return "%s --prompt-file %s" % (quoted, prompt_quoted)
    if agent == "antigravity":
        return "%s --prompt-interactive \"$PROMPT\"" % quoted
    if agent == "codex":
        return "%s exec \"$PROMPT\"" % quoted
    if agent == "claude":
        return "%s -p \"$PROMPT\"" % quoted
    return "%s \"$PROMPT\"" % quoted


def write_launch_bundle(
    workspace: str,
    room: str,
    agent: str,
    role: str,
    document: str,
    objective: str = "",
    binary: Optional[str] = None,
) -> Dict[str, str]:
    directory = run_dir(workspace)
    safe = safe_room_name(room)
    prompt_path = directory / ("%s-%s.txt" % (safe, agent))
    script_path = directory / ("%s-%s.command" % (safe, agent))
    exe_name = CANONICAL_SEATS.get(agent, (role, agent))[1]
    resolved = binary or resolve_binary(exe_name)
    if not resolved:
        raise FileNotFoundError("Missing agent CLI: %s" % exe_name)
    prompt = paste_prompt(room, agent, role, document, workspace, objective)
    prompt_path.write_text(prompt, encoding="utf-8")
    session = "%s-%s" % (agent, datetime.now().strftime("%H%M%S%f"))
    launch = launch_argv(agent, resolved, prompt_path)
    script_path.write_text(
        "#!/bin/zsh\n"
        "set -euo pipefail\n"
        "export PATH=\"$HOME/.local/bin:$HOME/.npm-global/bin:$HOME/.grok/bin:/opt/homebrew/bin:/usr/local/bin:$PATH\"\n"
        "cd %s\n"
        "export SYNAPSEFORGE_ROOM=%s SYNAPSEFORGE_SESSION=%s SYNAPSEFORGE_WORKSPACE=%s\n"
        "export AGENT_TEAM_ROOM=$SYNAPSEFORGE_ROOM AGENT_TEAM_SESSION=$SYNAPSEFORGE_SESSION\n"
        "PROMPT=$(cat %s)\n"
        "exec %s\n"
        % (
            shlex.quote(workspace),
            shlex.quote(room),
            shlex.quote(session),
            shlex.quote(workspace),
            shlex.quote(str(prompt_path)),
            launch,
        ),
        encoding="utf-8",
    )
    script_path.chmod(0o755)
    return {
        "agent": agent,
        "role": role,
        "binary": resolved,
        "prompt_path": str(prompt_path),
        "script_path": str(script_path),
        "prompt": prompt,
    }


def open_in_terminal(script_path: str, runner: Optional[Callable[..., subprocess.CompletedProcess]] = None) -> str:
    """Open macOS Terminal.app on a short wrapper script. Never embed the join prompt in AppleScript."""
    run = runner or subprocess.run
    script_path = str(Path(script_path).resolve())
    command = "/bin/zsh %s" % shlex.quote(script_path)
    errors: List[str] = []
    try:
        result = run(
            [
                "osascript",
                "-e", 'tell application "Terminal" to activate',
                "-e", "tell application \"Terminal\" to do script %s" % json.dumps(command, ensure_ascii=False),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return "terminal-applescript"
        errors.append((result.stderr or result.stdout or "osascript exit %s" % result.returncode).strip())
    except Exception as exc:
        errors.append(str(exc))
    try:
        result = run(
            ["open", "-a", "Terminal", script_path],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            return "terminal-open"
        errors.append((result.stderr or "open Terminal exit %s" % result.returncode).strip())
    except Exception as exc:
        errors.append(str(exc))
    raise RuntimeError("Could not open Terminal.app for %s: %s" % (script_path, "; ".join(errors)))


def wait_for_joins(store, room: str, launched: Sequence[str], timeout_seconds: int = 20) -> Tuple[List[str], List[str]]:
    pending = list(launched)
    joined: List[str] = []
    deadline = time.time() + max(0, int(timeout_seconds))
    while pending:
        try:
            live = set(store.status(room).get("live_agents") or [])
        except Exception:
            live = set()
        still = []
        for agent in pending:
            if agent in live:
                joined.append(agent)
            else:
                still.append(agent)
        pending = still
        if not pending or time.time() >= deadline:
            break
        time.sleep(0.5)
    return joined, pending


def infer_host_agents() -> set:
    skip = set()
    raw = os.environ.get("SYNAPSEFORGE_SKIP_AGENTS") or os.environ.get("AGENT_TEAM_SKIP_AGENTS") or ""
    skip.update(part.strip() for part in raw.split(",") if part.strip())
    if os.environ.get("GROK_AGENT") or os.environ.get("GROK_SESSION_ID"):
        skip.add("grok")
    names = set(_ancestor_names(os.getppid()))
    if {"grok", "grok-app"} & names:
        skip.add("grok")
    if "codex" in names:
        skip.add("codex")
    if {"agy", "antigravity"} & names:
        skip.add("antigravity")
    if "claude" in names:
        skip.add("claude")
    return skip


def _ancestor_names(pid, depth=8):
    names = []
    current = pid
    for _ in range(depth):
        if not current or int(current) <= 1:
            break
        try:
            comm = subprocess.check_output(["ps", "-p", str(current), "-o", "comm="], text=True).strip().lower()
            args = subprocess.check_output(["ps", "-p", str(current), "-o", "args="], text=True).strip()
            ppid = subprocess.check_output(["ps", "-p", str(current), "-o", "ppid="], text=True).strip()
        except Exception:
            break
        exe = (args.split() or [comm])[0].lower()
        names.append(os.path.basename(exe).replace(".exe", ""))
        names.append(os.path.basename(comm).replace(".exe", ""))
        try:
            current = int(ppid)
        except (TypeError, ValueError):
            break
    return names


def _replace_toml_table(text: str, header: str, body: str) -> str:
    lines = text.splitlines(keepends=True)
    start = None
    for i, line in enumerate(lines):
        if line.strip() == header:
            start = i
            break
    block = header + "\n" + body.rstrip() + "\n\n"
    if start is None:
        sep = "" if not text or text.endswith("\n") else "\n"
        return text + sep + ("\n" if text.strip() else "") + block
    end = len(lines)
    for j in range(start + 1, len(lines)):
        stripped = lines[j].strip()
        if stripped.startswith("[") and not stripped.startswith("[."):
            end = j
            break
    return "".join(lines[:start]) + block + "".join(lines[end:])


def mcp_command() -> Tuple[str, List[str]]:
    python = sys.executable
    return python, ["-m", "synapseforge.mcp.server"]


def install_mcp(home: Optional[Path] = None) -> Dict[str, Any]:
    """Write [mcp_servers.synapseforge_team] into Grok / Codex / Gemini configs.

    Does not overwrite an existing ``agent_team`` server entry.
    """
    home = Path(home or os.environ.get("HOME") or Path.home()).expanduser()
    python, args = mcp_command()
    grok_config = home / ".grok" / "config.toml"
    codex_config = home / ".codex" / "config.toml"
    gemini_config = home / ".gemini" / "antigravity" / "mcp_config.json"

    grok_body = (
        "command = %s\n"
        "args = %s\n"
        "enabled = true\n"
        "startup_timeout_sec = 20\n"
        % (json.dumps(python), json.dumps(args))
    )
    grok_config.parent.mkdir(parents=True, exist_ok=True)
    grok_text = grok_config.read_text(encoding="utf-8") if grok_config.exists() else ""
    grok_config.write_text(_replace_toml_table(grok_text, "[mcp_servers.synapseforge_team]", grok_body), encoding="utf-8")

    codex_body = (
        "command = %s\n"
        "args = %s\n"
        'default_tools_approval_mode = "auto"\n'
        'env_vars = ["SYNAPSEFORGE_ROOM", "SYNAPSEFORGE_TEAM_DB", "SYNAPSEFORGE_SESSION", "SYNAPSEFORGE_WORKSPACE"]\n'
        "enabled = true\n"
        "startup_timeout_sec = 20\n"
        % (json.dumps(python), json.dumps(args))
    )
    codex_config.parent.mkdir(parents=True, exist_ok=True)
    codex_text = codex_config.read_text(encoding="utf-8") if codex_config.exists() else ""
    codex_config.write_text(_replace_toml_table(codex_text, "[mcp_servers.synapseforge_team]", codex_body), encoding="utf-8")

    gemini: Dict[str, Any] = {"mcpServers": {}}
    if gemini_config.exists():
        try:
            gemini = json.loads(gemini_config.read_text(encoding="utf-8")) or gemini
        except json.JSONDecodeError:
            gemini = {"mcpServers": {}}
    gemini.setdefault("mcpServers", {})
    gemini["mcpServers"]["synapseforge_team"] = {
        "command": python,
        "args": args,
        "trust": True,
    }
    gemini_config.parent.mkdir(parents=True, exist_ok=True)
    gemini_config.write_text(json.dumps(gemini, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "python": python,
        "args": args,
        "updated": [str(grok_config), str(codex_config), str(gemini_config)],
    }


def _mcp_handshake(mode: str, timeout: float = 4.0, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    python, args = mcp_command()
    proc_env = dict(os.environ)
    if env:
        proc_env.update(env)
    proc_env.pop("SYNAPSEFORGE_ROOM", None)
    proc_env.pop("AGENT_TEAM_ROOM", None)
    repo_root = str(Path(__file__).resolve().parents[2])
    proc_env["PYTHONPATH"] = repo_root + os.pathsep + proc_env.get("PYTHONPATH", "")
    proc = subprocess.Popen(
        [python, "-u", *args],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=proc_env,
    )
    init = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "synapseforge-doctor", "version": "1"},
        },
    }).encode("utf-8")
    try:
        assert proc.stdin is not None and proc.stdout is not None
        if mode == "framed":
            proc.stdin.write(("Content-Length: %d\r\n\r\n" % len(init)).encode("ascii") + init)
        else:
            proc.stdin.write(init + b"\n")
        proc.stdin.flush()
        deadline = time.time() + timeout
        buf = b""
        while time.time() < deadline:
            remaining = max(0.05, deadline - time.time())
            readable, _, _ = select.select([proc.stdout], [], [], remaining)
            if not readable:
                continue
            chunk = os.read(proc.stdout.fileno(), 4096)
            if not chunk:
                break
            buf += chunk
            if mode == "framed" and b"\r\n\r\n" in buf:
                header, rest = buf.split(b"\r\n\r\n", 1)
                length = 0
                for line in header.decode("utf-8", errors="replace").splitlines():
                    if line.lower().startswith("content-length:"):
                        length = int(line.split(":", 1)[1].strip())
                if len(rest) >= length:
                    payload = json.loads(rest[:length].decode("utf-8"))
                    return {"ok": True, "version": payload.get("result", {}).get("serverInfo", {}).get("version")}
            if mode == "ndjson" and b"\n" in buf:
                payload = json.loads(buf.split(b"\n", 1)[0].decode("utf-8"))
                return {"ok": True, "version": payload.get("result", {}).get("serverInfo", {}).get("version")}
        return {"ok": False, "error": "handshake timed out", "raw": buf[:200].decode("utf-8", errors="replace")}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
    finally:
        try:
            if proc.stdin:
                proc.stdin.close()
        except Exception:
            pass
        proc.kill()
        try:
            proc.wait(timeout=1)
        except Exception:
            pass


def doctor(workspace: Optional[str] = None) -> Dict[str, Any]:
    store = open_bus(workspace=workspace)
    ndjson = _mcp_handshake("ndjson")
    framed = _mcp_handshake("framed")
    agents = {name: resolve_binary(exe) for name, (_, exe) in CANONICAL_SEATS.items()}
    checks = {
        "database": str(store.db_path),
        "database_writable": os.access(str(store.db_path.parent), os.W_OK),
        "python": sys.executable,
        "agents": agents,
        "mcp_ndjson": ndjson,
        "mcp_content_length": framed,
    }
    checks["ok"] = bool(
        checks["database_writable"]
        and ndjson.get("ok")
        and framed.get("ok")
    )
    return checks


def launch_room(
    document: str,
    workspace: str,
    room: Optional[str] = None,
    objective: str = "",
    new_room: bool = False,
    skip_agents: Optional[Iterable[str]] = None,
    wait_join_seconds: int = 20,
    open_terminal: bool = True,
    terminal_opener: Optional[Callable[[str], str]] = None,
) -> Dict[str, Any]:
    doc = Path(document).expanduser().resolve()
    if not doc.is_file():
        raise FileNotFoundError("document not found: %s" % doc)
    workspace = str(Path(workspace).expanduser().resolve())
    store = open_bus(workspace=workspace)
    skip = infer_host_agents()
    if skip_agents:
        skip.update(a.strip() for a in skip_agents if a and str(a).strip())
    resumed = False
    if not room and not new_room:
        live = store.find_live_workspace_room(workspace)
        if live:
            room = live["name"]
            resumed = True
    if not room:
        stem = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in doc.stem).strip("-") or "team"
        room = "%s-%s" % (stem[:48], datetime.now().strftime("%Y%m%d-%H%M%S"))
    store.join(room, "launcher", "session launcher", objective or ("Collaborate on %s" % doc.name), workspace)
    shared = store.share_document(room, "launcher", str(doc))
    already = set()
    try:
        already = {
            p["agent"]
            for p in store.status(room)["participants"]
            if p.get("online") and p["agent"] in CANONICAL_SEATS
        }
        skip.update(already)
    except Exception:
        already = set()

    bundles = []
    missing = []
    launched = []
    for agent, (role, exe) in CANONICAL_SEATS.items():
        if agent in skip:
            continue
        binary = resolve_binary(exe)
        if not binary:
            missing.append({"agent": agent, "binary": exe})
            continue
        bundle = write_launch_bundle(workspace, room, agent, role, str(doc), objective, binary=binary)
        bundles.append(bundle)
        launched.append(agent)

    terminal_backend = None
    launch_errors: List[str] = []
    opener = terminal_opener or open_in_terminal
    if open_terminal:
        for bundle in bundles:
            try:
                terminal_backend = opener(bundle["script_path"])
                time.sleep(0.3)
            except Exception as exc:
                launch_errors.append(str(exc))

    joined, not_joined = wait_for_joins(store, room, launched, timeout_seconds=wait_join_seconds) if open_terminal else ([], launched)
    paste = {item["agent"]: item["prompt"] for item in bundles if item["agent"] in not_joined or not open_terminal}
    if not open_terminal:
        paste = {item["agent"]: item["prompt"] for item in bundles}
        paste.update({agent: paste_prompt(room, agent, role, str(doc), workspace, objective)
                      for agent, (role, _) in CANONICAL_SEATS.items() if agent not in paste})
    return {
        "ok": True,
        "room": room,
        "workspace": workspace,
        "document": str(doc),
        "shared_document": shared,
        "resumed": resumed,
        "skipped_host_agents": sorted(skip),
        "already_online": sorted(already),
        "terminals": launched,
        "joined": joined,
        "not_joined": not_joined,
        "paste_prompts": paste,
        "prompt_files": {item["agent"]: item["prompt_path"] for item in bundles},
        "script_files": {item["agent"]: item["script_path"] for item in bundles},
        "missing_binaries": missing,
        "terminal_backend": terminal_backend,
        "launch_errors": launch_errors,
        "protocol": TEAM_PROTOCOL,
        "mcp": "synapseforge team mcp",
    }
