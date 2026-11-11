#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml==6.0.3"]
# ///
"""kb_tool.py - keep an ODI knowledge base (one YAML file) growing from interview transcripts.

Part of the Product Weaver distill-kb skill · https://productweaver.com

A study lives in one folder, .pw-kb/ at the root of the workspace: the KB .pw-kb/pw-kb.yaml, and next to it
patches/, backups/, logs/, transcripts/ (a copy of every transcript the KB cites), review.md and discovery-map.html.

Commands
  init      .pw-kb/pw-kb.yaml --project NAME [--interviewer NAME]
                                                              start an empty KB
  context   <kb.yaml> [--json]                                compact view of the KB to map new evidence against
  merge     <kb.yaml> <patch.yaml> [--transcripts DIR ...] [--dry-run] [--json]
                                                              check every quote and reference, fold the patch in and
                                                              copy new transcripts into .pw-kb/transcripts/
  apply     <kb.yaml> <proposal-id> --decision approve|reject [--note TEXT]
                                                              act on a proposed structural change
  review    <kb.yaml> [--since DATE] [--out FILE]             write review.md, a plain sheet for human reviewers
  map       <kb.yaml> [--template FILE] [--out FILE] [--open] write discovery-map.html, the interactive map, KB inside;
                                                              --open also shows it in the default browser
  themes    <kb.yaml> <themes.yaml> [--dry-run] [--json]      check one core job's value themes and write them:
                                                              few needs that group the outcomes, for ideation
  overview  <kb.yaml> <overview.yaml> [--dry-run] [--json]  check one core job's overview and write it: the
                                                              study as a short story, with what to do next
  validate  <kb.yaml> [--structure-only] [--schema FILE] [--rehash]
                                                              check the structure, then every quote and transcript hash
  migrate   <kb.yaml> [--to .pw-kb/pw-kb.yaml] [--transcripts DIR ...]
                                                              bring an older KB up to the current schema version, and
                                                              move a study made by an earlier version into .pw-kb/

Run it with no setup:   uv run --locked kb_tool.py <command> ...      (uv installs PyYAML in its cache the first time)
Or install PyYAML once: python3 -m pip install pyyaml==6.0.3
.docx transcripts need python-docx==1.2.0, .pdf transcripts need pypdf==6.21.4.

Every run, including a failed one or a dry run, appends one JSON line to .pw-kb/logs/kb_tool.jsonl:
what was asked, how it ended, error and warning codes, counts, versions. Never quotes, names or file names.
Set KB_TOOL_LOG=0 to switch the log off and KB_TOOL_AGENT=<assistant> to name the assistant that is running.
Set KB_TOOL_OPEN=0 and map --open never starts a browser.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import datetime as dt
import difflib
import glob
import hashlib
import json
import os
import pathlib
import platform
import re
import shutil
import sys
import time
import uuid
import webbrowser
from dataclasses import dataclass, field
from typing import Any, Callable

try:
    import yaml
except ImportError:  # pragma: no cover - depends on the machine
    sys.exit("PyYAML is missing. Run `uv run --locked kb_tool.py ...` or `python3 -m pip install pyyaml==6.0.3`.")

try:
    import jsonschema as _jsonschema  # optional: richer schema messages when it is installed
except ImportError:  # pragma: no cover - depends on the machine
    _jsonschema = None

__version__ = "0.8.0"
SCHEMA_VERSION = 2

BRAND = "Product Weaver"
SITE = "https://productweaver.com"
MADE_WITH = f"Made with {BRAND} · productweaver.com"

DERIVED = ["survey", "simulation", "value_themes", "overview", "use_cases"]
SOURCES = ("transcript", "quoted_in_notes", "interviewer_notes")
STAGES = ["define", "locate", "prepare", "confirm", "execute", "monitor", "modify", "conclude"]
PROPOSAL_TYPES = ["new_step", "reword_step", "reword_outcome", "reword_core_job",
                  "merge_outcomes", "move_outcome", "new_segment", "new_core_job", "confirm_core_job",
                  "move_step", "relink_interview", "merge_solutions", "move_solution", "reword_solution",
                  "reword_solution_group", "other"]
PATCH_SECTIONS = ("interviews", "bootstrap", "step_evidence", "outcome_evidence", "new_outcomes",
                  "solution_groups", "new_solutions", "solution_evidence", "proposed_changes")
SOLUTION_KINDS = ["product", "everyday_tool", "people", "own_method"]
SOLUTION_STATUS = ["current", "stopped"]
KIND_LABELS = {"product": "product or app", "everyday_tool": "everyday tool", "people": "other people",
               "own_method": "own method"}
PATCH_KEYS = (*PATCH_SECTIONS, "provenance")  # every top-level key a patch may carry
PROVENANCE_KEYS = ("assistant", "model", "started", "transcripts_read", "notes")
LOG_FOLDER, LOG_FILE = "logs", "kb_tool.jsonl"
KB_FOLDER, KB_FILE, COPIES = ".pw-kb", "pw-kb.yaml", "transcripts"  # <workspace root>/.pw-kb/pw-kb.yaml
KB_HOME = f"{KB_FOLDER}/{KB_FILE}"
OLD_TRANSCRIPTS = "Interviews"  # where earlier versions kept a study's transcripts: <study>/Interviews/
MOVED_ON_MIGRATE = ("patches", "backups", LOG_FOLDER, "review.md", "discovery-map.html")
DIRECTION = re.compile(r"^(Minimize|Maximize|Increase|Reduce) ")
JOB_ID = re.compile(r"^[A-Z]{1,2}$")
STEP_ID = re.compile(r"^[A-Z]{1,2}\.[0-9]+$")
OUTCOME_ID = re.compile(r"^[A-Z]{1,2}\.[0-9]+\.[0-9]+$")
BARE_OUTCOME_ID = re.compile(r"^[0-9]+\.[0-9]+$")  # schema 1, before IDs carried the core job's letter
SOLUTION_ID = re.compile(r"^S[0-9]+$")
THEME_ID = re.compile(r"^[A-Z]{1,2}\.T[0-9]+$")
HIGHLIGHT_KINDS = ["pain", "struggle", "desire"]
THEME_KEYS = ("id", "label", "need", "why", "outcomes", "highlights")
THEME_COUNT = (5, 9)       # value themes per core job
THEME_MIN_OUTCOMES = 3     # outcomes a theme should gather, and outcomes a core job needs per theme
THEME_MAX_SHARE = 3        # no theme should hold more than one in this many of the job's outcomes
THEME_MAX_PER_OUTCOME = 2  # themes one outcome may sit in
THEME_HIGHLIGHTS = 6       # quotes picked for one theme, at most
OVERVIEW_KEYS = ("job", "bottom_line", "why", "opening", "people", "today", "gaps", "needs", "focus", "next")
GAP_KINDS = ["pain", "struggle"]  # what goes wrong today, and a fix that did not work
GAP_MAX = 5                # gaps an overview should show, at most
# what to do next: the statuses each track may have, and the fields it holds besides status and action
NEXT_TRACKS = {"learn": (("now", "enough"), ("why", "ask", "tip")),
               "prototype": (("ready", "early"), ("why", "test", "later")),
               "market": (("ready", "early"), ("who", "words", "unknown"))}
NEXT_LISTS = {"ask": 2, "words": 3}  # fields that are lists, and how many items each may hold
SCORE_WORDS = re.compile(r"\d\s?%|\bpercent\b|\b(opportunity|importance|satisfaction) (score|rating)s?\b",
                         re.IGNORECASE)
GROUP_KEY = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
TRANSCRIPT_EXTS = (".md", ".markdown", ".txt", ".docx", ".pdf")
KEEP_BACKUPS = 20
THIN_STEP = 3
MAX_PROBLEMS = 60

Json = dict[str, Any]


class KbError(Exception):
    """A problem the user can fix. main() prints it as a message, never as a traceback.

    `code` is a short stable name for the kind of problem; the run log counts runs by it."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class Report:
    """Problems found while checking a patch or a KB. Errors block, warnings do not.

    Each message carries a code, so the run log can count what goes wrong without storing the message,
    which may hold a quote or a name. The codes are listed in references/run-log.md."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error_codes: dict[str, int] = field(default_factory=dict)
    warning_codes: dict[str, int] = field(default_factory=dict)

    def error(self, message: str, *, code: str) -> None:
        self.errors.append(message)
        self.error_codes[code] = self.error_codes.get(code, 0) + 1

    def warn(self, message: str, *, code: str) -> None:
        self.warnings.append(message)
        self.warning_codes[code] = self.warning_codes.get(code, 0) + 1


def today() -> str:
    return dt.date.today().isoformat()


# ---------- run log ----------
def file_sha256(path: str) -> str | None:
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError:
        return None


def kb_summary(path: str) -> Json | None:
    """How big the KB is after a run, as counts only, so the log can draw trend lines."""
    try:
        with open(path, encoding="utf-8") as handle:
            kb = yaml.safe_load(handle)
    except (OSError, yaml.YAMLError):
        return None
    if not isinstance(kb, dict):
        return None
    steps = (kb.get("job_map") or {}).get("steps") or []
    outcomes = (kb.get("desired_outcomes") or {}).get("outcomes") or []
    proposals = kb.get("proposed_changes") or []
    records = [r for r in kb.get("interviews") or [] if isinstance(r, dict)]
    unlinked = [r for r in records if not (r.get("core_functional_job") or {}).get("job")]
    return {"interviews": len(records), "core_jobs": len(kb.get("core_jobs") or []),
            "unlinked_interviews": len(unlinked), "steps": len(steps),
            "thin_steps": len([s for s in steps if s.get("coverage", 0) < THIN_STEP]),
            "outcomes": len([o for o in outcomes if not o.get("merged_into")]),
            "pending_proposals": len([p for p in proposals if p.get("status") == "pending"]),
            "solutions": len(live_solutions(kb)), "solution_groups": len(groups_of(kb)),
            "themes": len(themes_of(kb)), "overviews": len(overviews_of(kb)),
            "stale": [k for k in DERIVED if isinstance(kb.get(k), dict) and kb[k].get("stale")]}


def agent_name() -> str | None:
    """Best guess at the assistant running the tool: KB_TOOL_AGENT, a known host marker, or the terminal program."""
    given = os.environ.get("KB_TOOL_AGENT", "").strip()
    if given:
        return given
    if os.environ.get("CLAUDECODE"):
        return "claude-code"
    if os.environ.get("GEMINI_CLI"):
        return "gemini-cli"
    return os.environ.get("TERM_PROGRAM", "").strip().lower() or None


class Run:
    """One invocation of the tool, as logs/kb_tool.jsonl records it.

    Commands add facts with note(); main() writes the line when the command ends, however it ends. The line
    holds IDs, counts, codes, hashes and versions. It never holds a quote, a person's name, a transcript file
    name or an absolute path, so the log can be shared for debugging without a data-protection question."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.started = dt.datetime.now().astimezone()
        self.clock = time.monotonic()
        self.kb_path = str(getattr(args, "kb", ""))
        self.folder = os.path.dirname(os.path.abspath(self.kb_path)) if self.kb_path else ""
        self.facts: Json = {"kb_sha256_before": file_sha256(self.kb_path) if self.kb_path else None}
        self.error_codes: dict[str, int] = {}
        self.warning_codes: dict[str, int] = {}

    @property
    def ts(self) -> str:
        return self.started.isoformat(timespec="seconds")

    def stamp(self) -> Json:
        """The fields a changelog entry carries so it can be traced to its log line."""
        return {"ts": self.ts, "run_id": self.id}

    def note(self, **facts: Any) -> None:
        self.facts.update(facts)

    def add_report(self, report: Report) -> None:
        for code, count in report.error_codes.items():
            self.error_codes[code] = self.error_codes.get(code, 0) + count
        for code, count in report.warning_codes.items():
            self.warning_codes[code] = self.warning_codes.get(code, 0) + count

    def fail(self, code: str, count: int = 1) -> None:
        self.error_codes[code] = self.error_codes.get(code, 0) + count

    def relative(self, path: Any) -> str | None:
        """A path as the log may show it: relative to the KB folder, never absolute, never a transcript file."""
        if not path:
            return None
        try:
            return os.path.relpath(os.path.abspath(str(path)), self.folder).replace(os.sep, "/")
        except ValueError:  # another drive on Windows
            return os.path.basename(str(path))

    def public_args(self, args: argparse.Namespace) -> Json:
        """The command-line options worth keeping. Free text (--note, names) and the KB path itself are left out."""
        hidden = {"cmd", "func", "run", "kb", "transcripts", "note", "project", "interviewer"}
        public: Json = {}
        for key, value in sorted(vars(args).items()):
            if key in hidden or value in (None, False):
                continue
            paths = ("patch", "themes", "out", "template", "schema", "to")
            public[key] = self.relative(value) if key in paths else value
        roots = getattr(args, "transcripts", None) or []
        if roots:  # a root that is a single file would name an interviewee; log folders only
            public["transcripts"] = [self.relative(r) if os.path.isdir(r) else "<file>" for r in roots]
        return public

    def line(self, args: argparse.Namespace, code: int) -> Json:
        head: Json = {"run_id": self.id, "ts": self.ts, "duration_ms": int((time.monotonic() - self.clock) * 1000),
                      "command": getattr(args, "cmd", None), "args": self.public_args(args), "exit_code": code,
                      "written": bool(self.facts.get("written")), "tool_version": __version__,
                      "schema_version": SCHEMA_VERSION, "python": platform.python_version(), "os": sys.platform,
                      "agent": agent_name()}
        tail = {"kb_sha256_after": file_sha256(self.kb_path) if self.kb_path else None,
                "kb": kb_summary(self.kb_path) if self.kb_path else None,
                "errors": self.error_codes, "warnings": self.warning_codes}
        return {**head, **{k: v for k, v in self.facts.items() if k != "written"}, **tail}

    def moved(self, kb_path: str) -> None:
        """The KB now lives at kb_path (migrate moved it): the line goes to its new logs/ folder."""
        self.kb_path = kb_path
        self.folder = os.path.dirname(os.path.abspath(kb_path))

    def write(self, args: argparse.Namespace, code: int) -> None:
        """Append the line, only inside a .pw-kb folder. A log that cannot be written never fails the command."""
        if os.environ.get("KB_TOOL_LOG", "").strip() in ("0", "off", "false") or not os.path.isdir(self.folder):
            return
        if os.path.basename(self.folder) != KB_FOLDER:  # e.g. a refused run on a study made by an earlier version
            return
        try:
            folder = os.path.join(self.folder, LOG_FOLDER)
            os.makedirs(folder, exist_ok=True)
            with open(os.path.join(folder, LOG_FILE), "a", encoding="utf-8") as handle:
                handle.write(json.dumps(self.line(args, code), ensure_ascii=False, default=str) + "\n")
        except OSError as exc:  # pragma: no cover - depends on the machine
            print(f"warning: could not write the run log: {exc}", file=sys.stderr)


def changelog_entry(run: Run, action: str, **fields: Any) -> Json:
    """A changelog entry stamped with the run that wrote it."""
    return {"date": today(), "action": action, **run.stamp(), **fields}


# ---------- files ----------
def load_yaml(path: str) -> Any:
    try:
        with open(path, encoding="utf-8") as handle:
            return yaml.safe_load(handle)
    except FileNotFoundError:
        raise KbError(f"file not found: {path}", code="file_missing") from None
    except yaml.YAMLError as exc:
        raise KbError(f"{path} is not valid YAML: {exc}", code="yaml_invalid") from None


class _Dumper(yaml.SafeDumper):
    def ignore_aliases(self, data: Any) -> bool:
        return True


def save_yaml(data: Json, path: str) -> None:
    """Write atomically: dump to a temporary file, reload it, then replace the target."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        yaml.dump(data, handle, Dumper=_Dumper, sort_keys=False, allow_unicode=True, width=110)
    with open(tmp, encoding="utf-8") as handle:
        yaml.safe_load(handle)  # never leave a file in place that will not load
    os.replace(tmp, path)


KB_ORDER = ["meta", "core_jobs", "clusters", "interviews", "job_map", "desired_outcomes", "current_solutions",
            "proposed_changes", "changelog"]


def save_kb(kb: Json, path: str) -> None:
    """Stamp the versions, put the top-level keys in a stable order and write."""
    kb["meta"]["schema_version"] = SCHEMA_VERSION
    kb["meta"]["tool_version"] = __version__
    ordered = {key: kb[key] for key in KB_ORDER if key in kb}
    ordered.update({key: value for key, value in kb.items() if key not in ordered})
    kb.clear()
    kb.update(ordered)
    save_yaml(kb, path)


def backup(kb_path: str, source: str | None = None) -> str:
    """Copy the KB (or `source`, the file it is about to replace) into backups/ next to it, named after the KB.
    Names carry microseconds, so two writes never collide.

    Only the newest KEEP_BACKUPS copies are kept."""
    folder = os.path.join(os.path.dirname(os.path.abspath(kb_path)), "backups")
    os.makedirs(folder, exist_ok=True)
    stem, ext = os.path.splitext(os.path.basename(kb_path))
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target = os.path.join(folder, f"{stem}.{stamp}{ext}")
    counter = 1
    while os.path.exists(target):
        target = os.path.join(folder, f"{stem}.{stamp}-{counter}{ext}")
        counter += 1
    shutil.copy2(source or kb_path, target)
    pattern = re.compile(rf"^{re.escape(stem)}\.\d{{8}}-\d{{6}}-\d{{6}}(-\d+)?{re.escape(ext)}$")
    kept = sorted(name for name in os.listdir(folder) if pattern.match(name))
    for name in kept[:-KEEP_BACKUPS]:
        os.remove(os.path.join(folder, name))
    return target


def skill_file(folder: str, name: str, given: str | None = None) -> str | None:
    """Find a file that ships with the skill: a path given on the command line, a copy next to this script,
    or the skill's own folder (scripts/../<folder>/<name>)."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = ([given] if given else []) + [os.path.join(here, name), os.path.join(here, "..", folder, name)]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


# ---------- where a study lives ----------
def at_home(kb_path: str) -> bool:
    """True when the path is <somewhere>/.pw-kb/pw-kb.yaml, the only place a study lives."""
    absolute = os.path.abspath(kb_path)
    return os.path.basename(absolute) == KB_FILE and os.path.basename(os.path.dirname(absolute)) == KB_FOLDER


def check_home(kb_path: str) -> None:
    """Refuse a KB anywhere but .pw-kb/pw-kb.yaml. One made by an earlier version is moved by migrate."""
    if at_home(kb_path):
        return
    if os.path.isfile(kb_path):
        raise KbError(f"{kb_path} is not where a study lives: the KB is {KB_HOME} at the root of the workspace. "
                      f"If it was made by an earlier version of the skill, run `kb_tool.py migrate {kb_path}` from "
                      "the workspace root to move the study there", code="kb_location")
    raise KbError(f"the KB is {KB_HOME} at the root of the workspace, not {kb_path}", code="kb_location")


def copies_folder(kb_path: str) -> str:
    """.pw-kb/transcripts/: the study's own copy of every transcript the KB cites."""
    return os.path.join(os.path.dirname(os.path.abspath(kb_path)), COPIES)


def git_note(kb_path: str) -> str | None:
    """A line for the user when .pw-kb/ sits in a git repository with no .gitignore of its own, else None."""
    folder = os.path.dirname(os.path.abspath(kb_path))
    if os.path.exists(os.path.join(folder, ".gitignore")):
        return None
    current = folder
    while not os.path.exists(os.path.join(current, ".git")):
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent
    return (f"git: {KB_FOLDER}/ is inside a git repository and has no .gitignore. It holds interviewees' names, "
            "quotes and transcripts, so it is committed only if the user wants to share it through git")


# ---------- text ----------
_CHAR_MAP = [
    ("\u2019", "'"), ("\u2018", "'"), ("\u201c", '"'), ("\u201d", '"'), ("\u201e", '"'),
    ("\u2013", "-"), ("\u2014", "-"), ("\u2010", "-"), ("\u2026", "..."),
    ("\u00a0", " "), ("\u202f", " "), ("\u2009", " "),
    ("\u200b", ""), ("\u200c", ""), ("\u200d", ""), ("\ufeff", ""), ("\u00ad", ""),
]
_LINE_MARKERS = re.compile(r"^[ \t]*(?:>+[ \t]?|[-*+\u2022][ \t]+|#{1,6}[ \t]+)", re.MULTILINE)


def norm(text: str) -> str:
    """Normalize text so a quote and its transcript compare the same way.

    Curly quotes, dashes and ellipses become ASCII, invisible characters go, markdown markers go,
    and runs of whitespace collapse to one space. Both sides of every comparison pass through here."""
    for old, new in _CHAR_MAP:
        text = text.replace(old, new)
    text = _LINE_MARKERS.sub("", text)
    text = re.sub(r"[*_]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def read_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".md", ".markdown", ".txt", ""):
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    if ext == ".docx":
        try:
            import docx  # noqa: PLC0415  (python-docx, optional)
        except ImportError:
            raise KbError(f"{path}: reading .docx needs python-docx "
                          "(uv run --locked --with python-docx==1.2.0 kb_tool.py ... "
                          "or pip install python-docx==1.2.0)",
                          code="reader_missing") from None
        return "\n".join(paragraph.text for paragraph in docx.Document(path).paragraphs)
    if ext == ".pdf":
        try:
            from pypdf import PdfReader  # noqa: PLC0415  (optional)
        except ImportError:
            raise KbError(f"{path}: reading .pdf needs pypdf "
                          "(uv run --locked --with pypdf==6.21.4 kb_tool.py ... or pip install pypdf==6.21.4)",
                          code="reader_missing") from None
        return "\n".join((page.extract_text() or "") for page in PdfReader(path).pages)
    raise KbError(f"unsupported transcript type: {path}", code="transcript_type")


def closest_span(text: str, quote: str) -> str:
    """The span of a normalized transcript that looks most like a quote, so the fix is one edit instead of a search."""
    if not text or not quote:
        return ""
    matcher = difflib.SequenceMatcher(None, text, quote, autojunk=False)
    block = matcher.find_longest_match(0, len(text), 0, len(quote))
    if block.size < max(12, len(quote) // 4):
        return ""
    start = max(0, block.a - block.b)
    return text[start:start + len(quote) + 20]


def short(text: str, limit: int = 80) -> str:
    return text if len(text) <= limit else text[:limit - 1] + "\u2026"


# ---------- transcripts ----------
@dataclass
class Transcript:
    path: str
    text: str  # normalized
    sha256: str  # hash of the raw text, as read from the file


def _transcript_files(root: str) -> list[str] | None:
    """Every transcript file under a folder, or the root itself when it is one file. None when it does not exist."""
    if os.path.isdir(root):
        paths = sorted(glob.glob(os.path.join(glob.escape(root), "**", "*"), recursive=True))
    elif os.path.isfile(root):
        paths = [root]
    else:
        return None
    return [p for p in paths if os.path.isfile(p) and os.path.splitext(p)[1].lower() in TRANSCRIPT_EXTS]


class Transcripts:
    """Finds transcript files and reads each one the first time it is asked for.

    The study's own copies (`own`, .pw-kb/transcripts/) come first: a name found there is always read from there.
    Other names are looked up under the --transcripts roots. Files are keyed by base name, as interview records
    store them. A name that exists in two of those roots is refused, because the tool could not tell which one
    the evidence came from."""

    def __init__(self, roots: list[str], own: str | None = None) -> None:
        self.own: dict[str, str] = {}
        self.index: dict[str, list[str]] = {}
        self.cache: dict[str, Transcript | None] = {}
        self.warnings: list[str] = []
        for path in (_transcript_files(own) or []) if own else []:
            self.own.setdefault(os.path.basename(path), path)
        for root in roots:
            paths = _transcript_files(root)
            if paths is None:
                self.warnings.append(f"--transcripts {root}: no such file or folder")
                continue
            for path in paths:
                self.index.setdefault(os.path.basename(path), []).append(path)

    def has(self, name: str) -> bool:
        base = os.path.basename(name)
        return base in self.own or base in self.index

    def is_copy(self, transcript: Transcript) -> bool:
        """True when the transcript was read from the study's own copies."""
        return self.own.get(os.path.basename(transcript.path)) == transcript.path

    def get(self, name: str) -> Transcript | None:
        base = os.path.basename(name)
        if base in self.cache:
            return self.cache[base]
        paths = [self.own[base]] if base in self.own else self.index.get(base, [])
        if not paths:
            self.cache[base] = None
            return None
        if len(paths) > 1:
            raise KbError(f"transcript '{base}' exists in more than one place: {', '.join(paths)}. "
                          "Keep one copy per file name under --transcripts.", code="transcript_duplicate")
        try:
            raw = read_text(paths[0])
        except KbError:
            raise
        except Exception as exc:
            raise KbError(f"cannot read {paths[0]}: {exc}", code="transcript_unreadable") from None
        self.cache[base] = Transcript(paths[0], norm(raw), hashlib.sha256(raw.encode("utf-8")).hexdigest())
        return self.cache[base]


def transcripts_for(roots: list[str], report: Report, own: str | None = None) -> Transcripts:
    """Index the study's copies and the transcript roots; a root that does not exist becomes a coded warning."""
    transcripts = Transcripts(roots, own)
    for warning in transcripts.warnings:
        report.warn(warning, code="transcripts_root_missing")
    return transcripts


# ---------- KB access ----------
def _guess_version(kb: Json) -> int:
    """A KB written before schema_version existed: schema 1 if it still has the single market core job."""
    steps = (kb.get("job_map") or {}).get("steps") or []
    old = "market_core_job" in kb or any(isinstance(s, dict) and "job" not in s for s in steps)
    return 1 if old else SCHEMA_VERSION


def ensure(kb: Any, label: str = "the KB") -> Json:
    if kb is None:
        kb = {}
    if not isinstance(kb, dict):
        raise KbError(f"{label} is not a YAML mapping", code="kb_shape")
    kb.setdefault("meta", {})
    kb["meta"].setdefault("schema_version", _guess_version(kb))
    kb["meta"].setdefault("generated_with", MADE_WITH)
    kb.setdefault("core_jobs", [])
    kb.setdefault("interviews", [])
    kb.setdefault("job_map", {}).setdefault("steps", [])
    kb.setdefault("desired_outcomes", {}).setdefault("outcomes", [])
    kb.setdefault("proposed_changes", [])
    kb.setdefault("changelog", [])
    return kb


def check_version(kb: Json, path: str) -> int:
    version = kb["meta"].get("schema_version", SCHEMA_VERSION)
    if not isinstance(version, int) or isinstance(version, bool):
        raise KbError(f"{path}: meta.schema_version must be a whole number, found {version!r}", code="schema_version")
    if version > SCHEMA_VERSION:
        raise KbError(f"{path} uses KB schema version {version}, but this tool (v{__version__}) knows version "
                      f"{SCHEMA_VERSION}. Update the distill-kb skill, then try again.", code="schema_version")
    return version


def load_kb(path: str) -> Json:
    check_home(path)
    kb = ensure(load_yaml(path), path)
    version = check_version(kb, path)
    if version < SCHEMA_VERSION:
        raise KbError(f"{path} uses KB schema version {version}; run `kb_tool.py migrate {path}` first",
                      code="migrate_needed")
    return kb


def job_letter(index: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA: the ID of the core job in that position."""
    letters, index = "", index + 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(65 + rest) + letters
    return letters


def job_index(letter: str) -> int:
    index = 0
    for char in letter:
        index = index * 26 + ord(char) - 64
    return index - 1


def job_of(ref: str) -> str:
    """The core job a step ID ("B.2") or outcome ID ("B.2.1") belongs to."""
    return str(ref).split(".")[0]


def step_key(step: Json) -> str:
    return f"{step.get('job', '?')}.{int(step['n'])}"


def step_of(outcome_id: str) -> str:
    return str(outcome_id).rsplit(".", 1)[0]


def jobs_by_id(kb: Json) -> dict[str, Json]:
    return {str(job["id"]): job for job in kb["core_jobs"]}


def next_job_id(kb: Json) -> str:
    return job_letter(max((job_index(str(job["id"])) for job in kb["core_jobs"]), default=-1) + 1)


def steps_by_id(kb: Json) -> dict[str, Json]:
    return {step_key(step): step for step in kb["job_map"]["steps"]}


def next_step_n(kb: Json, job: str) -> int:
    return max((int(s["n"]) for s in kb["job_map"]["steps"] if s.get("job") == job), default=0) + 1


def outcomes_by_id(kb: Json) -> dict[str, Json]:
    return {str(outcome["id"]): outcome for outcome in kb["desired_outcomes"]["outcomes"]}


def interviews_by_file(kb: Json) -> dict[str, Json]:
    return {os.path.basename(str(record.get("file", ""))): record for record in kb["interviews"]}


def id_width(kb: Json) -> int:
    return max([2] + [len(str(record.get("id", ""))) for record in kb["interviews"]])


def next_interview_id(records: list[Json]) -> str:
    numbers = [int(record["id"]) for record in records if str(record.get("id", "")).isdigit()]
    highest = max(numbers) if numbers else 0
    return str(highest + 1).zfill(max(2, len(str(highest))))


def step_sort_key(step_id: str) -> tuple[int, int]:
    job, n = str(step_id).split(".")
    return job_index(job), int(n)


def outcome_sort_key(outcome: Json) -> tuple[int, int, int]:
    return (*step_sort_key(str(outcome["step"])), int(str(outcome["id"]).rsplit(".", 1)[1]))


def next_outcome_id(kb: Json, step_id: str) -> str:
    used = [int(str(o["id"]).rsplit(".", 1)[1]) for o in kb["desired_outcomes"]["outcomes"]
            if str(o["step"]) == step_id]
    return f"{step_id}.{(max(used) if used else 0) + 1}"


def sort_outcomes(kb: Json) -> None:
    kb["desired_outcomes"]["outcomes"].sort(key=outcome_sort_key)


def sort_steps(kb: Json) -> None:
    kb["job_map"]["steps"].sort(key=lambda s: step_sort_key(step_key(s)))


def evidence_key(item: Json) -> tuple[str, str]:
    return str(item.get("interview")), norm(str(item.get("quote", "")))


def add_evidence(target: Json, items: list[Json]) -> int:
    """Append evidence items that are not there yet. Returns how many were added."""
    have = {evidence_key(item) for item in target.setdefault("evidence", [])}
    added = 0
    for item in items:
        key = evidence_key(item)
        if key not in have:
            target["evidence"].append({"interview": item["interview"], "source": item["source"],
                                       "quote": item["quote"]})
            have.add(key)
            added += 1
    return added


def main_job(record: Json) -> str | None:
    """The core job an interview's own core functional job rolls up to, if any."""
    return (record.get("core_functional_job") or {}).get("job")


def unlinked_reason(record: Json) -> str:
    """Why an interview's own core job rolls up to none of the study's core jobs, if it was said."""
    return str((record.get("core_functional_job") or {}).get("unlinked_reason") or "").strip()


def related_links(record: Json) -> list[str]:
    return [str(job["job"]) for job in record.get("related_jobs") or [] if isinstance(job, dict) and job.get("job")]


def _recount_steps(kb: Json, names: dict[str, str]) -> None:
    stamped = []
    for step in kb["job_map"]["steps"]:
        for item in step.get("evidence", []):
            item["name"] = names.get(str(item.get("interview")), item.get("name", ""))
        ids = sorted({str(item.get("interview")) for item in step.get("evidence", [])})
        step["interviews"], step["coverage"] = ids, len(ids)
        rest = {k: v for k, v in step.items() if k not in ("id", "job", "n")}
        stamped.append({"id": step_key(step), "job": step["job"], "n": int(step["n"]), **rest})
    kb["job_map"]["steps"][:] = stamped


def _recount_jobs(kb: Json) -> None:
    quoted: dict[str, set[str]] = {}
    for step in kb["job_map"]["steps"]:
        quoted.setdefault(str(step["job"]), set()).update(step.get("interviews", []))
    for outcome in kb["desired_outcomes"]["outcomes"]:
        if not outcome.get("merged_into"):
            quoted.setdefault(job_of(outcome["step"]), set()).update(outcome.get("interviews", []))
    for job in kb["core_jobs"]:
        jid = str(job["id"])
        main = sorted(str(r["id"]) for r in kb["interviews"] if main_job(r) == jid)
        job["interviews"] = main
        job["related_interviews"] = sorted(str(r["id"]) for r in kb["interviews"]
                                           if jid in related_links(r) and str(r["id"]) not in main)
        job["coverage"] = len(quoted.get(jid, set()))


def recount(kb: Json) -> None:
    """Recompute every derived count, name, step ID and link list. Run after any change."""
    names = {str(record["id"]): record.get("name", "") for record in kb["interviews"]}
    _recount_steps(kb, names)
    for outcome in kb["desired_outcomes"]["outcomes"]:
        for item in outcome.get("evidence", []):
            item["name"] = names.get(str(item.get("interview")), item.get("name", ""))
        ids = sorted({str(item.get("interview")) for item in outcome.get("evidence", [])})
        outcome["interviews"], outcome["interview_count"] = ids, len(ids)
        outcome["quote_count"] = len(outcome.get("evidence", []))
    _recount_jobs(kb)
    _recount_solutions(kb, names)
    _recount_themes(kb, names)
    _recount_overview(kb, names)
    kb["meta"]["interview_count"] = len(kb["interviews"])
    dates = sorted(str(record["date"]) for record in kb["interviews"] if record.get("date"))
    if dates:
        kb["meta"]["date_range"] = f"{dates[0]} to {dates[-1]}"
    for key, cluster in (kb.get("clusters") or {}).items():
        cluster["interviews"] = sorted(str(r["id"]) for r in kb["interviews"] if r.get("cluster") == key)


def mark_stale(kb: Json, reason: str) -> None:
    for key in DERIVED:
        layer = kb.get(key)
        if isinstance(layer, dict):
            layer["stale"] = True
            layer.setdefault("stale_reasons", []).append(f"{today()}: {reason}")


def thin_steps(kb: Json) -> list[Json]:
    return [step for step in kb["job_map"]["steps"] if step.get("coverage", 0) < THIN_STEP]


def stale_layers(kb: Json) -> list[str]:
    return [key for key in DERIVED if isinstance(kb.get(key), dict) and kb[key].get("stale")]


# ---------- current solutions ----------
# What people use today to get a step done. The section is optional and created by the first merge that adds a
# solution, so a KB without solutions stays exactly as it was. Readers are lenient about its shape, because
# recount runs before the structure check reports what is wrong.
def solutions_of(kb: Json) -> list[Json]:
    section = kb.get("current_solutions")
    items = section.get("solutions") if isinstance(section, dict) else None
    return [s for s in items if isinstance(s, dict)] if isinstance(items, list) else []


def live_solutions(kb: Json) -> list[Json]:
    return [s for s in solutions_of(kb) if not s.get("merged_into")]


def groups_of(kb: Json) -> dict[str, Json]:
    section = kb.get("current_solutions")
    groups = section.get("groups") if isinstance(section, dict) else None
    return {str(k): v for k, v in groups.items() if isinstance(v, dict)} if isinstance(groups, dict) else {}


def solution_section(kb: Json) -> Json:
    """The current_solutions section, created when the first solution or group arrives."""
    section = kb.setdefault("current_solutions", {})
    section.setdefault("groups", {})
    section.setdefault("solutions", [])
    return section


def solutions_by_id(kb: Json) -> dict[str, Json]:
    return {str(s.get("id")): s for s in solutions_of(kb)}


def next_solution_id(kb: Json) -> str:
    numbers = [int(str(s["id"])[1:]) for s in solutions_of(kb) if SOLUTION_ID.match(str(s.get("id", "")))]
    return f"S{max(numbers, default=0) + 1}"


def uses_of(solution: Json) -> list[Json]:
    uses = solution.get("uses")
    return [u for u in uses if isinstance(u, dict)] if isinstance(uses, list) else []


def use_status(use: Json) -> str:
    return str(use.get("status") or "current")


def _step_order(step: Any) -> tuple[int, int]:
    return step_sort_key(str(step)) if STEP_ID.match(str(step)) else (10 ** 6, 0)


def add_use(solution: Json, step: str, status: str, evidence: list[Json]) -> int:
    """Add quotes to the solution's use at a step, with that status, creating the use if needed. Returns how many
    quotes were new."""
    use = next((u for u in uses_of(solution) if str(u.get("step")) == step and use_status(u) == status), None)
    if use is None:
        use = {"step": step, "status": status, "evidence": []}
        solution.setdefault("uses", []).append(use)
    return add_evidence(use, evidence)


def folded_uses(solution: Json) -> list[Json]:
    """The solution's uses with any two for the same step and status folded into one, in step order."""
    folded: dict[tuple[str, str], Json] = {}
    for use in uses_of(solution):
        key = (str(use.get("step")), use_status(use))
        if key not in folded:
            folded[key] = {"step": key[0], "status": key[1], "evidence": []}
        add_evidence(folded[key], [e for e in use.get("evidence") or [] if isinstance(e, dict)])
    return sorted(folded.values(), key=lambda u: (_step_order(u["step"]), u["status"] != "current"))


def solution_steps(solution: Json) -> list[str]:
    return sorted({str(u.get("step")) for u in uses_of(solution)}, key=_step_order)


def known_names(obj: Json) -> set[str]:
    """A solution's or group's name and every earlier name in its history, normalized for comparison."""
    earlier = [h for h in obj.get("history") or [] if isinstance(h, dict) and h.get("was")]
    return {norm(str(obj.get("name", ""))).lower()} | {norm(str(h["was"])).lower() for h in earlier}


def _known_whys(group: Json) -> set[str]:
    earlier = [h for h in group.get("history") or [] if isinstance(h, dict) and h.get("was_why")]
    return {norm(str(group.get("why", "")))} | {norm(str(h["was_why"])) for h in earlier}


def _recount_solutions(kb: Json, names: dict[str, str]) -> None:
    """Who uses each solution now, who stopped, how many different quotes mention it, and each group's members."""
    solutions = solutions_of(kb)
    for solution in solutions:
        current: set[str] = set()
        stopped: set[str] = set()
        quotes: set[tuple[str, str]] = set()
        for use in uses_of(solution):
            for item in [e for e in use.get("evidence") or [] if isinstance(e, dict)]:
                item["name"] = names.get(str(item.get("interview")), item.get("name", ""))
                quotes.add(evidence_key(item))
                (current if use_status(use) == "current" else stopped).add(str(item.get("interview")))
        solution["interviews"], solution["stopped_by"] = sorted(current), sorted(stopped - current)
        solution["quote_count"] = len(quotes)
    for key, group in groups_of(kb).items():
        group["solutions"] = [str(s.get("id")) for s in solutions if s.get("group") == key and not s.get("merged_into")]


def _solution_problems(kb: Json, steps: dict[str, Json]) -> list[str]:
    """Cross-references of the current_solutions section that the schema cannot express."""
    solutions, groups, by_id = solutions_of(kb), groups_of(kb), solutions_by_id(kb)
    problems = [f"solution id {dup} is used more than once"
                for dup in _duplicates([str(s.get("id")) for s in solutions])]
    for solution in solutions:
        sid, target = solution.get("id"), solution.get("merged_into")
        if str(solution.get("group")) not in groups:
            problems.append(f"solution {sid}: group {solution.get('group')} does not exist")
        if target and (str(target) not in by_id or str(target) == str(sid)):
            problems.append(f"solution {sid}: merged_into {target} does not exist")
        if target and uses_of(solution):
            problems.append(f"solution {sid} was merged into {target} but still has uses; move them to {target}")
        for use in uses_of(solution):
            if str(use.get("step")) not in steps:
                problems.append(f"solution {sid}: step {use.get('step')} does not exist")
        pairs = [f"{u.get('step')} ({use_status(u)})" for u in uses_of(solution)]
        problems += [f"solution {sid}: two uses for step {dup}; fold them into one" for dup in _duplicates(pairs)]
    return problems


def _rename_use_refs(kb: Json, renamed: dict[str, str]) -> None:
    """Point solution uses at a step's new ID after the step moved."""
    for solution in solutions_of(kb):
        if any(str(u.get("step")) in renamed for u in uses_of(solution)):
            for use in uses_of(solution):
                use["step"] = renamed.get(str(use.get("step")), use.get("step"))
            solution["uses"] = folded_uses(solution)


# ---------- value themes ----------
# A value theme is a need in the customer's words that gathers the outcomes serving one judgment, across job steps.
# `themes` writes the layer, one core job at a time. A theme with no ID was written by hand before that command
# existed: it is kept as it is, never counted and never checked, until `themes` replaces it.
def themes_of(kb: Json, job: str | None = None) -> list[Json]:
    layer = kb.get("value_themes")
    items = layer.get("themes") if isinstance(layer, dict) else None
    found = [t for t in items if isinstance(t, dict) and THEME_ID.match(str(t.get("id", "")))] \
        if isinstance(items, list) else []
    return [t for t in found if job is None or str(t.get("job")) == job]


def theme_outcomes(theme: Json) -> list[str]:
    items = theme.get("outcomes")
    return [str(o) for o in items] if isinstance(items, list) else []


def theme_number(theme: Json) -> int:
    return int(str(theme["id"]).rsplit("T", 1)[1])


def unassigned_outcomes(kb: Json) -> list[str]:
    """Live outcomes that sit in no theme, for the core jobs that have themes."""
    themes = themes_of(kb)
    jobs = {str(t.get("job")) for t in themes}
    used = {o for t in themes for o in theme_outcomes(t)}
    return [str(o["id"]) for o in kb["desired_outcomes"]["outcomes"]
            if not o.get("merged_into") and job_of(o.get("step", "")) in jobs and str(o["id"]) not in used]


def _recount_themes(kb: Json, names: dict[str, str]) -> None:
    themes, layer = themes_of(kb), kb.get("value_themes")
    if not themes:
        if isinstance(layer, dict):
            layer.pop("unassigned", None)
        return
    outcomes = outcomes_by_id(kb)
    for theme in themes:
        members = [outcomes[o] for o in theme_outcomes(theme) if o in outcomes]
        ids = sorted({i for o in members for i in o.get("interviews", [])})
        theme["interviews"], theme["interview_count"] = ids, len(ids)
        theme["quote_count"] = sum(o.get("quote_count", 0) for o in members)
        for item in theme.get("highlights") or []:
            if isinstance(item, dict):
                item["name"] = names.get(str(item.get("interview")), item.get("name", ""))
    layer["unassigned"] = unassigned_outcomes(kb)


def _rename_theme_refs(kb: Json, renamed: dict[str, str]) -> None:
    """Point themes at an outcome's new ID after it moved or was merged. An outcome that left the theme's core job
    leaves the theme."""
    for theme in themes_of(kb):
        moved = dict.fromkeys(renamed.get(o, o) for o in theme_outcomes(theme))
        theme["outcomes"] = [o for o in moved if job_of(o) == str(theme.get("job"))]


def _theme_problems(kb: Json, jobs: dict[str, Json], outcomes: dict[str, Json]) -> list[str]:
    """Cross-references of the value_themes layer that the schema cannot express."""
    themes = themes_of(kb)
    problems = [f"value theme id {dup} is used more than once" for dup in _duplicates([str(t["id"]) for t in themes])]
    for theme in themes:
        tid, job = str(theme["id"]), str(theme.get("job"))
        if job not in jobs:
            problems.append(f"value theme {tid}: core job {job} does not exist")
        if job_of(tid) != job:
            problems.append(f"value theme {tid}: its ID does not match core job {job}")
        problems += [f"value theme {tid}: {key} is missing" for key in ("label", "need")
                     if not str(theme.get(key) or "").strip()]
        for oid in theme_outcomes(theme):
            problems += _theme_link_problems(tid, job, oid, outcomes)
    return problems


def _theme_link_problems(tid: str, job: str, oid: str, outcomes: dict[str, Json]) -> list[str]:
    target = outcomes.get(oid)
    if not target:
        return [f"value theme {tid}: outcome {oid} does not exist"]
    if target.get("merged_into"):
        return [f"value theme {tid}: outcome {oid} was merged into {target['merged_into']}; use that one"]
    if job_of(oid) != job:
        return [f"value theme {tid}: outcome {oid} belongs to core job {job_of(oid)}, not {job}"]
    return []


# ---------- schema ----------
_SCHEMA_ANNOTATIONS = {"$schema", "$id", "$comment", "title", "description", "examples", "default", "$defs"}
_SCHEMA_KEYWORDS = {"$ref", "type", "enum", "required", "properties", "items", "pattern",
                    "minLength", "minimum", "minItems", "additionalProperties"}
_TYPE_NAMES = {dict: "mapping", list: "list", str: "string", bool: "boolean", int: "integer",
               float: "number", type(None): "null"}


def load_schema(name: str, given: str | None = None) -> Json:
    path = skill_file("references", name, given)
    if not path:
        raise KbError(f"{name} not found: keep it next to kb_tool.py, or run the kb_tool.py that sits in the skill's "
                      "scripts/ folder", code="skill_file_missing")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _quote_hint(value: Any, expected: list[str]) -> str:
    if "string" in expected and isinstance(value, float):
        return f' (an ID must be written in quotes, like "{value}")'
    if "string" in expected and isinstance(value, int) and not isinstance(value, bool):
        return f' (write it in quotes, like "{value:02d}")'
    return ""


def schema_errors(data: Any, schema: Json, root: str = "kb") -> list[str]:
    """Check data against a JSON Schema and return readable problems, at most MAX_PROBLEMS.

    Uses the jsonschema package when it is installed. Otherwise a built-in checker covers the keywords our
    schemas use and refuses any other keyword, so a new keyword can never pass unchecked."""
    plain = json.loads(json.dumps(data, default=str))  # YAML dates become strings, as in the schema
    if _jsonschema is not None:
        return _library_schema_errors(plain, schema, root)
    return _builtin_schema_errors(plain, schema, root)


def _path_text(root: str, parts: Any) -> str:
    out = root
    for part in parts:
        out += f"[{part}]" if isinstance(part, int) else f".{part}"
    return out


def _library_message(err: Any) -> str:
    """Say it the way the built-in checker does, so the output does not depend on what is installed."""
    value = err.validator_value
    if err.validator == "type":
        names = value if isinstance(value, list) else [value]
        found = _TYPE_NAMES.get(type(err.instance), type(err.instance).__name__)
        return f"expected {' or '.join(names)}, found {found}{_quote_hint(err.instance, names)}"
    if err.validator == "required":
        match = re.match(r"^'(.+)' is a required property$", err.message)
        return f"missing '{match.group(1)}'" if match else err.message
    if err.validator == "minItems":
        return f"needs at least {value} item(s)"
    if err.validator == "minLength":
        return "must not be empty"
    if err.validator == "enum":
        return f"{err.instance!r} is not one of {value}"
    if err.validator == "pattern":
        return f"'{short(str(err.instance), 60)}' does not match {value}"
    if err.validator == "minimum":
        return f"{err.instance} is below {value}"
    return str(err.message)


def _library_schema_errors(data: Any, schema: Json, root: str) -> list[str]:
    validator = _jsonschema.Draft202012Validator(schema)
    found = sorted(validator.iter_errors(data), key=lambda err: [str(p) for p in err.absolute_path])
    return [f"{_path_text(root, err.absolute_path)}: {_library_message(err)}" for err in found[:MAX_PROBLEMS]]


def _type_ok(value: Any, name: str) -> bool:
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "boolean":
        return isinstance(value, bool)
    return isinstance(value, {"object": dict, "array": list, "string": str, "null": type(None)}[name])


class _SchemaChecker:
    """Built-in JSON Schema checker for the keywords our schemas use. Any other keyword raises."""

    def __init__(self, schema: Json) -> None:
        self.defs = schema.get("$defs", {})
        self.errors: list[str] = []

    def resolve(self, sub: Json) -> Json:
        while "$ref" in sub:
            ref = sub["$ref"]
            if not ref.startswith("#/$defs/"):
                raise KbError(f"schema: the built-in checker only follows #/$defs/ references, not {ref}",
                              code="schema_unsupported")
            sub = self.defs[ref.split("/")[-1]]
        return sub

    def check(self, value: Any, sub: Json, path: str) -> None:
        if len(self.errors) >= MAX_PROBLEMS:
            return
        sub = self.resolve(sub)
        unknown = set(sub) - _SCHEMA_KEYWORDS - _SCHEMA_ANNOTATIONS
        if unknown:
            raise KbError(f"schema keyword(s) {sorted(unknown)} at {path} are not supported by the built-in checker; "
                          "install the jsonschema package or use only the supported keywords",
                          code="schema_unsupported")
        expected = sub.get("type")
        names = (expected if isinstance(expected, list) else [expected]) if expected else []
        if names and not any(_type_ok(value, name) for name in names):
            found = _TYPE_NAMES.get(type(value), type(value).__name__)
            self.errors.append(f"{path}: expected {' or '.join(names)}, found {found}{_quote_hint(value, names)}")
            return
        if "enum" in sub and value not in sub["enum"]:
            self.errors.append(f"{path}: {value!r} is not one of {sub['enum']}")
        if isinstance(value, str):
            self.check_string(value, sub, path)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            if value < sub.get("minimum", value):
                self.errors.append(f"{path}: {value} is below {sub['minimum']}")
        elif isinstance(value, dict):
            self.check_mapping(value, sub, path)
        elif isinstance(value, list):
            self.check_list(value, sub, path)

    def check_string(self, value: str, sub: Json, path: str) -> None:
        if len(value) < sub.get("minLength", 0):
            self.errors.append(f"{path}: must not be empty")
        if "pattern" in sub and not re.search(sub["pattern"], value):
            self.errors.append(f"{path}: '{short(value, 60)}' does not match {sub['pattern']}")

    def check_mapping(self, value: Json, sub: Json, path: str) -> None:
        for key in sub.get("required", []):
            if key not in value:
                self.errors.append(f"{path}: missing '{key}'")
        props, extra = sub.get("properties", {}), sub.get("additionalProperties")
        for key, item in value.items():
            if key in props:
                self.check(item, props[key], f"{path}.{key}")
            elif isinstance(extra, dict):
                self.check(item, extra, f"{path}.{key}")
            elif extra is False:
                self.errors.append(f"{path}: unexpected field '{key}'")

    def check_list(self, value: list[Any], sub: Json, path: str) -> None:
        if len(value) < sub.get("minItems", 0):
            self.errors.append(f"{path}: needs at least {sub['minItems']} item(s)")
        if "items" in sub:
            for index, item in enumerate(value):
                self.check(item, sub["items"], f"{path}[{index}]")


def _builtin_schema_errors(data: Any, schema: Json, root: str) -> list[str]:
    checker = _SchemaChecker(schema)
    checker.check(data, schema, root)
    return checker.errors


def _duplicates(values: list[str]) -> list[str]:
    return sorted({v for v in values if values.count(v) > 1})


def _link_problems(kb: Json, jobs: dict[str, Json]) -> list[str]:
    problems = []
    for record in kb["interviews"]:
        for link in ([main_job(record)] if main_job(record) else []) + related_links(record):
            if link not in jobs:
                problems.append(f"interview {record['id']}: core job {link} does not exist")
        if main_job(record) and unlinked_reason(record):
            problems.append(f"interview {record['id']}: core_functional_job has both a core job and an "
                            "unlinked_reason; keep one")
    return problems


def structure_problems(kb: Json, schema_path: str | None = None) -> list[str]:
    """Schema check plus the cross-references a schema cannot express."""
    problems = schema_errors(kb, load_schema("kb-schema.json", schema_path))
    if problems:
        return problems
    jobs = jobs_by_id(kb)
    job_ids = [str(j["id"]) for j in kb["core_jobs"]]
    problems += [f"core job id {dup} is used more than once" for dup in _duplicates(job_ids)]
    keys = [step_key(s) for s in kb["job_map"]["steps"]]
    problems += [f"step {dup} is used more than once" for dup in _duplicates(keys)]
    for step in kb["job_map"]["steps"]:
        if step["job"] not in jobs:
            problems.append(f"step {step_key(step)}: core job {step['job']} does not exist")
        if step.get("id") and step["id"] != step_key(step):
            problems.append(f"step {step['id']}: its id does not match job {step['job']} and number {step['n']}")
    steps, outcomes = steps_by_id(kb), outcomes_by_id(kb)
    problems += [f"outcome id {dup} is used more than once"
                 for dup in _duplicates([str(o["id"]) for o in kb["desired_outcomes"]["outcomes"]])]
    for outcome in kb["desired_outcomes"]["outcomes"]:
        if str(outcome["step"]) not in steps:
            problems.append(f"outcome {outcome['id']}: step {outcome['step']} does not exist")
        if step_of(outcome["id"]) != str(outcome["step"]):
            problems.append(f"outcome {outcome['id']}: its ID does not match step {outcome['step']}")
        target = outcome.get("merged_into")
        if target and target not in outcomes:
            problems.append(f"outcome {outcome['id']}: merged_into {target} does not exist")
    iv_ids = [str(r["id"]) for r in kb["interviews"]]
    problems += [f"interview id {dup} is used more than once" for dup in _duplicates(iv_ids)]
    return problems + _link_problems(kb, jobs) + _solution_problems(kb, steps) + _theme_problems(kb, jobs, outcomes) \
        + _overview_problems(kb, jobs)


# ---------- clarity ----------
BANNED_NAMES = {"(": "brackets", ";": "a semicolon", "e.g.": "an example", "i.e.": "an aside",
                " and/or ": "and/or", "/": "a slash"}


@dataclass
class Style:
    """Writing rules the merge enforces. A study can override any of them in meta.style."""

    limits: dict[str, int] = field(default_factory=lambda: {
        "executor": 16, "job": 10, "step": 10, "outcome": 16, "feeling": 12, "rationale": 30,
        "solution": 6, "group": 6, "theme": 6, "need": 25,
        "headline": 20, "finding": 50, "action": 20})
    banned: list[str] = field(default_factory=lambda: list(BANNED_NAMES))
    idioms: list[str] = field(default_factory=lambda: ["bread and butter", "in and out"])
    acronyms: list[str] = field(default_factory=lambda: ["OTR", "US", "UK", "EU"])


def style_of(kb: Json) -> Style:
    style = Style()
    given = kb["meta"].get("style") or {}
    if not isinstance(given, dict):
        raise KbError("meta.style must be a mapping with any of: limits, banned, idioms, acronyms",
                      code="style_invalid")
    limits = given.get("limits") or {}
    if not isinstance(limits, dict):
        raise KbError("meta.style.limits must be a mapping such as {outcome: 16}", code="style_invalid")
    style.limits.update({str(k): int(v) for k, v in limits.items()})
    for name in ("banned", "idioms", "acronyms"):
        if name in given:
            if not isinstance(given[name], list):
                raise KbError(f"meta.style.{name} must be a list", code="style_invalid")
            setattr(style, name, [str(x) for x in given[name]])
    return style


def clarity(text: str, kind: str, label: str, style: Style, report: Report) -> None:
    """Reviewers read these statements cold. Keep each one short, single-idea and free of asides."""
    statement = (text or "").strip()
    words = len(statement.split())
    limit = style.limits.get(kind)
    if limit and words > limit:
        report.error(f"clarity: {label} has {words} words (max {limit} for this kind of statement): '{statement}'",
                     code="clarity_length")
    for token in style.banned:
        if token in statement:
            what = BANNED_NAMES.get(token, f"'{token.strip()}'")
            report.error(f"clarity: {label} contains {what}; move detail into evidence or tags: '{statement}'",
                         code="clarity_banned")
    if re.search(r"\betc\b", statement):
        report.error(f"clarity: {label} ends a list with etc.; name the items or drop the list: '{statement}'",
                     code="clarity_etc")
    if kind in ("job", "step") and re.search(r"\b(and|or)\b", statement) \
            and not any(idiom in statement for idiom in style.idioms):
        report.warn(f"clarity: {label} may hold two jobs ('and'/'or'): '{statement}'", code="clarity_two_jobs")
    found = re.findall(r"\b[A-Z]{2,}\b", statement) if kind != "solution" else []  # product names keep their letters
    acronyms = [w for w in found if w not in style.acronyms]
    if acronyms:
        report.warn(f"clarity: {label} uses {', '.join(acronyms)}; spell out unless every reviewer knows it",
                    code="clarity_acronym")


# ---------- evidence ----------
Lookup = Callable[[str], "tuple[str | None, str | None]"]


class QuoteChecker:
    """Checks that every evidence quote appears word for word in its interview's transcript.

    `lookup(reference)` returns (normalized transcript text, None) or (None, why it is missing)."""

    def __init__(self, lookup: Lookup) -> None:
        self.lookup = lookup

    def check(self, items: list[Json], label: str, report: Report) -> None:
        if not items:
            report.error(f"{label}: needs at least one evidence item", code="evidence_missing")
            return
        for item in items:
            if not isinstance(item, dict):
                report.error(f"{label}: each evidence item must be a mapping with interview, source and quote",
                             code="evidence_shape")
                continue
            if item.get("source") not in SOURCES:
                report.error(f"{label}: source must be one of {list(SOURCES)}", code="source_invalid")
            reference = str(item.get("interview"))
            quote = str(item.get("quote") or "")
            text, problem = self.lookup(reference)
            if text is None:
                report.error(f"{label}: {problem}", code="interview_unresolved")
            elif not quote.strip():
                report.error(f"{label}: empty quote", code="quote_empty")
            elif norm(quote) not in text:
                hint = closest_span(text, norm(quote))
                report.error(f'{label}: quote not found word for word in interview {reference}: "{short(quote)}"'
                             + (f'; closest span in the transcript: "{hint}"' if hint else ""), code="quote_not_found")


# ---------- merge: load and resolve ----------
def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def schema_names(node: Any, names: set[str] | None = None) -> set[str]:
    """Every property name a JSON Schema defines, at any depth."""
    names = set() if names is None else names
    if isinstance(node, dict):
        for key, value in (node.get("properties") or {}).items():
            names.add(key)
            schema_names(value, names)
        for value in [node.get("items"), node.get("additionalProperties"), *(node.get("$defs") or {}).values()]:
            schema_names(value, names)
    return names


class _PatchReader:
    """Reads YAML values the way the patch writer meant them. Remembers the interview IDs it had to pad, and the keys
    with no value that the patch format does not have: what YAML makes of an unquoted comma in `{a: x, y}`."""

    def __init__(self, width: int, known: set[str] | None = None) -> None:
        self.width = width
        self.fixed: set[str] = set()
        self.known = known or set()
        self.split: list[str] = []

    def pad(self, value: Any) -> Any:
        if not _is_int(value):
            return value
        self.fixed.add(str(value).zfill(self.width))
        return str(value).zfill(self.width)

    def walk(self, node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                self.walk(item)
            return
        if not isinstance(node, dict):
            return
        for key, value in list(node.items()):
            if value is None and str(key) not in self.known:
                self.split.append(str(key))
            if isinstance(value, (dt.date, dt.datetime)):
                node[key] = value.isoformat()
            elif key == "interview":
                node[key] = self.pad(value)
            elif key == "interviews" and isinstance(value, list):
                node[key] = [self.pad(v) for v in value]
                self.walk(node[key])
            else:
                self.walk(value)


def coerce_patch(patch: Any, width: int, report: Report) -> Json:
    """Read the YAML the way the writer meant it: dates become strings and a bare interview number
    becomes a zero-padded ID, with a warning. Outcome IDs are never coerced, because 2.10 would become 2.1."""
    if patch is None:
        raise KbError("the patch file is empty", code="patch_empty")
    if not isinstance(patch, dict):
        raise KbError(f"the patch must be a YAML mapping with keys such as {', '.join(PATCH_SECTIONS)}",
                      code="patch_shape")
    reader = _PatchReader(width, schema_names(load_schema("patch-schema.json")) | set(PATCH_KEYS))
    reader.walk(patch)
    for proposal in patch.get("proposed_changes") or []:
        if isinstance(proposal, dict) and proposal.get("type") == "relink_interview":
            proposal["target"] = reader.pad(proposal.get("target"))
    if reader.split:
        names = ", ".join(f"'{short(key, 40)}'" for key in reader.split[:5])
        report.error(f"patch: {names} has no value and is not a field of the patch format. YAML does this when a "
                     'value with a comma is not in quotes: {covers: Pick lanes, regions} becomes covers "Pick lanes" '
                     'plus a key "regions". Put quotes around every value that holds a comma',
                     code="yaml_split")
    if reader.fixed:
        report.warn(f"interview IDs were not quoted and were read as {sorted(reader.fixed)}; write IDs in quotes, "
                    'like "01"', code="ids_unquoted")
    unknown = sorted(set(patch) - set(PATCH_KEYS))
    if unknown:
        report.warn(f"unknown top-level key(s) {unknown} are ignored; a patch uses {list(PATCH_KEYS)}",
                    code="unknown_key")
    return patch


def upgrade_bootstrap(patch: Json, report: Report) -> None:
    """The bootstrap of schema 1 had one market_core_job and its steps. Read it as core job A."""
    boot = patch.get("bootstrap")
    if not isinstance(boot, dict):
        return
    old = "market_core_job" in boot or "steps" in boot
    if "core_jobs" in boot:
        if old:
            report.error("patch format: patch.bootstrap: give core_jobs, not market_core_job and steps as well "
                         "(see references/patch-format.md)", code="patch_format")
        return
    if "market_core_job" in boot and "steps" in boot:
        patch["bootstrap"] = {"core_jobs": [{"id": "A", **boot["market_core_job"], "steps": boot["steps"]}]}
        report.warn("bootstrap uses the older market_core_job form; read as core job A", code="ref_legacy")
        return
    report.error("patch format: patch.bootstrap: missing 'core_jobs' (see references/patch-format.md)",
                 code="patch_format")


class JobRefs:
    """Turns step and outcome IDs without a job letter ("6", "6.3") into full IDs ("A.6", "A.6.3").

    That is safe only when the KB has exactly one core job. With several, a bare ID is refused."""

    def __init__(self, kb: Json, patch: Json, report: Report) -> None:
        boot = patch.get("bootstrap") or {}
        self.jobs = [str(j["id"]) for j in kb["core_jobs"]] or [str(j.get("id")) for j in boot.get("core_jobs", [])]
        self.only = self.jobs[0] if len(self.jobs) == 1 else None
        self.report = report
        self.read: list[str] = []

    def _bare(self, value: str, kind: str, where: str) -> str:
        if self.only:
            self.read.append(f"{value} -> {self.only}.{value}")
            return f"{self.only}.{value}"
        example = f"{self.jobs[0] if self.jobs else 'A'}.{value}"
        self.report.error(f"{where}: {kind} {value} has no job letter; write it with the letter of its core job, "
                          f'like "{example}"', code="ref_ambiguous")
        return value

    def step(self, value: Any, where: str) -> Any:
        if _is_int(value) or (isinstance(value, str) and value.isdigit()):
            return self._bare(str(int(value)), "step", where)
        return value

    def outcome(self, value: Any, where: str) -> Any:
        if isinstance(value, str) and BARE_OUTCOME_ID.match(value):
            return self._bare(value, "outcome", where)
        return value

    def job(self, proposal: Json, key: str) -> None:
        """A proposal that must name a core job may leave it out while the KB has only one."""
        if self.only and not proposal.get(key):
            proposal[key] = self.only


def resolve_job_refs(kb: Json, patch: Json, report: Report) -> None:
    """Give every step and outcome reference in the patch its job letter, or refuse the ones that need it."""
    upgrade_bootstrap(patch, report)
    refs = JobRefs(kb, patch, report)
    for index, item in enumerate(patch.get("step_evidence", [])):
        item["step"] = refs.step(item["step"], f"step_evidence[{index}]")
    for index, item in enumerate(patch.get("new_outcomes", [])):
        item["step"] = refs.step(item["step"], f"new_outcomes[{index}]")
    for index, item in enumerate(patch.get("outcome_evidence", [])):
        item["outcome"] = refs.outcome(item["outcome"], f"outcome_evidence[{index}]")
    for index, proposal in enumerate(patch.get("proposed_changes", [])):
        kind, where = proposal.get("type"), f"proposal {index + 1} ({proposal.get('type')})"
        if kind in ("reword_step", "move_step"):
            proposal["target"] = refs.step(proposal.get("target"), where)
        elif kind in ("reword_outcome", "merge_outcomes", "move_outcome"):
            proposal["target"] = refs.outcome(proposal.get("target"), where)
        if kind == "merge_outcomes":
            proposal["merge"] = refs.outcome(proposal.get("merge"), where)
        if kind == "move_outcome":
            proposal["to_step"] = refs.step(proposal.get("to_step"), where)
        if kind == "new_step":
            refs.job(proposal, "job")
        if kind in ("reword_core_job", "confirm_core_job"):
            refs.job(proposal, "target")
    _resolve_solution_refs(refs, patch)
    if refs.read:
        report.warn(f"IDs without a job letter were read as job {refs.only}: {', '.join(refs.read[:8])}; "
                    f'write the letter, like "{refs.only}.6" and "{refs.only}.6.3"', code="ref_legacy")


def _resolve_solution_refs(refs: JobRefs, patch: Json) -> None:
    for index, item in enumerate(patch.get("solution_evidence", [])):
        item["step"] = refs.step(item["step"], f"solution_evidence[{index}]")
    for index, item in enumerate(patch.get("new_solutions", [])):
        for number, use in enumerate(item.get("uses", [])):
            use["step"] = refs.step(use["step"], f"new_solutions[{index}].uses[{number}]")


@dataclass
class MergePlan:
    """What a patch resolves to against the current KB."""

    new_interviews: list[Json] = field(default_factory=list)
    keymap: dict[str, str] = field(default_factory=dict)  # patch key or KB id -> KB id
    skipped: dict[str, str] = field(default_factory=dict)  # patch key -> why it was skipped
    texts: dict[str, str | None] = field(default_factory=dict)  # KB id -> normalized transcript
    copies: list[str] = field(default_factory=list)  # new transcripts to copy into .pw-kb/transcripts/
    bootstrap: Json | None = None
    dropped: int = 0


def _wordings(obj: Json) -> set[str]:
    """The current statement plus every earlier one kept in history, normalized."""
    return {norm(str(obj.get("statement", "")))} | {norm(str(h.get("was", ""))) for h in obj.get("history", [])}


def resolve_bootstrap(kb: Json, patch: Json, plan: MergePlan, report: Report) -> None:
    """A bootstrap only applies to an empty KB. The same bootstrap merged again is ignored, so a batch can be re-run."""
    bootstrap = patch.get("bootstrap")
    if not bootstrap:
        return
    if not (kb["job_map"]["steps"] or kb["core_jobs"]):
        plan.bootstrap = bootstrap
        return
    jobs, steps = jobs_by_id(kb), steps_by_id(kb)
    known = all(str(job["id"]) in jobs and norm(job["statement"]) in _wordings(jobs[str(job["id"])])
                and all(f"{job['id']}.{int(s['n'])}" in steps
                        and norm(s["statement"]) in _wordings(steps[f"{job['id']}.{int(s['n'])}"])
                        for s in job["steps"])
                for job in bootstrap["core_jobs"])
    if known:
        report.warn("bootstrap already applied to this KB; ignored", code="bootstrap_repeated")
        patch.pop("bootstrap")
    else:
        report.error("bootstrap given but the KB already has a core job or job map; use proposed_changes",
                     code="bootstrap_conflict")


def resolve_interviews(kb: Json, patch: Json, transcripts: Transcripts, report: Report) -> MergePlan:
    """Give every new interview an ID, skip the ones the KB already holds, and drop evidence that only
    came from skipped interviews."""
    plan = MergePlan()
    resolve_bootstrap(kb, patch, plan, report)
    by_file = interviews_by_file(kb)
    known_hashes = {record["sha256"] for record in kb["interviews"] if record.get("sha256")}
    for record in kb["interviews"]:  # backfill hashes written by older versions, so renamed copies are caught
        if not record.get("sha256"):
            transcript = transcripts.get(str(record.get("file", "")))
            if transcript:
                record["sha256"] = transcript.sha256
                known_hashes.add(transcript.sha256)
    plan.keymap = {str(record["id"]): str(record["id"]) for record in kb["interviews"]}
    seen_keys: set[str] = set()
    for interview in patch.get("interviews", []):
        key, name = str(interview.get("key")), os.path.basename(str(interview.get("file", "")))
        if key in seen_keys:
            report.error(f"interview key '{key}' is used twice in the patch", code="key_duplicate")
        seen_keys.add(key)
        if key in plan.keymap:
            report.error(f"interview key '{key}' is already an interview ID in the KB; use a key such as n1",
                         code="key_is_id")
            continue
        if not transcripts.has(name):
            report.error(f"interview {key}: file '{name}' not found in {KB_FOLDER}/{COPIES}/ or under --transcripts",
                         code="transcript_missing")
            continue
        transcript = transcripts.get(name)
        if name in by_file:
            plan.skipped[key] = f"already in the KB as interview {by_file[name].get('id')}"
        elif transcript and transcript.sha256 in known_hashes:
            plan.skipped[key] = "already in the KB under another file name (same content)"
        if key in plan.skipped:
            report.warn(f"skip {name}: {plan.skipped[key]}", code="interview_skipped")
            continue
        new_id = next_interview_id(kb["interviews"] + plan.new_interviews)
        plan.keymap[key] = new_id
        plan.texts[new_id] = transcript.text if transcript else None
        record = {"id": new_id}
        record.update({k: v for k, v in interview.items() if k != "key"})
        record["file"] = f"{COPIES}/{name}"  # the study's own copy, made when the merge is written
        record["sha256"] = transcript.sha256 if transcript else ""
        record["added"] = today()
        plan.new_interviews.append(record)
        if transcript and not transcripts.is_copy(transcript):
            plan.copies.append(transcript.path)
    _drop_skipped_evidence(patch, plan, report)
    return plan


def _live(evidence: Any, skipped: dict[str, str]) -> Any:
    if not isinstance(evidence, list):
        return evidence
    return [e for e in evidence if not (isinstance(e, dict) and str(e.get("interview")) in skipped)]


def _evidence_holders(item: Json) -> list[Json]:
    """The item itself, a new core job's steps and a new solution's uses: everything in a patch item that can
    hold evidence."""
    return [item] + [h for key in ("steps", "uses") for h in item.get(key) or [] if isinstance(h, dict)]


def _keep_item(item: Json, skipped: dict[str, str]) -> bool:
    """Trim what came from skipped interviews out of a patch item. False when nothing of it is left."""
    cited = 0
    for holder in _evidence_holders(item):
        evidence = holder.get("evidence")
        if isinstance(evidence, list) and evidence:
            cited += len(evidence)
            holder["evidence"] = _live(evidence, skipped)
    if isinstance(item.get("uses"), list):  # a use whose every quote came from a skipped interview is gone
        item["uses"] = [u for u in item["uses"] if not isinstance(u, dict) or u.get("evidence")]
    named = item.get("interviews")
    if isinstance(named, list) and named:
        cited += len(named)
        item["interviews"] = [ref for ref in named if str(ref) not in skipped]
    left = len(item.get("interviews") or []) + sum(len(h.get("evidence") or []) for h in _evidence_holders(item))
    return not cited or left > 0


def _drop_skipped_evidence(patch: Json, plan: MergePlan, report: Report) -> None:
    for section in ("step_evidence", "outcome_evidence", "new_outcomes", "new_solutions", "solution_evidence",
                    "proposed_changes"):
        kept = [item for item in patch.get(section, []) if _keep_item(item, plan.skipped)]
        plan.dropped += len(patch.get(section, [])) - len(kept)
        if section in patch:
            patch[section] = kept
    if plan.dropped:
        report.warn(f"dropped {plan.dropped} patch item(s) whose evidence comes only from skipped interviews",
                    code="evidence_dropped")


def groups_wanted(patch: Json) -> set[str]:
    """The groups the patch's new solutions and move_solution proposals name."""
    named = {str(item.get("group")) for item in patch.get("new_solutions", []) if isinstance(item, dict)}
    return named | {str(p.get("to_group")) for p in patch.get("proposed_changes", [])
                    if isinstance(p, dict) and p.get("type") == "move_solution"}


def resolve_solution_groups(kb: Json, patch: Json, wanted: set[str], report: Report) -> None:
    """Drop new groups the KB already holds, so a batch can be re-run, and new groups whose only solutions came from
    skipped interviews. A new group that nothing in the patch puts a solution into is refused.

    `wanted` is groups_wanted() read before evidence from skipped interviews was dropped."""
    groups = groups_of(kb)
    used = groups_wanted(patch)
    kept = []
    for item in patch.get("solution_groups", []):
        key, known = str(item["key"]), groups.get(str(item["key"]))
        if known and norm(str(item["name"])).lower() in known_names(known) \
                and norm(str(item["why"])) in _known_whys(known):
            report.warn(f"solution group '{key}' is already in the KB; ignored", code="solution_group_repeated")
        elif key in used or key not in wanted:  # wanted but unused: its solutions came only from skipped interviews
            kept.append(item)
    if "solution_groups" in patch:
        patch["solution_groups"] = kept
    for item in kept:
        if str(item["key"]) not in used:
            report.error(f"solution group '{item['key']}' gets no solution in this patch; put a new solution in it, "
                         "propose move_solution into it, or leave the group out", code="solution_group_unused")


def resolve_provenance(patch: Json, plan: MergePlan, report: Report) -> Json | None:
    """The patch's provenance block, with transcript references turned into KB interview IDs.

    A reference that is neither a KB ID nor a key in this patch is dropped with a warning: it is usually a file
    name, and file names carry the interviewee's name. One that names a skipped interview is dropped quietly."""
    given = patch.get("provenance")
    if not isinstance(given, dict):
        return None
    provenance = {key: given[key] for key in PROVENANCE_KEYS if key in given}
    if "transcripts_read" in given:
        read: set[str] = set()
        for reference in given.get("transcripts_read") or []:
            if str(reference) in plan.keymap:
                read.add(plan.keymap[str(reference)])
            elif str(reference) not in plan.skipped:
                report.warn(f"provenance.transcripts_read: '{reference}' is not an interview ID in the KB or a key in "
                            "this patch; name interviews by ID or key, never by file name", code="provenance_ref")
        provenance["transcripts_read"] = sorted(read)
    return provenance


def make_lookup(kb: Json, plan: MergePlan, transcripts: Transcripts, report: Report) -> Lookup:
    """Resolve a patch reference (a new key or a KB id) to its normalized transcript, reading lazily."""
    by_id = {str(record["id"]): record for record in kb["interviews"]}
    drift_warned: set[str] = set()

    def lookup(reference: str) -> tuple[str | None, str | None]:
        if reference in plan.skipped:
            return None, f"interview {reference} was skipped ({plan.skipped[reference]})"
        kb_id = plan.keymap.get(reference)
        if kb_id is None:
            return None, (f"unknown interview '{reference}': not an ID in the KB and not a key in this patch's "
                          "interviews")
        if kb_id not in plan.texts:
            record = by_id[kb_id]
            transcript = transcripts.get(str(record.get("file", "")))
            plan.texts[kb_id] = transcript.text if transcript else None
            changed = transcript and record.get("sha256") and transcript.sha256 != record["sha256"]
            if changed and kb_id not in drift_warned:
                drift_warned.add(kb_id)
                report.warn(f"transcript for interview {kb_id} ({record.get('file')}) changed since it was added; "
                            "run validate to re-check its quotes", code="transcript_changed")
        if plan.texts[kb_id] is None:
            return None, (f"transcript for interview {kb_id} ({by_id[kb_id].get('file')}) not found in "
                          f"{KB_FOLDER}/{COPIES}/ or under --transcripts")
        return plan.texts[kb_id], None

    return lookup


# ---------- merge: checks ----------
@dataclass
class Checks:
    """What the content checks need: the KB and its lookups, the study's style, and where to report."""

    kb: Json
    jobs: set[str]
    steps: dict[str, Json]
    outcomes: dict[str, Json]
    style: Style
    checker: QuoteChecker
    report: Report
    interviews: set[str] = field(default_factory=set)  # KB IDs and the keys of new interviews in this patch


def _check_link(job: Any, label: str, ctx: Checks) -> None:
    if job is not None and str(job) not in ctx.jobs:
        ctx.report.error(f"{label}: core job {job} does not exist; link to one of {sorted(ctx.jobs)} or leave it out",
                         code="job_missing")


def check_new_interviews(plan: MergePlan, patch: Json, ctx: Checks) -> None:
    key_of = {kb_id: key for key, kb_id in plan.keymap.items()}
    awaiting = {str(ref) for p in patch.get("proposed_changes", []) if p.get("type") == "new_core_job"
                for ref in p.get("interviews") or []}
    for record in plan.new_interviews:
        key, label = key_of[record["id"]], os.path.basename(str(record["file"]))
        for fld, kind in (("job_executor", "executor"), ("core_functional_job", "job")):
            clarity(record[fld]["statement"], kind, f"{label} {fld}", ctx.style, ctx.report)
            own = [{**e, "interview": key} for e in record[fld].get("evidence", [])]
            ctx.checker.check(own, f"{label} {fld}", ctx.report)
        _check_link(main_job(record), f"{label} core_functional_job", ctx)
        if not (main_job(record) or key in awaiting or unlinked_reason(record)):
            ctx.report.warn(f"interview {key} ({label}) is not linked to a core job; link it, list it in a "
                            "new_core_job proposal, or say why in unlinked_reason", code="job_unlinked")
        for fld in ("related_jobs", "emotional_jobs", "social_jobs"):
            kind = "job" if fld == "related_jobs" else "feeling"
            for job in record.get(fld) or []:
                clarity(job.get("statement", ""), kind, f"{label} {fld}", ctx.style, ctx.report)
                own = [{**e, "interview": key} for e in job.get("evidence", [])]
                ctx.checker.check(own, f"{label} {fld}: {short(job.get('statement', ''), 40)}", ctx.report)
                if fld == "related_jobs":
                    _check_link(job.get("job"), f"{label} related job", ctx)
        cluster = record.get("cluster")
        if cluster and cluster not in (ctx.kb.get("clusters") or {}):
            ctx.report.warn(f"{label}: segment '{cluster}' is not in the KB; add a new_segment proposal",
                            code="segment_unknown")


def check_bootstrap(bootstrap: Json, ctx: Checks) -> None:
    given = [str(job["id"]) for job in bootstrap["core_jobs"]]
    if given != [job_letter(i) for i in range(len(given))]:
        ctx.report.error(f"bootstrap: core job IDs must be A, B, C… in order; found {given}", code="job_order")
    for job in bootstrap["core_jobs"]:
        clarity(job["statement"], "job", f"core job {job['id']}", ctx.style, ctx.report)
        numbers = [int(step["n"]) for step in job["steps"]]
        for dup in sorted({n for n in numbers if numbers.count(n) > 1}):
            ctx.report.error(f"bootstrap: step {job['id']}.{dup} is used more than once", code="step_duplicate")
        for step in job["steps"]:
            clarity(step.get("statement", ""), "step", f"step {job['id']}.{step.get('n')}", ctx.style, ctx.report)


def check_step_evidence(patch: Json, ctx: Checks) -> None:
    for item in patch.get("step_evidence", []):
        if str(item["step"]) not in ctx.steps:
            ctx.report.error(f"step_evidence: step {item['step']} does not exist", code="step_missing")
        ctx.checker.check(item["evidence"], f"step {item['step']}", ctx.report)


def check_outcome_evidence(patch: Json, ctx: Checks) -> None:
    for item in patch.get("outcome_evidence", []):
        outcome = ctx.outcomes.get(str(item["outcome"]))
        if not outcome:
            ctx.report.error(f"outcome_evidence: outcome {item['outcome']} does not exist", code="outcome_missing")
        elif outcome.get("merged_into"):
            ctx.report.error(f"outcome {item['outcome']} was merged into {outcome['merged_into']}; cite that one",
                             code="outcome_merged")
        ctx.checker.check(item["evidence"], f"outcome {item['outcome']}", ctx.report)


def check_new_outcomes(patch: Json, ctx: Checks) -> None:
    seen = {(job_of(o["step"]), norm(o["statement"]).lower()): str(o["id"]) for o in ctx.outcomes.values()}
    for item in patch.get("new_outcomes", []):
        statement, step = item["statement"], str(item["step"])
        label = f"new outcome '{short(statement, 40)}'"
        if step not in ctx.steps:
            ctx.report.error(f"{label}: step {step} does not exist", code="step_missing")
        clarity(statement, "outcome", f"new outcome (step {step})", ctx.style, ctx.report)
        if not DIRECTION.match(statement):
            ctx.report.error(f"{label}: an outcome must start with Minimize, Maximize, Increase or Reduce",
                             code="outcome_direction")
        key = (job_of(step), norm(statement).lower())
        if key in seen:
            ctx.report.error(f"{label}: duplicates {seen[key]}; send it as outcome_evidence",
                             code="outcome_duplicate")
        seen[key] = "another new outcome in this patch"
        ctx.checker.check(item["evidence"], label, ctx.report)


def solution_name_index(kb: Json, skip: Any = None) -> dict[str, str]:
    """Every solution name in the KB, current and earlier, mapped to what to do instead of adding it again."""
    index: dict[str, str] = {}
    own = str(skip.get("id")) if isinstance(skip, dict) else None
    for solution in sorted(solutions_of(kb), key=lambda s: not s.get("merged_into")):  # live ones win
        if solution is skip or (own and str(solution.get("merged_into")) == own):  # its own names stay free to it
            continue
        hint = (f"was merged into {solution['merged_into']}; cite that one in solution_evidence"
                if solution.get("merged_into") else f"is already solution {solution.get('id')}; "
                "send it as solution_evidence")
        index.update({name: hint for name in known_names(solution)})
    return index


def check_solution_groups(patch: Json, ctx: Checks) -> None:
    groups = groups_of(ctx.kb)
    names = {name: key for key, group in groups.items() for name in known_names(group)}
    for item in patch.get("solution_groups", []):
        key, label = str(item["key"]), f"solution group '{item['key']}'"
        if key in groups:
            ctx.report.error(f"{label} is already in the KB; use it as it is, or propose reword_solution_group to "
                             "change its name or why", code="solution_group_duplicate")
        elif key in names.values():
            ctx.report.error(f"{label}: the key is used twice in this patch", code="solution_group_duplicate")
        name = norm(str(item["name"])).lower()
        if name in names and names[name] != key:
            ctx.report.error(f"{label}: the name '{item['name']}' is already group '{names[name]}'; put the solutions "
                             "there", code="solution_group_duplicate")
        names[name] = key
        clarity(str(item["name"]), "group", f"{label} name", ctx.style, ctx.report)
        clarity(str(item["why"]), "rationale", f"{label} why", ctx.style, ctx.report)


def _check_use(use: Json, label: str, ctx: Checks) -> None:
    step = str(use["step"])
    if step not in ctx.steps:
        ctx.report.error(f"{label}: step {step} does not exist", code="step_missing")
    ctx.checker.check(use["evidence"], f"{label} at step {step}", ctx.report)


def check_new_solutions(patch: Json, ctx: Checks) -> None:
    groups = set(groups_of(ctx.kb)) | {str(g["key"]) for g in patch.get("solution_groups", [])}
    seen = solution_name_index(ctx.kb)
    for item in patch.get("new_solutions", []):
        name = str(item["name"])
        label = f"new solution '{short(name, 40)}'"
        clarity(name, "solution", label, ctx.style, ctx.report)
        if norm(name).lower() in seen:
            ctx.report.error(f"{label} {seen[norm(name).lower()]}", code="solution_duplicate")
        seen[norm(name).lower()] = "repeats another new solution in this patch; give it one entry with several uses"
        if str(item["group"]) not in groups:
            ctx.report.error(f"{label}: group '{item['group']}' does not exist; use a group from context or add it "
                             "under solution_groups", code="solution_group_missing")
        for use in item["uses"]:
            _check_use(use, label, ctx)


def check_solution_evidence(patch: Json, ctx: Checks) -> None:
    solutions = solutions_by_id(ctx.kb)
    for item in patch.get("solution_evidence", []):
        sid = str(item["solution"])
        solution = solutions.get(sid)
        if not solution:
            ctx.report.error(f"solution_evidence: solution {sid} does not exist", code="solution_missing")
        elif solution.get("merged_into"):
            ctx.report.error(f"solution {sid} was merged into {solution['merged_into']}; cite that one",
                             code="solution_merged")
        _check_use(item, f"solution {sid}", ctx)


class ProposalRefs:
    """Resolves the things a proposal points at. Each miss becomes one readable problem."""

    def __init__(self, kb: Json, steps: dict[str, Json], outcomes: dict[str, Json],
                 interviews: set[str] | None = None, jobs: set[str] | None = None, *,
                 groups: set[str] | None = None) -> None:
        self.kb, self.steps, self.outcomes = kb, steps, outcomes
        self.jobs = jobs if jobs is not None else set(jobs_by_id(kb))
        self.interviews = interviews if interviews is not None else {str(r["id"]) for r in kb["interviews"]}
        self.groups = groups if groups is not None else set(groups_of(kb))
        self.problems: list[str] = []

    def solution(self, value: Any, what: str) -> Json | None:
        key = str(value) if value is not None else ""
        if not SOLUTION_ID.match(key):
            self.problems.append(f"{what} must be a solution ID such as \"S3\", got {value!r}")
            return None
        solution = solutions_by_id(self.kb).get(key)
        if not solution:
            self.problems.append(f"{what}: solution {key} does not exist")
        elif solution.get("merged_into"):
            self.problems.append(f"{what}: solution {key} was merged into {solution['merged_into']}; use that one")
            return None
        return solution

    def group(self, value: Any, what: str) -> str | None:
        if str(value) not in self.groups:
            self.problems.append(f"{what}: solution group '{value}' does not exist")
            return None
        return str(value)

    def outcome(self, value: Any, what: str) -> Json | None:
        key = str(value) if value is not None else ""
        if not OUTCOME_ID.match(key):
            self.problems.append(f"{what} must be an outcome ID such as \"A.6.3\", got {value!r}")
            return None
        outcome = self.outcomes.get(key)
        if not outcome:
            self.problems.append(f"{what}: outcome {key} does not exist")
        elif outcome.get("merged_into"):
            self.problems.append(f"{what}: outcome {key} was merged into {outcome['merged_into']}; use that one")
            return None
        return outcome

    def step(self, value: Any, what: str) -> str | None:
        if value is None or not STEP_ID.match(str(value)):
            self.problems.append(f"{what} must be a step ID such as \"A.6\", got {value!r}")
            return None
        if str(value) not in self.steps:
            self.problems.append(f"{what}: step {value} does not exist")
            return None
        return str(value)

    def job(self, value: Any, what: str) -> str | None:
        if not self.jobs:
            self.problems.append(f"{what}: the KB has no core job yet")
            return None
        if not isinstance(value, str) or str(value) not in self.jobs:
            self.problems.append(f"{what} must name a core job, one of {sorted(self.jobs)}, got {value!r}")
            return None
        return value

    def stage(self, value: Any, what: str) -> None:
        if value not in STAGES:
            self.problems.append(f"{what} needs a stage, one of {STAGES}")


def _refs_new_step(refs: ProposalRefs, proposal: Json) -> None:
    refs.stage(proposal.get("stage"), "new_step")
    refs.job(proposal.get("job"), "job")


def _refs_reword_step(refs: ProposalRefs, proposal: Json) -> None:
    refs.step(proposal.get("target"), "target")


def _refs_reword_outcome(refs: ProposalRefs, proposal: Json) -> None:
    refs.outcome(proposal.get("target"), "target")


def _refs_reword_core_job(refs: ProposalRefs, proposal: Json) -> None:
    refs.job(proposal.get("target"), "target")


def _refs_merge_outcomes(refs: ProposalRefs, proposal: Json) -> None:
    keep, drop = refs.outcome(proposal.get("target"), "target"), refs.outcome(proposal.get("merge"), "merge")
    if keep and drop and keep is drop:
        refs.problems.append("merge_outcomes: target and merge are the same outcome")
    elif keep and drop and job_of(keep["id"]) != job_of(drop["id"]):
        refs.problems.append(f"merge_outcomes: {keep['id']} and {drop['id']} sit under different core jobs; "
                             "move one of them first")


def _refs_move_outcome(refs: ProposalRefs, proposal: Json) -> None:
    outcome, step = refs.outcome(proposal.get("target"), "target"), refs.step(proposal.get("to_step"), "to_step")
    if outcome and step is not None and str(outcome["step"]) == step:
        refs.problems.append(f"move_outcome: outcome {outcome['id']} is already under step {step}")


def _refs_new_segment(refs: ProposalRefs, proposal: Json) -> None:
    target = proposal.get("target")
    if not isinstance(target, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", target):
        refs.problems.append("new_segment needs a short lowercase target key, such as fleet")
    elif target in (refs.kb.get("clusters") or {}):
        refs.problems.append(f"new_segment: segment '{target}' already exists")


def _refs_new_core_job(refs: ProposalRefs, proposal: Json) -> None:
    for index, step in enumerate(proposal.get("steps") or []):
        refs.stage(step.get("stage"), f"new_core_job steps[{index}]")
    for ref in proposal.get("interviews") or []:
        if str(ref) not in refs.interviews:
            refs.problems.append(f"new_core_job: interview {ref} does not exist")


def _refs_confirm_core_job(refs: ProposalRefs, proposal: Json) -> None:
    job = refs.job(proposal.get("target"), "target")
    if job and jobs_by_id(refs.kb).get(job, {}).get("status") == "approved":
        refs.problems.append(f"confirm_core_job: core job {job} is already approved")


def _refs_move_step(refs: ProposalRefs, proposal: Json) -> None:
    step, job = refs.step(proposal.get("target"), "target"), refs.job(proposal.get("to_job"), "to_job")
    if step and job and job_of(step) == job:
        refs.problems.append(f"move_step: step {step} is already under core job {job}")
    if proposal.get("stage") is not None:
        refs.stage(proposal["stage"], "move_step")


def _related_job(record: Json, statement: str) -> Json | None:
    return next((job for job in record.get("related_jobs") or []
                 if isinstance(job, dict) and norm(str(job.get("statement", ""))) == norm(statement)), None)


def _refs_relink_interview(refs: ProposalRefs, proposal: Json) -> None:
    target = str(proposal.get("target") or "")
    if target not in refs.interviews:
        refs.problems.append(f"relink_interview: interview {target or '(none)'} does not exist")
        return
    if "job" not in proposal:
        refs.problems.append("relink_interview needs job: a core job ID, or null to remove the link")
    elif proposal["job"] is not None:
        refs.job(proposal["job"], "job")
    record = next((r for r in refs.kb["interviews"] if str(r["id"]) == target), None)
    related = proposal.get("related_job")
    if record and related and not _related_job(record, str(related)):
        refs.problems.append(f"relink_interview: interview {target} has no related job '{short(str(related), 60)}'")


def _refs_merge_solutions(refs: ProposalRefs, proposal: Json) -> None:
    keep, drop = refs.solution(proposal.get("target"), "target"), refs.solution(proposal.get("merge"), "merge")
    if keep and drop and keep is drop:
        refs.problems.append("merge_solutions: target and merge are the same solution")


def _refs_move_solution(refs: ProposalRefs, proposal: Json) -> None:
    solution, group = refs.solution(proposal.get("target"), "target"), refs.group(proposal.get("to_group"), "to_group")
    if solution and group and str(solution.get("group")) == group:
        refs.problems.append(f"move_solution: solution {solution['id']} is already in group '{group}'")


def _refs_reword_solution(refs: ProposalRefs, proposal: Json) -> None:
    solution = refs.solution(proposal.get("target"), "target")
    taken = solution_name_index(refs.kb, skip=solution).get(norm(str(proposal.get("proposal", ""))).lower())
    if solution and taken:
        refs.problems.append(f"reword_solution: the name '{proposal.get('proposal')}' {taken}")


def _refs_reword_solution_group(refs: ProposalRefs, proposal: Json) -> None:
    group = refs.group(proposal.get("target"), "target")
    name = norm(str(proposal.get("proposal", ""))).lower()
    others = [key for key, other in groups_of(refs.kb).items() if key != group and name in known_names(other)]
    if group and others:
        refs.problems.append(f"reword_solution_group: the name '{proposal.get('proposal')}' is already group "
                             f"'{others[0]}'")


PROPOSAL_CHECKS: dict[str, Callable[[ProposalRefs, Json], None]] = {
    "new_step": _refs_new_step,
    "reword_step": _refs_reword_step,
    "reword_outcome": _refs_reword_outcome,
    "reword_core_job": _refs_reword_core_job,
    "merge_outcomes": _refs_merge_outcomes,
    "move_outcome": _refs_move_outcome,
    "new_segment": _refs_new_segment,
    "new_core_job": _refs_new_core_job,
    "confirm_core_job": _refs_confirm_core_job,
    "move_step": _refs_move_step,
    "relink_interview": _refs_relink_interview,
    "merge_solutions": _refs_merge_solutions,
    "move_solution": _refs_move_solution,
    "reword_solution": _refs_reword_solution,
    "reword_solution_group": _refs_reword_solution_group,
}


def proposal_problems(refs: ProposalRefs, proposal: Json) -> list[str]:
    """Check that a proposal's references point at real things. Used at merge time and again before apply."""
    refs.problems = []
    check = PROPOSAL_CHECKS.get(str(proposal.get("type")))
    if check:
        check(refs, proposal)
    return refs.problems


def check_proposals(patch: Json, ctx: Checks) -> None:
    kinds = {"new_step": "step", "reword_step": "step", "reword_core_job": "job", "reword_outcome": "outcome",
             "new_core_job": "job", "confirm_core_job": "job", "reword_solution": "solution",
             "reword_solution_group": "group"}
    limit = ctx.style.limits.get("rationale", 30)
    groups = set(groups_of(ctx.kb)) | {str(g["key"]) for g in patch.get("solution_groups", [])}
    refs = ProposalRefs(ctx.kb, ctx.steps, ctx.outcomes, ctx.interviews, ctx.jobs, groups=groups)
    for index, proposal in enumerate(patch.get("proposed_changes", [])):
        label = f"proposal {index + 1} ({proposal.get('type')})"
        kind = kinds.get(str(proposal.get("type")))
        if kind:
            clarity(proposal["proposal"], kind, label, ctx.style, ctx.report)
        if proposal.get("why"):
            clarity(str(proposal["why"]), "rationale", f"{label} why", ctx.style, ctx.report)
        if len(str(proposal.get("rationale", "")).split()) > limit:
            ctx.report.error(f"clarity: {label} rationale is over {limit} words; say why in one plain sentence",
                             code="rationale_length")
        for problem in proposal_problems(refs, proposal):
            ctx.report.error(f"{label}: {problem}", code="proposal_ref")
        if proposal.get("evidence"):
            ctx.checker.check(proposal["evidence"], label, ctx.report)
        if proposal.get("type") == "new_core_job":
            _check_new_core_job(proposal, label, ctx)


def _check_new_core_job(proposal: Json, label: str, ctx: Checks) -> None:
    if proposal.get("job_executor"):
        clarity(proposal["job_executor"], "executor", f"{label} job_executor", ctx.style, ctx.report)
    for index, step in enumerate(proposal.get("steps") or []):
        clarity(str(step.get("statement", "")), "step", f"{label} steps[{index}]", ctx.style, ctx.report)
        if step.get("evidence"):
            ctx.checker.check(step["evidence"], f"{label} steps[{index}]", ctx.report)


def check_patch(kb: Json, patch: Json, plan: MergePlan, transcripts: Transcripts, report: Report) -> None:
    jobs, steps = set(jobs_by_id(kb)), steps_by_id(kb)
    if not steps and plan.bootstrap:
        jobs = {str(job["id"]) for job in plan.bootstrap["core_jobs"]}
        steps = {f"{job['id']}.{int(step['n'])}": step for job in plan.bootstrap["core_jobs"] for step in job["steps"]}
    ctx = Checks(kb, jobs, steps, outcomes_by_id(kb), style_of(kb),
                 QuoteChecker(make_lookup(kb, plan, transcripts, report)), report, set(plan.keymap))
    check_new_interviews(plan, patch, ctx)
    if plan.bootstrap:
        check_bootstrap(plan.bootstrap, ctx)
    check_step_evidence(patch, ctx)
    check_outcome_evidence(patch, ctx)
    check_new_outcomes(patch, ctx)
    check_solution_groups(patch, ctx)
    check_new_solutions(patch, ctx)
    check_solution_evidence(patch, ctx)
    check_proposals(patch, ctx)


# ---------- merge: write ----------
def remap(items: list[Json], keymap: dict[str, str]) -> list[Json]:
    return [{**item, "interview": keymap.get(str(item["interview"]), str(item["interview"]))} for item in items]


def remap_proposal(proposal: Json, keymap: dict[str, str]) -> Json:
    """A proposal as the KB stores it: patch keys turned into interview IDs, wherever it names an interview."""
    record = dict(proposal)
    if record.get("evidence"):
        record["evidence"] = remap(record["evidence"], keymap)
    if record.get("steps"):
        record["steps"] = [{**step, "evidence": remap(step.get("evidence") or [], keymap)} for step in record["steps"]]
    if record.get("interviews"):
        record["interviews"] = [keymap.get(str(ref), str(ref)) for ref in record["interviews"]]
    if record.get("type") == "relink_interview":
        record["target"] = keymap.get(str(record.get("target")), str(record.get("target")))
    return record


def has_new_evidence(kb: Json, patch: Json, plan: MergePlan) -> bool:
    steps, outcomes = steps_by_id(kb), outcomes_by_id(kb)
    pairs = [(steps.get(str(i["step"])), i["evidence"]) for i in patch.get("step_evidence", [])]
    pairs += [(outcomes.get(str(i["outcome"])), i["evidence"]) for i in patch.get("outcome_evidence", [])]
    for target, evidence in pairs:
        have = {evidence_key(e) for e in (target or {}).get("evidence", [])}
        if any(evidence_key(e) not in have for e in remap(evidence, plan.keymap)):
            return True
    return has_new_solution_evidence(kb, patch, plan)


def has_new_solution_evidence(kb: Json, patch: Json, plan: MergePlan) -> bool:
    solutions = solutions_by_id(kb)
    for item in patch.get("solution_evidence", []):
        status = str(item.get("status") or "current")
        use = next((u for u in uses_of(solutions.get(str(item["solution"])) or {})
                    if str(u.get("step")) == str(item["step"]) and use_status(u) == status), {})
        have = {evidence_key(e) for e in use.get("evidence", [])}
        if any(evidence_key(e) not in have for e in remap(item["evidence"], plan.keymap)):
            return True
    return False


def _apply_solutions(kb: Json, patch: Json, plan: MergePlan) -> Json:
    """Add the patch's new groups, new solutions and new uses. Returns what changed, for the changelog."""
    changes: Json = {"new_solutions": [], "new_solution_groups": [], "solution_quotes": 0}
    if not any(patch.get(key) for key in ("solution_groups", "new_solutions", "solution_evidence")):
        return changes
    section = solution_section(kb)
    for item in patch.get("solution_groups", []):
        section["groups"][str(item["key"])] = {"name": item["name"], "why": item["why"], "added": today()}
        changes["new_solution_groups"].append(str(item["key"]))
    solutions = solutions_by_id(kb)
    for item in patch.get("solution_evidence", []):
        status = str(item.get("status") or "current")
        solution = solutions[str(item["solution"])]
        changes["solution_quotes"] += add_use(solution, str(item["step"]), status, remap(item["evidence"], plan.keymap))
    for item in patch.get("new_solutions", []):
        record = {"id": next_solution_id(kb), "name": item["name"], "kind": item["kind"],
                  "group": str(item["group"]), "added": today(), "uses": []}
        section["solutions"].append(record)
        for use in item["uses"]:
            add_use(record, str(use["step"]), str(use.get("status") or "current"), remap(use["evidence"], plan.keymap))
        changes["new_solutions"].append(record["id"])
    return changes


def job_support(kb: Json, job: str) -> str:
    """How many people interviewed back a core job, in one sentence for reviewers."""
    total = len(kb["interviews"])
    main = sum(1 for r in kb["interviews"] if main_job(r) == job)
    related = sum(1 for r in kb["interviews"] if main_job(r) != job and job in related_links(r))
    if total == 1:
        return f"The one person interviewed {'has' if main else 'does not have'} it as their main job."
    text = f"{main} of {total} people interviewed {'has' if main == 1 else 'have'} it as their main job"
    text += f", {related} more as a related job." if related else "."
    return text + (" It rests on one interview." if main == 1 else "")


def confirmation(kb: Json, job: str, why: str) -> Json:
    """A decision asking the team to confirm a core job the tool set up, such as the first batch's."""
    return {"type": "confirm_core_job", "target": job, "proposal": jobs_by_id(kb)[job]["statement"],
            "rationale": f"{why} {job_support(kb, job)}"}


def file_proposal(kb: Json, proposal: Json) -> str:
    """Add a pending proposal with the next free P-number. Returns its ID."""
    numbers = [int(str(p["id"])[1:]) for p in kb["proposed_changes"] if re.fullmatch(r"P\d+", str(p.get("id", "")))]
    record = {"id": f"P{max(numbers, default=0) + 1}", "status": "pending", "raised": today(), **proposal}
    kb["proposed_changes"].append(record)
    return record["id"]


def _bootstrap_into(kb: Json, bootstrap: Json) -> str:
    jobs = bootstrap["core_jobs"]
    kb["core_jobs"] = [{**{k: v for k, v in job.items() if k != "steps"}, "status": "proposed"} for job in jobs]
    kb["job_map"]["stages"] = [{"key": k, "name": k.capitalize()} for k in STAGES]
    kb["job_map"]["steps"] = [{"job": str(job["id"]), **step, "evidence": []} for job in jobs for step in job["steps"]]
    ids = ", ".join(str(job["id"]) for job in jobs)
    return f"bootstrapped core job{'s' if len(jobs) > 1 else ''} {ids} and {len(kb['job_map']['steps'])} steps"


def apply_patch(kb: Json, patch: Json, plan: MergePlan, stamp: Json) -> Json | None:
    """Fold a checked patch into the KB in place. Returns the changelog entry, or None when nothing is new.

    `stamp` is what the changelog entry records about the run itself: patch name, ts, run_id and provenance."""
    fresh = has_new_evidence(kb, patch, plan)
    anything = (plan.new_interviews or plan.bootstrap or fresh or patch.get("new_outcomes")
                or patch.get("new_solutions") or patch.get("proposed_changes"))
    if not anything:
        return None
    log: list[str] = []
    if plan.bootstrap:
        log.append(_bootstrap_into(kb, plan.bootstrap))
    kb["interviews"].extend(plan.new_interviews)
    added_ids = [record["id"] for record in plan.new_interviews]
    log.append(f"added interviews {', '.join(added_ids) or 'none'}")
    steps, outcomes = steps_by_id(kb), outcomes_by_id(kb)
    step_quotes = sum(add_evidence(steps[str(i["step"])], remap(i["evidence"], plan.keymap))
                      for i in patch.get("step_evidence", []))
    outcome_quotes = sum(add_evidence(outcomes[str(i["outcome"])], remap(i["evidence"], plan.keymap))
                         for i in patch.get("outcome_evidence", []))
    new_outcome_ids = []
    for item in patch.get("new_outcomes", []):
        step = str(item["step"])
        record = {"id": next_outcome_id(kb, step), "step": step, "statement": item["statement"], "added": today(),
                  "evidence": []}
        add_evidence(record, remap(item["evidence"], plan.keymap))
        kb["desired_outcomes"]["outcomes"].append(record)
        new_outcome_ids.append(record["id"])
    sort_outcomes(kb)
    proposal_ids = []
    filed = [confirmation(kb, str(job["id"]), "Set up from the first batch.") for job in kb["core_jobs"]] \
        if plan.bootstrap else []
    solved = _apply_solutions(kb, patch, plan)
    for proposal in filed + [remap_proposal(p, plan.keymap) for p in patch.get("proposed_changes", [])]:
        proposal_ids.append(file_proposal(kb, proposal))
    log += [f"{step_quotes} step quotes", f"{outcome_quotes} outcome quotes",
            f"new outcomes {', '.join(new_outcome_ids) or 'none'}"]
    if "current_solutions" in kb:
        log += [f"new solutions {', '.join(solved['new_solutions']) or 'none'}",
                f"{solved['solution_quotes']} solution quotes"]
    log.append(f"proposals {', '.join(proposal_ids) or 'none'}")
    recount(kb)
    if added_ids or new_outcome_ids or solved["new_solutions"]:
        mark_stale(kb, f"interviews {', '.join(added_ids) or '-'} and outcomes "
                       f"{', '.join(new_outcome_ids) or '-'} added"
                       + (f"; solutions {', '.join(solved['new_solutions'])}" if solved["new_solutions"] else ""))
    entry: Json = {"date": today(), "action": "merge", **stamp, "summary": "; ".join(log),
                   "added_interviews": added_ids, "new_outcomes": new_outcome_ids, "step_quotes": step_quotes,
                   "outcome_quotes": outcome_quotes, "proposals": proposal_ids}
    if "current_solutions" in kb:
        entry.update(solved)
    if plan.bootstrap:
        entry["bootstrap"] = True
    kb["changelog"].append(entry)
    return entry


class MergeOutput:
    """Collects what merge has to say and prints it once, as text or as one JSON object."""

    def __init__(self, args: argparse.Namespace, report: Report) -> None:
        self.args, self.report = args, report
        self.result: Json = {"ok": False, "dry_run": bool(args.dry_run), "written": False, "kb": args.kb,
                             "patch": args.patch, "run_id": args.run.id}
        self.header: list[str] = []
        self.verdict: list[str] = []

    def log(self) -> None:
        """Hand the run log what this merge did: codes and counts, never the messages or the notes."""
        run: Run = self.args.run
        run.add_report(self.report)
        changes = self.result.get("changes") or {}
        provenance = {k: v for k, v in (changes.get("provenance") or {}).items() if k != "notes"}
        run.note(dry_run=self.result["dry_run"], written=self.result["written"],
                 nothing_new=bool(self.result.get("nothing_new")), patch_sha256=file_sha256(self.args.patch),
                 bootstrap=bool(changes.get("bootstrap")), backup=run.relative(self.result.get("backup")),
                 counts={"interviews_added": len(changes.get("added_interviews") or []),
                         "interviews_skipped": len(self.result.get("skipped") or {}),
                         "outcomes_added": len(changes.get("new_outcomes") or []),
                         "step_quotes": changes.get("step_quotes", 0),
                         "outcome_quotes": changes.get("outcome_quotes", 0),
                         "proposals_filed": len(changes.get("proposals") or []),
                         "transcripts_copied": len(self.result.get("transcripts_copied") or []),
                         "solutions_added": len(changes.get("new_solutions") or []),
                         "solution_groups_added": len(changes.get("new_solution_groups") or []),
                         "solution_quotes": changes.get("solution_quotes", 0)},
                 provenance=provenance or None)

    def finish(self, code: int) -> int:
        self.result.update({"warnings": self.report.warnings, "errors": self.report.errors})
        self.log()
        if self.args.json:
            print(json.dumps(self.result, ensure_ascii=False, indent=2, default=str))
            return code
        lines = self.header + [f"WARN {w}" for w in self.report.warnings] + self.verdict
        if self.report.errors:
            lines.append(f"\n{len(self.report.errors)} problem(s); nothing written:")
            lines += [f"  - {e}" for e in self.report.errors]
        print("\n".join(lines))
        return code


def copy_transcripts(kb_path: str, sources: list[str]) -> None:
    """Copy new transcripts into .pw-kb/transcripts/, so the study keeps every transcript its quotes come from."""
    folder = copies_folder(kb_path)
    os.makedirs(folder, exist_ok=True)
    for source in sources:
        shutil.copy2(source, os.path.join(folder, os.path.basename(source)))


def _merge_verdict(out: MergeOutput, entry: Json, candidate: Json, copies: list[str]) -> None:
    out.result.update({"ok": True, "changes": entry, "thin_steps": [step_key(s) for s in thin_steps(candidate)],
                       "stale": stale_layers(candidate),
                       "transcripts_copied": [os.path.basename(path) for path in copies]})
    copied = f"{len(copies)} new transcript(s) into {KB_FOLDER}/{COPIES}/"
    if out.args.dry_run:
        out.verdict += ["dry run OK: every quote matches, every reference resolves and the KB structure stays valid",
                        f"would merge: {entry['summary']}"] + ([f"would copy {copied}"] if copies else [])
        return
    copy_transcripts(out.args.kb, copies)  # before the KB is written, so it never cites a missing copy
    out.result["backup"] = backup(out.args.kb)
    save_kb(candidate, out.args.kb)
    out.result["written"] = True
    out.verdict += [f"merged: {entry['summary']}", f"backup: {out.result['backup']}"]
    if copies:
        out.verdict.append(f"copied {copied}")
    if out.result["thin_steps"]:
        numbers = ", ".join(str(n) for n in out.result["thin_steps"])
        out.verdict.append(f"thin steps (<{THIN_STEP} interviews): {numbers}")
    if out.result["stale"]:
        out.verdict.append("now stale: " + ", ".join(out.result["stale"]))


def cmd_merge(args: argparse.Namespace) -> int:
    """Check a patch, then fold it in. The dry run and the real merge share every step up to the write."""
    report = Report()
    out = MergeOutput(args, report)
    kb = load_kb(args.kb)
    patch = coerce_patch(load_yaml(args.patch), id_width(kb), report)
    for problem in schema_errors(patch, load_schema("patch-schema.json"), "patch"):
        report.error(f"patch format: {problem} (see references/patch-format.md)", code="patch_format")
    if not report.errors:
        resolve_job_refs(kb, patch, report)
    if report.errors:
        return out.finish(1)
    transcripts = transcripts_for(args.transcripts or [], report, copies_folder(args.kb))
    wanted = groups_wanted(patch)
    plan = resolve_interviews(kb, patch, transcripts, report)
    resolve_solution_groups(kb, patch, wanted, report)
    provenance = resolve_provenance(patch, plan, report)
    out.result["new_interviews"] = {key: kb_id for key, kb_id in plan.keymap.items() if key != kb_id}
    out.result["skipped"] = plan.skipped
    assigned = ", ".join(f"{k} -> {v}" for k, v in out.result["new_interviews"].items())
    out.header.append(f"interviews: {len(plan.new_interviews)} new" + (f" ({assigned})" if assigned else "")
                      + f", {len(plan.skipped)} skipped")
    if not report.errors:
        check_patch(kb, patch, plan, transcripts, report)
    if report.errors:
        return out.finish(1)
    candidate = copy.deepcopy(kb)
    stamp: Json = {"patch": os.path.basename(args.patch), **args.run.stamp()}
    if provenance:
        stamp["provenance"] = provenance
    entry = apply_patch(candidate, patch, plan, stamp)
    if entry is None:
        out.result.update({"ok": True, "nothing_new": True})
        out.verdict.append("nothing new to merge; KB unchanged")
        return out.finish(0)
    for problem in structure_problems(candidate):
        report.error(f"the merge would break the KB structure: {problem}", code="structure")
    if report.errors:
        return out.finish(1)
    _merge_verdict(out, entry, candidate, plan.copies)
    return out.finish(0)


# ---------- apply ----------
def _history(obj: Json, **entry: Any) -> None:
    obj.setdefault("history", []).append({"date": today(), **entry})


def _clean_evidence(items: list[Json] | None) -> list[Json]:
    return [{k: v for k, v in e.items() if k in ("interview", "source", "quote")} for e in items or []]


def _apply_new_step(kb: Json, proposal: Json) -> str:
    job = str(proposal["job"])
    number = next_step_n(kb, job)
    kb["job_map"]["steps"].append({"job": job, "n": number, "stage": proposal["stage"],
                                   "statement": proposal["proposal"], "covers": proposal.get("covers", ""),
                                   "evidence": _clean_evidence(proposal.get("evidence"))})
    sort_steps(kb)
    return f"added step {job}.{number}"


def _apply_reword(kb: Json, proposal: Json) -> str:
    kind = proposal["type"]
    if kind == "reword_step":
        target = steps_by_id(kb)[str(proposal["target"])]
    elif kind == "reword_outcome":
        target = outcomes_by_id(kb)[str(proposal["target"])]
    else:
        target = jobs_by_id(kb)[str(proposal["target"])]
    _history(target, was=target["statement"])
    target["statement"] = proposal["proposal"]
    if kind != "reword_core_job":
        return f"reworded {proposal['target']}"
    for other in kb["proposed_changes"]:  # a pending confirmation asks about the job as it now reads
        if other.get("type") == "confirm_core_job" and other.get("status") == "pending" \
                and str(other.get("target")) == str(proposal["target"]):
            other["proposal"] = proposal["proposal"]
    return f"reworded core job {proposal['target']}"


def _apply_merge_outcomes(kb: Json, proposal: Json) -> str:
    outcomes = outcomes_by_id(kb)
    keep, drop = outcomes[str(proposal["target"])], outcomes[str(proposal["merge"])]
    add_evidence(keep, drop.get("evidence", []))
    drop["merged_into"] = keep["id"]
    _rename_theme_refs(kb, {str(drop["id"]): str(keep["id"])})
    for other in kb["desired_outcomes"]["outcomes"]:  # anything that pointed at the dropped one now points at keep
        if other.get("merged_into") == drop["id"] and other is not drop:
            other["merged_into"] = keep["id"]
    return f"merged {drop['id']} into {keep['id']}"


REF_FIELDS = ("target", "merge", "to_step")


def rename_refs(kb: Json, renamed: dict[str, str]) -> None:
    """Point every reference to a renamed step or outcome at its new ID: merged_into, solution uses, value themes
    and pending proposals."""
    for outcome in kb["desired_outcomes"]["outcomes"]:
        if outcome.get("merged_into") in renamed:
            outcome["merged_into"] = renamed[outcome["merged_into"]]
    _rename_use_refs(kb, renamed)
    _rename_theme_refs(kb, renamed)
    for proposal in kb["proposed_changes"]:
        if proposal.get("status") == "pending":
            for key in REF_FIELDS:
                if str(proposal.get(key)) in renamed:
                    proposal[key] = renamed[str(proposal[key])]


def _apply_move_outcome(kb: Json, proposal: Json) -> str:
    outcome = outcomes_by_id(kb)[str(proposal["target"])]
    step = str(proposal["to_step"])
    old, new = str(outcome["id"]), next_outcome_id(kb, step)
    _history(outcome, was_id=old)
    outcome["id"], outcome["step"] = new, step
    rename_refs(kb, {old: new})
    sort_outcomes(kb)
    return f"moved {old} to {new} under step {step}"


def _apply_new_segment(kb: Json, proposal: Json) -> str:
    kb.setdefault("clusters", {})[proposal["target"]] = {"name": proposal["proposal"],
                                                          "description": proposal.get("rationale", "")}
    return f"added segment {proposal['target']}"


def _link(own: Json, job: str | None, reason: str = "") -> None:
    """Point an interview's own job statement at a core job, keeping the old link and the old reason for having
    none in its history. Removing the main link records why, so the KB never says a linked person has no job."""
    if own.get("job") == job:
        return
    entry: Json = {"was_job": own.get("job")}
    if own.get("unlinked_reason"):
        entry["was_reason"] = own["unlinked_reason"]
    _history(own, **entry)
    own.pop("unlinked_reason", None)
    if job is None:
        own.pop("job", None)
        if reason:
            own["unlinked_reason"] = reason
    else:
        own["job"] = job


def _apply_new_core_job(kb: Json, proposal: Json) -> str:
    job = next_job_id(kb)
    record = {"id": job, "statement": proposal["proposal"], "status": "approved"}
    if proposal.get("job_executor"):
        record["job_executor"] = proposal["job_executor"]
    kb["core_jobs"].append(record)
    added = []
    for n, step in enumerate(proposal.get("steps") or [], start=1):
        kb["job_map"]["steps"].append({"job": job, "n": n, "stage": step["stage"], "statement": step["statement"],
                                       "covers": step.get("covers", ""),
                                       "evidence": _clean_evidence(step.get("evidence"))})
        added.append(f"{job}.{n}")
    linked = [str(ref) for ref in proposal.get("interviews") or []]
    for record in kb["interviews"]:
        if str(record["id"]) in linked:
            _link(record["core_functional_job"], job)
    message = f"added core job {job}" + (f" with steps {', '.join(added)}" if added else "")
    return message + (f"; linked interviews {', '.join(linked)}" if linked else "")


def _apply_confirm_core_job(kb: Json, proposal: Json) -> str:
    jobs_by_id(kb)[str(proposal["target"])]["status"] = "approved"
    return f"confirmed core job {proposal['target']}"


def _apply_move_step(kb: Json, proposal: Json) -> str:
    old = str(proposal["target"])
    step, job = steps_by_id(kb)[old], str(proposal["to_job"])
    number = next_step_n(kb, job)
    new = f"{job}.{number}"
    _history(step, was_id=old)
    step["job"], step["n"] = job, number
    if proposal.get("stage"):
        step["stage"] = proposal["stage"]
    renamed = {old: new}
    for outcome in kb["desired_outcomes"]["outcomes"]:
        if str(outcome["step"]) == old:
            moved = f"{new}.{str(outcome['id']).rsplit('.', 1)[1]}"
            _history(outcome, was_id=outcome["id"])
            renamed[str(outcome["id"])] = moved
            outcome["id"], outcome["step"] = moved, new
    rename_refs(kb, renamed)
    sort_steps(kb)
    sort_outcomes(kb)
    pairs = [f"{a} to {b}" for a, b in renamed.items() if a != old]
    return f"moved step {old} to {new}" + (f", with outcomes {', '.join(pairs)}" if pairs else "")


def _apply_relink_interview(kb: Json, proposal: Json) -> str:
    record = next(r for r in kb["interviews"] if str(r["id"]) == str(proposal["target"]))
    job = proposal["job"]
    if proposal.get("related_job"):
        _link(_related_job(record, str(proposal["related_job"])) or {}, job)
        what = f"a related job of interview {record['id']}"
    else:
        _link(record["core_functional_job"], job, str(proposal.get("rationale") or ""))
        what = f"interview {record['id']}"
    return f"linked {what} to core job {job}" if job else f"unlinked {what}"


def _apply_merge_solutions(kb: Json, proposal: Json) -> str:
    solutions = solutions_by_id(kb)
    keep, drop = solutions[str(proposal["target"])], solutions[str(proposal["merge"])]
    for use in uses_of(drop):
        evidence = [e for e in use.get("evidence") or [] if isinstance(e, dict)]
        add_use(keep, str(use.get("step")), use_status(use), evidence)
    keep["uses"] = folded_uses(keep)
    drop["uses"], drop["merged_into"] = [], keep["id"]
    for other in solutions_of(kb):  # anything that pointed at the folded one now points at keep
        if other.get("merged_into") == drop["id"] and other is not drop:
            other["merged_into"] = keep["id"]
    return f"merged solution {drop['id']} into {keep['id']}"


def _apply_move_solution(kb: Json, proposal: Json) -> str:
    solution = solutions_by_id(kb)[str(proposal["target"])]
    _history(solution, was_group=solution.get("group"))
    solution["group"] = str(proposal["to_group"])
    return f"moved solution {solution['id']} to group {proposal['to_group']}"


def _apply_rename_solution(kb: Json, proposal: Json) -> str:
    """Rename a solution, and fix its kind if the proposal says so; or rename a group and update its why."""
    if proposal["type"] == "reword_solution":
        target, what, extra = solutions_by_id(kb)[str(proposal["target"])], "solution", "kind"
    else:
        target, what, extra = groups_of(kb)[str(proposal["target"])], "solution group", "why"
    entry: Json = {}
    if norm(str(proposal["proposal"])) != norm(str(target.get("name", ""))):
        entry["was"] = target.get("name", "")
    if proposal.get(extra) and proposal[extra] != target.get(extra):
        entry[f"was_{extra}"] = target.get(extra, "")
        target[extra] = proposal[extra]
    if entry:
        _history(target, **entry)
    target["name"] = proposal["proposal"]
    return f"changed {what} {proposal['target']}"


APPLY_HANDLERS: dict[str, Callable[[Json, Json], str]] = {
    "new_step": _apply_new_step,
    "reword_step": _apply_reword,
    "reword_outcome": _apply_reword,
    "reword_core_job": _apply_reword,
    "merge_outcomes": _apply_merge_outcomes,
    "move_outcome": _apply_move_outcome,
    "new_segment": _apply_new_segment,
    "new_core_job": _apply_new_core_job,
    "confirm_core_job": _apply_confirm_core_job,
    "move_step": _apply_move_step,
    "relink_interview": _apply_relink_interview,
    "merge_solutions": _apply_merge_solutions,
    "move_solution": _apply_move_solution,
    "reword_solution": _apply_rename_solution,
    "reword_solution_group": _apply_rename_solution,
}


def cmd_apply(args: argparse.Namespace) -> int:
    kb = load_kb(args.kb)
    proposal = next((p for p in kb["proposed_changes"] if p.get("id") == args.id), None)
    args.run.note(proposal=args.id, proposal_type=str((proposal or {}).get("type") or ""), decision=args.decision)
    if not proposal:
        raise KbError(f"no proposal {args.id} in {args.kb}", code="proposal_missing")
    if proposal.get("status") != "pending":
        raise KbError(f"{args.id} is already {proposal['status']}", code="proposal_decided")
    candidate = copy.deepcopy(kb)
    proposal = next(p for p in candidate["proposed_changes"] if p.get("id") == args.id)
    status = "approved" if args.decision == "approve" else "rejected"
    message = f"{args.id} {status}"
    if status == "approved":
        refs = ProposalRefs(candidate, steps_by_id(candidate), outcomes_by_id(candidate))
        problems = proposal_problems(refs, proposal)
        if problems:
            raise KbError(f"{args.id} cannot be applied as it stands:\n  - " + "\n  - ".join(problems)
                          + "\nFix the KB or reject the proposal.", code="proposal_stale")
    proposal.update({"status": status, "decided": today(), "note": args.note or ""})
    if status == "approved":
        handler = APPLY_HANDLERS.get(str(proposal.get("type")))
        message += ": " + (handler(candidate, proposal) if handler
                           else "no automatic action for this type; edit the KB by hand")
        recount(candidate)
        mark_stale(candidate, message)
    candidate["changelog"].append(changelog_entry(args.run, "decide", proposal=args.id, decision=status,
                                                  summary=message))
    problems = structure_problems(candidate)
    if problems:
        raise KbError("applying the proposal would break the KB structure; nothing written:\n  - "
                      + "\n  - ".join(problems), code="structure")
    made = backup(args.kb)
    save_kb(candidate, args.kb)
    args.run.note(written=True, backup=args.run.relative(made))
    print(message)
    return 0


# ---------- themes ----------
@dataclass
class ThemeChecks:
    """What the checks of one core job's value themes need at hand."""

    kb: Json
    job: str
    outcomes: dict[str, Json]
    style: Style
    report: Report
    solutions: list[str]  # names of the live solutions: a theme names a need, never one of these


def read_themes_file(path: str, kb: Json) -> tuple[str, list[Any]]:
    data = load_yaml(path)
    if not isinstance(data, dict) or not isinstance(data.get("themes"), list) or not data.get("job"):
        raise KbError(f"{path} must hold `job` (a core job ID such as A) and `themes` (a list: the full set of value "
                      "themes for that core job)", code="themes_file")
    unknown = sorted(str(key) for key in set(data) - {"job", "themes"})
    if unknown:
        raise KbError(f"{path}: unknown key {', '.join(unknown)}; the file holds `job` and `themes` only",
                      code="themes_file")
    job = str(data["job"])
    if job not in jobs_by_id(kb):
        raise KbError(f"{path}: core job {job} is not in the KB", code="themes_file")
    return job, data["themes"]


def _clean_highlights(items: Any, label: str, width: int, report: Report) -> list[Json]:
    if items is None:
        return []
    if not isinstance(items, list):
        report.error(f"{label}: highlights must be a list", code="theme_shape")
        return []
    clean = []
    for item in items:
        if not (isinstance(item, dict) and item.get("kind") in HIGHLIGHT_KINDS and item.get("interview") is not None
                and str(item.get("quote") or "").strip()):
            report.error(f"{label}: each highlight needs kind ({', '.join(HIGHLIGHT_KINDS)}), interview and quote",
                         code="theme_shape")
            continue
        ref = item["interview"]
        clean.append({"kind": item["kind"], "interview": str(ref).zfill(width) if _is_int(ref) else str(ref),
                      "quote": str(item["quote"])})
    return clean


def _clean_theme(item: Any, label: str, width: int, report: Report) -> Json | None:
    """One theme of the file in a known shape, or None when it is not a mapping."""
    if not isinstance(item, dict):
        report.error(f"{label}: must be a mapping with label, need, why and outcomes", code="theme_shape")
        return None
    unknown = sorted(str(key) for key in set(item) - set(THEME_KEYS))
    if unknown:
        report.error(f"{label}: unknown key {', '.join(unknown)}; a theme holds {', '.join(THEME_KEYS)}",
                     code="theme_shape")
    theme: Json = {"id": str(item.get("id") or "")}
    for key in ("label", "need", "why"):
        theme[key] = str(item.get(key) or "").strip()
        if not theme[key]:
            report.error(f"{label}: {key} is missing", code="theme_shape")
    outcomes = item.get("outcomes")
    if not isinstance(outcomes, list) or not outcomes:
        report.error(f"{label}: outcomes must be a list of outcome IDs, at least one", code="theme_shape")
        outcomes = []
    theme["outcomes"] = list(dict.fromkeys(str(o) for o in outcomes))
    theme["highlights"] = _clean_highlights(item.get("highlights"), label, width, report)
    return theme


def _number_themes(themes: list[Json], before: list[Json], job: str, report: Report) -> None:
    """Keep the IDs the file gives, give a theme with an unchanged label the ID it had, and number the rest."""
    known = {str(t["id"]) for t in before}
    by_label = {str(t.get("label", "")).lower(): str(t["id"]) for t in before}
    given = [t["id"] for t in themes if t["id"]]
    for tid in sorted(set(given)):
        if tid not in known:
            report.error(f"value theme {tid} is not a theme of core job {job}; leave `id` out for a new theme",
                         code="theme_id")
        if given.count(tid) > 1:
            report.error(f"value theme id {tid} is used more than once", code="theme_id")
    taken = set(given)
    for theme in themes:
        same = by_label.get(theme["label"].lower())
        if not theme["id"] and same and same not in taken:
            theme["id"] = same
            taken.add(same)
    number = max([theme_number(t) for t in before], default=0)
    for theme in themes:
        if not theme["id"]:
            number += 1
            theme["id"] = f"{job}.T{number}"


def _check_theme_links(ctx: ThemeChecks, theme: Json, label: str) -> None:
    for oid in theme["outcomes"]:
        target = ctx.outcomes.get(oid)
        if not target:
            ctx.report.error(f"{label}: outcome {oid} is not in the KB; take IDs from `context`",
                             code="theme_outcome")
        elif target.get("merged_into"):
            ctx.report.error(f"{label}: outcome {oid} was merged into {target['merged_into']}; use that one",
                             code="theme_outcome")
        elif job_of(oid) != ctx.job:
            ctx.report.error(f"{label}: outcome {oid} belongs to core job {job_of(oid)}; a theme groups the "
                             f"outcomes of one core job, here {ctx.job}", code="theme_outcome")


def _check_theme_text(ctx: ThemeChecks, theme: Json, label: str) -> None:
    clarity(theme["label"], "theme", f"{label} label", ctx.style, ctx.report)
    clarity(theme["need"], "need", f"{label} need", ctx.style, ctx.report)
    clarity(theme["why"], "rationale", f"{label} why", ctx.style, ctx.report)
    if theme["need"] and not theme["need"].startswith("Help me "):
        ctx.report.error(f"{label}: the need must start with 'Help me', in the customer's voice: '{theme['need']}'",
                         code="theme_need_form")
    text = f"{theme['label']} {theme['need']}".lower()
    named = [name for name in ctx.solutions if name.lower() in text]
    if named:
        ctx.report.warn(f"{label} names a current solution ({', '.join(named)}); a theme states a need, so that "
                        "ideas stay open", code="theme_names_solution")


def _highlight_pool(kb: Json, outcome_ids: list[str]) -> dict[tuple[str, str], Json]:
    """The quotes a theme may show: those on its outcomes, and on the solutions used at its outcomes' steps."""
    outcomes = outcomes_by_id(kb)
    members = [outcomes[o] for o in outcome_ids if o in outcomes]
    steps = {str(o.get("step")) for o in members}
    items = [e for o in members for e in o.get("evidence", [])]
    items += [e for s in live_solutions(kb) for use in uses_of(s) if str(use.get("step")) in steps
              for e in use.get("evidence", [])]
    return {evidence_key(e): e for e in items}


def _check_highlights(ctx: ThemeChecks, theme: Json, label: str) -> None:
    """Every highlight must be a quote the KB already holds, so a theme never shows words nobody said."""
    pool = _highlight_pool(ctx.kb, theme["outcomes"])
    kept = []
    for item in theme["highlights"]:
        found = pool.get(evidence_key(item))
        if not found:
            ctx.report.error(f'{label}: highlight quote from interview {item["interview"]} is not on one of its '
                             f'outcomes, nor on a solution used at their steps: "{short(item["quote"])}"',
                             code="theme_highlight")
            continue
        kept.append({"kind": item["kind"], "interview": str(found["interview"]), "source": found["source"],
                     "quote": found["quote"]})
    theme["highlights"] = kept
    if not theme["highlights"] or len(kept) > THEME_HIGHLIGHTS:
        ctx.report.warn(f"{label} shows {len(kept)} quotes; pick 3 to {THEME_HIGHLIGHTS} that show the pain, the "
                        "struggle and the desire", code="theme_quotes")


def _check_theme_count(ctx: ThemeChecks, themes: list[Json], live: int) -> None:
    low, high = THEME_COUNT
    count, most = len(themes), max(live // THEME_MIN_OUTCOMES, 1)
    if count > most:
        ctx.report.warn(f"{count} value themes for {plural(live, 'outcome')} in core job {ctx.job}: keep at most one "
                        f"theme per {THEME_MIN_OUTCOMES} outcomes, here {most}", code="theme_count")
    elif count > high or (count < low and live >= low * THEME_MIN_OUTCOMES):
        ctx.report.warn(f"{count} value themes in core job {ctx.job}: aim for {low} to {high}, few enough to hold in "
                        "mind and enough to tell needs apart", code="theme_count")


def _check_theme_sizes(ctx: ThemeChecks, themes: list[Json], live: int) -> None:
    for theme in themes:
        size, label = len(theme["outcomes"]), f"theme {theme['id']} '{theme['label']}'"
        if size < THEME_MIN_OUTCOMES:
            ctx.report.warn(f"{label} gathers {plural(size, 'outcome')}; a theme with fewer than "
                            f"{THEME_MIN_OUTCOMES} is often one outcome reworded", code="theme_size")
        elif live >= THEME_COUNT[0] * THEME_MIN_OUTCOMES and size * THEME_MAX_SHARE > live:
            ctx.report.warn(f"{label} gathers {size} of the job's {live} outcomes; split a theme that holds more "
                            f"than one in {THEME_MAX_SHARE}", code="theme_size")
        people = {i for o in theme["outcomes"] for i in ctx.outcomes.get(o, {}).get("interviews", [])}
        if len(people) == 1:
            ctx.report.warn(f"{label} rests on one person; say so when you present it", code="theme_one_person")


def _check_theme_overlap(ctx: ThemeChecks, themes: list[Json]) -> None:
    homes: dict[str, list[str]] = {}
    for theme in themes:
        for oid in theme["outcomes"]:
            homes.setdefault(oid, []).append(theme["id"])
    for oid, where in homes.items():
        if len(where) > THEME_MAX_PER_OUTCOME:
            ctx.report.warn(f"outcome {oid} sits in {len(where)} themes ({', '.join(where)}); keep it in at most "
                            f"{THEME_MAX_PER_OUTCOME}", code="theme_overlap")
    for theme in themes:
        if theme["outcomes"] and all(len(homes[o]) > 1 for o in theme["outcomes"]):
            ctx.report.warn(f"theme {theme['id']} '{theme['label']}' has no outcome of its own; merge it into the "
                            "themes that share its outcomes", code="theme_overlap")


def _check_theme_set(ctx: ThemeChecks, themes: list[Json]) -> None:
    labels = [theme["label"].lower() for theme in themes if theme["label"]]
    for dup in _duplicates(labels):
        ctx.report.error(f"two value themes of core job {ctx.job} share the label '{dup}'", code="theme_duplicate")
    live = len([o for o in ctx.outcomes.values() if not o.get("merged_into") and job_of(o["id"]) == ctx.job])
    if themes:
        _check_theme_count(ctx, themes, live)
    _check_theme_sizes(ctx, themes, live)
    _check_theme_overlap(ctx, themes)


def build_themes(kb: Json, job: str, items: list[Any], before: list[Json], report: Report) -> list[Json]:
    """Check the file's themes against the KB and return them as the KB stores them."""
    solutions = [str(s.get("name")) for s in live_solutions(kb) if s.get("name")]
    ctx = ThemeChecks(kb, job, outcomes_by_id(kb), style_of(kb), report, solutions)
    width = id_width(kb)
    cleaned = [_clean_theme(item, f"themes[{index}]", width, report) for index, item in enumerate(items)]
    themes = [theme for theme in cleaned if theme]
    _number_themes(themes, before, job, report)
    added = {str(t["id"]): t.get("added") for t in before}
    for theme in themes:
        label = f"theme {theme['id']} '{theme['label']}'"
        _check_theme_links(ctx, theme, label)
        _check_theme_text(ctx, theme, label)
        _check_highlights(ctx, theme, label)
    _check_theme_set(ctx, themes)
    return [{"id": t["id"], "job": job, "label": t["label"], "need": t["need"], "why": t["why"],
             "outcomes": t["outcomes"], "highlights": t["highlights"], "added": added.get(t["id"]) or today()}
            for t in themes]


def store_themes(kb: Json, job: str, themes: list[Json]) -> int:
    """Replace the core job's themes, keep those of other core jobs and clear the layer's stale flag. Returns how
    many themes written by hand, with no ID, were dropped."""
    layer = kb.get("value_themes") if isinstance(kb.get("value_themes"), dict) else {}
    old = layer.get("themes") if isinstance(layer.get("themes"), list) else []
    kept = [t for t in themes_of(kb) if str(t.get("job")) != job]
    rest = {k: v for k, v in layer.items() if k not in ("stale", "stale_reasons", "themes", "unassigned")}
    merged = sorted(kept + themes, key=lambda t: (job_index(str(t["job"])), theme_number(t)))
    kb["value_themes"] = {"stale": False, "themes": merged, **rest}
    return len(old) - len(themes_of({"value_themes": layer}))


def theme_changes(before: list[Json], after: list[Json]) -> list[str]:
    """What a new set changes, in words: themes added, removed and reworded, and outcomes that joined or left."""
    old, new = {str(t["id"]): t for t in before}, {str(t["id"]): t for t in after}
    lines = [f"added {tid} {theme['label']}" for tid, theme in new.items() if tid not in old]
    for tid, theme in new.items():
        was = old.get(tid)
        if not was:
            continue
        if any(str(was.get(key, "")) != theme[key] for key in ("label", "need", "why")):
            renamed = f" (was '{was.get('label', '')}')" if was.get("label") != theme["label"] else ""
            lines.append(f"reworded {tid} {theme['label']}{renamed}")
        joined = [o for o in theme["outcomes"] if o not in theme_outcomes(was)]
        left = [o for o in theme_outcomes(was) if o not in theme["outcomes"]]
        if joined or left:
            lines.append(f"{tid} {theme['label']}:" + (f" added {', '.join(joined)}" if joined else "")
                         + (f" removed {', '.join(left)}" if left else ""))
    return lines + [f"removed {tid} {theme.get('label', '')}" for tid, theme in old.items() if tid not in new]


def _themes_text(kb: Json, job: str, themes: list[Json], result: Json) -> list[str]:
    outcomes = outcomes_by_id(kb)
    lines = [f"VALUE THEMES for core job {job}: {jobs_by_id(kb)[job]['statement']}"]
    for theme in themes:
        lines.append(f"{theme['id']} {theme['label']}: {theme['need']}  "
                     f"({plural(len(theme['outcomes']), 'outcome')}, people {theme.get('interview_count', 0)})")
        lines += [f"   {oid:>7}  {outcomes[oid]['statement']}" for oid in theme["outcomes"] if oid in outcomes]
    if result["unassigned"]:
        lines.append(f"IN NO THEME ({len(result['unassigned'])})")
        lines += [f"   {oid:>7}  {outcomes[oid]['statement']}" for oid in result["unassigned"]]
    if result["changes"]:
        lines += ["CHANGES"] + [f"  {line}" for line in result["changes"]]
    if result["legacy_dropped"]:
        lines.append(f"dropped {plural(result['legacy_dropped'], 'theme')} written by hand before this command "
                     "existed; the backup still has them")
    if result["other_jobs"]:
        lines.append(f"themes of core job {', '.join(result['other_jobs'])} were not touched; update them too if "
                     "they are out of date")
    return lines


def _themes_finish(args: argparse.Namespace, report: Report, result: Json, lines: list[str]) -> int:
    result.update({"warnings": report.warnings, "errors": report.errors})
    args.run.add_report(report)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0 if result["ok"] else 1
    lines = lines + [f"WARN {w}" for w in report.warnings]
    if report.errors:
        lines.append(f"\n{len(report.errors)} problem(s); nothing written:")
        lines += [f"  - {e}" for e in report.errors]
    print("\n".join(lines))
    return 0 if result["ok"] else 1


def cmd_themes(args: argparse.Namespace) -> int:
    """Check one core job's value themes and write them. The dry run and the real run share every step up to the
    write."""
    kb = load_kb(args.kb)
    report = Report()
    job, items = read_themes_file(args.themes, kb)
    args.run.note(dry_run=bool(args.dry_run), job=job)
    candidate = copy.deepcopy(kb)
    before = themes_of(kb, job)
    built = build_themes(candidate, job, items, before, report)
    result: Json = {"ok": False, "dry_run": bool(args.dry_run), "job": job, "written": False, "run_id": args.run.id}
    if report.errors:
        return _themes_finish(args, report, result, [])
    legacy = store_themes(candidate, job, built)
    recount(candidate)
    themes = themes_of(candidate, job)
    unassigned = [o for o in candidate["value_themes"].get("unassigned", []) if job_of(o) == job]
    summary = f"value themes of core job {job}: {', '.join(t['id'] for t in themes) or 'none'}"
    candidate["changelog"].append(changelog_entry(args.run, "rebuild", layer="value_themes", job=job,
                                                  themes=[t["id"] for t in themes], summary=summary))
    problems = structure_problems(candidate)
    if problems:
        raise KbError("these themes would break the KB structure; nothing written:\n  - " + "\n  - ".join(problems),
                      code="structure")
    result.update({"ok": True, "themes": themes, "unassigned": unassigned, "legacy_dropped": legacy,
                   "changes": theme_changes(before, themes),
                   "other_jobs": sorted({str(t["job"]) for t in themes_of(candidate)} - {job})})
    args.run.note(counts={"themes": len(themes), "theme_outcomes": len({o for t in themes for o in t["outcomes"]}),
                          "unassigned": len(unassigned)})
    lines = _themes_text(candidate, job, themes, result)
    if args.dry_run:
        lines.append("dry run OK: every outcome and every quote is in the KB; nothing written")
    else:
        result["backup"] = backup(args.kb)
        save_kb(candidate, args.kb)
        result["written"] = True
        args.run.note(written=True, backup=args.run.relative(result["backup"]))
        lines += [f"wrote {summary}", f"backup: {result['backup']}"]
    return _themes_finish(args, report, result, lines)


# ---------- overview ----------
# The overview tells one core job's study as a short story for someone new to the method: a bottom line, the
# people, how they work today, where that falls short, and what to do next. `overview` writes it, one core job at a
# time. The map counts the unmet needs and ranks the themes itself; this layer holds only the sentences the
# assistant writes, and every quote in it is one the KB already holds.
@dataclass
class OverviewChecks:
    """What the checks of one core job's overview need at hand."""

    kb: Json
    job: str
    style: Style
    report: Report
    pool: dict[tuple[str, str], Json]  # every quote the KB holds for this core job
    width: int


def overviews_of(kb: Json, job: str | None = None) -> list[Json]:
    layer = kb.get("overview")
    items = layer.get("jobs") if isinstance(layer, dict) else None
    found = [o for o in items if isinstance(o, dict) and o.get("job")] if isinstance(items, list) else []
    return [o for o in found if job is None or str(o["job"]) == job]


def _own_statements(record: Json) -> list[Json]:
    lists = [record.get(key) or [] for key in ("related_jobs", "emotional_jobs", "social_jobs")]
    items = [record.get("job_executor"), record.get("core_functional_job")] + [s for group in lists for s in group]
    return [s for s in items if isinstance(s, dict)]


def _overview_pool(kb: Json, job: str) -> dict[tuple[str, str], Json]:
    """The quotes an overview may show: those on the core job's steps, outcomes and solution uses, and what the
    people linked to it said about themselves."""
    steps = [s for s in kb["job_map"]["steps"] if str(s["job"]) == job]
    keys = {step_key(s) for s in steps}
    items = [e for s in steps for e in s.get("evidence", [])]
    items += [e for o in kb["desired_outcomes"]["outcomes"]
              if not o.get("merged_into") and job_of(o["step"]) == job for e in o.get("evidence", [])]
    items += [e for s in live_solutions(kb) for use in uses_of(s) if str(use.get("step")) in keys
              for e in use.get("evidence", [])]
    for record in kb["interviews"]:
        if main_job(record) == job or job in related_links(record):
            items += [{**e, "interview": str(record["id"])} for s in _own_statements(record)
                      for e in s.get("evidence") or [] if isinstance(e, dict)]
    return {evidence_key(e): e for e in items if isinstance(e, dict)}


def read_overview_file(path: str, kb: Json) -> tuple[str, Json]:
    data = load_yaml(path)
    if not isinstance(data, dict) or not data.get("job"):
        raise KbError(f"{path} must be a mapping with `job` (a core job ID such as A) and the overview of that core "
                      f"job: {', '.join(OVERVIEW_KEYS[1:])}", code="overview_file")
    unknown = sorted(str(key) for key in set(data) - set(OVERVIEW_KEYS))
    if unknown:
        raise KbError(f"{path}: unknown key {', '.join(unknown)}; the file holds {', '.join(OVERVIEW_KEYS)}",
                      code="overview_file")
    job = str(data["job"])
    if job not in jobs_by_id(kb):
        raise KbError(f"{path}: core job {job} is not in the KB", code="overview_file")
    return job, data


def _ov_text(ctx: OverviewChecks, data: Any, key: str, kind: str, label: str, *,
             required: bool = True) -> str:
    """One sentence of the overview, checked against the writing rules."""
    value = data.get(key) if isinstance(data, dict) else None
    text = str(value).strip() if isinstance(value, (str, int, float)) else ""
    if not text:
        if required:
            ctx.report.error(f"{label}: {key} is missing", code="overview_shape")
        return ""
    clarity(text, kind, f"{label} {key}", ctx.style, ctx.report)
    _ov_no_score(ctx, text, f"{label} {key}")
    return text


def _ov_no_score(ctx: OverviewChecks, text: str, label: str) -> None:
    """Interviews show what people said, not how much it matters: an overview carries no score and no percentage."""
    if SCORE_WORDS.search(text):
        ctx.report.error(f"{label}: no percentages and no score words in an overview; say how many people said it: "
                         f"'{text}'", code="overview_score")


def _ov_mapping(ctx: OverviewChecks, data: Any, key: str, allowed: tuple[str, ...], label: str) -> Json:
    section = data.get(key) if isinstance(data, dict) else None
    if not isinstance(section, dict):
        ctx.report.error(f"{label}: {key} must be a mapping with {', '.join(allowed)}", code="overview_shape")
        return {}
    unknown = sorted(str(k) for k in set(section) - set(allowed))
    if unknown:
        ctx.report.error(f"{label}: {key} has unknown key {', '.join(unknown)}; it holds {', '.join(allowed)}",
                         code="overview_shape")
    return section


def _ov_quote(ctx: OverviewChecks, item: Any, label: str) -> Json | None:
    """A quote of the overview as the KB holds it, so the overview never shows words nobody said."""
    if not (isinstance(item, dict) and item.get("interview") is not None and str(item.get("quote") or "").strip()):
        ctx.report.error(f"{label}: quote needs interview and quote", code="overview_shape")
        return None
    ref = item["interview"]
    key = {"interview": str(ref).zfill(ctx.width) if _is_int(ref) else str(ref), "quote": str(item["quote"])}
    found = ctx.pool.get(evidence_key(key))
    if not found:
        ctx.report.error(f'{label}: the quote from interview {key["interview"]} is not in the KB for core job '
                         f'{ctx.job}; copy one from a step, an outcome, a solution or the person: '
                         f'"{short(key["quote"])}"', code="overview_quote")
        return None
    return {"interview": str(found["interview"]), "source": found.get("source", "transcript"),
            "quote": found["quote"]}


def _ov_section(ctx: OverviewChecks, data: Json, key: str, quote: bool = False) -> Json:
    """A step of the story: the answer in one sentence, an optional explanation, and for the people a quote."""
    allowed = ("answer", "text", "quote") if quote else ("answer", "text")
    section = _ov_mapping(ctx, data, key, allowed, "overview")
    out: Json = {"answer": _ov_text(ctx, section, "answer", "headline", key)}
    text = _ov_text(ctx, section, "text", "finding", key, required=False)
    if text:
        out["text"] = text
    if quote and section.get("quote") is not None:
        found = _ov_quote(ctx, section["quote"], key)
        if found:
            out["quote"] = found
    return out


def _ov_gap_solutions(ctx: OverviewChecks, item: Json, label: str) -> list[str]:
    given = item.get("solutions")
    if given is None:
        return []
    if not isinstance(given, list):
        ctx.report.error(f"{label}: solutions must be a list of solution IDs such as S3", code="overview_shape")
        return []
    known = {str(s.get("id")) for s in live_solutions(ctx.kb)}
    ids = list(dict.fromkeys(str(s) for s in given))
    for sid in ids:
        if sid not in known:
            ctx.report.error(f"{label}: solution {sid} is not a solution in use in the KB; take IDs from `context`",
                             code="overview_solution")
    return [sid for sid in ids if sid in known]


def _ov_gap(ctx: OverviewChecks, item: Any, label: str) -> Json | None:
    keys = ("label", "text", "kind", "solutions", "quote")
    if not isinstance(item, dict):
        ctx.report.error(f"{label}: must be a mapping with {', '.join(keys)}", code="overview_shape")
        return None
    unknown = sorted(str(k) for k in set(item) - set(keys))
    if unknown:
        ctx.report.error(f"{label}: unknown key {', '.join(unknown)}; a gap holds {', '.join(keys)}",
                         code="overview_shape")
    gap: Json = {"label": _ov_text(ctx, item, "label", "theme", label),
                 "text": _ov_text(ctx, item, "text", "rationale", label), "kind": str(item.get("kind") or "")}
    if gap["kind"] not in GAP_KINDS:
        ctx.report.error(f"{label}: kind must be one of {', '.join(GAP_KINDS)}", code="overview_shape")
    gap["solutions"] = _ov_gap_solutions(ctx, item, label)
    quote = _ov_quote(ctx, item.get("quote"), label)
    if quote:
        gap["quote"] = quote
    return gap


def _ov_gaps(ctx: OverviewChecks, data: Json) -> Json:
    section = _ov_mapping(ctx, data, "gaps", ("answer", "items"), "overview")
    items = section.get("items")
    if not isinstance(items, list) or not items:
        ctx.report.error("gaps: items must be a list with at least one gap", code="overview_shape")
        items = []
    gaps = [g for g in (_ov_gap(ctx, item, f"gaps.items[{index}]") for index, item in enumerate(items)) if g]
    if len(gaps) > GAP_MAX:
        ctx.report.warn(f"{len(gaps)} gaps; keep at most {GAP_MAX}, the ones most people described",
                        code="overview_count")
    for dup in _duplicates([g["label"].lower() for g in gaps if g["label"]]):
        ctx.report.error(f"two gaps share the label '{dup}'", code="overview_shape")
    return {"answer": _ov_text(ctx, section, "answer", "headline", "gaps"), "items": gaps}


def _ov_list(ctx: OverviewChecks, track: Json, key: str, label: str) -> list[str]:
    given = track.get(key)
    if not isinstance(given, list) or not given or not all(isinstance(x, str) and x.strip() for x in given):
        ctx.report.error(f"{label}: {key} must be a list of 1 to {NEXT_LISTS[key]} sentences", code="overview_shape")
        return []
    items = [x.strip() for x in given]
    if len(items) > NEXT_LISTS[key]:
        ctx.report.error(f"{label}: {key} holds {len(items)} items; keep at most {NEXT_LISTS[key]}",
                         code="overview_count")
    for text in items:
        clarity(text, "rationale", f"{label} {key}", ctx.style, ctx.report)
        _ov_no_score(ctx, text, f"{label} {key}")
    return items


def _ov_words(ctx: OverviewChecks, words: list[str], label: str) -> None:
    """The customers' words to reuse in messaging must be words a customer said."""
    said = [norm(str(e.get("quote", ""))).lower() for e in ctx.pool.values()]
    for text in words:
        needle = norm(text).lower().strip(" .!?\"'")
        if not any(needle in quote for quote in said):
            ctx.report.error(f'{label}: "{short(text)}" is not part of a quote in the KB for core job {ctx.job}; '
                             "use the customers' exact words", code="overview_quote")


def _ov_track(ctx: OverviewChecks, data: Json, name: str) -> Json:
    statuses, fields = NEXT_TRACKS[name]
    label = f"next.{name}"
    track = _ov_mapping(ctx, data, name, ("status", "action", *fields), "next")
    out: Json = {"status": str(track.get("status") or ""), "action": _ov_text(ctx, track, "action", "action", label)}
    if out["status"] not in statuses:
        ctx.report.error(f"{label}: status must be one of {', '.join(statuses)}", code="overview_shape")
    for key in fields:
        out[key] = _ov_list(ctx, track, key, label) if key in NEXT_LISTS else \
            _ov_text(ctx, track, key, "rationale", label)
    if out.get("words"):
        _ov_words(ctx, out["words"], label)
    return out


def build_overview(kb: Json, job: str, data: Json, report: Report) -> Json:
    """Check the file's overview against the KB and return it as the KB stores it."""
    ctx = OverviewChecks(kb, job, style_of(kb), report, _overview_pool(kb, job), id_width(kb))
    entry: Json = {"job": job, "bottom_line": _ov_text(ctx, data, "bottom_line", "headline", "overview"),
                   "why": _ov_text(ctx, data, "why", "rationale", "overview"),
                   "opening": _ov_text(ctx, data, "opening", "rationale", "overview"),
                   "people": _ov_section(ctx, data, "people", quote=True), "today": _ov_section(ctx, data, "today"),
                   "gaps": _ov_gaps(ctx, data), "needs": _ov_section(ctx, data, "needs"),
                   "focus": _ov_section(ctx, data, "focus")}
    steps = _ov_mapping(ctx, data, "next", tuple(NEXT_TRACKS), "overview")
    entry["next"] = {name: _ov_track(ctx, steps, name) for name in NEXT_TRACKS}
    entry["written"] = today()
    return entry


def store_overview(kb: Json, entry: Json) -> None:
    """Replace the core job's overview, keep those of other core jobs and clear the layer's stale flag."""
    layer = kb.get("overview") if isinstance(kb.get("overview"), dict) else {}
    kept = [o for o in overviews_of(kb) if str(o["job"]) != entry["job"]]
    rest = {k: v for k, v in layer.items() if k not in ("stale", "stale_reasons", "jobs")}
    kb["overview"] = {"stale": False, "jobs": sorted(kept + [entry], key=lambda o: job_index(str(o["job"]))),
                      **rest}


def _recount_overview(kb: Json, names: dict[str, str]) -> None:
    for entry in overviews_of(kb):
        gaps = entry.get("gaps") if isinstance(entry.get("gaps"), dict) else {}
        people = entry.get("people") if isinstance(entry.get("people"), dict) else {}
        holders = [people] + [g for g in gaps.get("items") or [] if isinstance(g, dict)]
        for quote in [h.get("quote") for h in holders]:
            if isinstance(quote, dict):
                quote["name"] = names.get(str(quote.get("interview")), quote.get("name", ""))


def _overview_problems(kb: Json, jobs: dict[str, Json]) -> list[str]:
    """Cross-references of the overview layer that the schema cannot express."""
    entries = overviews_of(kb)
    problems = [f"overview of core job {dup} is there more than once"
                for dup in _duplicates([str(o["job"]) for o in entries])]
    for entry in entries:
        job = str(entry["job"])
        if job not in jobs:
            problems.append(f"overview: core job {job} does not exist")
        if not str(entry.get("bottom_line") or "").strip():
            problems.append(f"overview of core job {job}: bottom_line is missing")
    return problems


def _overview_text(kb: Json, entry: Json, result: Json) -> list[str]:
    job = entry["job"]
    lines = [f"OVERVIEW for core job {job}: {jobs_by_id(kb)[job]['statement']}",
             f"bottom line: {entry['bottom_line']}", f"opening: {entry['opening']}"]
    lines += [f"{key}: {entry[key]['answer']}" for key in ("people", "today", "gaps", "needs", "focus")]
    lines += [f"   gap ({g['kind']}): {g['label']}" for g in entry["gaps"]["items"]]
    lines += [f"next, {name} ({track['status']}): {track['action']}" for name, track in entry["next"].items()]
    if result["other_jobs"]:
        lines.append(f"the overview of core job {', '.join(result['other_jobs'])} was not touched; update it too if "
                     "it is out of date")
    if result["missing_jobs"]:
        lines.append(f"core job {', '.join(result['missing_jobs'])} has no overview yet")
    return lines


def cmd_overview(args: argparse.Namespace) -> int:
    """Check one core job's overview and write it. The dry run and the real run share every step up to the write."""
    kb = load_kb(args.kb)
    report = Report()
    job, data = read_overview_file(args.overview, kb)
    args.run.note(dry_run=bool(args.dry_run), job=job)
    candidate = copy.deepcopy(kb)
    entry = build_overview(candidate, job, data, report)
    result: Json = {"ok": False, "dry_run": bool(args.dry_run), "job": job, "written": False, "run_id": args.run.id}
    if report.errors:
        return _themes_finish(args, report, result, [])
    store_overview(candidate, entry)
    recount(candidate)
    summary = f"overview of core job {job}"
    candidate["changelog"].append(changelog_entry(args.run, "rebuild", layer="overview", job=job, summary=summary))
    problems = structure_problems(candidate)
    if problems:
        raise KbError("this overview would break the KB structure; nothing written:\n  - " + "\n  - ".join(problems),
                      code="structure")
    written = {str(o["job"]) for o in overviews_of(candidate)}
    result.update({"ok": True, "overview": overviews_of(candidate, job)[0], "other_jobs": sorted(written - {job}),
                   "missing_jobs": sorted(set(jobs_by_id(candidate)) - written)})
    args.run.note(counts={"overview_gaps": len(entry["gaps"]["items"]), "overviews": len(written)})
    lines = _overview_text(candidate, entry, result)
    if args.dry_run:
        lines.append("dry run OK: every quote and every solution is in the KB; nothing written")
    else:
        result["backup"] = backup(args.kb)
        save_kb(candidate, args.kb)
        result["written"] = True
        args.run.note(written=True, backup=args.run.relative(result["backup"]))
        lines += [f"wrote {summary}", f"backup: {result['backup']}"]
    return _themes_finish(args, report, result, lines)


# ---------- init, context ----------
def cmd_init(args: argparse.Namespace) -> int:
    if not at_home(args.kb):
        raise KbError(f"a study lives in {KB_HOME} at the root of the workspace: run `kb_tool.py init {KB_HOME}` "
                      f"from there, not init {args.kb}", code="kb_location")
    if os.path.exists(args.kb):
        raise KbError(f"{args.kb} exists; refusing to overwrite", code="kb_exists")
    kb = ensure({"meta": {"project": args.project, "method": "Outcome-Driven Innovation (Ulwick)",
                          "interviewer": args.interviewer or "", "created": today(), "interview_count": 0}})
    kb["job_map"]["stages"] = [{"key": k, "name": k.capitalize()} for k in STAGES]
    kb["changelog"].append(changelog_entry(args.run, "init"))
    folder = os.path.dirname(os.path.abspath(args.kb))
    os.makedirs(folder, exist_ok=True)
    save_kb(kb, args.kb)
    args.run.note(written=True)
    note = git_note(args.kb)
    args.run.note(git=bool(note))
    print(f"created {args.kb}" + (f"\n{note}" if note else ""))
    return 0


def _job_steps(kb: Json, job: str) -> list[Json]:
    by_step: dict[str, list[Json]] = {}
    for outcome in kb["desired_outcomes"]["outcomes"]:
        if not outcome.get("merged_into"):
            by_step.setdefault(str(outcome["step"]), []).append(outcome)
    steps = sorted((s for s in kb["job_map"]["steps"] if s.get("job") == job), key=lambda s: int(s["n"]))
    return [{"id": step_key(step), "stage": step.get("stage", ""), "statement": step["statement"],
             "coverage": step.get("coverage", 0),
             "outcomes": [{"id": o["id"], "statement": o["statement"], "interview_count": o.get("interview_count", 0)}
                          for o in by_step.get(step_key(step), [])]}
            for step in steps]


def people_data(kb: Json) -> list[Json]:
    """Each interview with its own core job and the core jobs it is linked to. The basis for abstracting jobs."""
    return [{"id": str(r["id"]), "name": r.get("name", ""),
             "core_functional_job": (r.get("core_functional_job") or {}).get("statement", ""), "job": main_job(r),
             "unlinked_reason": unlinked_reason(r),
             "related": [{"statement": j.get("statement", ""), "job": j.get("job")}
                         for j in r.get("related_jobs") or [] if isinstance(j, dict)],
             "analyst_note": r.get("analyst_note", "")}
            for r in kb["interviews"]]


def context_data(kb: Json) -> Json:
    jobs = [{"id": str(job["id"]), "statement": job["statement"], "status": job.get("status", ""),
             "job_executor": job.get("job_executor", ""), "interviews": job.get("interviews", []),
             "related_interviews": job.get("related_interviews", []), "steps": _job_steps(kb, str(job["id"]))}
            for job in kb["core_jobs"]]
    people = people_data(kb)
    return {"project": kb["meta"].get("project", ""), "interview_count": len(kb["interviews"]),
            "core_jobs": jobs, "people": people, "unlinked": [p["id"] for p in people if not p["job"]],
            "segments": {k: v.get("name", "") for k, v in (kb.get("clusters") or {}).items()},
            "processed_files": sorted(interviews_by_file(kb)),
            "pending_proposals": [{"id": p["id"], "type": p["type"], "target": p.get("target") or p.get("job") or "",
                                   "proposal": p.get("proposal", "")}
                                  for p in kb["proposed_changes"] if p.get("status") == "pending"],
            "current_solutions": solutions_data(kb), "value_themes": themes_data(kb),
            "overview": [{"job": str(o["job"]), "bottom_line": o.get("bottom_line", ""),
                          "written": o.get("written", "")} for o in overviews_of(kb)],
            "stale": stale_layers(kb), "schema_version": kb["meta"].get("schema_version"),
            "tool_version": __version__}


def solutions_data(kb: Json) -> Json:
    """The groups and the live solutions, with the steps each is used for: what a new batch is matched against."""
    groups = [{"key": key, "name": group.get("name", ""), "why": group.get("why", ""),
               "solutions": group.get("solutions", [])} for key, group in groups_of(kb).items()]
    solutions = [{"id": str(s.get("id")), "name": s.get("name", ""), "kind": s.get("kind", ""),
                  "group": s.get("group", ""), "steps": solution_steps(s), "interviews": s.get("interviews", []),
                  "stopped_by": s.get("stopped_by", [])} for s in live_solutions(kb)]
    return {"groups": groups, "solutions": solutions}


def themes_data(kb: Json) -> Json:
    """The value themes with the text of their outcomes, and the outcomes that sit in no theme yet."""
    outcomes = outcomes_by_id(kb)

    def texts(ids: list[str]) -> list[Json]:
        return [{"id": oid, "statement": outcomes[oid]["statement"]} for oid in ids if oid in outcomes]

    themes = [{"id": str(t["id"]), "job": str(t.get("job")), "label": t.get("label", ""), "need": t.get("need", ""),
               "why": t.get("why", ""), "outcomes": texts(theme_outcomes(t)),
               "interview_count": t.get("interview_count", 0)} for t in themes_of(kb)]
    return {"themes": themes, "unassigned": texts(unassigned_outcomes(kb))}


def _print_themes(data: Json, stale: bool) -> None:
    if not data["themes"]:
        return
    print("\nVALUE THEMES" + (" [out of date]" if stale else "")
          + " (when you update them, keep each ID, label and need unless there is a reason to change it)")
    for theme in data["themes"]:
        print(f"{theme['id']} {theme['label']}: {theme['need']}  (people {theme['interview_count']})")
        for outcome in theme["outcomes"]:
            print(f"   {outcome['id']:>7}  {outcome['statement']}")
    if data["unassigned"]:
        print("IN NO THEME YET")
        for outcome in data["unassigned"]:
            print(f"   {outcome['id']:>7}  {outcome['statement']}")


def _person_line(person: Json) -> str:
    links = person["job"] or "no core job" + (f" ({person['unlinked_reason']})" if person["unlinked_reason"] else "")
    also = sorted({r["job"] for r in person["related"] if r["job"] and r["job"] != person["job"]})
    return f"  {person['id']} {person['name']}: {person['core_functional_job']} -> {links}" + \
        (f"; also {', '.join(also)}" if also else "")


def _print_jobs(data: Json) -> None:
    print(f"PROJECT {data['project']}  interviews={data['interview_count']}  core jobs={len(data['core_jobs'])}")
    if not data["core_jobs"]:
        print("CORE JOB: (none yet: bootstrap)")
    for job in data["core_jobs"]:
        print(f"\nCORE JOB {job['id']}: {job['statement']}  [{job['status']}]")
        if job["job_executor"]:
            print(f"  EXECUTOR: {job['job_executor']}")
        main, also = ", ".join(job["interviews"]) or "none", ", ".join(job["related_interviews"]) or "none"
        print(f"  PEOPLE: main {main}; also {also}")
        for step in job["steps"]:
            print(f"STEP {step['id']} [{step['stage']}] {step['statement']}  (interviews {step['coverage']})")
            for outcome in step["outcomes"]:
                print(f"   {outcome['id']:>7}  {outcome['statement']}  (iv {outcome['interview_count']})")


def _print_solutions(data: Json) -> None:
    if not (data["groups"] or data["solutions"]):
        return
    print("\nCURRENT SOLUTIONS (cite an ID in solution_evidence; add only what is not here to new_solutions)")
    for group in data["groups"]:
        print(f"GROUP {group['key']}: {group['name']}. Why: {group['why']}")
        for solution in [s for s in data["solutions"] if s["group"] == group["key"]]:
            stopped = f", stopped {len(solution['stopped_by'])}" if solution["stopped_by"] else ""
            mark = "  [stopped]" if not solution["interviews"] else ""
            print(f"  {solution['id']} [{solution['kind']}] {solution['name']}  steps {', '.join(solution['steps'])}"
                  f"  (people {len(solution['interviews'])}{stopped}){mark}")


def cmd_context(args: argparse.Namespace) -> int:
    data = context_data(load_kb(args.kb))
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        return 0
    _print_jobs(data)
    _print_solutions(data["current_solutions"])
    _print_themes(data["value_themes"], "value_themes" in data["stale"])
    if data["overview"]:
        print("\nOVERVIEW" + (" [out of date]" if "overview" in data["stale"] else ""))
        for entry in data["overview"]:
            print(f"{entry['job']} written {entry['written']}: {entry['bottom_line']}")
    if data["segments"]:
        print("\nSEGMENTS: " + "; ".join(f"{k}={v}" for k, v in data["segments"].items()))
    if data["people"]:
        print("\nPEOPLE AND THEIR JOBS (their own core job -> the core job it rolls up to)")
        for person in data["people"]:
            print(_person_line(person))
    print("\nPROCESSED FILES: " + ", ".join(data["processed_files"]))
    if data["pending_proposals"]:
        pending = "; ".join(f"{p['id']} {p['type']} {p['target']}" for p in data["pending_proposals"])
        print(f"\nPENDING PROPOSALS: {pending}")
    if data["stale"]:
        print("\nSTALE LAYERS: " + ", ".join(data["stale"]))
    return 0


# ---------- review ----------
def describe_proposal(proposal: Json) -> str:
    return {"new_step": f"Add a step to core job {proposal.get('job')}",
            "reword_step": f"Reword step {proposal.get('target')}",
            "reword_outcome": f"Reword outcome {proposal.get('target')}",
            "reword_core_job": f"Reword core job {proposal.get('target')}",
            "merge_outcomes": f"Merge outcome {proposal.get('merge')} into {proposal.get('target')}",
            "move_outcome": f"Move outcome {proposal.get('target')} to step {proposal.get('to_step')}",
            "new_segment": "Add a segment", "new_core_job": "Add a core job",
            "confirm_core_job": f"Confirm core job {proposal.get('target')}",
            "move_step": f"Move step {proposal.get('target')} to core job {proposal.get('to_job')}",
            "relink_interview": f"Link interview {proposal.get('target')} to "
                                + (f"core job {proposal['job']}" if proposal.get("job") else "no core job"),
            "merge_solutions": f"Merge solution {proposal.get('merge')} into {proposal.get('target')}",
            "move_solution": f"Move solution {proposal.get('target')} to group {proposal.get('to_group')}",
            "reword_solution": f"Rename solution {proposal.get('target')}",
            "reword_solution_group": f"Rename solution group {proposal.get('target')}",
            }.get(str(proposal.get("type")), "Change")


def _review_head(kb: Json, live_outcomes: list[Json]) -> list[str]:
    in_use = [s for s in live_solutions(kb) if s.get("interviews")]
    solutions = f" · {len(in_use)} solutions in use" if "current_solutions" in kb else ""
    lines = [f"# {kb['meta'].get('project', 'ODI study')}: review sheet", "",
             f"{len(kb['interviews'])} interviews · {len(kb['core_jobs'])} core jobs · "
             f"{len(kb['job_map']['steps'])} job steps · {len(live_outcomes)} outcomes{solutions} · updated {today()}",
             ""]
    if not kb["core_jobs"]:
        return lines + ["**Core job:** not set yet", ""]
    for job in kb["core_jobs"]:
        lines.append(f"- **Core job {job['id']}:** {job['statement']}"
                     + (" *(proposed)*" if job.get("status") == "proposed" else ""))
    return lines + [""]


def _review_decisions(kb: Json) -> list[str]:
    pending = [p for p in kb["proposed_changes"] if p.get("status") == "pending"]
    lines = ["## Decisions waiting for you", ""]
    if not pending:
        return lines + ["None.", ""]
    for proposal in pending:
        lines.append(f"- **{proposal['id']} · {describe_proposal(proposal)}:** {proposal['proposal']}. "
                     f"*Why:* {proposal['rationale']}")
    return lines + ["", "Reply approve or reject for each, by ID.", ""]


def _new_solution_lines(kb: Json, since: str) -> list[str]:
    groups = groups_of(kb)
    lines = [f"- New solution group **{group.get('name', '')}:** {group.get('why', '')}"
             for group in groups.values() if since and str(group.get("added", "")) >= since]
    for solution in live_solutions(kb):
        if since and str(solution.get("added", "")) >= since:
            group = groups.get(str(solution.get("group")), {}).get("name", solution.get("group"))
            lines.append(f"- New solution **{solution['id']} {solution.get('name', '')}** "
                         f"({KIND_LABELS.get(str(solution.get('kind')), solution.get('kind'))}), in *{group}*")
    return lines


def _review_new(kb: Json, since: str, new_outcomes: set[str]) -> list[str]:
    new_interviews = [i for i in kb["interviews"] if since and str(i.get("added", "")) >= since]
    solution_lines = _new_solution_lines(kb, since)
    if not (new_interviews or new_outcomes or solution_lines):
        return []
    lines = [f"## New since {since}", ""]
    for record in new_interviews:
        link = f"core job {main_job(record)}" if main_job(record) else "no core job yet"
        lines.append(f"- **{record['id']} {record.get('name', '')}:** {record['job_executor']['statement']} "
                     f"Core job: *{record['core_functional_job']['statement']}* ({link})")
    for outcome in kb["desired_outcomes"]["outcomes"]:
        if outcome["id"] in new_outcomes:
            lines.append(f"- New outcome **{outcome['id']}:** {outcome['statement']}")
    return lines + solution_lines + [""]


def _review_map(kb: Json, live_outcomes: list[Json], new_outcomes: set[str]) -> list[str]:
    by_step: dict[str, list[Json]] = {}
    for outcome in live_outcomes:
        by_step.setdefault(str(outcome["step"]), []).append(outcome)
    lines: list[str] = []
    for index, job in enumerate(kb["core_jobs"]):
        lines += [f"## Core job {job['id']}: {job['statement']}", ""]
        if index == 0:
            lines += ["Numbers in brackets show how many interviews support each line. ● marks what is new.", ""]
        ordered = sorted((s for s in kb["job_map"]["steps"] if s.get("job") == job["id"]), key=lambda s: int(s["n"]))
        for stage in STAGES:
            steps = [s for s in ordered if s.get("stage") == stage]
            if not steps:
                continue
            lines.append(f"### {stage.capitalize()}")
            for step in steps:
                lines.append(f"**{step_key(step)} {step['statement']}** [{step.get('coverage', 0)}]")
                for outcome in by_step.get(step_key(step), []):
                    mark = "● " if outcome["id"] in new_outcomes else ""
                    count = outcome.get("interview_count", 0)
                    lines.append(f"- {mark}{outcome['id']} {outcome['statement']} [{count}]")
                lines.append("")
    return lines


def _solution_line(solution: Json, steps: dict[str, Json], names: dict[str, str]) -> str:
    used = ", ".join(f"{steps[s]['statement']} ({s})" if s in steps else s for s in solution_steps(solution))
    people = ", ".join(names.get(i, i) for i in solution.get("interviews", []))
    stopped = ", ".join(names.get(i, i) for i in solution.get("stopped_by", []))
    kind = KIND_LABELS.get(str(solution.get("kind")), str(solution.get("kind")))
    return (f"- **{solution['id']} {solution.get('name', '')}** ({kind}) [{len(solution.get('interviews', []))}] "
            f"{people or 'nobody now'} · {plural(solution.get('quote_count', 0), 'mention')} · used for: {used}"
            + (f" · stopped: {stopped}" if stopped else ""))


def plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def _review_solutions(kb: Json) -> list[str]:
    solutions = live_solutions(kb)
    if not solutions:
        return []
    steps, names = steps_by_id(kb), {str(r["id"]): str(r.get("name", "")) for r in kb["interviews"]}
    lines = ["## Current solutions", "", "What people use today to get a step done, grouped by the work they compete "
             "for. Numbers in brackets show how many people use each one now.", ""]
    for key, group in groups_of(kb).items():
        members = sorted((s for s in solutions if s.get("group") == key and s.get("interviews")),
                         key=lambda s: (-len(s.get("interviews", [])), -s.get("quote_count", 0)))
        if members:
            lines += [f"### {group.get('name', key)}", "", f"*Why grouped:* {group.get('why', '')}", ""]
            lines += [_solution_line(s, steps, names) for s in members] + [""]
    gone = [s for s in solutions if not s.get("interviews")]
    if gone:
        lines += ["### Stopped using", "", "Nobody interviewed uses these any more. The quotes say why.", ""]
        lines += [_solution_line(s, steps, names) for s in gone] + [""]
    return lines


def _review_themes(kb: Json) -> list[str]:
    themes = themes_of(kb)
    if not themes:
        return []
    outcomes = outcomes_by_id(kb)

    def rows(ids: list[str]) -> list[str]:
        return [f"- {outcomes[o]['statement']} ({o}) [{outcomes[o].get('interview_count', 0)}]"
                for o in ids if o in outcomes]

    stale = " They are out of date: outcomes were added or changed since." if "value_themes" in stale_layers(kb) \
        else ""
    lines = ["## Value themes", "", "Needs that group the outcomes, to sort ideas into. Numbers in brackets show how "
             f"many people voiced a theme's outcomes: a signal from interviews, not a survey score.{stale}", ""]
    many = len(kb["core_jobs"]) > 1
    for theme in sorted(themes, key=lambda t: (job_index(str(t["job"])), -t.get("interview_count", 0))):
        where = f" (core job {theme['job']})" if many else ""
        lines += [f"### {theme.get('label', '')} [{theme.get('interview_count', 0)}]{where}", "",
                  f"*{theme.get('need', '')}*", ""]
        lines += ([theme["why"], ""] if theme.get("why") else []) + rows(theme_outcomes(theme)) + [""]
    left = unassigned_outcomes(kb)
    if left:
        lines += ["### In no theme yet", ""] + rows(left) + [""]
    return lines


def _review_people(kb: Json) -> list[str]:
    jobs = jobs_by_id(kb)
    named = [r for r in kb["interviews"] if main_job(r) or related_links(r)] if len(jobs) > 1 else []
    lines = []
    if named:
        lines += ["## People and their jobs", ""]
        for record in named:
            parts = [f"{jobs[j]['statement']} ({j})" for j in [main_job(record)] if j and j in jobs]
            also = [f"{jobs[j]['statement']} ({j})" for j in dict.fromkeys(related_links(record))
                    if j in jobs and j != main_job(record)]
            text = ", ".join(parts) + (", also " if parts and also else "also " if also else "") + ", ".join(also)
            lines.append(f"- **{record['id']} {record.get('name', '')}:** {text}")
        lines.append("")
    unlinked = [r for r in kb["interviews"] if not main_job(r)]
    if unlinked:
        lines += ["## Not linked to any core job", ""]
        for record in unlinked:
            note = unlinked_reason(record) or record.get("analyst_note") or record["core_functional_job"]["statement"]
            lines.append(f"- **{record['id']} {record.get('name', '')}:** {note}")
        lines.append("")
    return lines


ASK_NEXT = 5  # steps per core job that "ask about these next" names


def ask_next(kb: Json, job: str) -> tuple[list[Json], int]:
    """The core job's thin steps that fewest people support, at most ASK_NEXT of them, and how many thin ones are left
    out. After a small first batch every step is thin, so the list has to choose."""
    thin = sorted((s for s in thin_steps(kb) if s.get("job") == job),
                  key=lambda s: (s.get("coverage", 0), step_sort_key(step_key(s))))
    return thin[:ASK_NEXT], max(len(thin) - ASK_NEXT, 0)


def _review_tail(kb: Json) -> list[str]:
    lines = []
    picks = [(job, *ask_next(kb, str(job["id"]))) for job in kb["core_jobs"]]
    if any(steps for _, steps, _ in picks):
        lines += ["## Ask about these next", "", f"The steps that fewest interviews support (fewer than {THIN_STEP}), "
                  f"at most {ASK_NEXT} per core job:", ""]
    for job, steps, rest in picks:
        if steps and len(kb["core_jobs"]) > 1:
            lines.append(f"**{job['statement']} ({job['id']})**")
        lines += [f"- {step_key(s)} {s['statement']} [{s.get('coverage', 0)}]" for s in steps]
        if rest:
            lines.append(f"- *{plural(rest, 'more step')} with fewer than {THIN_STEP}*")
        if steps:
            lines.append("")
    stale = [k.replace("_", " ") for k in stale_layers(kb)]
    if stale:
        lines += [f"*Out of date until rebuilt: {', '.join(stale)}.*", ""]
    lines += ["---", "", f"*Made with [{BRAND}]({SITE}), the free ODI skill for AI assistants. "
                         f"Get the full {BRAND} experience at [productweaver.com]({SITE}).*", ""]
    return lines


def review_lines(kb: Json, since: str) -> list[str]:
    live_outcomes = [o for o in kb["desired_outcomes"]["outcomes"] if not o.get("merged_into")]
    new_outcomes = {o["id"] for o in kb["desired_outcomes"]["outcomes"] if since and str(o.get("added", "")) >= since}
    return (_review_head(kb, live_outcomes) + _review_decisions(kb) + _review_new(kb, since, new_outcomes)
            + _review_map(kb, live_outcomes, new_outcomes) + _review_solutions(kb) + _review_themes(kb)
            + _review_people(kb) + _review_tail(kb))


def cmd_review(args: argparse.Namespace) -> int:
    """Write a plain-language sheet for people who review the KB: what changed, what needs a decision, the map."""
    kb = load_kb(args.kb)
    last = next((c for c in reversed(kb["changelog"]) if c.get("action") in ("merge", "init")), {})
    since = args.since or str(last.get("date", ""))
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.kb)), "review.md")
    with open(out, "w", encoding="utf-8") as handle:
        handle.write("\n".join(review_lines(kb, since)))
    args.run.note(out=args.run.relative(out), since=since)
    print(f"wrote {out}")
    return 0


# ---------- map ----------
MAP_KEYS = ["meta", "core_jobs", "job_map", "desired_outcomes", "current_solutions", "interviews", "clusters",
            "proposed_changes", "changelog"]
MAP_START, MAP_END = "/* @kb-data:start */", "/* @kb-data:end */"
MAP_SCHEMA = f"/* @kb-schema:{SCHEMA_VERSION} */"  # the template can draw a KB of this schema version


def embed_kb(template: str, payload: str) -> str:
    """Put the KB's JSON between the template's data markers. Older generated maps without markers are upgraded."""
    block = f"{MAP_START}\nconst SAMPLE = {payload};\n{MAP_END}"
    start, end = template.find(MAP_START), template.find(MAP_END)
    if start != -1 and end > start:
        return template[:start] + block + template[end + len(MAP_END):]
    lines = template.split("\n")
    hits = [i for i, line in enumerate(lines) if line.startswith("const SAMPLE = ")]
    if len(hits) != 1:
        raise KbError("the template has no data markers and no single 'const SAMPLE = ' line; "
                      "use discovery-map-template.html from the skill", code="template_invalid")
    lines[hits[0]] = block
    return "\n".join(lines)


def has_local_browser() -> bool:
    """False on a machine the user is not sitting at: an SSH session, a remote container, Linux with no display."""
    if os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY"):
        return False
    if os.environ.get("CODESPACES") or os.environ.get("REMOTE_CONTAINERS"):
        return False
    if not sys.platform.startswith("linux"):
        return True
    if "microsoft" in platform.release().lower():  # WSL: the browser lives on the Windows side
        return False
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def open_in_browser(uri: str) -> str:
    """Show a file in the default browser. Returns what happened: opened, failed, no_display or off."""
    if os.environ.get("KB_TOOL_OPEN", "").strip() in ("0", "off", "false"):
        return "off"
    if not has_local_browser():  # here webbrowser would start a text browser in the terminal, or hang
        return "no_display"
    try:
        return "opened" if webbrowser.open(uri) else "failed"
    except (webbrowser.Error, OSError):
        return "failed"


MAP_NEXT = {
    None: "Open the link in any browser. If the map is already open, reload the tab.",
    "opened": "Opened in the default browser. If nothing appeared, open the link.",
    "failed": "Could not start a browser here. Open the link in any browser.",
    "no_display": "This machine has no browser to show it (a remote session, or no display). Download the file, "
                  "or open it from your editor's file tree.",
    "off": "Opening is switched off (KB_TOOL_OPEN=0). Open the link in any browser.",
}


def cmd_map(args: argparse.Namespace) -> int:
    """Rebuild the interactive discovery map with the current KB embedded, so it opens with no setup."""
    kb = load_kb(args.kb)
    data = {key: kb[key] for key in MAP_KEYS if key in kb}
    if themes_of(kb):  # a KB with no themes gives the map it always gave
        data["value_themes"] = kb["value_themes"]
    if overviews_of(kb):  # the written findings of the Overview view; the map counts the rest itself
        data["overview"] = kb["overview"]
    payload = json.dumps(data, default=str, ensure_ascii=False)
    payload = payload.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    template_path = skill_file("assets", "discovery-map-template.html", args.template)
    if not template_path:
        raise KbError("map template not found: put discovery-map-template.html next to kb_tool.py, run the kb_tool.py "
                      "that sits in the skill's scripts/ folder, or pass --template (a discovery-map.html made earlier "
                      "also works)", code="skill_file_missing")
    with open(template_path, encoding="utf-8") as handle:
        template = handle.read()
    if MAP_SCHEMA not in template:
        raise KbError(f"the map template {template_path} is older than KB schema {SCHEMA_VERSION} and cannot draw "
                      "several core jobs; use discovery-map-template.html from the skill", code="template_old")
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.kb)), "discovery-map.html")
    with open(out, "w", encoding="utf-8") as handle:
        handle.write(embed_kb(template, payload))
    args.run.note(out=args.run.relative(out))
    uri = pathlib.Path(os.path.abspath(out)).as_uri()
    browser = open_in_browser(uri) if args.open else None
    if browser:
        args.run.note(browser=browser)
    print(f"wrote {out} ({len(kb['interviews'])} interviews, {len(kb['desired_outcomes']['outcomes'])} outcomes)\n"
          f"link: {uri}\n{MAP_NEXT[browser]}\n"
          "It contains every name and quote in the KB, so treat it as personal data.")
    return 0


# ---------- validate, migrate ----------
def _transcript_texts(kb: Json, transcripts: Transcripts,
                      report: Report) -> tuple[dict[str, str | None], dict[str, str]]:
    """Normalized transcript per interview ID, plus {id: new sha256} for transcripts that changed since added."""
    texts: dict[str, str | None] = {}
    drifted: dict[str, str] = {}
    for record in kb["interviews"]:
        kb_id = str(record["id"])
        transcript = transcripts.get(str(record.get("file", "")))
        texts[kb_id] = transcript.text if transcript else None
        if transcript is None:
            report.error(f"interview {kb_id}: file {record.get('file')} not found in {KB_FOLDER}/{COPIES}/",
                         code="transcript_missing")
        elif record.get("sha256") and transcript.sha256 != record["sha256"]:
            drifted[kb_id] = transcript.sha256
    return texts, drifted


def _check_own_quotes(kb: Json, texts: dict[str, str | None], checker: QuoteChecker, report: Report) -> None:
    for record in kb["interviews"]:
        kb_id = str(record["id"])
        if texts.get(kb_id) is None:
            continue
        for fld in ("job_executor", "core_functional_job"):
            own = [{**e, "interview": kb_id} for e in record.get(fld, {}).get("evidence", [])]
            checker.check(own, f"{kb_id} {fld}", report)
        for fld in ("related_jobs", "emotional_jobs", "social_jobs"):
            for job in record.get(fld) or []:
                own = [{**e, "interview": kb_id} for e in job.get("evidence", [])]
                checker.check(own, f"{kb_id} {fld}", report)


def _check_shared_quotes(kb: Json, checker: QuoteChecker, report: Report) -> None:
    for step in kb["job_map"]["steps"]:
        if step.get("evidence"):
            checker.check(step["evidence"], f"step {step_key(step)}", report)
    for outcome in kb["desired_outcomes"]["outcomes"]:
        if outcome.get("evidence"):
            checker.check(outcome["evidence"], f"outcome {outcome['id']}", report)
    for proposal in kb["proposed_changes"]:
        if proposal.get("status") != "pending":
            continue
        if proposal.get("evidence"):
            checker.check(proposal["evidence"], f"proposal {proposal.get('id')}", report)
        for index, step in enumerate(proposal.get("steps") or []):
            if step.get("evidence"):
                checker.check(step["evidence"], f"proposal {proposal.get('id')} steps[{index}]", report)


def _check_solution_quotes(kb: Json, checker: QuoteChecker, report: Report) -> None:
    for solution in solutions_of(kb):
        for use in uses_of(solution):
            if use.get("evidence"):
                checker.check(use["evidence"], f"solution {solution.get('id')} at step {use.get('step')}", report)


def _check_theme_quotes(kb: Json, checker: QuoteChecker, report: Report) -> None:
    for theme in themes_of(kb):
        if theme.get("highlights"):
            checker.check(theme["highlights"], f"value theme {theme['id']}", report)


def check_stored_quotes(kb: Json, transcripts: Transcripts, report: Report) -> dict[str, str]:
    """Re-check every quote in the KB against its transcript. Returns the transcripts whose content changed."""
    texts, drifted = _transcript_texts(kb, transcripts, report)

    def lookup(reference: str) -> tuple[str | None, str | None]:
        if reference not in texts:
            return None, f"unknown interview '{reference}'"
        if texts[reference] is None:
            return None, f"transcript for interview {reference} not found"
        return texts[reference], None

    checker = QuoteChecker(lookup)
    _check_own_quotes(kb, texts, checker, report)
    _check_shared_quotes(kb, checker, report)
    _check_solution_quotes(kb, checker, report)
    _check_theme_quotes(kb, checker, report)
    return drifted


def _accept_drift(kb: Json, drifted: dict[str, str], args: argparse.Namespace) -> None:
    """Store the new content hashes of transcripts that changed, once every quote still matches."""
    by_id = {str(r["id"]): r for r in kb["interviews"]}
    for kb_id, digest in drifted.items():
        by_id[kb_id]["sha256"] = digest
    kb["changelog"].append(changelog_entry(args.run, "edit",
                                           summary=f"accepted changed transcripts for interviews {', '.join(drifted)}"))
    made = backup(args.kb)
    save_kb(kb, args.kb)
    args.run.note(written=True, backup=args.run.relative(made))
    print(f"rehashed interviews {', '.join(drifted)}")


def cmd_validate(args: argparse.Namespace) -> int:
    kb = load_kb(args.kb)
    problems = structure_problems(kb, args.schema)
    args.run.note(structure_problems=len(problems))
    if problems:
        args.run.fail("structure", len(problems))
        print(f"structure: {len(problems)} problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("structure: matches kb-schema.json and every reference resolves")
    if args.structure_only:
        return 0
    report = Report()
    transcripts = transcripts_for([], report, copies_folder(args.kb))
    drifted = check_stored_quotes(kb, transcripts, report)
    quotes = sum(len(o.get("evidence", [])) for o in kb["desired_outcomes"]["outcomes"])
    print(f"{len(kb['interviews'])} interviews, {len(kb['job_map']['steps'])} steps, "
          f"{len(kb['desired_outcomes']['outcomes'])} outcomes, {quotes} outcome quotes")
    for warning in report.warnings:
        print(f"WARN {warning}")
    for kb_id in drifted:
        if args.rehash and not report.errors:
            continue
        report.error(f"transcript for interview {kb_id} changed since it was added"
                     + ("; fix the quotes above first" if report.errors else
                        "; if the change is intended, run validate --rehash to accept it"),
                     code="transcript_changed")
    args.run.add_report(report)
    args.run.note(outcome_quotes=quotes, drifted=len(drifted), rehash=bool(args.rehash))
    if report.errors:
        print(f"{len(report.errors)} problem(s):")
        for problem in report.errors[:MAX_PROBLEMS]:
            print(f"  - {problem}")
        return 1
    if drifted:
        _accept_drift(kb, drifted, args)
    print("valid: every quote matches its transcript")
    return 0


def _prefixed(value: Any, job: str) -> Any:
    """A schema 1 step number or outcome ID with the job letter in front: 6 -> "A.6", "6.3" -> "A.6.3"."""
    if _is_int(value) or (isinstance(value, str) and (value.isdigit() or BARE_OUTCOME_ID.match(value))):
        return f"{job}.{value}"
    return value


def _migrate_proposal_1(proposal: Json) -> None:
    kind = proposal.get("type")
    renamed = ("reword_step", "reword_outcome", "merge_outcomes", "move_outcome")
    if kind in renamed and proposal.get("target") not in (None, ""):
        proposal["target"] = _prefixed(proposal["target"], "A")
    for key in ("merge", "to_step"):
        if key in proposal:
            proposal[key] = _prefixed(proposal[key], "A")
    if kind == "new_step":
        proposal["job"] = "A"
    if kind == "reword_core_job":
        proposal["target"] = "A"


def _migrate_1(kb: Json) -> str:
    """Schema 1 -> 2. The one market core job becomes core job A, and every step and outcome ID gets its letter."""
    old = kb.pop("market_core_job", None) or {}
    job_map = kb["job_map"]
    statement, status = old.get("statement") or job_map.get("core_job"), old.get("status") or job_map.get("status")
    job_map.pop("core_job", None)
    job_map.pop("status", None)
    if not (statement or job_map["steps"]):
        return "no core job yet, so nothing to rename"
    job = {"id": "A", "statement": statement or "Core job not named yet", "status": status or "proposed"}
    job.update({k: old[k] for k in ("job_executor", "history") if k in old})
    kb["core_jobs"] = [job]
    for step in job_map["steps"]:
        step["job"] = "A"
    for outcome in kb["desired_outcomes"]["outcomes"]:
        outcome["id"], outcome["step"] = _prefixed(str(outcome["id"]), "A"), f"A.{int(outcome['step'])}"
        if outcome.get("merged_into"):
            outcome["merged_into"] = _prefixed(str(outcome["merged_into"]), "A")
        for entry in outcome.get("history", []):
            if "was_id" in entry:
                entry["was_id"] = _prefixed(str(entry["was_id"]), "A")
    for proposal in kb["proposed_changes"]:
        _migrate_proposal_1(proposal)
    for record in kb["interviews"]:
        record["core_functional_job"]["job"] = "A"
    mark_stale(kb, "step and outcome IDs gained the job letter A, so text that cites old IDs is out of date")
    recount(kb)
    if job["status"] == "proposed":
        file_proposal(kb, confirmation(kb, "A", "Set up before a core job could be confirmed."))
    return "the core job is now core job A; step and outcome IDs gained the prefix A. (6.3 is now A.6.3)"


MIGRATIONS: dict[int, Callable[[Json], str]] = {1: _migrate_1}  # from version -> upgrade to version + 1


def _upgrade(kb: Json, version: int) -> list[str]:
    """Run the schema migrations from `version` up to the current one. Returns one note per step."""
    notes = []
    while version < SCHEMA_VERSION:
        notes.append(MIGRATIONS[version](kb))
        version += 1
        kb["meta"]["schema_version"] = version
    return notes


def _old_transcripts(kb: Json, kb_path: str, roots: list[str], report: Report) -> list[str]:
    """Find the transcript of every interview of a study made by an earlier version, and point its record at
    the copy the move will make. Returns the paths to copy. Without roots, looks in <study>/Interviews/."""
    study = os.path.dirname(os.path.dirname(os.path.abspath(kb_path)))
    transcripts = transcripts_for(roots or [os.path.join(study, OLD_TRANSCRIPTS)], report)
    found = []
    for record in kb["interviews"]:
        transcript = transcripts.get(str(record.get("file", "")))
        if transcript is None:
            report.error(f"interview {record.get('id')}: transcript {record.get('file')} not found; pass the folder "
                         "that holds it with --transcripts", code="transcript_missing")
            continue
        if record.get("sha256") and transcript.sha256 != record["sha256"]:
            report.warn(f"transcript for interview {record.get('id')} changed since it was added; run validate "
                        "after the move to re-check its quotes", code="transcript_changed")
        record.setdefault("sha256", transcript.sha256)
        record["file"] = f"{COPIES}/{os.path.basename(transcript.path)}"
        found.append(transcript.path)
    return found


def _clashes(old_folder: str, new_folder: str, sources: list[str]) -> list[str]:
    """What the move would overwrite in .pw-kb/: a file or folder of the same name, or a different transcript."""
    found = [name for name in MOVED_ON_MIGRATE
             if os.path.exists(os.path.join(old_folder, name)) and os.path.exists(os.path.join(new_folder, name))]
    for source in sources:
        target = os.path.join(new_folder, COPIES, os.path.basename(source))
        if os.path.exists(target) and file_sha256(target) != file_sha256(source):
            found.append(f"{COPIES}/{os.path.basename(source)}")
    return found


def _move_study(old: str, new: str, kb: Json, sources: list[str]) -> str:
    """Copy the transcripts into .pw-kb/, move the study's files there, write the KB and remove the old one.

    Backups keep their time stamps and take the new KB's name. Returns the backup of the old KB file."""
    old_folder, new_folder = os.path.dirname(os.path.abspath(old)), os.path.dirname(os.path.abspath(new))
    os.makedirs(new_folder, exist_ok=True)
    copy_transcripts(new, sources)
    for name in MOVED_ON_MIGRATE:
        if os.path.exists(os.path.join(old_folder, name)):
            shutil.move(os.path.join(old_folder, name), os.path.join(new_folder, name))
    old_stem, new_stem = (os.path.splitext(os.path.basename(p))[0] for p in (old, new))
    backups = os.path.join(new_folder, "backups")
    for name in sorted(os.listdir(backups)) if os.path.isdir(backups) and old_stem != new_stem else []:
        if name.startswith(f"{old_stem}."):
            os.replace(os.path.join(backups, name), os.path.join(backups, new_stem + name[len(old_stem):]))
    made = backup(new, source=old)
    save_kb(kb, new)
    os.remove(old)
    with contextlib.suppress(OSError):
        os.rmdir(old_folder)  # only when nothing else is left in it
    return made


def _migrate_move(args: argparse.Namespace) -> int:
    """Move a study made by an earlier version (the KB in <study>/KB/, transcripts in <study>/Interviews/) into
    .pw-kb/pw-kb.yaml."""
    new = args.to or KB_HOME
    if not at_home(new):
        raise KbError(f"--to must be {KB_HOME} at the root of the workspace, not {new}", code="kb_location")
    if os.path.exists(new):
        raise KbError(f"{new} already holds a study, and a workspace holds one study. Nothing moved. Open the old "
                      "study in a workspace of its own, or move the other one out first", code="kb_exists")
    kb = ensure(load_yaml(args.kb), args.kb)
    version = check_version(kb, args.kb)
    args.run.note(schema_from=version, moved=True)
    report = Report()
    sources = _old_transcripts(kb, args.kb, args.transcripts or [], report)
    for clash in _clashes(os.path.dirname(os.path.abspath(args.kb)), os.path.dirname(os.path.abspath(new)), sources):
        report.error(f"{KB_FOLDER}/{clash} exists already and would be overwritten; move it out of the way first",
                     code="move_conflict")
    args.run.add_report(report)
    lines = [f"WARN {warning}" for warning in report.warnings]
    if report.errors:
        print("\n".join(lines + [f"{len(report.errors)} problem(s); nothing moved:"]
                        + [f"  - {e}" for e in report.errors]))
        return 1
    notes = _upgrade(kb, version)
    summary = f"moved the study into {KB_FOLDER}/ and copied its {len(sources)} transcript(s) there"
    if notes:
        summary += f"; migrated from schema version {version} to {SCHEMA_VERSION}: " + "; ".join(notes)
    kb["changelog"].append(changelog_entry(args.run, "migrate", summary=summary))
    problems = structure_problems(kb)
    if problems:
        raise KbError("the migrated KB would break the KB structure; nothing moved. Fix these first:\n  - "
                      + "\n  - ".join(problems), code="structure")
    old_folder = os.path.dirname(os.path.abspath(args.kb))
    made = _move_study(args.kb, new, kb, sources)
    args.run.moved(new)
    args.run.note(written=True, backup=args.run.relative(made), transcripts_copied=len(sources))
    left = sorted(n for n in os.listdir(old_folder) if not n.startswith(".")) if os.path.isdir(old_folder) else []
    lines.append(f"{summary}. The KB is now {new}; the old file is in {KB_FOLDER}/backups/")
    if left:
        lines.append(f"left in {old_folder}: {', '.join(left)}")
    note = git_note(new)
    args.run.note(git=bool(note))
    print("\n".join(lines + ([note] if note else [])))
    return 0


def cmd_migrate(args: argparse.Namespace) -> int:
    if not at_home(args.kb):
        return _migrate_move(args)
    kb = ensure(load_yaml(args.kb), args.kb)
    version = check_version(kb, args.kb)
    args.run.note(schema_from=version)
    if version == SCHEMA_VERSION:
        print(f"nothing to do: {args.kb} already uses schema version {SCHEMA_VERSION}")
        return 0
    start, notes = version, _upgrade(kb, version)
    summary = f"migrated from schema version {start} to {SCHEMA_VERSION}: " + "; ".join(notes)
    kb["changelog"].append(changelog_entry(args.run, "migrate", summary=summary))
    problems = structure_problems(kb)
    if problems:
        raise KbError("the migrated KB would break the KB structure; nothing written. Fix these first:\n  - "
                      + "\n  - ".join(problems), code="structure")
    made = backup(args.kb)
    save_kb(kb, args.kb)
    args.run.note(written=True, backup=args.run.relative(made))
    print(f"migrated {args.kb} {summary[len('migrated '):]}")
    return 0


# ---------- cli ----------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"kb_tool {__version__} (KB schema {SCHEMA_VERSION})")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def command(name: str, func: Callable[[argparse.Namespace], int], help_text: str) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("kb", help="path to the KB YAML file")
        sp.set_defaults(func=func)
        return sp

    sp = command("init", cmd_init, "start an empty KB")
    sp.add_argument("--project", required=True)
    sp.add_argument("--interviewer")
    sp = command("context", cmd_context, "compact view of the KB")
    sp.add_argument("--json", action="store_true", help="print the same information as JSON")
    sp = command("merge", cmd_merge, "check a patch and fold it into the KB")
    sp.add_argument("patch", help="path to the patch YAML file")
    sp.add_argument("--transcripts", action="append",
                    help="folder or file with new transcripts; repeat for several. "
                         f"{KB_FOLDER}/{COPIES}/ is always read first")
    sp.add_argument("--dry-run", action="store_true", help="run every check, write nothing")
    sp.add_argument("--json", action="store_true", help="print the result as one JSON object")
    sp = command("apply", cmd_apply, "decide on a proposed change")
    sp.add_argument("id", help="proposal ID, such as P3")
    sp.add_argument("--decision", choices=["approve", "reject"], required=True)
    sp.add_argument("--note")
    sp = command("review", cmd_review, "write review.md")
    sp.add_argument("--since", help="YYYY-MM-DD; default: date of the last merge")
    sp.add_argument("--out")
    sp = command("map", cmd_map, "write discovery-map.html")
    sp.add_argument("--template")
    sp.add_argument("--out")
    sp.add_argument("--open", action="store_true",
                    help="also show the map in the default browser; set KB_TOOL_OPEN=0 to never do so")
    sp = command("themes", cmd_themes, "check one core job's value themes and write them")
    sp.add_argument("themes", help="path to a YAML file with `job` and `themes`, the full set for that core job")
    sp.add_argument("--dry-run", action="store_true", help="run every check, write nothing")
    sp.add_argument("--json", action="store_true", help="print the result as one JSON object")
    sp = command("overview", cmd_overview, "check one core job's overview and write it")
    sp.add_argument("overview", help="path to a YAML file with `job` and the overview of that core job")
    sp.add_argument("--dry-run", action="store_true", help="run every check, write nothing")
    sp.add_argument("--json", action="store_true", help="print the result as one JSON object")
    sp = command("validate", cmd_validate, f"check the KB's structure, then its quotes against {KB_FOLDER}/{COPIES}/")
    sp.add_argument("--structure-only", action="store_true", help="check the structure, not the quotes")
    sp.add_argument("--schema", help="path to kb-schema.json, if it is not next to the script")
    sp.add_argument("--rehash", action="store_true",
                    help="accept transcripts whose content changed since they were added")
    sp = command("migrate", cmd_migrate, f"bring an older KB up to date and move it into {KB_FOLDER}/")
    sp.add_argument("--to", help=f"where to move a study made by an earlier version; default {KB_HOME}")
    sp.add_argument("--transcripts", action="append",
                    help=f"folder or file with that study's transcripts; default <study>/{OLD_TRANSCRIPTS}")
    return parser


def run_command(args: argparse.Namespace) -> int:
    """Run the chosen command. A KbError becomes a message and exit code 1, never a traceback."""
    try:
        return int(args.func(args) or 0)
    except KbError as exc:
        args.run.fail(exc.code)
        if getattr(args, "json", False):
            print(json.dumps({"ok": False, "errors": [str(exc)], "code": exc.code, "run_id": args.run.id},
                             ensure_ascii=False, indent=2))
        else:
            print(f"error: {exc}")
        return 1


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # the output holds · and ●
    args = build_parser().parse_args(argv)
    args.run = run = Run(args)
    code = 2
    try:
        code = run_command(args)
    except Exception as exc:  # a bug, not a user error: record it in the log, then let the traceback show
        run.fail("crash")
        run.note(exception=type(exc).__name__)
        raise
    finally:
        run.write(args, code)
    return code


if __name__ == "__main__":
    sys.exit(main())
