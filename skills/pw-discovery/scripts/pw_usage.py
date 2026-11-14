#!/usr/bin/env python3
"""pw_usage.py - the opt-in for usage statistics, kept per study in .pw-kb/usage/.

Part of the Product Weaver pw-discovery skill · https://productweaver.com

Nothing is recorded or sent until the user has said yes. This script asks nothing itself: the skill asks, then runs
  python3 pw_usage.py set <.pw-kb> yes|no [--skill S] [--path P] [--assistant A] [--model M]
  python3 pw_usage.py start <.pw-kb> ...        and        python3 pw_usage.py end <.pw-kb> ... [--guide-written]
Each prints one line, "usage: <status>", and exits 0, whatever went wrong,
except that bad arguments make argparse print its own "usage: pw_usage.py ..." help and exit 2.

Status  ask (no answer yet), on, off (a no, or a settings file that cannot be trusted), no-study (no .pw-kb/ folder),
        disabled (KB_TOOL_USAGE=0 or DO_NOT_TRACK=1 in the environment; wins over everything).

The events and the files are described in references/usage.md. Only the standard library is used.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:  # the OS file lock: fcntl on macOS and Linux, msvcrt on Windows (the Windows branch is not run in CI)
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]
    import msvcrt

ENDPOINT = "https://www.productweaver.com/api/plugin-usage"
FORMAT_VERSION = 1
USAGE_FOLDER = "usage"
SETTINGS, README, GITIGNORE = "settings.json", "README.md", ".gitignore"
WAITING, SENT, LOCK = "waiting.jsonl", "sent.jsonl", ".lock"
MAX_AGE_DAYS, MAX_WAITING = 90, 1_000
BATCH_EVENTS, BATCH_BYTES = 100, 60_000
REQUEST_TIMEOUT_S, MIN_POST_BUDGET_S = 2.0, 0.5
LOCK_WAIT_SESSION_S, LOCK_WAIT_SET_S = 1.0, 5.0
RUN_LOG = Path("logs") / "kb_tool.jsonl"
README_TEMPLATE = Path(__file__).resolve().parent.parent / "assets" / "usage-readme.md"
ASSISTANTS = ("claude-code", "claude-cowork", "claude-ai", "chatgpt", "codex", "copilot-cli", "vscode", "cursor",
              "gemini-cli", "antigravity", "other")
SKILLS = ("pw-start", "pw-discovery")
PATHS = ("transcripts", "no_transcripts", "existing_study")
MODEL_PATTERN = r"[a-z0-9][a-z0-9.-]{0,47}"
UUID4_PATTERN = r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}"


def new_id() -> str:
    return str(uuid.uuid4())


def disabled() -> bool:
    """True when the user switched usage statistics off in the environment."""
    if os.environ.get("KB_TOOL_USAGE", "").strip().lower() in ("0", "off", "false"):
        return True
    return os.environ.get("DO_NOT_TRACK", "").strip().lower() in ("1", "true")


@dataclass
class Session:
    """Who is running: the skill, how the person starts (pw-start only), the assistant and the model."""
    skill: str
    path: str | None
    assistant: str
    model: str | None

    @classmethod
    def make(cls, skill: str, path: str | None, assistant: str | None, model: str | None) -> Session:
        if skill not in SKILLS:
            raise ValueError("unknown skill")
        assistant = assistant if assistant in ASSISTANTS else "other"
        if not (isinstance(model, str) and re.fullmatch(MODEL_PATTERN, model, re.ASCII)):
            model = None
        path = path if skill == "pw-start" and path in PATHS else None
        return cls(skill, path, assistant, model)


# --- files -----------------------------------------------------------------------------------------------------

def write_atomic(path: Path, data: bytes) -> None:
    """Write through a temporary file in the same folder, then replace: a reader never sees half a file."""
    handle, temp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(data)
        os.replace(temp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temp)
        raise


def count_lines(path: Path) -> int:
    """Lines in a file, read one at a time. 0 when the file is missing."""
    try:
        with open(path, "rb") as handle:
            return sum(1 for _ in handle)
    except FileNotFoundError:
        return 0


def utc_stamp(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def usage_folder(pw_kb: Path) -> Path:
    return pw_kb / USAGE_FOLDER


# --- status ----------------------------------------------------------------------------------------------------

def read_settings(pw_kb: Path) -> tuple[str, dict]:
    """The saved choice as (state, data): "ask" (no file), "on" (a valid yes) or "off" (a no, or a file to distrust)."""
    path = usage_folder(pw_kb) / SETTINGS
    if not path.is_file():
        return "ask", {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):
        return "off", {}
    if not isinstance(data, dict) or not isinstance(data.get("share"), bool):
        return "off", {}
    if data["share"] is False:
        return "off", data
    study = data.get("study")
    if not (isinstance(study, str) and re.fullmatch(UUID4_PATTERN, study, re.ASCII)):
        return "off", {}
    return "on", data


def status(pw_kb: Path) -> str:
    if disabled():
        return "disabled"
    if not pw_kb.is_dir():
        return "no-study"
    return read_settings(pw_kb)[0]


def git_shared(pw_kb: Path) -> bool:
    """True when the study may travel through git with its run log: a repository around it, and either no ignore
    rule for `*` or `logs/` in .pw-kb/.gitignore, or git's index still listing the log (a rule does not untrack it)."""
    study = pw_kb.resolve()
    root = next((folder for folder in study.parents if (folder / ".git").exists()), None)
    if root is None:
        return False
    try:
        lines = {line.strip() for line in (pw_kb / GITIGNORE).read_text(encoding="utf-8").splitlines()}
    except (OSError, ValueError):
        lines = set()
    return not lines & {"*", "logs/"} or log_tracked(root, study / RUN_LOG)


def log_tracked(root: Path, log: Path) -> bool:
    """True when git's index lists the run log, or when the index cannot be read: the safe answer. A repository with
    no index file yet tracks nothing. Read as bytes, never by running git."""
    try:
        name = log.relative_to(root).as_posix().lower().encode("utf-8") + b"\x00"
        dot_git = root / ".git"
        if dot_git.is_dir():
            folder = dot_git
        else:  # a worktree or a submodule: `.git` is a file that names the repository's folder
            text = dot_git.read_text(encoding="utf-8").strip()
            if not text.startswith("gitdir:"):
                return True
            folder = root / text[len("gitdir:"):].strip()  # an absolute path replaces root
        if not folder.is_dir():
            return True
        if not (folder / "index").exists():
            return False
        return any(index_holds(path, name) for path in (folder / "index", *sorted(folder.glob("sharedindex.*"))))
    except (OSError, ValueError):
        return True


def index_holds(path: Path, name: bytes) -> bool:
    """Whether a git index file holds `name` (lower case, NUL at the end), compared without case. Versions 2 and 3
    store every path in full; any other version, or a file that is not an index, counts as holding it."""
    with open(path, "rb") as handle:
        head = handle.read(8)
        if head[:4] != b"DIRC" or int.from_bytes(head[4:8], "big") not in (2, 3):
            return True
        tail = b""
        while True:
            chunk = handle.read(1 << 20)
            if not chunk:
                return False
            block = tail + chunk.lower()
            if name in block:
                return True
            tail = block[-len(name):]


# --- the answer ------------------------------------------------------------------------------------------------

def prepare_folder(pw_kb: Path) -> Path:
    """Make usage/ with its .gitignore and README, so nothing in it can reach git."""
    folder = usage_folder(pw_kb)
    folder.mkdir(exist_ok=True)
    write_atomic(folder / GITIGNORE, b"*\n")
    write_atomic(folder / README, README_TEMPLATE.read_bytes())
    return folder


def yes_settings(pw_kb: Path, now: datetime) -> dict:
    """The settings of a yes. A yes given again keeps the study ID and the cursor; a new one starts at the log's end."""
    state, data = read_settings(pw_kb)
    if state == "on":
        return {**data, "answered_at": utc_stamp(now)}
    return {"share": True, "answered_at": utc_stamp(now), "study": new_id(),
            "log_lines": count_lines(pw_kb / RUN_LOG),
            "last_ts": now.astimezone(timezone.utc).isoformat()}


def set_choice(pw_kb: Path, share: bool, session: Session, now: datetime) -> str:
    """Save the answer. Writes nothing when usage is disabled or there is no study. Returns the new status.
    A no keeps the study ID of an earlier yes (a deletion request needs it); a yes after a no makes a new one."""
    current = status(pw_kb)
    if current in ("disabled", "no-study"):
        return current
    folder = prepare_folder(pw_kb)
    if share:
        data = yes_settings(pw_kb, now)
    else:
        data = {"share": False, "answered_at": utc_stamp(now)}
        study = read_settings(pw_kb)[1].get("study")
        if matches(UUID4_PATTERN, study):  # the key for a deletion request stays where the README says it is
            data["study"] = study
        (folder / WAITING).unlink(missing_ok=True)
    write_atomic(folder / SETTINGS, (json.dumps(data, indent=2) + "\n").encode("utf-8"))
    return status(pw_kb)


# --- the converter ---------------------------------------------------------------------------------------------
# Every run-log line becomes one `tool_run` event through ALLOWED_FIELDS. A value that does not fit its entry is left
# out, so no free text can pass: only booleans, bounded numbers, fixed words and strings that match a pattern.

INT_MAX = 1_000_000
VERSION_PATTERN = r"[0-9]+\.[0-9]+\.[0-9]+"
CODE_PATTERN = r"[a-z][a-z0-9_]{0,39}"
LANGUAGE_PATTERN = r"[a-z]{2,3}(-[A-Z][a-z]{3})?(-([A-Z]{2}|[0-9]{3}))?"
COMMANDS = ("init", "labels", "context", "merge", "apply", "themes", "overview", "review", "map", "validate", "migrate")
KB_KEYS = ("interviews", "core_jobs", "unlinked_interviews", "steps", "thin_steps", "outcomes", "pending_proposals",
           "solutions", "solution_groups", "themes", "overviews", "stale")
COUNTS_KEYS = ("interviews_added", "interviews_skipped", "outcomes_added", "step_quotes", "outcome_quotes",
               "proposals_filed", "transcripts_copied", "solutions_added", "solution_groups_added", "solution_quotes",
               "themes", "theme_outcomes", "unassigned", "overview_gaps", "overviews")
LABELS_KEYS = ("missing", "added", "refused", "migrated")
MAX_CODES = 50  # the server accepts at most this many keys in an errors or warnings map

# field -> (kind, argument). Kinds: bool; int (argument: the top of the range); ms (milliseconds, rounded to 100, the
# argument is the top); enum; pattern; codes (a map of codes to counts, the argument is the most keys); keys (a map of
# fixed keys to counts, the argument is the keys); derived (worked out from other fields, never copied).
# The order is the order of usage.md, and so the order of the keys in an event.
ALLOWED_FIELDS: dict = {
    "command": ("enum", COMMANDS),
    "exit_code": ("int", 2),
    "written": ("bool", None),
    "duration_ms": ("ms", 86_400_000),
    "dry_run": ("bool", None),
    "nothing_new": ("bool", None),
    "bootstrap": ("bool", None),
    "rehash": ("bool", None),
    "moved": ("bool", None),
    "git": ("bool", None),
    "errors": ("codes", MAX_CODES),
    "warnings": ("codes", MAX_CODES),
    "counts": ("keys", COUNTS_KEYS),
    "kb": ("keys", KB_KEYS),
    "labels": ("keys", LABELS_KEYS),
    "language": ("pattern", LANGUAGE_PATTERN),
    "browser": ("enum", ("opened", "failed", "no_display", "off")),
    "exception": ("pattern", r"[A-Z][A-Za-z]{0,39}"),
    "schema_from": ("int", INT_MAX),
    "proposal_type": ("pattern", CODE_PATTERN),
    "decision": ("enum", ("approve", "reject")),
    "structure_problems": ("int", INT_MAX),
    "outcome_quotes": ("int", INT_MAX),
    "drifted": ("int", INT_MAX),
    "transcripts_copied": ("int", INT_MAX),
    "batch_minutes": ("derived", None),
    "attempt": ("derived", None),
    "transcripts_read": ("derived", None),
}
REQUIRED_FIELDS = ("command", "exit_code", "written", "duration_ms")


def valid_int(value: object, top: int = INT_MAX) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= top


def matches(pattern: str, value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(pattern, value, re.ASCII) is not None


def clean_map(kind: str, argument: object, value: object) -> dict | None:
    """A map of counts through its allow-list: fixed keys (`keys`) or codes (`codes`). None when nothing is left."""
    if not isinstance(value, dict):
        return None
    result: dict = {}
    for key, count in value.items():
        if kind == "keys" and key not in argument:  # type: ignore[operator]
            continue
        if kind == "codes" and (len(result) >= argument or not matches(CODE_PATTERN, key)):  # type: ignore[operator]
            continue
        number = len(count) if argument == KB_KEYS and key == "stale" and isinstance(count, list) else count
        if valid_int(number):
            result[key] = number
    if kind == "keys":  # in the order of the allow-list
        result = {key: result[key] for key in argument if key in result}  # type: ignore[union-attr]
    return result or None


def clean_value(spec: tuple, value: object) -> tuple[bool, object]:
    """(True, the value as it may leave) or (False, None) when it does not fit its allow-list entry."""
    kind, argument = spec
    if kind == "bool":
        return (True, value) if isinstance(value, bool) else (False, None)
    if kind == "int":
        return (True, value) if valid_int(value, argument) else (False, None)
    if kind == "ms":
        if not valid_int(value, argument + 49):
            return False, None
        rounded = (value + 50) // 100 * 100  # type: ignore[operator]
        return (True, rounded) if rounded <= argument else (False, None)
    if kind == "enum":
        return (True, value) if isinstance(value, str) and value in argument else (False, None)
    if kind == "pattern":
        return (True, value) if matches(argument, value) else (False, None)
    if kind in ("codes", "keys"):
        result = clean_map(kind, argument, value)
        return (True, result) if result else (False, None)
    return False, None


def clean_kb(value: object) -> dict:
    """The `kb` block through the allow-list. Empty when there is nothing usable."""
    return clean_map("keys", KB_KEYS, value) or {}


def parse_ts(ts: object) -> datetime | None:
    """A run-log time with an offset, as a datetime. None when it is not one."""
    if not isinstance(ts, str):
        return None
    text = ts.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        return None
    return moment if moment.tzinfo is not None and moment.utcoffset() is not None else None


def minute_stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def at_minute(ts: object) -> str | None:
    """An ISO time with an offset as `YYYY-MM-DDTHH:MMZ` in UTC (the seconds dropped, not rounded)."""
    moment = parse_ts(ts)
    try:
        return minute_stamp(moment) if moment else None
    except (OverflowError, OSError, ValueError):
        return None


def plugin_version() -> str | None:
    """The plugin's version, from plugin.json at the plugin's root. None when it cannot be read."""
    try:
        data = json.loads((Path(__file__).resolve().parents[3] / "plugin.json").read_text(encoding="utf-8"))
        version = data.get("version") if isinstance(data, dict) else None
    except (OSError, ValueError, RecursionError, IndexError):
        return None
    return version if matches(VERSION_PATTERN, version) else None


def tool_version() -> str | None:
    """The version of the kb_tool.py beside this script. None when it cannot be read."""
    try:
        text = (Path(__file__).resolve().parent / "kb_tool.py").read_text(encoding="utf-8")
    except (OSError, ValueError):
        return None
    found = re.search(r'^__version__ = "([\d.]+)"', text, re.M)
    return found.group(1) if found and matches(VERSION_PATTERN, found.group(1)) else None


def os_family() -> str:
    return {"darwin": "macos", "win32": "windows", "linux": "linux"}.get(sys.platform, "other")


def python_version() -> str:
    return f"{sys.version_info[0]}.{sys.version_info[1]}"


def envelope(name: str, study: str, session: Session, at: str, tool: str | None, os_name: str,  # noqa: PLR0917
             python: str) -> dict:
    if not matches(UUID4_PATTERN, study):
        raise ValueError("no valid study ID")
    return {"v": FORMAT_VERSION, "id": new_id(), "event": name, "at": at, "study": study, "plugin": plugin_version(),
            "tool": tool, "assistant": session.assistant, "model": session.model, "os": os_name, "python": python}


def line_assistant(agent: object) -> str:
    """The run log's `agent` as a value of the fixed list: `codex/1.2` becomes `codex`, anything unknown `other`."""
    head = agent.split("/")[0] if isinstance(agent, str) else ""
    return head if head in ASSISTANTS else "other"


def provenance_of(line: dict) -> dict:
    value = line.get("provenance")
    return value if isinstance(value, dict) else {}


def batch_minutes(line: dict, moment: datetime) -> int | None:
    started = parse_ts(provenance_of(line).get("started"))
    if started is None:
        return None
    try:
        seconds = (moment - started).total_seconds()
    except OverflowError:
        return None
    if seconds < 0:
        return None  # `started` after `ts`: not a duration
    minutes = int(seconds / 60 + 0.5)
    return minutes if valid_int(minutes) else None


def derived_fields(line: dict, attempt: int | None, moment: datetime) -> dict:
    """The fields of a merge worked out from the line, not copied from it."""
    if line.get("command") != "merge":
        return {}
    found: dict = {}
    provenance = provenance_of(line)
    if "started" in provenance:
        found["batch_minutes"] = batch_minutes(line, moment)
    if attempt is not None:
        found["attempt"] = attempt
    if isinstance(provenance.get("transcripts_read"), list):
        found["transcripts_read"] = len(provenance["transcripts_read"])
    return {key: value for key, value in found.items() if valid_int(value)}


def tool_event(line: dict, attempt: int | None, study: str, session: Session) -> dict | None:
    """One run-log line as a `tool_run` event, or None when the line cannot make a valid one."""
    if not matches(UUID4_PATTERN, study):
        return None
    moment = parse_ts(line.get("ts"))
    at = at_minute(line.get("ts"))
    if moment is None or at is None:
        return None
    fields: dict = {}
    derived = derived_fields(line, attempt, moment)
    for name, spec in ALLOWED_FIELDS.items():
        if spec[0] == "derived":
            if name in derived:
                fields[name] = derived[name]
        elif name in line:
            ok, value = clean_value(spec, line[name])
            if ok:
                fields[name] = value
    if any(name not in fields for name in REQUIRED_FIELDS):
        return None
    own = line.get("tool_version")
    tool = own if matches(VERSION_PATTERN, own) else tool_version()
    model = provenance_of(line).get("model")
    made = replace(session,
                   assistant=session.assistant if session.assistant != "other" else line_assistant(line.get("agent")),
                   model=session.model if session.model is not None or not matches(MODEL_PATTERN, model) else model)
    return {**envelope("tool_run", study, made, at, tool, os_family(), python_version()), **fields}


def read_log(path: Path):
    """Yield (parsed line or None, whether the line was complete) for each line of the run log, in order."""
    try:
        handle = open(path, "rb")  # noqa: SIM115 - a generator: the file stays open while it is read
    except FileNotFoundError:
        return
    with handle:
        for raw in handle:
            try:
                parsed = json.loads(raw.decode("utf-8", errors="replace"))
            except (ValueError, RecursionError):
                parsed = None
            yield (parsed if isinstance(parsed, dict) else None), raw.endswith(b"\n")


def is_wanted(reset: bool, index: int, cursor: int, moment: datetime | None, last_moment: datetime | None) -> bool:
    """Whether the line at `index` is new: after the cursor or, once the log was replaced, after the last time seen."""
    if reset:
        return moment is not None and last_moment is not None and moment > last_moment
    return index >= cursor


def tool_events(pw_kb: Path, settings: dict, session: Session) -> tuple[list[dict], dict]:
    """Events for the run-log lines after the cursor, and the settings with the cursor moved on.

    The cursor is `log_lines` (lines consumed) and `last_ts` (the newest readable time seen). A log shorter than the
    cursor was replaced: it is read from its start, keeping only lines newer than `last_ts`. A study shared through
    git sends nothing, and its cursor moves to the end of the log."""
    cursor = settings.get("log_lines")
    last_ts = settings.get("last_ts")
    send = isinstance(cursor, int) and not isinstance(cursor, bool) and cursor >= 0 and not git_shared(pw_kb)
    reset = send and count_lines(pw_kb / RUN_LOG) < cursor
    last_moment = parse_ts(last_ts)
    newest: tuple[datetime, str] | None = None
    seen: dict = {}
    events: list[dict] = []
    consumed = 0
    for line, complete in read_log(pw_kb / RUN_LOG):
        if line is None and not complete:
            break  # a line still being written: read it next time
        moment = parse_ts(line.get("ts")) if line else None
        attempt = None
        digest = line.get("patch_sha256") if line else None
        if isinstance(digest, str) and line.get("command") == "merge":  # type: ignore[union-attr]
            attempt = 1 + seen.get(digest, 0)
            seen[digest] = attempt
        if moment is not None and (newest is None or moment > newest[0]):
            newest = (moment, line["ts"])  # type: ignore[index]
        if send and line is not None and is_wanted(reset, consumed, cursor, moment, last_moment):
            event = tool_event(line, attempt, settings.get("study", ""), session)
            if event:
                events.append(event)
        consumed += 1
    moved = {**settings, "log_lines": consumed}
    if newest is not None and (last_moment is None or newest[0] > last_moment):
        moved["last_ts"] = newest[1]  # never backward: a time once seen is not sent again
    return events, moved


def round_count(job: object) -> int:
    """How many round entries one core job's plan holds: 0 when the job has no plan."""
    try:
        rounds = job["next"]["learn"]["round"]  # type: ignore[index]
    except (KeyError, TypeError):
        return 0
    return len(rounds) if isinstance(rounds, list) else 0


def kb_facts(pw_kb: Path) -> dict:
    """The study's language and how many round entries its plan holds. Nothing else of pw-kb.json is read."""
    facts = {"language": "en", "plan_entries": 0}
    try:
        data = json.loads((pw_kb / "pw-kb.json").read_text(encoding="utf-8"))
        meta = data.get("meta")
        language = meta.get("language") if isinstance(meta, dict) else None
        if isinstance(language, str) and language:
            facts["language"] = language
        total = sum(round_count(job) for job in data["overview"]["jobs"])
        facts["plan_entries"] = min(total, INT_MAX)
    except (OSError, ValueError, RecursionError, KeyError, TypeError, AttributeError):
        pass
    return facts


def last_kb(pw_kb: Path) -> dict:
    """The `kb` block of the last run-log line that has one, through the allow-list."""
    found: dict = {}
    for line, _complete in read_log(pw_kb / RUN_LOG):
        if line is not None and isinstance(line.get("kb"), dict):
            found = clean_kb(line["kb"])
    return found


def session_event(kind: str, pw_kb: Path, settings: dict, session: Session, now: datetime,  # noqa: PLR0917
                  guide_written: bool = False) -> dict:
    """`usage_on`, `session_start` or `session_end`."""
    base = envelope(kind, settings.get("study", ""), session, minute_stamp(now), tool_version(), os_family(),
                    python_version())
    facts = kb_facts(pw_kb)
    language = facts["language"] if matches(LANGUAGE_PATTERN, facts["language"]) else None
    extra: dict = {}
    if kind == "usage_on":
        kb = last_kb(pw_kb)
        extra["asked_at"] = "existing_study" if kb.get("interviews", 0) > 0 else "new_study"
    elif kind == "session_start":
        extra["skill"] = session.skill
        if session.path:
            extra["path"] = session.path
    else:
        extra["skill"] = session.skill
        if session.skill == "pw-start":
            extra["guide_written"] = bool(guide_written)
        extra["plan_entries"] = facts["plan_entries"]
    if kind != "session_end" and language:
        extra["language"] = language
    if kind == "usage_on":
        extra["kb"] = kb
    return {**base, **extra}


def record(pw_kb: Path, events: list[dict]) -> None:
    """Append events to usage/waiting.jsonl, one line each."""
    if not events:
        return
    folder = usage_folder(pw_kb)
    folder.mkdir(exist_ok=True)
    with open(folder / WAITING, "a", encoding="utf-8") as out:
        for event in events:
            out.write(json.dumps(event, separators=(",", ":")) + "\n")


def record_yes(pw_kb: Path, session: Session, now: datetime, first_yes: bool) -> None:
    """After a first yes: `usage_on` and `session_start`. After a yes given again: nothing."""
    state, settings = read_settings(pw_kb)
    if state != "on":
        return
    if first_yes:  # a yes given again changes nothing: `start` records the session
        (usage_folder(pw_kb) / WAITING).unlink(missing_ok=True)  # never send what an old study left behind
        record(pw_kb, [session_event(kind, pw_kb, settings, session, now) for kind in ("usage_on", "session_start")])


# --- sending ---------------------------------------------------------------------------------------------------
# Only here does anything leave the computer. An OS lock on usage/.lock keeps two sessions from posting the same
# batch, and a folder that cannot be written is never posted from (the lock is refused).

def try_lock(folder: Path) -> int | None:
    """One try at an OS lock on usage/.lock (the file is made if missing and never deleted). Returns the open file
    handle, or None when another process holds the lock. The OS drops the lock when its holder dies, so nothing can
    go stale. Raises OSError when the folder cannot be written (nothing is then recorded or sent) or the file cannot
    be opened."""
    if not os.access(folder, os.W_OK):
        raise PermissionError(f"{folder} is not writable")
    handle = os.open(folder / LOCK, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if fcntl is not None:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        else:  # pragma: no cover
            msvcrt.locking(handle, msvcrt.LK_NBLCK, 1)
    except OSError:  # busy
        os.close(handle)
        return None
    return handle


def acquire_lock(folder: Path, wait_s: float = 0.0) -> int | None:
    """The lock's handle, waiting up to wait_s seconds (polling every 50 ms). None when it stayed held by another.
    A folder that is missing or cannot be written raises at once; any other OSError (a sharing violation, say) is
    tried again until the end."""
    deadline = time.monotonic() + wait_s
    while True:
        try:
            handle = try_lock(folder)
        except OSError:
            if not folder.is_dir() or not os.access(folder, os.W_OK):
                raise
            handle = None
        if handle is not None or time.monotonic() >= deadline:
            return handle
        time.sleep(0.05)


def release_lock(handle: int | None) -> None:
    """Unlock and close. Closing alone would release it too."""
    if handle is None:
        return
    with contextlib.suppress(OSError):
        if fcntl is not None:
            fcntl.flock(handle, fcntl.LOCK_UN)
        else:  # pragma: no cover
            os.lseek(handle, 0, os.SEEK_SET)
            msvcrt.locking(handle, msvcrt.LK_UNLCK, 1)
    with contextlib.suppress(OSError):
        os.close(handle)


def encode_event(event: dict) -> bytes:
    return json.dumps(event, separators=(",", ":")).encode("utf-8")


# waiting.jsonl is a plain file anyone can edit, so each event is checked again before it is posted: the envelope,
# then every field against the converter's own allow-list entries. An event that fails is dropped, never posted.

ENVELOPE_KEYS = ("v", "id", "event", "at", "study", "plugin", "tool", "assistant", "model", "os", "python")
AT_PATTERN = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}Z"
EVENT_FIELDS: dict = {  # event -> (its fields, as ALLOWED_FIELDS gives them; the ones it must have)
    "usage_on": ({"asked_at": ("enum", ("new_study", "existing_study")), "language": ("pattern", LANGUAGE_PATTERN),
                  "kb": ("kb", None)}, ("asked_at", "kb")),
    "session_start": ({"skill": ("enum", SKILLS), "path": ("enum", PATHS), "language": ("pattern", LANGUAGE_PATTERN)},
                      ("skill",)),
    "session_end": ({"skill": ("enum", SKILLS), "guide_written": ("bool", None), "plan_entries": ("int", INT_MAX)},
                    ("skill", "plan_entries")),
    "tool_run": (ALLOWED_FIELDS, REQUIRED_FIELDS),
}


def fits(spec: tuple, value: object) -> bool:
    """Whether the allow-list entry lets this value out unchanged."""
    if spec[0] == "derived":
        return valid_int(value)
    if spec[0] == "kb":  # the snapshot of usage_on, which is empty for a study with no runs yet
        return isinstance(value, dict) and clean_kb(value) == value
    ok, cleaned = clean_value(spec, value)
    return ok and type(cleaned) is type(value) and cleaned == value


def fits_contract(event: object, study: str) -> bool:
    """Whether an event is one this script could have made for this study: the envelope, then only the fields of
    its own event type, each through its allow-list entry, the required ones present."""
    if not (isinstance(event, dict) and all(key in event for key in ENVELOPE_KEYS)):
        return False
    kind = event["event"] if isinstance(event["event"], str) else None
    if kind not in EVENT_FIELDS or not matches(UUID4_PATTERN, study) or event["study"] != study:
        return False
    envelope_ok = (type(event["v"]) is int and event["v"] == FORMAT_VERSION and matches(UUID4_PATTERN, event["id"])
                   and matches(AT_PATTERN, event["at"]) and parse_ts(event["at"]) is not None
                   and all(event[key] is None or matches(VERSION_PATTERN, event[key]) for key in ("plugin", "tool"))
                   and fits(("enum", ASSISTANTS), event["assistant"])
                   and (event["model"] is None or matches(MODEL_PATTERN, event["model"]))
                   and fits(("enum", ("macos", "windows", "linux", "other")), event["os"])
                   and matches(r"[0-9]+\.[0-9]+", event["python"]))
    fields, required = EVENT_FIELDS[kind]
    return (envelope_ok and all(key in event for key in required)
            and all(key in fields and fits(fields[key], event[key]) for key in event if key not in ENVELOPE_KEYS))


def read_waiting(folder: Path) -> list[dict]:
    """The waiting events in file order. Unparseable lines, events without an id and repeated ids are left out."""
    events: list[dict] = []
    seen: set = set()
    for line, _complete in read_log(folder / WAITING):
        event_id = line.get("id") if line else None
        if isinstance(event_id, str) and event_id not in seen:
            seen.add(event_id)
            events.append(line)  # type: ignore[arg-type]
    return events


def sent_ids(folder: Path) -> set:
    found: set = set()
    for line, _complete in read_log(folder / SENT):
        data = line.get("data") if line else None
        if isinstance(data, dict) and isinstance(data.get("id"), str):
            found.add(data["id"])
    return found


def too_old(event: dict, now: datetime) -> bool:
    moment = parse_ts(event.get("at"))
    try:
        return moment is None or now - moment > timedelta(days=MAX_AGE_DAYS)
    except OverflowError:
        return True


def drop_waiting(folder: Path, gone: set) -> None:
    """Rewrite waiting.jsonl without the events whose ids are in `gone`. The file is read again first, so an event
    another session recorded in the meantime stays. No events left: the file is removed."""
    keep = [e for e in read_waiting(folder) if e["id"] not in gone]
    if keep:
        write_atomic(folder / WAITING, b"".join(encode_event(e) + b"\n" for e in keep))
    else:
        (folder / WAITING).unlink(missing_ok=True)


def next_batch(events: list[dict]) -> tuple[list[dict], list[dict]]:
    """(the events for one request, the single events too big to ever send). The body stays under BATCH_BYTES."""
    batch: list[dict] = []
    too_big: list[dict] = []
    size = len(b'{"v":1,"events":[]}')
    for event in events:
        length = len(encode_event(event))
        if size + length >= BATCH_BYTES:  # the body must stay under the limit
            if not batch:
                too_big.append(event)
                continue
            break
        if len(batch) >= BATCH_EVENTS:
            break
        batch.append(event)
        size += length + 1
    return batch, too_big


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: ANN002, ANN003 - a redirect is an answer, never followed
        return None


def post_now(url: str, body: bytes, timeout: float) -> bool:
    """POST one body. True when the events moved on: 2xx, or the endpoint's own 400 or 413 (a batch it will never
    take). Any other answer (a redirect, 401, 403, 404, 408, 429, 5xx: a firewall, a moved route, a busy server)
    and any network error keep them waiting, within the 90-day and 1,000-event caps."""
    request = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "User-Agent": f"productweaver-plugin/{plugin_version() or 'unknown'}"})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as answer:
            code = answer.status
    except urllib.error.HTTPError as error:
        code = error.code
        error.close()
    except Exception:  # noqa: BLE001 - URLError, OSError, TimeoutError, ValueError, http.client errors: try next time
        return False
    return 200 <= code < 300 or code in (400, 413)


def post(url: str, body: bytes, timeout: float, patience: float) -> bool:
    """post_now in a daemon thread that is given `patience` seconds in all: name lookups and slow answers have no
    time limit of their own. A POST that has not finished then counts as not sent (the events stay waiting)."""
    result: list[bool] = []
    worker = threading.Thread(target=lambda: result.append(post_now(url, body, timeout)), daemon=True)
    worker.start()
    worker.join(patience)
    return bool(result and result[0])


def append_sent(folder: Path, events: list[dict], now: datetime) -> None:
    stamp = utc_stamp(now)
    with open(folder / SENT, "ab") as out:
        for event in events:
            out.write(json.dumps({"sent_at": stamp, "data": event}, separators=(",", ":")).encode("utf-8") + b"\n")
        out.flush()
        os.fsync(out.fileno())


def send_locked(pw_kb: Path, now: datetime, url: str | None = None, budget_s: float = 3.0) -> int:
    """Send the waiting events in batches. The caller holds the lock. Returns how many are still waiting.

    Waiting events already sent, older than 90 days, past the newest 1,000, or not fitting the contract for this
    study (fits_contract) are dropped first, never posted. Before every POST and every rewrite the status is read
    again: a `no` given in the meantime stops the sending and waiting.jsonl is not written again."""
    folder = usage_folder(pw_kb)
    deadline = time.monotonic() + budget_s
    if status(pw_kb) != "on":
        return count_lines(folder / WAITING)
    study = read_settings(pw_kb)[1].get("study", "")
    on_disk = read_waiting(folder)
    already = sent_ids(folder)
    events = [e for e in on_disk
              if e["id"] not in already and not too_old(e, now) and fits_contract(e, study)][-MAX_WAITING:]
    if len(events) != count_lines(folder / WAITING):
        drop_waiting(folder, {e["id"] for e in on_disk} - {e["id"] for e in events})
    while events and status(pw_kb) == "on":
        batch, too_big = next_batch(events)
        if too_big:
            events = [e for e in events if not any(e is big for big in too_big)]
            drop_waiting(folder, {e["id"] for e in too_big})
            continue
        remaining = deadline - time.monotonic()
        if remaining < MIN_POST_BUDGET_S:
            break
        body = b'{"v":1,"events":[' + b",".join(encode_event(e) for e in batch) + b"]}"
        if not post(url or ENDPOINT, body, min(REQUEST_TIMEOUT_S, remaining), remaining):
            break
        append_sent(folder, batch, now)  # whatever left is always recorded, whatever the status is now
        if status(pw_kb) != "on":
            break  # a no in the meantime: waiting.jsonl is not written again
        events = events[len(batch):]
        drop_waiting(folder, {e["id"] for e in batch})
    return count_lines(folder / WAITING)


def send_waiting(pw_kb: Path, now: datetime, url: str | None = None, budget_s: float = 3.0) -> int:
    """send_locked under the lock. Nothing is sent when the lock is held by another session or cannot be made."""
    folder = usage_folder(pw_kb)
    try:
        token = try_lock(folder)
    except OSError:
        token = None
    if token is None:
        return count_lines(folder / WAITING)
    try:
        return send_locked(pw_kb, now, url, budget_s)
    finally:
        release_lock(token)


# --- command line ----------------------------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Opt-in usage statistics for the Product Weaver plugin.")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("start", "set", "end"):
        sub = commands.add_parser(name)
        sub.add_argument("pw_kb", help="the study's .pw-kb folder")
        if name == "set":
            sub.add_argument("choice", choices=("yes", "no"))
        sub.add_argument("--skill", choices=SKILLS, default="pw-discovery")
        sub.add_argument("--path")
        sub.add_argument("--assistant")
        sub.add_argument("--model")
        if name == "end":
            sub.add_argument("--guide-written", action="store_true")
    return parser


def run(args: argparse.Namespace) -> str:
    pw_kb = Path(args.pw_kb)
    session = Session.make(args.skill, args.path, args.assistant, args.model)
    if args.command == "set":
        now = datetime.now(timezone.utc)
        # The answer wins: wait for a running send, then go on without the lock if it is still held.
        token = lock_for(pw_kb, LOCK_WAIT_SET_S)
        try:
            before = status(pw_kb)
            result = set_choice(pw_kb, args.choice == "yes", session, now)
            if args.choice == "yes" and result == "on":
                record_yes(pw_kb, session, now, before != "on")
        finally:
            release_lock(token)
        return result
    return run_session(pw_kb, session, args)


def lock_for(pw_kb: Path, wait_s: float) -> int | None:
    """The lock's handle when the usage folder exists and the lock could be taken; None otherwise."""
    folder = usage_folder(pw_kb)
    if not folder.is_dir():
        return None
    try:
        return acquire_lock(folder, wait_s)
    except OSError:
        return None


def run_session(pw_kb: Path, session: Session, args: argparse.Namespace) -> str:
    """start and end: record the session event, convert the new run-log lines, move the cursor, send. Only on `on`.
    All of it happens under the lock, so two sessions never convert the same lines or lose each other's events."""
    current = status(pw_kb)
    if current != "on":
        return current
    folder = usage_folder(pw_kb)
    token = acquire_lock(folder, LOCK_WAIT_SESSION_S)  # OSError (read-only folder): main reports the status
    if token is None:
        # Another session is busy. Do nothing now: the run log keeps the tool events for next time. This call's session
        # event may be lost, which is accepted.
        return status(pw_kb)
    try:
        now = datetime.now(timezone.utc)
        state, settings = read_settings(pw_kb)
        if state != "on":
            return state
        converted, moved = tool_events(pw_kb, settings, session)
        if args.command == "start":
            events = [session_event("session_start", pw_kb, settings, session, now), *converted]
        else:
            events = [*converted, session_event("session_end", pw_kb, settings, session, now,
                                                guide_written=args.guide_written)]
        if read_settings(pw_kb)[0] != "on":  # a no given while we converted (set waited for the lock in vain)
            return status(pw_kb)
        record(pw_kb, events)
        # Accepted risk: a crash right here, before the cursor is saved, converts the same lines again next time with
        # new ids (a few duplicate events, nothing lost).
        save_cursor(pw_kb, settings, moved)
        send_locked(pw_kb, now)
        return status(pw_kb)
    finally:
        release_lock(token)


def save_cursor(pw_kb: Path, before: dict, moved: dict) -> None:
    """Put the converter's new place in the run log (`log_lines`, `last_ts`) onto settings.json as it is now, and
    only while it still holds the same yes: a `no` that `set` wrote without the lock is never undone."""
    state, current = read_settings(pw_kb)
    if state != "on" or current.get("study") != before.get("study"):
        return
    saved = {**current, **{key: moved[key] for key in ("log_lines", "last_ts") if key in moved}}
    if saved != current:
        write_atomic(usage_folder(pw_kb) / SETTINGS, (json.dumps(saved, indent=2) + "\n").encode("utf-8"))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = run(args)
    except Exception:  # noqa: BLE001 - never a traceback: report what is on disk
        result = real_status(Path(args.pw_kb))
    print(f"usage: {result}")
    return 0


def real_status(pw_kb: Path) -> str:
    """The status as the disk has it, after a command failed. "off" when even that cannot be read."""
    try:
        return status(pw_kb)
    except Exception:  # noqa: BLE001
        return "off"


if __name__ == "__main__":
    sys.exit(main())
