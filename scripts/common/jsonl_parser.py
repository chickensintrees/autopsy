"""
JSONL parsing for Claude Code session files.

Boundary model
--------------
A *boundary* is a point where context was reconstructed rather than remembered.
There are two kinds, and they are not the same event:

    compaction      A `type=system subtype=compact_boundary` line. The harness
                    records what it discarded and what it kept, including which
                    tools the agent had discovered at that moment.

    session_resume  A summary injected with no compaction that produced it —
                    i.e. `--continue` / `--resume` into a fresh session file.

Note on the summary message: after a compaction, the harness injects a user-role
message carrying `isCompactSummary: True` on the line *immediately after* the
compact_boundary. That message is the compaction's payload, NOT a second boundary.
It is also not a real user message — counting it as one manufactures false
correction pairs, so it stays flagged synthetic and excluded from user scans.

A summary marker with no compaction next to it is the interesting case: that is a
genuine cross-session resume. See README — it is detected here but unverified
against a corpus known to contain one.
"""

import json
import os
import glob
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# How many lines back from a summary marker to look for the compaction that caused it.
# Observed in practice: the summary lands on boundary_line + 1.
SUMMARY_ADJACENCY_WINDOW = 3


@dataclass
class Boundary:
    """A point where context was reconstructed instead of remembered."""
    line_number: int
    timestamp: str
    kind: str  # "compaction" | "session_resume"
    uuid: str = ""
    trigger: str = ""  # "auto" | "manual" | "" for session_resume
    pre_tokens: int = 0
    post_tokens: int = 0
    kept_messages: int = 0
    known_tools: list = field(default_factory=list)  # preCompactDiscoveredTools
    summary_text: str = ""

    @property
    def discarded_tokens(self) -> int:
        return max(0, self.pre_tokens - self.post_tokens)

    @property
    def retention_pct(self) -> float:
        """Percent of context that survived. The rest was summarized away."""
        if not self.pre_tokens:
            return 0.0
        return round(100.0 * self.post_tokens / self.pre_tokens, 1)


@dataclass
class Message:
    """A parsed message from a session JSONL."""
    line_number: int
    type: str  # "user", "assistant", "system"
    subtype: str
    role: str
    content_text: str
    tool_uses: list
    timestamp: str
    uuid: str
    session_id: str
    is_post_boundary: bool = False
    boundary_index: int = -1  # which boundary this follows (-1 = before any)
    boundary_kind: str = ""  # kind of the most recent preceding boundary
    is_tool_result_only: bool = False
    is_synthetic: bool = False  # system-injected content wearing a user role
    is_compact_summary: bool = False


@dataclass
class Session:
    """A parsed Claude Code session."""
    session_id: str
    file_path: str
    file_size: int
    messages: list
    boundaries: list
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    @property
    def boundary_count(self) -> int:
        return len(self.boundaries)

    @property
    def compactions(self) -> list:
        return [b for b in self.boundaries if b.kind == "compaction"]

    @property
    def resumes(self) -> list:
        return [b for b in self.boundaries if b.kind == "session_resume"]

    @property
    def compaction_count(self) -> int:
        return len(self.compactions)

    @property
    def entry_kind(self) -> str:
        """How this session began: resumed from a prior one, or cold."""
        if self.boundaries and self.boundaries[0].kind == "session_resume":
            return "resumed"
        return "cold"

    @property
    def size_mb(self) -> float:
        return self.file_size / (1024 * 1024)


def extract_text(content) -> str:
    """Extract plain text from message content (handles string and list formats)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    texts.append(block.get("text", ""))
                elif block.get("type") == "thinking":
                    texts.append(block.get("thinking", ""))
        return "\n".join(texts)
    return ""


def extract_tool_uses(content) -> list:
    """Extract tool_use blocks from message content."""
    if not isinstance(content, list):
        return []
    tools = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_use":
            tools.append({
                "name": block.get("name", ""),
                "input": block.get("input", {}),
            })
    return tools


def parse_message(line_number: int, obj: dict) -> Optional[Message]:
    """Parse a single JSONL line into a Message."""
    msg_type = obj.get("type", "")
    if msg_type not in ("user", "assistant", "system"):
        return None

    subtype = obj.get("subtype", "")
    session_id = obj.get("sessionId", "")
    timestamp = obj.get("timestamp", "")
    uuid = obj.get("uuid", "")

    msg = obj.get("message", {})
    if isinstance(msg, dict):
        role = msg.get("role", msg_type)
        content = msg.get("content", "")
    else:
        role = msg_type
        content = obj.get("content", "")

    content_text = extract_text(content)
    tool_uses = extract_tool_uses(content) if isinstance(content, list) else []

    is_tool_result_only = (
        msg_type == "user"
        and not content_text.strip()
        and isinstance(content, list)
        and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content)
    )

    # The harness marks the post-compaction summary explicitly. Trust the field,
    # not the sentence — the wording is not a contract, the field is.
    is_compact_summary = bool(obj.get("isCompactSummary", False))

    is_synthetic = is_compact_summary
    if msg_type == "user" and content_text and not is_synthetic:
        # Injected content that REPLACES the user message: the harness prepends this,
        # and the rest of the message is skill prose, not speech. Prefix-anchored,
        # because a human quoting the phrase mid-sentence is still a human talking.
        # (2a46fab shipped this as an `in` match; that silently dropped real
        # frustration signals that happened to quote the string — anyone discussing
        # skills. See tests/test_synthetic_markers.py. Fixed 2026-07-17.)
        synthetic_prefixes = (
            "Base directory for this skill:",
        )
        # Injected content that can appear ANYWHERE, including appended to real text.
        synthetic_anywhere = (
            "This session is being continued from a previous conversation",
            "<task-notification",
            "<system-reminder",
        )
        is_synthetic = (
            content_text.startswith(synthetic_prefixes)
            or any(marker in content_text for marker in synthetic_anywhere)
        )

    return Message(
        line_number=line_number,
        type=msg_type,
        subtype=subtype,
        role=role,
        content_text=content_text,
        tool_uses=tool_uses,
        timestamp=timestamp,
        uuid=uuid,
        session_id=session_id,
        is_tool_result_only=is_tool_result_only,
        is_synthetic=is_synthetic,
        is_compact_summary=is_compact_summary,
    )


def parse_compaction(line_number: int, obj: dict) -> Optional[Boundary]:
    """Parse a compact_boundary marker into a Boundary."""
    if obj.get("type") != "system" or obj.get("subtype") != "compact_boundary":
        return None

    meta = obj.get("compactMetadata", {})
    preserved = meta.get("preservedMessages", {}) or {}
    return Boundary(
        line_number=line_number,
        timestamp=obj.get("timestamp", ""),
        kind="compaction",
        uuid=obj.get("uuid", ""),
        trigger=meta.get("trigger", "unknown"),
        pre_tokens=meta.get("preTokens", 0),
        post_tokens=meta.get("postTokens", 0),
        kept_messages=len(preserved.get("uuids", []) or []),
        known_tools=list(meta.get("preCompactDiscoveredTools", []) or []),
    )


def parse_session(file_path: str) -> Session:
    """Parse a full session JSONL file."""
    session_id = Path(file_path).stem
    try:
        file_size = os.path.getsize(file_path)
    except OSError:
        return Session(session_id=session_id, file_path=file_path,
                       file_size=0, messages=[], boundaries=[])

    messages = []
    boundaries = []

    try:
        f = open(file_path, "r", encoding="utf-8", errors="replace")
    except (OSError, PermissionError) as e:
        import sys
        print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
        return Session(session_id=session_id, file_path=file_path,
                       file_size=file_size, messages=[], boundaries=[])

    with f:
        for i, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue

            cb = parse_compaction(i, obj)
            if cb:
                boundaries.append(cb)
                continue

            msg = parse_message(i, obj)
            if not msg:
                continue
            messages.append(msg)

            if msg.is_compact_summary:
                # Is there a compaction right behind this? Then this is its payload.
                owner = None
                for b in reversed(boundaries):
                    if b.kind == "compaction" and i - b.line_number <= SUMMARY_ADJACENCY_WINDOW:
                        owner = b
                    break
                if owner is not None:
                    owner.summary_text = msg.content_text[:2000]
                else:
                    # A summary with no compaction behind it: context was rebuilt
                    # from a *previous session*. That is a resume, not a compaction.
                    boundaries.append(Boundary(
                        line_number=i,
                        timestamp=msg.timestamp,
                        kind="session_resume",
                        uuid=msg.uuid,
                        summary_text=msg.content_text[:2000],
                    ))

    boundaries.sort(key=lambda b: b.line_number)

    # Mark each message with the most recent boundary preceding it.
    for msg in messages:
        for bi, b in enumerate(boundaries):
            if msg.line_number > b.line_number:
                msg.is_post_boundary = True
                msg.boundary_index = bi
                msg.boundary_kind = b.kind
            else:
                break

    timestamps = [m.timestamp for m in messages if m.timestamp]
    return Session(
        session_id=session_id,
        file_path=file_path,
        file_size=file_size,
        messages=messages,
        boundaries=boundaries,
        start_time=timestamps[0] if timestamps else None,
        end_time=timestamps[-1] if timestamps else None,
    )


def find_sessions(base_path: Optional[str] = None, min_size: int = 1024) -> list:
    """Find all session JSONL files, newest first."""
    if base_path is None:
        base_path = os.path.expanduser("~/.claude/projects/")

    pattern = os.path.join(base_path, "**", "*.jsonl")
    files = glob.glob(pattern, recursive=True)

    # Subagent sessions are spawned by the Task tool, not driven by a user.
    files = [f for f in files if "subagents" not in Path(f).parts]

    sized = [(f, os.path.getsize(f)) for f in files]
    valid = [(f, s) for f, s in sized if s >= min_size]
    valid.sort(key=lambda x: os.path.getmtime(x[0]), reverse=True)
    return [f for f, _ in valid]


def find_sessions_by_date(base_path: Optional[str] = None, days: int = 1) -> list:
    """Find sessions modified within the last N days."""
    import time
    cutoff = time.time() - (days * 86400)
    return [f for f in find_sessions(base_path) if os.path.getmtime(f) >= cutoff]
