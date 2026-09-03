#!/usr/bin/env python3
"""SQLite-backed local collaboration bus for host Agent CLIs.

Lets Codex, Grok Build, Antigravity, Claude Code, and humans share a room:
exclusive seats, messages (including human directives), a task board with
dedup, workspace-scoped file locks, heartbeat / coordinator-silent detection,
stale-lock reclaim, and one-shot action claims for push/submit/deploy.

Data lives in ``.synapse/team.db`` (or ``SYNAPSEFORGE_TEAM_DB``). This is the
local counterpart to Tailscale room sync: same machine, several CLIs.
"""

import hashlib
import json
import mimetypes
import os
import re
import sqlite3
import time
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DB = Path(
    os.environ.get("SYNAPSEFORGE_TEAM_DB")
    or os.environ.get("AGENT_TEAM_DB")
    or "~/.synapseforge/team.db"
).expanduser()


def workspace_db(workspace=None):
    """Place the bus next to the writing workspace: ``<workspace>/.synapse/team.db``."""
    root = Path(workspace or os.environ.get("SYNAPSEFORGE_WORKSPACE") or Path.cwd()).expanduser()
    return root.resolve() / ".synapse" / "team.db"


def open_bus(workspace=None, db_path=None, session_id=None):
    """Open a TeamBus bound to a workspace DB unless SYNAPSEFORGE_TEAM_DB is set."""
    if db_path is None:
        if os.environ.get("SYNAPSEFORGE_TEAM_DB") or os.environ.get("AGENT_TEAM_DB"):
            db_path = DEFAULT_DB
        else:
            db_path = workspace_db(workspace)
    return TeamBus(db_path, session_id=session_id)
TEXT_SUFFIXES = {
    ".txt", ".md", ".markdown", ".rst", ".py", ".js", ".mjs", ".cjs",
    ".ts", ".tsx", ".jsx", ".json", ".toml", ".yaml", ".yml", ".xml",
    ".html", ".css", ".scss", ".sh", ".zsh", ".bash", ".go", ".rs",
    ".java", ".c", ".h", ".cpp", ".hpp", ".swift", ".sql", ".tex",
}
MESSAGE_KINDS = {
    "discussion", "proposal", "decision", "question", "answer",
    "blocker", "review", "document", "system", "directive",
}
PRIVILEGED_AGENTS = {"human", "launcher"}
CANONICAL_AGENTS = {"codex", "grok", "antigravity"}
ONLINE_TTL_S = 75
STALE_LOCK_S = 120
DEDUP_WINDOW_S = 8
PROTOCOL = TEAM_PROTOCOL = [
    "Read the shared document, recent messages, and any human directive before acting.",
    "kind=directive from human is the current user instruction; act on it immediately, ahead of peer debate.",
    "If the user is talking to you in your own session, that is also a human directive: post it to the room and act. Do not wait for agent-team say.",
    "You occupy one exclusive seat (codex / grok / antigravity). If join returns already_online, you are a duplicate: do not claim tasks, lock files, or post as that agent.",
    "Claim a task and lock its files before editing; never edit a file locked by another live agent.",
    "If a lock holder is silent (no heartbeat), call team_reclaim_stale_locks instead of waiting forever.",
    "If the coordinator (codex) is silent after one wait_for_activity timeout, remaining live agents freeze the plan and continue. Do not wait a second cycle for freeze authority. An OS process that is alive is not a heartbeat.",
    "Before team_create_task, list open tasks. If one already covers the same files or the same work, claim that task. create_task itself returns deduplicated=true when it reuses a card.",
    "Before an irreversible shared action (submit, push, deploy, send), call team_claim_action with a unique key. Only the agent that received the claim may call the API; everyone else must not. Default submitter is antigravity. Reviewers never submit.",
    "Lock and task file paths must sit inside the room workspace (or be a shared document). Relative paths resolve against the workspace.",
    "Heartbeat by reading or waiting at least every 60 seconds while working.",
]


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_task_title(title):
    text = (title or "").strip().lower()
    text = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def _titles_similar(left, right):
    a = _normalize_task_title(left)
    b = _normalize_task_title(right)
    if not a or not b:
        return False
    if a == b:
        return True
    return a in b or b in a


def _validate_label(value, field, max_len=120):
    value = (value or "").strip()
    if not value:
        raise ValueError("%s is required" % field)
    if len(value) > max_len:
        raise ValueError("%s is too long (max %d)" % (field, max_len))
    if not re.match(r"^[\w.\-:/\u4e00-\u9fff ]+$", value, re.UNICODE):
        raise ValueError("%s contains unsupported characters" % field)
    return value


def _age_seconds(iso):
    if not iso:
        return 10**9
    dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return time.time() - dt.timestamp()


def default_session_id():
    env = (os.environ.get("SYNAPSEFORGE_SESSION") or os.environ.get("AGENT_TEAM_SESSION") or "").strip()
    if env:
        return env[:80]
    return "pid-%d" % os.getpid()


class TeamBus:
    def __init__(self, db_path=None, session_id=None):
        self.db_path = Path(db_path or DEFAULT_DB).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_id = session_id or default_session_id()
        self._init_schema()

    def connect(self):
        conn = sqlite3.connect(str(self.db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def connection(self):
        with closing(self.connect()) as conn:
            with conn:
                yield conn

    def _init_schema(self):
        with self.connection() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS rooms (
                    name TEXT PRIMARY KEY,
                    objective TEXT NOT NULL DEFAULT '',
                    workspace TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS participants (
                    room TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'online',
                    last_seen TEXT NOT NULL,
                    last_read_message_id INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (room, agent),
                    FOREIGN KEY (room) REFERENCES rooms(name) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room TEXT NOT NULL,
                    title TEXT NOT NULL,
                    path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    mime_type TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    content TEXT,
                    added_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(room, path),
                    FOREIGN KEY (room) REFERENCES rooms(name) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    recipient TEXT,
                    kind TEXT NOT NULL DEFAULT 'discussion',
                    body TEXT NOT NULL,
                    reply_to INTEGER,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (room) REFERENCES rooms(name) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    room TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'open',
                    priority INTEGER NOT NULL DEFAULT 2,
                    created_by TEXT NOT NULL,
                    assignee TEXT,
                    files_json TEXT NOT NULL DEFAULT '[]',
                    result TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (room) REFERENCES rooms(name) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS file_locks (
                    room TEXT NOT NULL,
                    path TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    task_id INTEGER,
                    expires_at REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (room, path),
                    FOREIGN KEY (room) REFERENCES rooms(name) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_messages_room_id ON messages(room, id);
                CREATE INDEX IF NOT EXISTS idx_tasks_room_status ON tasks(room, status, priority);
                CREATE TABLE IF NOT EXISTS action_claims (
                    room TEXT NOT NULL,
                    action_key TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    session_id TEXT NOT NULL DEFAULT '',
                    expires_at REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (room, action_key),
                    FOREIGN KEY (room) REFERENCES rooms(name) ON DELETE CASCADE
                );
                """
            )
            self._ensure_column(conn, "participants", "session_id", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(conn, "participants", "pid", "INTEGER NOT NULL DEFAULT 0")

    @staticmethod
    def _ensure_column(conn, table, column, decl):
        cols = {row[1] for row in conn.execute("PRAGMA table_info(%s)" % table)}
        if column not in cols:
            conn.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, column, decl))

    def _ensure_room(self, conn, room, objective="", workspace=""):
        room = _validate_label(room, "room")
        now = utc_now()
        conn.execute(
            "INSERT OR IGNORE INTO rooms(name, objective, workspace, created_at, updated_at) VALUES(?,?,?,?,?)",
            (room, objective or "", workspace or "", now, now),
        )
        if objective or workspace:
            current = conn.execute("SELECT objective, workspace FROM rooms WHERE name=?", (room,)).fetchone()
            conn.execute(
                "UPDATE rooms SET objective=?, workspace=?, updated_at=? WHERE name=?",
                (objective or current["objective"], workspace or current["workspace"], now, room),
            )
        return room

    @staticmethod
    def _rows(rows):
        return [dict(row) for row in rows]

    @staticmethod
    def _pid_alive(pid):
        try:
            pid = int(pid or 0)
        except (TypeError, ValueError):
            return None
        if pid <= 0:
            return None
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return None

    def _occupant_live(self, row):
        if not row:
            return False
        if _age_seconds(row["last_seen"]) > ONLINE_TTL_S:
            return False
        keys = row.keys() if hasattr(row, "keys") else []
        pid = row["pid"] if "pid" in keys else 0
        alive = self._pid_alive(pid)
        if alive is False:
            return False
        return True

    def join(self, room, agent, role="", objective="", workspace=""):
        agent = _validate_label(agent, "agent", 80)
        workspace = str(Path(workspace).expanduser().resolve()) if workspace else ""
        now = utc_now()
        session_id = self.session_id
        pid = os.getpid()
        with self.connection() as conn:
            room = self._ensure_room(conn, room, objective, workspace)
            existing = conn.execute(
                "SELECT * FROM participants WHERE room=? AND agent=?", (room, agent)
            ).fetchone()
            already_online = False
            occupant_session = ""
            if existing:
                occupant_session = existing["session_id"] or ""
                live = (
                    occupant_session
                    and occupant_session != session_id
                    and self._occupant_live(existing)
                )
                if live and agent not in PRIVILEGED_AGENTS:
                    already_online = True
                else:
                    conn.execute(
                        """UPDATE participants SET role=?, status='online', last_seen=?, session_id=?, pid=?
                           WHERE room=? AND agent=?""",
                        (role or existing["role"], now, session_id, pid, room, agent),
                    )
            else:
                conn.execute(
                    """INSERT INTO participants(room, agent, role, status, last_seen, session_id, pid)
                       VALUES(?,?,?,?,?,?,?)""",
                    (room, agent, role or "", "online", now, session_id, pid),
                )
            docs = self._rows(conn.execute(
                "SELECT id,title,path,sha256,size,mime_type,added_by,updated_at FROM documents WHERE room=? ORDER BY id",
                (room,),
            ))
            tasks = self._rows(conn.execute(
                "SELECT * FROM tasks WHERE room=? AND status!='done' ORDER BY priority,id", (room,)
            ))
            messages = self._rows(conn.execute(
                "SELECT * FROM messages WHERE room=? ORDER BY id DESC LIMIT 10", (room,)
            ))[::-1]
        protocol = list(PROTOCOL)
        if already_online:
            protocol.insert(0, (
                "SEAT TAKEN: another live %s session is already in this room. "
                "You are a duplicate observer. Do not claim tasks, lock files, "
                "post as %s, or submit. Wait or exit." % (agent, agent)
            ))
        return {
            "room": room,
            "agent": agent,
            "role": role,
            "session_id": session_id,
            "already_online": already_online,
            "occupant_session": occupant_session if already_online else session_id,
            "observer": already_online,
            "documents": docs,
            "active_tasks": tasks,
            "recent_messages": messages,
            "protocol": protocol,
        }

    def _heartbeat(self, conn, room, agent):
        if agent in PRIVILEGED_AGENTS:
            conn.execute(
                "UPDATE participants SET last_seen=? WHERE room=? AND agent=?",
                (utc_now(), room, agent),
            )
            return
        conn.execute(
            """UPDATE participants SET last_seen=?, pid=?
               WHERE room=? AND agent=? AND session_id=?""",
            (utc_now(), os.getpid(), room, agent, self.session_id),
        )

    def _assert_seat(self, conn, room, agent):
        if agent in PRIVILEGED_AGENTS:
            return
        row = conn.execute(
            "SELECT session_id, last_seen, pid FROM participants WHERE room=? AND agent=?",
            (room, agent),
        ).fetchone()
        if not row:
            return
        occupant = row["session_id"] or ""
        if occupant and occupant != self.session_id and self._occupant_live(row):
            raise ValueError(
                "seat occupied: %s is already live in another session; observe only (no edits, claims, or posts)"
                % agent
            )
        if occupant != self.session_id:
            conn.execute(
                """UPDATE participants SET session_id=?, pid=?, last_seen=?, status='online'
                   WHERE room=? AND agent=?""",
                (self.session_id, os.getpid(), utc_now(), room, agent),
            )

    def share_document(self, room, agent, path, title="", copy_content=True):
        agent = _validate_label(agent, "agent", 80)
        source = Path(path).expanduser().resolve()
        if not source.is_file():
            raise ValueError("document does not exist or is not a file: %s" % source)
        raw = source.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        mime = mimetypes.guess_type(str(source))[0] or "application/octet-stream"
        content = None
        if copy_content and len(raw) <= 2 * 1024 * 1024 and (source.suffix.lower() in TEXT_SUFFIXES or mime.startswith("text/")):
            content = raw.decode("utf-8", errors="replace")
        now = utc_now()
        with self.connection() as conn:
            room = self._ensure_room(conn, room)
            self._assert_seat(conn, room, agent)
            conn.execute(
                """INSERT INTO documents(room,title,path,sha256,mime_type,size,content,added_by,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(room,path) DO UPDATE SET title=excluded.title,sha256=excluded.sha256,
                     mime_type=excluded.mime_type,size=excluded.size,content=excluded.content,
                     added_by=excluded.added_by,updated_at=excluded.updated_at""",
                (room, title or source.name, str(source), digest, mime, len(raw), content, agent, now, now),
            )
            row = conn.execute("SELECT * FROM documents WHERE room=? AND path=?", (room, str(source))).fetchone()
            conn.execute(
                "INSERT INTO messages(room,sender,kind,body,created_at) VALUES(?,?,?,?,?)",
                (room, agent, "document", "Shared document #%d: %s (%s)" % (row["id"], row["title"], row["path"]), now),
            )
        result = dict(row)
        result.pop("content", None)
        result["content_copied"] = content is not None
        return result

    def list_documents(self, room):
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT id,title,path,sha256,mime_type,size,added_by,created_at,updated_at FROM documents WHERE room=? ORDER BY id",
                (room,),
            ).fetchall()
        return self._rows(rows)

    def read_document(self, room, document_id=None, path=None, offset=0, max_chars=30000):
        if document_id is None and not path:
            raise ValueError("document_id or path is required")
        with self.connection() as conn:
            if document_id is not None:
                row = conn.execute("SELECT * FROM documents WHERE room=? AND id=?", (room, int(document_id))).fetchone()
            else:
                resolved = str(Path(path).expanduser().resolve())
                row = conn.execute("SELECT * FROM documents WHERE room=? AND path=?", (room, resolved)).fetchone()
        if not row:
            raise ValueError("document not found in room")
        item = dict(row)
        content = item.pop("content", None)
        live = Path(item["path"])
        if live.is_file() and live.stat().st_size <= 2 * 1024 * 1024 and (live.suffix.lower() in TEXT_SUFFIXES or item["mime_type"].startswith("text/")):
            content = live.read_text(encoding="utf-8", errors="replace")
        if content is None:
            item["content_available"] = False
            item["hint"] = "Read the local path with your native file/PDF tools."
            return item
        offset = max(0, int(offset))
        max_chars = min(max(1, int(max_chars)), 100000)
        item["content_available"] = True
        item["content"] = content[offset:offset + max_chars]
        item["offset"] = offset
        item["next_offset"] = offset + len(item["content"]) if offset + len(item["content"]) < len(content) else None
        item["total_chars"] = len(content)
        return item

    def post_message(self, room, agent, message, kind="discussion", to_agent=None, reply_to=None):
        agent = _validate_label(agent, "agent", 80)
        if to_agent:
            to_agent = _validate_label(to_agent, "to_agent", 80)
        kind = kind if kind in MESSAGE_KINDS else "discussion"
        if agent == "human" and kind == "discussion":
            kind = "directive"
        message = (message or "").strip()
        if not message:
            raise ValueError("message is required")
        if len(message) > 50000:
            raise ValueError("message is too long (max 50000 characters)")
        now = utc_now()
        with self.connection() as conn:
            room = self._ensure_room(conn, room)
            self._assert_seat(conn, room, agent)
            recent = conn.execute(
                "SELECT * FROM messages WHERE room=? AND sender=? ORDER BY id DESC LIMIT 1",
                (room, agent),
            ).fetchone()
            if recent and recent["body"] == message and recent["kind"] == kind:
                if _age_seconds(recent["created_at"]) <= DEDUP_WINDOW_S:
                    dup = dict(recent)
                    dup["deduplicated"] = True
                    return dup
            cur = conn.execute(
                "INSERT INTO messages(room,sender,recipient,kind,body,reply_to,created_at) VALUES(?,?,?,?,?,?,?)",
                (room, agent, to_agent, kind, message, reply_to, now),
            )
            row = conn.execute("SELECT * FROM messages WHERE id=?", (cur.lastrowid,)).fetchone()
            self._heartbeat(conn, room, agent)
        result = dict(row)
        result["deduplicated"] = False
        return result

    def read_messages(self, room, agent, after_id=0, limit=50, mark_read=True):
        agent = _validate_label(agent, "agent", 80)
        limit = min(max(1, int(limit)), 200)
        with self.connection() as conn:
            rows = conn.execute(
                """SELECT * FROM messages WHERE room=? AND id>? AND (recipient IS NULL OR recipient=? OR sender=?)
                   ORDER BY id LIMIT ?""",
                (room, int(after_id), agent, agent, limit),
            ).fetchall()
            occupant = conn.execute(
                "SELECT session_id FROM participants WHERE room=? AND agent=?",
                (room, agent),
            ).fetchone()
            seated = agent in PRIVILEGED_AGENTS or not occupant or (occupant["session_id"] or "") in ("", self.session_id)
            if seated and mark_read:
                last_id = rows[-1]["id"] if rows else None
                if last_id is not None:
                    conn.execute(
                        """UPDATE participants SET last_read_message_id=?, last_seen=?, pid=?
                           WHERE room=? AND agent=? AND (session_id=? OR session_id='' OR session_id IS NULL)""",
                        (last_id, utc_now(), os.getpid(), room, agent, self.session_id),
                    )
                else:
                    self._heartbeat(conn, room, agent)
            elif seated:
                self._heartbeat(conn, room, agent)
        return self._rows(rows)

    def create_task(self, room, agent, title, description="", priority=2, files=None):
        agent = _validate_label(agent, "agent", 80)
        title = (title or "").strip()
        if not title:
            raise ValueError("title is required")
        priority = min(max(1, int(priority)), 5)
        files = list(files or [])
        now = utc_now()
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            room = self._ensure_room(conn, room)
            self._assert_seat(conn, room, agent)
            files = self._normalize_lock_paths(conn, room, files)
            files_set = set(files)
            existing = conn.execute(
                "SELECT * FROM tasks WHERE room=? AND status IN ('open','in_progress','blocked') ORDER BY id",
                (room,),
            ).fetchall()
            for row in existing:
                existing_files = set(json.loads(row["files_json"] or "[]"))
                same_files = bool(files_set) and files_set == existing_files
                overlapping = bool(files_set and existing_files and files_set & existing_files)
                similar = _titles_similar(title, row["title"])
                if same_files or (similar and (not files_set or not existing_files or overlapping)):
                    result = self._decode_task(row)
                    result["deduplicated"] = True
                    self._heartbeat(conn, room, agent)
                    return result
            cur = conn.execute(
                """INSERT INTO tasks(room,title,description,priority,created_by,files_json,created_at,updated_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                (room, title, description or "", priority, agent, json.dumps(files, ensure_ascii=False), now, now),
            )
            row = conn.execute("SELECT * FROM tasks WHERE id=?", (cur.lastrowid,)).fetchone()
            conn.execute(
                "INSERT INTO messages(room,sender,kind,body,created_at) VALUES(?,?,?,?,?)",
                (room, agent, "system", "Created task #%d: %s" % (row["id"], title), now),
            )
            self._heartbeat(conn, room, agent)
        result = self._decode_task(row)
        result["deduplicated"] = False
        return result

    @staticmethod
    def _decode_task(row):
        result = dict(row)
        result["files"] = json.loads(result.pop("files_json") or "[]")
        return result

    @staticmethod
    def _room_workspace(conn, room):
        row = conn.execute("SELECT workspace FROM rooms WHERE name=?", (room,)).fetchone()
        raw = (row["workspace"] if row else "") or ""
        return str(Path(raw).expanduser().resolve()) if raw else ""

    def _shared_document_paths(self, conn, room):
        return {
            str(Path(row["path"]).expanduser().resolve())
            for row in conn.execute("SELECT path FROM documents WHERE room=?", (room,)).fetchall()
            if row["path"]
        }

    def _normalize_lock_paths(self, conn, room, paths):
        workspace = self._room_workspace(conn, room)
        allowed = self._shared_document_paths(conn, room)
        normalized = []
        for raw in paths or []:
            candidate = Path(str(raw)).expanduser()
            if not candidate.is_absolute() and workspace:
                candidate = Path(workspace) / candidate
            resolved = str(candidate.resolve())
            if workspace:
                root = workspace.rstrip("/")
                inside = resolved == root or resolved.startswith(root + os.sep)
                if not inside and resolved not in allowed:
                    raise ValueError(
                        "lock path is outside the room workspace: %s (workspace=%s)"
                        % (resolved, workspace)
                    )
            normalized.append(resolved)
        return normalized

    def list_tasks(self, room, status=None):
        with self.connection() as conn:
            if status:
                rows = conn.execute("SELECT * FROM tasks WHERE room=? AND status=? ORDER BY priority,id", (room, status)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM tasks WHERE room=? ORDER BY CASE status WHEN 'in_progress' THEN 0 WHEN 'open' THEN 1 WHEN 'blocked' THEN 2 ELSE 3 END,priority,id", (room,)).fetchall()
        return [self._decode_task(row) for row in rows]

    def claim_task(self, room, agent, task_id, lock_minutes=30):
        agent = _validate_label(agent, "agent", 80)
        now = utc_now()
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._assert_seat(conn, room, agent)
            row = conn.execute("SELECT * FROM tasks WHERE room=? AND id=?", (room, int(task_id))).fetchone()
            if not row:
                raise ValueError("task not found")
            if row["status"] == "done":
                raise ValueError("task is already done")
            if row["assignee"] and row["assignee"] != agent:
                raise ValueError("task is already assigned to %s" % row["assignee"])
            files = json.loads(row["files_json"] or "[]")
            self._acquire_locks(conn, room, agent, files, int(task_id), lock_minutes)
            conn.execute("UPDATE tasks SET status='in_progress',assignee=?,updated_at=? WHERE id=?", (agent, now, int(task_id)))
            conn.execute(
                "INSERT INTO messages(room,sender,kind,body,created_at) VALUES(?,?,?,?,?)",
                (room, agent, "system", "Claimed task #%d: %s" % (row["id"], row["title"]), now),
            )
            self._heartbeat(conn, room, agent)
            updated = conn.execute("SELECT * FROM tasks WHERE id=?", (int(task_id),)).fetchone()
        return self._decode_task(updated)

    def _acquire_locks(self, conn, room, agent, paths, task_id, lock_minutes):
        now_epoch = time.time()
        conn.execute("DELETE FROM file_locks WHERE expires_at<=?", (now_epoch,))
        self._drop_stale_holder_locks(conn, room)
        normalized = [str(Path(p).expanduser().resolve()) for p in paths]
        conflicts = []
        for path in normalized:
            row = conn.execute("SELECT * FROM file_locks WHERE room=? AND path=?", (room, path)).fetchone()
            if row and row["agent"] != agent:
                conflicts.append({"path": path, "agent": row["agent"], "task_id": row["task_id"]})
        if conflicts:
            raise ValueError("file lock conflict: %s" % json.dumps(conflicts, ensure_ascii=False))
        expires = now_epoch + min(max(1, int(lock_minutes)), 240) * 60
        for path in normalized:
            conn.execute(
                """INSERT INTO file_locks(room,path,agent,task_id,expires_at,created_at) VALUES(?,?,?,?,?,?)
                   ON CONFLICT(room,path) DO UPDATE SET agent=excluded.agent,task_id=excluded.task_id,
                     expires_at=excluded.expires_at,created_at=excluded.created_at""",
                (room, path, agent, task_id, expires, utc_now()),
            )
        return normalized

    def lock_files(self, room, agent, paths, task_id=None, lock_minutes=30):
        agent = _validate_label(agent, "agent", 80)
        if not paths:
            raise ValueError("paths is required")
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._assert_seat(conn, room, agent)
            paths = self._normalize_lock_paths(conn, room, paths)
            normalized = self._acquire_locks(conn, room, agent, paths, task_id, lock_minutes)
            self._heartbeat(conn, room, agent)
        return {"room": room, "agent": agent, "paths": normalized, "lock_minutes": min(max(1, int(lock_minutes)), 240)}

    def unlock_files(self, room, agent, paths=None):
        agent = _validate_label(agent, "agent", 80)
        with self.connection() as conn:
            self._assert_seat(conn, room, agent)
            if paths:
                normalized = [str(Path(p).expanduser().resolve()) for p in paths]
                placeholders = ",".join("?" for _ in normalized)
                cur = conn.execute(
                    "DELETE FROM file_locks WHERE room=? AND agent=? AND path IN (%s)" % placeholders,
                    [room, agent] + normalized,
                )
            else:
                cur = conn.execute("DELETE FROM file_locks WHERE room=? AND agent=?", (room, agent))
            self._heartbeat(conn, room, agent)
        return {"unlocked": cur.rowcount}

    def update_task(self, room, agent, task_id, status, result=""):
        agent = _validate_label(agent, "agent", 80)
        if status not in {"open", "in_progress", "blocked", "done"}:
            raise ValueError("status must be open, in_progress, blocked, or done")
        now = utc_now()
        with self.connection() as conn:
            self._assert_seat(conn, room, agent)
            row = conn.execute("SELECT * FROM tasks WHERE room=? AND id=?", (room, int(task_id))).fetchone()
            if not row:
                raise ValueError("task not found")
            if row["assignee"] and row["assignee"] != agent:
                raise ValueError("task is assigned to %s" % row["assignee"])
            assignee = agent if status in {"in_progress", "blocked", "done"} else None
            conn.execute(
                "UPDATE tasks SET status=?,assignee=?,result=?,updated_at=? WHERE id=?",
                (status, assignee, result or row["result"], now, int(task_id)),
            )
            if status in {"done", "open"}:
                conn.execute("DELETE FROM file_locks WHERE room=? AND agent=? AND task_id=?", (room, agent, int(task_id)))
            conn.execute(
                "INSERT INTO messages(room,sender,kind,body,created_at) VALUES(?,?,?,?,?)",
                (room, agent, "system", "Task #%d -> %s%s" % (int(task_id), status, (": " + result) if result else ""), now),
            )
            self._heartbeat(conn, room, agent)
            updated = conn.execute("SELECT * FROM tasks WHERE id=?", (int(task_id),)).fetchone()
        return self._decode_task(updated)

    def _annotate_participant(self, row):
        item = dict(row)
        age = _age_seconds(item.get("last_seen"))
        item["age_seconds"] = round(age, 1)
        pid_alive = self._pid_alive(item.get("pid"))
        item["pid_alive"] = pid_alive
        # last_seen is the heartbeat. A one-shot CLI process that just exited is
        # still "online" until TTL; already_online / seat takeover uses _occupant_live
        # (pid must still be alive) so sequential CLI commands can take the seat.
        item["online"] = age <= ONLINE_TTL_S
        item["process_live"] = age <= ONLINE_TTL_S and pid_alive is not False
        item["silent"] = age > ONLINE_TTL_S
        item["stale"] = age > STALE_LOCK_S
        if not item["online"]:
            item["status"] = "offline"
        return item

    @staticmethod
    def _canonical_presence(participants):
        live = []
        silent = []
        for item in participants:
            name = item.get("agent")
            if name not in CANONICAL_AGENTS:
                continue
            if item.get("online"):
                live.append(name)
            else:
                silent.append(name)
        return {
            "live_agents": live,
            "silent_agents": silent,
            "coordinator_silent": "codex" not in live,
        }

    def _drop_stale_holder_locks(self, conn, room):
        holders = self._rows(conn.execute(
            "SELECT agent, last_seen FROM participants WHERE room=?", (room,)
        ))
        stale = [h["agent"] for h in holders if _age_seconds(h["last_seen"]) > STALE_LOCK_S]
        if not stale:
            return 0
        placeholders = ",".join("?" for _ in stale)
        cur = conn.execute(
            "DELETE FROM file_locks WHERE room=? AND agent IN (%s)" % placeholders,
            [room] + stale,
        )
        return cur.rowcount

    def status(self, room):
        with self.connection() as conn:
            conn.execute("DELETE FROM file_locks WHERE expires_at<=?", (time.time(),))
            room_row = conn.execute("SELECT * FROM rooms WHERE name=?", (room,)).fetchone()
            if not room_row:
                raise ValueError("room not found: %s" % room)
            participants = [
                self._annotate_participant(row)
                for row in conn.execute("SELECT * FROM participants WHERE room=? ORDER BY agent", (room,))
            ]
            tasks = [self._decode_task(row) for row in conn.execute("SELECT * FROM tasks WHERE room=? ORDER BY priority,id", (room,))]
            locks = self._rows(conn.execute("SELECT * FROM file_locks WHERE room=? ORDER BY path", (room,)))
            for lock in locks:
                holder = next((p for p in participants if p["agent"] == lock["agent"]), None)
                lock["holder_online"] = bool(holder and holder["online"])
                lock["holder_stale"] = bool(holder and holder["stale"]) or holder is None
            docs = self.list_documents(room)
            last_message_id = conn.execute("SELECT COALESCE(MAX(id),0) AS id FROM messages WHERE room=?", (room,)).fetchone()["id"]
            directives = conn.execute(
                "SELECT COUNT(*) AS n FROM messages WHERE room=? AND kind='directive'", (room,)
            ).fetchone()["n"]
            claims = self._rows(conn.execute(
                "SELECT * FROM action_claims WHERE room=? AND expires_at>? ORDER BY action_key",
                (room, time.time()),
            ))
        presence = self._canonical_presence(participants)
        return {
            "room": dict(room_row),
            "participants": participants,
            "documents": docs,
            "tasks": tasks,
            "file_locks": locks,
            "action_claims": claims,
            "last_message_id": last_message_id,
            "directive_count": directives,
            "live_agents": presence["live_agents"],
            "silent_agents": presence["silent_agents"],
            "coordinator_silent": presence["coordinator_silent"],
        }

    def find_live_workspace_room(self, workspace):
        workspace = str(Path(workspace).expanduser().resolve()) if workspace else ""
        if not workspace:
            return None
        for item in self.list_rooms()["rooms"]:
            raw = item.get("workspace") or ""
            if not raw:
                continue
            try:
                resolved = str(Path(raw).expanduser().resolve())
            except Exception:
                resolved = raw
            if resolved == workspace and item.get("online_agents", 0) >= 1:
                return item
        return None

    def list_rooms(self):
        with self.connection() as conn:
            rows = conn.execute(
                "SELECT name, objective, workspace, created_at, updated_at FROM rooms ORDER BY updated_at DESC"
            ).fetchall()
            rooms = []
            for row in rows:
                item = dict(row)
                item["last_message_id"] = conn.execute(
                    "SELECT COALESCE(MAX(id),0) AS id FROM messages WHERE room=?", (row["name"],)
                ).fetchone()["id"]
                online = 0
                for p in conn.execute("SELECT last_seen FROM participants WHERE room=?", (row["name"],)):
                    if _age_seconds(p["last_seen"]) <= ONLINE_TTL_S:
                        online += 1
                item["online_agents"] = online
                rooms.append(item)
        return {"rooms": rooms}

    def reclaim_stale_locks(self, room, agent):
        agent = _validate_label(agent, "agent", 80)
        now = utc_now()
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM file_locks WHERE expires_at<=?", (time.time(),))
            dropped = self._drop_stale_holder_locks(conn, room)
            remaining = self._rows(conn.execute("SELECT * FROM file_locks WHERE room=?", (room,)))
            if dropped:
                conn.execute(
                    "INSERT INTO messages(room,sender,kind,body,created_at) VALUES(?,?,?,?,?)",
                    (room, agent, "system", "Reclaimed %d stale file lock(s)" % dropped, now),
                )
            self._heartbeat(conn, room, agent)
        return {"reclaimed": dropped, "remaining": remaining}

    def claim_action(self, room, agent, action_key, ttl_seconds=600):
        agent = _validate_label(agent, "agent", 80)
        action_key = (action_key or "").strip()
        if not action_key:
            raise ValueError("action_key is required")
        if len(action_key) > 200:
            raise ValueError("action_key is too long")
        ttl_seconds = min(max(5, int(ttl_seconds)), 3600)
        now_epoch = time.time()
        now = utc_now()
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._assert_seat(conn, room, agent)
            conn.execute("DELETE FROM action_claims WHERE expires_at<=?", (now_epoch,))
            row = conn.execute(
                "SELECT * FROM action_claims WHERE room=? AND action_key=?", (room, action_key)
            ).fetchone()
            if row and row["expires_at"] > now_epoch and row["agent"] != agent:
                raise ValueError(
                    "action already claimed by %s until %s: %s" % (row["agent"], row["expires_at"], action_key)
                )
            conn.execute(
                """INSERT INTO action_claims(room,action_key,agent,session_id,expires_at,created_at)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(room,action_key) DO UPDATE SET
                     agent=excluded.agent, session_id=excluded.session_id,
                     expires_at=excluded.expires_at, created_at=excluded.created_at""",
                (room, action_key, agent, self.session_id, now_epoch + ttl_seconds, now),
            )
            conn.execute(
                "INSERT INTO messages(room,sender,kind,body,created_at) VALUES(?,?,?,?,?)",
                (room, agent, "system", "Claimed action %s for %ss" % (action_key, ttl_seconds), now),
            )
            self._heartbeat(conn, room, agent)
            claimed = conn.execute(
                "SELECT * FROM action_claims WHERE room=? AND action_key=?", (room, action_key)
            ).fetchone()
        return dict(claimed)

    def wait_for_activity(self, room, agent, after_message_id=0, timeout_seconds=20):
        timeout_seconds = min(max(0, int(timeout_seconds)), 30)
        started = time.monotonic()
        deadline = started + timeout_seconds
        while True:
            messages = self.read_messages(room, agent, after_message_id, 100, False)
            timed_out = not bool(messages)
            if messages or time.monotonic() >= deadline:
                status = self.status(room)
                stale_locks = [lock for lock in status["file_locks"] if lock.get("holder_stale")]
                return {
                    "messages": messages,
                    "timed_out": timed_out,
                    "waited_seconds": round(time.monotonic() - started, 2),
                    "stale_locks": stale_locks,
                    "last_message_id": status["last_message_id"],
                    "silent_agents": status.get("silent_agents") or [],
                    "live_agents": status.get("live_agents") or [],
                    "coordinator_silent": bool(status.get("coordinator_silent")),
                }
            time.sleep(0.5)

    def leave(self, room, agent):
        """Mark this session's seat offline and drop its file locks."""
        agent = _validate_label(agent, "agent", 80)
        now = utc_now()
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            self._assert_seat(conn, room, agent)
            dropped = conn.execute(
                "DELETE FROM file_locks WHERE room=? AND agent=?", (room, agent)
            ).rowcount
            conn.execute(
                """UPDATE participants SET status='offline', last_seen=?
                   WHERE room=? AND agent=? AND (session_id=? OR session_id='' OR session_id IS NULL)""",
                (now, room, agent, self.session_id),
            )
            conn.execute(
                "INSERT INTO messages(room,sender,kind,body,created_at) VALUES(?,?,?,?,?)",
                (room, agent, "system", "%s left the room" % agent, now),
            )
        return {"ok": True, "room": room, "agent": agent, "status": "offline", "unlocked": dropped}
