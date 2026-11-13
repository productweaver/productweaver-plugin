#!/usr/bin/env python3
"""kb_tool.py - keep an ODI knowledge base (one JSON file) growing from interview transcripts.

Part of the Product Weaver pw-discovery skill · https://productweaver.com

A study lives in one folder, .pw-kb/ at the root of the workspace: the KB .pw-kb/pw-kb.json, and next to it
patches/, backups/, logs/, transcripts/ (a copy of every transcript the KB cites), review.md and discovery-map.html.

Commands
  init      .pw-kb/pw-kb.json --project NAME [--interviewer NAME] [--language CODE]
                                                              start an empty KB, in English unless --language says
  labels    <kb.json> [--language CODE] [--add FILE] [--json] set the study's language (before the first interview);
                                                              write the map's and review sheet's text still to write
                                                              in it, or check and keep that text (--add)
  context   <kb.json> [--json]                                compact view of the KB to map new evidence against
  merge     <kb.json> <patch.json> [--transcripts DIR ...] [--dry-run] [--json]
                                                              check every quote and reference, fold the patch in and
                                                              copy new transcripts into .pw-kb/transcripts/
  apply     <kb.json> <proposal-id> --decision approve|reject [--note TEXT]
                                                              act on a proposed structural change
  review    <kb.json> [--since DATE] [--out FILE]             write review.md, a plain sheet for human reviewers
  map       <kb.json> [--template FILE] [--out FILE] [--open] write discovery-map.html, the interactive map, KB inside;
                                                              --open also shows it in the default browser
  themes    <kb.json> <themes.json> [--dry-run] [--json]      check one core job's value themes and write them:
                                                              few needs that group the outcomes, for ideation
  overview  <kb.json> <overview.json> [--dry-run] [--json]  check one core job's overview and write it: the
                                                              study as a short story, with what to do next
  validate  <kb.json> [--structure-only] [--schema FILE] [--rehash]
                                                              check the structure, then every quote and transcript hash
  migrate   <kb> [--to .pw-kb/pw-kb.json] [--transcripts DIR ...]
                                                              bring an older KB up to the current schema version, turn
                                                              a YAML study into JSON, and move a study made by an
                                                              earlier version into .pw-kb/

Run it with python3 kb_tool.py <command> ... It needs Python 3.9 or newer and nothing else: only the standard library.
Two packages help when they are installed, and nothing needs them: pypdf==6.21.4 reads .pdf transcripts, and
pyyaml==6.0.3 lets migrate read a study written in YAML by version 0.10.0 or earlier.

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
import importlib.util
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
import zipfile
from dataclasses import dataclass, field
from typing import Any, Callable
from xml.etree import ElementTree

try:
    import jsonschema as _jsonschema  # optional: richer schema messages when it is installed
except ImportError:  # pragma: no cover - depends on the machine
    _jsonschema = None

__version__ = "0.12.0"
SCHEMA_VERSION = 3

BRAND = "Product Weaver"
SITE = "https://www.productweaver.com/"
# Fixed tags on the review sheet's links, holding nothing from the study (the map's pwUrl does the same).
REVIEW_LINK = (f"{SITE}?utm_source=productweaver-plugin&utm_medium=review-sheet&utm_campaign=pw-discovery"
               "&utm_content=review-footer")
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
KIND_LABELS = {"product": "review.kind.product", "everyday_tool": "review.kind.everyday_tool",
               "people": "review.kind.people", "own_method": "review.kind.own_method"}  # the review sheet's names
PATCH_KEYS = (*PATCH_SECTIONS, "provenance", "generated_with")  # every top-level key a patch may carry
PROVENANCE_KEYS = ("assistant", "model", "started", "transcripts_read", "notes")
LOG_FOLDER, LOG_FILE = "logs", "kb_tool.jsonl"
KB_FOLDER, KB_FILE, COPIES = ".pw-kb", "pw-kb.json", "transcripts"  # <workspace root>/.pw-kb/pw-kb.json
OLD_KB_FILE, OLD_STUDY_LABELS = "pw-kb.yaml", "labels.yaml"  # what versions up to 0.10.0 wrote; migrate reads them
KB_HOME = f"{KB_FOLDER}/{KB_FILE}"
# The study's own labels (written by `labels`) override LABELS_FILE's English.
ENGLISH = "en"
LABELS_FILE, STUDY_LABELS = "labels-en.js", "labels.json"
OLD_TRANSCRIPTS = "Interviews"  # where earlier versions kept a study's transcripts: <study>/Interviews/
MOVED_ON_MIGRATE = ("patches", "backups", LOG_FOLDER, "review.md", "interview-guide.md", "discovery-map.html")
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
OVERVIEW_KEYS = ("job", "executor", "bottom_line", "why", "opening", "people", "today", "gaps", "needs", "focus",
                 "next")
EXECUTOR_KEYS = ("label", "text", "icon", "others")
# the icons the map draws for the people at the center of a study; `person` when none fits
ROLE_ICONS = ("person", "office", "finance", "shop", "sales", "support", "manager", "developer", "designer", "driver",
              "warehouse", "builder", "repair", "cook", "health", "care", "teacher", "student", "farmer", "legal",
              "parent")
EXECUTOR_OTHERS = 3        # other people in the story an overview may name, at most
GAP_KINDS = ["pain", "struggle"]  # what goes wrong today, and a fix that did not work
GAP_MAX = 5                # gaps an overview should show, at most
# what to do next: the statuses each track may have, and the fields it holds besides status and action
NEXT_TRACKS = {"learn": (("now", "enough"), ("why", "ask", "tip")),
               "prototype": (("ready", "early"), ("why", "test", "later")),
               "market": (("ready", "early"), ("who", "words", "unknown"))}
NEXT_LISTS = {"ask": 2, "words": 3}  # fields that are lists, and how many items each may hold
LEARN_PLAN = ("traits", "rests_on", "round")  # the plan for the next round; kb_tool adds at_write and previous
TRAIT_COUNT, TRAIT_VALUES = (2, 3), (2, 5)
TRAIT_ID, TRAIT_VALUE_ID = re.compile(r"^T[0-9]+$"), re.compile(r"^T[0-9]+\.[0-9]+$")
RESTS_ON_MAX, ROUND_MAX, ROUND_COUNT, ROUND_ITEMS = 8, 5, (1, 3), 4
LEADING = re.compile(r"\b(would you|do you also|wouldn't it|how much would|if there was)\b", re.I)
SCORE_WORDS = re.compile(r"\d\s?[%％٪]|\bpercent\b|\b(opportunity|importance|satisfaction) (score|rating)s?\b",
                         re.IGNORECASE)
# Overview readers are new to the method: method words are refused, vague words warned, each with plain words to
# use. A space in a pattern also matches a hyphen.
METHOD_WORDS = (("core jobs?", "core job", "the goal, or what they try to get done"),
                ("job executors?", "job executor", "the people, by their role"),
                ("desired outcomes?", "desired outcome", "what they want to get better"),
                ("outcome statements?", "outcome statement", "a need"),
                ("job steps?", "job step", "a step, or a part of the work"),
                ("job maps?", "job map", "the map"),
                ("jobs? to be done", "jobs to be done", "what they try to get done"),
                ("JTBD", "JTBD", "what they try to get done"),
                ("ODI", "ODI", "say what you did: you listened to people"))
JARGON_WORDS = (("pain points?", "pain point", "say what goes wrong"),
                ("friction", "friction", "say what slows them down"),
                ("workflows?", "workflow", "say how they work"),
                ("leverag(?:e|es|ed|ing)", "leverage", "use"),
                ("stakeholders?", "stakeholder", "name the person, such as the owner"),
                ("value propositions?", "value proposition", "say what it does for them"),
                ("streamlin(?:e|es|ed|ing)", "streamline", "make faster or simpler"),
                ("optimi[sz](?:e|es|ed|ing|ation)", "optimize", "say what gets better"),
                ("seamless(?:ly)?", "seamless", "say what gets easier, or drop it"),
                ("solution space", "solution space", "ideas"),
                ("unmet needs?", "unmet need", "a need"),
                ("end to end", "end-to-end", "from start to finish"),
                ("ecosystems?", "ecosystem", "name the tools or the people"),
                ("holistic(?:ally)?", "holistic", "drop it"),
                ("actionable", "actionable", "say what to do"),
                ("user journeys?", "user journey", "the steps they take"),
                ("personas?", "persona", "the people, by their role"))


def _plain_terms(terms: tuple[tuple[str, str, str], ...]) -> list[tuple[re.Pattern[str], str, str]]:
    """Compile a word list: whole words, any case except for acronyms, a space also matching a hyphen."""
    return [(re.compile(r"\b" + pattern.replace(" ", r"[\s-]+") + r"\b", 0 if pattern.isupper() else re.IGNORECASE),
             word, hint) for pattern, word, hint in terms]


METHOD_TERMS = _plain_terms(METHOD_WORDS)
JARGON_TERMS = _plain_terms(JARGON_WORDS)
GROUP_KEY = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
TRANSCRIPT_EXTS = (".md", ".markdown", ".txt", ".docx", ".pdf")
KEEP_BACKUPS = 20
THIN_STEP = 3
MAX_PROBLEMS = 60

Json = dict[str, Any]


class KbError(Exception):
    """A problem the user can fix, printed without a traceback. `code` names its kind for the run log."""

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class Report:
    """Problems found while checking. Errors block, warnings do not. Each has a code (references/run-log.md) so the
    run log can count them without the message, which may hold a quote."""

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
        with open(path, encoding="utf-8-sig") as handle:
            kb = json.load(handle)
    except (OSError, ValueError):
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
    """One invocation, as logs/kb_tool.jsonl records it: commands add facts with note(), main() writes the line.
    It holds IDs, counts, codes, hashes and versions, never a quote, name, file name or absolute path."""

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
            paths = ("patch", "themes", "out", "template", "schema", "to", "add")
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
JSON_RULES = ("JSON needs double quotes around every key and every text, \\\" for a quote mark inside a text, a comma "
              "between items but none after the last, and no comments")


def _no_twice(pairs: list[tuple[str, Any]]) -> Json:
    data: Json = {}
    for key, value in pairs:
        if key in data:
            raise ValueError(f'the key "{key}" appears twice in one object')
        data[key] = value
    return data


def _no_constant(name: str) -> Any:
    raise ValueError(f"{name} is not a number JSON allows")


def _json_spot(text: str, line: int, column: int, width: int = 120) -> str:
    """The line of a JSON error, cut to `width` characters around the column, with a caret under it."""
    lines = text.splitlines()
    shown = lines[line - 1].replace("\t", " ") if 0 < line <= len(lines) else ""
    start = max(0, column - 1 - width // 2)
    return f"  {shown[start:start + width]}\n  {' ' * (column - 1 - start)}^"


def load_json(path: str) -> Any:
    """Read a JSON file; an empty one gives None. A key written twice in one object, or NaN, is refused."""
    try:
        with open(path, encoding="utf-8-sig") as handle:  # -sig: accept the byte order mark some editors write
            text = handle.read()
    except FileNotFoundError:
        raise KbError(f"file not found: {path}", code="file_missing") from None
    except UnicodeDecodeError:
        raise KbError(f"{path} is not UTF-8 text; save it as UTF-8", code="json_invalid") from None
    if not text.strip():
        return None
    try:
        return json.loads(text, object_pairs_hook=_no_twice, parse_constant=_no_constant)
    except json.JSONDecodeError as exc:
        raise KbError(f"{path} is not valid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}:\n"
                      f"{_json_spot(text, exc.lineno, exc.colno)}\n{JSON_RULES}.", code="json_invalid") from None
    except (ValueError, RecursionError) as exc:
        raise KbError(f"{path} is not valid JSON: {exc}", code="json_invalid") from None


def dump_json(value: Any, indent: str = "") -> str:
    """Two-space JSON where an object holding no list or object, and a short list of plain values, stay on one
    line."""
    inner = list(value.values()) if isinstance(value, dict) else value if isinstance(value, list) else None
    line = json.dumps(value, ensure_ascii=False, allow_nan=False)
    if not inner or (not any(isinstance(item, (dict, list)) for item in inner)
                     and (isinstance(value, dict) or len(line) <= 100)):
        return line
    step = indent + "  "
    if isinstance(value, dict):
        lines = [f"{step}{json.dumps(str(k), ensure_ascii=False)}: {dump_json(v, step)}" for k, v in value.items()]
        return "{\n" + ",\n".join(lines) + f"\n{indent}}}"
    return "[\n" + ",\n".join(f"{step}{dump_json(item, step)}" for item in value) + f"\n{indent}]"


def save_json(data: Any, path: str) -> None:
    """Write atomically: dump to a temporary file, reload it, then replace the target."""
    text = dump_json(data) + "\n"
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    load_json(tmp)  # never leave a file in place that will not load
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
    save_json(kb, path)


def backup(kb_path: str, source: str | None = None) -> str:
    """Copy the KB (or `source`, the file about to be replaced) into backups/, named after the KB with microseconds
    so writes never collide. Keeps the newest KEEP_BACKUPS."""
    folder = os.path.join(os.path.dirname(os.path.abspath(kb_path)), "backups")
    os.makedirs(folder, exist_ok=True)
    stem = os.path.splitext(os.path.basename(kb_path))[0]
    ext = os.path.splitext(source or kb_path)[1]  # a YAML file from an earlier version stays .yaml
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
    """A skill file: the path given, a copy beside this script, or scripts/../<folder>/<name>."""
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = ([given] if given else []) + [os.path.join(here, name), os.path.join(here, "..", folder, name)]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return None


# ---------- language and labels ----------
# meta.language is a BCP 47 code; none means English. The map's and review sheet's own text comes from labels
# (LABELS_FILE, then the study's STUDY_LABELS). A missing or broken label shows in English, so it never breaks them.
LANGUAGE = re.compile(r"^[a-z]{2,3}(-[A-Z][a-z]{3})?(-([A-Z]{2}|\d{3}))?$")
PLURAL_FORMS = ("zero", "one", "two", "few", "many", "other")
PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")
LABELS_MARKER = re.compile(r"^var PW_LABELS_EN = ", re.M)  # the line that opens the table, never a comment
NO_SPACES = {"zh": 2.0, "ja": 2.5, "th": 4.0, "lo": 4.0, "km": 4.0, "my": 4.0}  # letters per English word
WORDIER = 1.2  # languages written with spaces use about a fifth more words than English for the same statement
_english: dict[str, Json] = {}


def normalize_language(code: str) -> str:
    """it, pt-BR, zh-Hans: the case BCP 47 uses. Refuses anything that is not a language code."""
    parts = str(code or "").strip().replace("_", "-").split("-")
    fixed = [parts[0].lower()] + [p.title() if len(p) == 4 else p.upper() for p in parts[1:]]
    language = "-".join(fixed)
    if not LANGUAGE.match(language):
        raise KbError(f"'{code}' is not a language code; use a BCP 47 code such as en, it, pt-BR or zh-Hans",
                      code="language_invalid")
    return language


def study_language(kb: Json) -> str:
    return str(kb["meta"].get("language") or ENGLISH)


def base_language(language: str) -> str:
    return language.split("-", maxsplit=1)[0].lower()


def english_table() -> Json:
    """{"labels": {key: text}, "notes": {key: note}} from the skill's labels-en.js, read once."""
    path = skill_file("assets", LABELS_FILE)
    if not path:
        raise KbError(f"{LABELS_FILE} not found: keep it in the skill's assets/ folder, next to "
                      "discovery-map-template.html", code="skill_file_missing")
    if path not in _english:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        found, end = LABELS_MARKER.search(text), text.rfind(";")
        try:
            table = json.loads(text[found.end():end]) if found and found.end() < end else None
        except ValueError:
            table = None
        if not isinstance(table, dict) or not isinstance(table.get("labels"), dict):
            raise KbError(f"{path} is not a label table: keep it as the skill ships it", code="skill_file_invalid")
        table.setdefault("notes", {})
        _english[path] = table
    return _english[path]


def _slavic(n: int, *, one_is_only_1: bool = False, rest: str = "many") -> str:
    """Russian, Ukrainian, Belarusian (rest many), Polish (one only for 1), Croatian, Serbian, Bosnian (rest other)."""
    if n % 10 == 1 and n % 100 != 11 and (n == 1 or not one_is_only_1):
        return "one"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "few"
    return rest


def _arabic(n: int) -> str:
    small = {0: "zero", 1: "one", 2: "two"}.get(n)
    return small or ("few" if 3 <= n % 100 <= 10 else "many" if 11 <= n % 100 <= 99 else "other")


PLURAL_RULES: dict[str, Callable[[int], str]] = {
    **dict.fromkeys(("ja", "zh", "ko", "th", "vi", "id", "ms", "lo", "km", "my"), lambda n: "other"),
    **dict.fromkeys(("fr", "hi", "fa", "bn"), lambda n: "one" if n in (0, 1) else "other"),
    **dict.fromkeys(("ru", "uk", "be"), _slavic),
    "pl": lambda n: _slavic(n, one_is_only_1=True),
    **dict.fromkeys(("hr", "sr", "bs"), lambda n: _slavic(n, rest="other")),
    **dict.fromkeys(("cs", "sk"), lambda n: "one" if n == 1 else "few" if 2 <= n <= 4 else "other"),
    "ar": _arabic,
    "he": lambda n: {1: "one", 2: "two"}.get(n, "other"),
}


def plural_category(language: str, n: int) -> str:
    """CLDR plural form of a whole number (one, few, many...) for common systems; others get one/other, and a form a
    label lacks falls back to other."""
    base = "fr" if language in ("pt", "pt-BR") else base_language(language)  # Brazilian Portuguese counts 0 as one
    rule = PLURAL_RULES.get(base)
    return rule(abs(int(n))) if rule else ("one" if abs(int(n)) == 1 else "other")


def needed_forms(language: str, english: Json) -> list[str]:
    """Plural forms a language needs for a label: for every number from 0, or from 2 when English has no `one`."""
    found = {plural_category(language, n) for n in range(0 if "one" in english else 2, 200)} | {"other"}
    return [form for form in PLURAL_FORMS if form in found]


def fill(text: str, values: Json) -> str:
    """Put the values into a label's {name} places. A name with no value stays as it is."""
    return PLACEHOLDER.sub(lambda m: str(values[m.group(1)]) if m.group(1) in values else m.group(0), text)


def _problem(why: str, *, code: str) -> tuple[str, str]:
    return code, why


def label_problem(value: Any, english: Any) -> tuple[str, str] | None:
    """(code, why) when a study label is unusable: it needs the English {name} places, no markup, and for a plural
    label a text per plural form, `other` included. Else None."""
    def one(text: Any, wanted: set[str]) -> tuple[str, str] | None:
        if not isinstance(text, str):
            return _problem("is not text: put it in quotes", code="labels_empty")
        if not text.strip() and re.search(r"\w", wanted_text(english)):
            return _problem("is empty", code="labels_empty")
        if "<" in text or ">" in text:
            return _problem("holds < or >; labels hold no markup", code="labels_markup")
        if set(PLACEHOLDER.findall(text)) != wanted:
            names = ", ".join("{" + p + "}" for p in sorted(wanted)) or "none"
            return _problem(f"must keep exactly these places: {names}", code="labels_placeholder")
        return None

    if isinstance(english, dict):
        if not isinstance(value, dict) or "other" not in value or set(value) - set(PLURAL_FORMS):
            return _problem("needs one text per plural form (zero, one, two, few, many, other), with other",
                            code="labels_plural")
        problems = [one(form, set(PLACEHOLDER.findall(english["other"]))) for form in value.values()]
        return next((p for p in problems if p), None)
    return one(value, set(PLACEHOLDER.findall(english)))


def wanted_text(english: Any) -> str:
    return english["other"] if isinstance(english, dict) else str(english)


def labels_path(kb_path: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(kb_path)), STUDY_LABELS)


def stored_labels(kb: Json, kb_path: str) -> Json:
    """The study's own labels as labels.json holds them, for the study's language; {} when there are none."""
    path = labels_path(kb_path)
    if base_language(study_language(kb)) == ENGLISH or not os.path.isfile(path):
        return {}
    try:
        data = load_json(path)
    except KbError:
        return {}
    if not isinstance(data, dict) or str(data.get("language")) != study_language(kb):
        return {}
    labels = data.get("labels")
    return {str(k): v for k, v in labels.items()} if isinstance(labels, dict) else {}


def study_labels(kb: Json, kb_path: str) -> tuple[Json, int]:
    """(the study's usable labels, how many labels show in English for want of one). English studies need none."""
    if base_language(study_language(kb)) == ENGLISH:
        return {}, 0
    english = english_table()["labels"]
    own = {k: v for k, v in stored_labels(kb, kb_path).items() if k in english and not label_problem(v, english[k])}
    return own, len(english) - len(own)


class Text:
    """Review-sheet words in the study's language: `text(key, name=value)`; English when missing, else the key."""

    def __init__(self, language: str = ENGLISH, own: Json | None = None) -> None:
        self.language = language
        self.english = english_table()["labels"]
        self.own = own or {}

    def __call__(self, key: str, **values: Any) -> str:
        label, language = self.own.get(key), self.language
        if label is None:
            label, language = self.english.get(key, key), ENGLISH
        if isinstance(label, dict):
            label = label.get(plural_category(language, int(values.get("n", 0)))) or label["other"]
        return fill(str(label), values)


def study_text(kb: Json, kb_path: str) -> tuple[Text, int]:
    own, missing = study_labels(kb, kb_path)
    return Text(study_language(kb), own), missing


def count_words(text: str, language: str = ENGLISH) -> int:
    """Words as the length limits count them. Chinese, Japanese, Thai and neighbours count letters, a few to a word,
    plus any Latin-letter word."""
    per_word = NO_SPACES.get(base_language(language))
    if not per_word:
        return len(text.split())
    latin = re.findall(r"[A-Za-z0-9][\w.'’-]*", text, flags=re.ASCII)
    rest = re.sub(r"[A-Za-z0-9][\w.'’-]*", " ", text, flags=re.ASCII)
    letters = sum(1 for ch in rest if ch.isalnum())
    return len(latin) + int(-(-letters // per_word))  # letters ÷ per word, rounded up


# ---------- where a study lives ----------
def at_home(kb_path: str) -> bool:
    """True when the path is <somewhere>/.pw-kb/pw-kb.json, the only place a study lives."""
    absolute = os.path.abspath(kb_path)
    return os.path.basename(absolute) == KB_FILE and os.path.basename(os.path.dirname(absolute)) == KB_FOLDER


def old_yaml(kb_path: str) -> str | None:
    """.pw-kb/pw-kb.yaml of a study from 0.10.0 or earlier, when kb_path names it or its missing pw-kb.json; else
    None."""
    folder, name = os.path.split(kb_path)
    old = os.path.join(folder, OLD_KB_FILE)
    if os.path.basename(os.path.abspath(folder or ".")) != KB_FOLDER or not os.path.isfile(old):
        return None
    return old if name == OLD_KB_FILE or (name == KB_FILE and not os.path.exists(kb_path)) else None


def check_home(kb_path: str) -> None:
    """Refuse a KB anywhere but .pw-kb/pw-kb.json. One made by an earlier version is moved or turned into JSON by
    migrate."""
    old = old_yaml(kb_path)
    if old:
        raise KbError(f"{old} was written in YAML by an earlier version of the skill; this version keeps the study in "
                      f"{KB_HOME}. Run `kb_tool.py migrate {old}` once from the workspace root, then try again",
                      code="migrate_needed")
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
    """Normalize text for quote matching: ASCII quotes, dashes and ellipses, no invisible characters or markdown
    markers, single spaces. Both sides of every comparison pass through here."""
    for old, new in _CHAR_MAP:
        text = text.replace(old, new)
    text = _LINE_MARKERS.sub("", text)
    text = re.sub(r"[*_]+", "", text)
    return re.sub(r"\s+", " ", text).strip()


W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DOCX_MAIN = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"


def _docx_part(archive: zipfile.ZipFile, name: str) -> ElementTree.Element:
    data = archive.read(name)
    if b"<!DOCTYPE" in data:  # Word never writes one; refusing it keeps entity tricks out
        raise ValueError(f"{name} declares a DOCTYPE")
    return ElementTree.fromstring(data)


def _docx_main(archive: zipfile.ZipFile) -> str:
    """The main document part, found through _rels/.rels the way Word and python-docx find it."""
    with contextlib.suppress(KeyError):
        for rel in _docx_part(archive, "_rels/.rels"):
            if rel.get("Type") == DOCX_MAIN and rel.get("Target"):
                return rel.get("Target", "").lstrip("/")
    return "word/document.xml"


def _run_text(run: ElementTree.Element) -> str:
    text = {"tab": "\t", "ptab": "\t", "cr": "\n", "noBreakHyphen": "-"}
    out = []
    for child in run:
        tag = child.tag[len(W_NS):] if child.tag.startswith(W_NS) else ""
        if tag == "t":
            out.append(child.text or "")
        elif tag == "br":  # a line break; a page or column break is no text
            out.append("\n" if child.get(f"{W_NS}type", "textWrapping") == "textWrapping" else "")
        else:
            out.append(text.get(tag, ""))
    return "".join(out)


def read_docx(path: str) -> str:
    """A .docx's text exactly as python-docx 1.2.0 gives it, so hashes hold: body paragraphs (not tables), each the
    text of its runs and hyperlinks' runs."""
    with zipfile.ZipFile(path) as archive:
        body = _docx_part(archive, _docx_main(archive)).find(f"{W_NS}body")
    if body is None:
        raise ValueError("it holds no Word document body")
    lines = []
    for paragraph in body.findall(f"{W_NS}p"):
        runs = []
        for child in paragraph:
            if child.tag == f"{W_NS}r":
                runs.append(child)
            elif child.tag == f"{W_NS}hyperlink":
                runs += child.findall(f"{W_NS}r")
        lines.append("".join(_run_text(run) for run in runs))
    return "\n".join(lines)


def read_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in (".md", ".markdown", ".txt", ""):
        with open(path, encoding="utf-8", errors="replace") as handle:
            return handle.read()
    if ext == ".docx":
        return read_docx(path)
    if ext == ".pdf":
        try:
            from pypdf import PdfReader  # noqa: PLC0415  (optional)
        except ImportError:
            stem = os.path.splitext(os.path.basename(path))[0]
            raise KbError(f"{path}: reading a .pdf needs pypdf, which is not installed here. Read the PDF yourself, "
                          f"save its text word for word as {KB_FOLDER}/{COPIES}/{stem}.txt, and cite that file "
                          "instead (or install pypdf: python3 -m pip install pypdf==6.21.4)",
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
    """Finds transcripts by base name and reads each once. The study's copies (.pw-kb/transcripts/) win; other
    names come from the --transcripts roots, and a name found in two roots is refused as ambiguous."""

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
def _guess_version(kb: Json, newest: int = SCHEMA_VERSION) -> int:
    """Schema of a KB from before schema_version: 1 with the single market core job, else `newest` (2 for YAML)."""
    steps = (kb.get("job_map") or {}).get("steps") or []
    old = "market_core_job" in kb or any(isinstance(s, dict) and "job" not in s for s in steps)
    return 1 if old else newest


def ensure(kb: Any, label: str = "the KB", newest: int = SCHEMA_VERSION) -> Json:
    if kb is None:
        kb = {}
    if not isinstance(kb, dict):
        raise KbError(f"{label} is not a JSON object", code="kb_shape")
    kb.setdefault("meta", {})
    kb["meta"].setdefault("schema_version", _guess_version(kb, newest))
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
                      f"{SCHEMA_VERSION}. Update the pw-discovery skill, then try again.", code="schema_version")
    return version


def load_kb(path: str) -> Json:
    check_home(path)
    kb = ensure(load_json(path), path)
    version = check_version(kb, path)
    if version < SCHEMA_VERSION:
        raise KbError(f"{path} uses KB schema version {version}; run `kb_tool.py migrate {path}` first",
                      code="migrate_needed")
    with contextlib.suppress(KeyError, TypeError, ValueError):  # a broken KB is for validate to report
        _recount_voices(kb)  # a KB written before steps had voices
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


def _recount_voices(kb: Json) -> None:
    """A step's voices: the people quoted on it or on any of its live outcomes. The thin rule counts these."""
    people: dict[str, set[str]] = {}
    for outcome in kb["desired_outcomes"]["outcomes"]:
        if not outcome.get("merged_into"):
            people.setdefault(str(outcome["step"]), set()).update(outcome.get("interviews", []))
    for step in kb["job_map"]["steps"]:
        step["voices"] = len(people.get(step_key(step), set()) | set(step.get("interviews", [])))


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
    _recount_voices(kb)
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
    return [step for step in kb["job_map"]["steps"] if step.get("voices", 0) < THIN_STEP]


# ---------- next interviews ----------
# The gaps a study still has, ranked: the map's Next interviews view computes the same list (nxGaps in the template).
OPEN_GAP_ORDER = ("step", "need", "who")
NEXT_LEVEL = (3, 8)  # conversations for "Early signs" and for "A clear pattern", as the map's overSure() counts them


def _natural(ref: str) -> list[Any]:
    return [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", ref)]


def learn_of(kb: Json, job: str) -> Json:
    """The core job's overview `next.learn`: the plan for the next round, or {} when there is none."""
    entry = next(iter(overviews_of(kb, job)), {})
    learn = entry.get("next", {}).get("learn") if isinstance(entry.get("next"), dict) else None
    return learn if isinstance(learn, dict) else {}


def live_outcome(kb: Json, ref: str) -> str:
    """Follow merged_into, so a plan written before a merge still points at the outcome that holds the evidence."""
    by_id = {str(o["id"]): o for o in kb["desired_outcomes"]["outcomes"]}
    seen: set[str] = set()
    while ref in by_id and by_id[ref].get("merged_into") and ref not in seen:
        seen.add(ref)
        ref = str(by_id[ref]["merged_into"])
    return ref


def open_gaps(kb: Json, job: str, learn: Json | None = None) -> list[Json]:
    """Thin steps, needs heard once (or from fewer than 3 under the main finding), unheard kinds; main first."""
    learn = learn_of(kb, job) if learn is None else learn
    live = {str(o["id"]): o for o in kb["desired_outcomes"]["outcomes"]
            if not o.get("merged_into") and job_of(str(o["step"])) == job}
    main = {ref for ref in (live_outcome(kb, str(r)) for r in learn.get("rests_on") or []) if ref in live}
    main_steps = {str(live[ref]["step"]) for ref in main}
    gaps = []
    for step in kb["job_map"]["steps"]:
        key = step_key(step)
        if step.get("job") == job and step.get("voices", 0) < THIN_STEP:
            people = set(step.get("interviews", [])).union(*[o.get("interviews", []) for o in live.values()
                                                             if str(o["step"]) == key])
            gaps.append({"ref": key, "kind": "step", "main": key in main_steps, "people": sorted(people),
                         "text": step["statement"]})
    for ref, outcome in live.items():
        if outcome.get("interview_count", 0) <= 1 or (ref in main and outcome.get("interview_count", 0) < THIN_STEP):
            gaps.append({"ref": ref, "kind": "need", "main": ref in main, "people": outcome.get("interviews", []),
                         "text": outcome["statement"]})
    for trait in learn.get("traits") or []:
        for value in trait.get("values") or [] if isinstance(trait, dict) else []:
            if isinstance(value, dict) and not value.get("interviews"):
                gaps.append({"ref": str(value.get("id")), "kind": "who", "main": False, "people": [],
                             "text": f"{trait.get('name', '')}: {value.get('label', '')}"})
    return sorted(gaps, key=lambda g: (not g["main"], OPEN_GAP_ORDER.index(g["kind"]), len(g["people"]),
                                       _natural(g["ref"])))


def round_snapshot(kb: Json, learn: Json) -> Json:
    """What a plan aimed at, and who had been heard."""
    values = {v["id"]: v["label"] for t in learn.get("traits") or [] for v in t["values"]}
    refs = list(dict.fromkeys(ref for entry in learn.get("round") or [] for ref in entry["gaps"]))
    return {"written": today(), "interviews": sorted(str(r["id"]) for r in kb["interviews"]),
            "targets": [{"ref": ref, "label": values.get(ref, "")} for ref in refs]}


def last_round(kb: Json, job: str) -> Json | None:
    """How many of the last round's targets closed; a renamed kind of person is not counted."""
    learn = learn_of(kb, job)
    if not isinstance(learn.get("previous"), dict):
        return None
    labels = {v.get("id"): v.get("label") for t in learn.get("traits") or [] for v in t.get("values") or []}
    known = {step_key(s) for s in kb["job_map"]["steps"] if s.get("job") == job} | {
        str(o["id"]) for o in kb["desired_outcomes"]["outcomes"] if job_of(str(o["step"])) == job}
    targets = [ref for t in learn["previous"].get("targets") or []  # a moved outcome's old ID is gone, not closed
               for ref in [str(t.get("ref")) if t.get("label") else live_outcome(kb, str(t.get("ref")))]
               if (labels.get(ref) == t["label"] if t.get("label") else ref in known)]
    still = [ref for ref in targets if ref in {g["ref"] for g in open_gaps(kb, job)}]
    return {"closed": len(targets) - len(still), "targeted": len(targets), "open": still}


def job_people(kb: Json, job: str) -> list[str]:
    """A core job's people as the map counts them: main, related, and anyone quoted on its parts."""
    job_entry = jobs_by_id(kb).get(job, {})
    people = set(job_entry.get("interviews", [])) | set(job_entry.get("related_interviews", []))
    for step in kb["job_map"]["steps"]:
        if step.get("job") == job:
            people.update(step.get("interviews", []))
    for outcome in kb["desired_outcomes"]["outcomes"]:
        if not outcome.get("merged_into") and job_of(str(outcome["step"])) == job:
            people.update(outcome.get("interviews", []))
    for solution in solutions_of(kb):
        for use in solution.get("uses") or []:
            if job_of(str(use.get("step", ""))) == job:
                people.update(str(e.get("interview")) for e in use.get("evidence") or [])
    return sorted(people)


def sure_level(kb: Json, job: str) -> Json:
    """The map's "How sure is this?" level (overSure) and the conversations to the next one."""
    many = len(kb["core_jobs"]) > 1
    scope = [r for r in kb["interviews"] if not many or str(r["id"]) in set(job_people(kb, job))]
    order = sorted(scope, key=lambda r: (str(r.get("date") or ""), _natural(str(r["id"]))))
    last, early = {str(r["id"]) for r in order[-2:]}, {str(r["id"]) for r in order[:-2]}
    fresh = sum(1 for o in kb["desired_outcomes"]["outcomes"]
                if not o.get("merged_into") and job_of(str(o["step"])) == job
                and set(o.get("interviews", [])) & last and not set(o.get("interviews", [])) & early)
    n = len(order)
    level = 1 if n < NEXT_LEVEL[0] else 3 if n >= NEXT_LEVEL[1] and fresh <= 2 else 2
    to_next = NEXT_LEVEL[0] - n if level == 1 else max(NEXT_LEVEL[1] - n, 0) if level == 2 else 0
    return {"level": level, "conversations": n, "fresh": fresh, "to_next": to_next}


def stale_layers(kb: Json) -> list[str]:
    return [key for key in DERIVED if isinstance(kb.get(key), dict) and kb[key].get("stale")]


# ---------- current solutions ----------
# Optional; made by the first merge that adds a solution. Readers are lenient about its shape, because recount runs
# before the structure check.
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
# Written by `themes`, per core job. A theme with no ID predates that command: kept as is, never counted or checked.
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
_TYPE_NAMES = {dict: "object", list: "array", str: "string", bool: "boolean", int: "integer",
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
    """Readable JSON Schema problems, at most MAX_PROBLEMS: jsonschema when installed, else a built-in checker that
    refuses any keyword it does not know."""
    plain = copy.deepcopy(data)
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
                " and/or ": "and/or", "/": "a slash", "（": "brackets", "；": "a semicolon", "／": "a slash",
                "؛": "a semicolon"}  # the last four: the full-width and Arabic forms
DIRECTIONS = ["Minimize ", "Maximize ", "Increase ", "Reduce "]  # how an outcome starts, in an English study
NEED_START = "Help me "  # how a value theme's need starts, in an English study


@dataclass
class Style:
    """Writing rules the merge enforces. A study can override any of them in meta.style."""

    limits: dict[str, int] = field(default_factory=lambda: {
        "executor": 16, "job": 10, "step": 10, "outcome": 16, "feeling": 12, "rationale": 30,
        "solution": 6, "group": 6, "theme": 6, "need": 25,
        "headline": 20, "finding": 50, "action": 20, "role": 4, "who": 25,
        "plan_who": 15, "question": 25, "listen": 15})
    banned: list[str] = field(default_factory=lambda: list(BANNED_NAMES))
    idioms: list[str] = field(default_factory=lambda: ["bread and butter", "in and out"])
    acronyms: list[str] = field(default_factory=lambda: ["OTR", "US", "UK", "EU"])
    language: str = ENGLISH
    # Fixed openings of outcomes and needs: English has them; other languages only if meta.style sets them.
    directions: list[str] = field(default_factory=lambda: list(DIRECTIONS))
    need_start: str = NEED_START

    @property
    def english(self) -> bool:
        return base_language(self.language) == ENGLISH


def style_of(kb: Json) -> Style:
    style = Style(language=study_language(kb))
    given = kb["meta"].get("style") or {}
    if not isinstance(given, dict):
        raise KbError("meta.style must be an object with any of: limits, banned, idioms, acronyms, directions, "
                      "need_start", code="style_invalid")
    if not style.english:
        style.directions, style.need_start = [], ""
        if base_language(style.language) not in NO_SPACES:  # the same statement takes more words than in English
            style.limits = {k: int(-(-v * WORDIER // 1)) for k, v in style.limits.items()}
        if base_language(style.language) == "el":  # in Greek, ; is the question mark
            style.banned = [token for token in style.banned if token != ";"]
    limits = given.get("limits") or {}
    if not isinstance(limits, dict):
        raise KbError('meta.style.limits must be an object such as {"outcome": 16}', code="style_invalid")
    style.limits.update({str(k): int(v) for k, v in limits.items()})
    for name in ("banned", "idioms", "acronyms", "directions"):
        if name in given:
            if not isinstance(given[name], list):
                raise KbError(f"meta.style.{name} must be a list", code="style_invalid")
            setattr(style, name, [str(x) for x in given[name]])
    if "need_start" in given:
        style.need_start = str(given["need_start"] or "")
    return style


def clarity(text: str, kind: str, label: str, style: Style, report: Report) -> None:
    """Reviewers read these statements cold. Keep each one short, single-idea and free of asides."""
    statement = (text or "").strip()
    words = count_words(statement, style.language)
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
    if kind in ("job", "step") and style.english and re.search(r"\b(and|or)\b", statement) \
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
    """Checks each quote appears word for word in its transcript. `lookup(reference)` returns (normalized text,
    None) or (None, why missing)."""

    def __init__(self, lookup: Lookup) -> None:
        self.lookup = lookup

    def check(self, items: list[Json], label: str, report: Report) -> None:
        if not items:
            report.error(f"{label}: needs at least one evidence item", code="evidence_missing")
            return
        for item in items:
            if not isinstance(item, dict):
                report.error(f"{label}: each evidence item must be an object with interview, source and quote",
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


class _PatchReader:
    """Reads interview IDs the way the patch writer meant them, and remembers the ones it had to pad: a bare
    number such as 7 becomes "07"."""

    def __init__(self, width: int) -> None:
        self.width = width
        self.fixed: set[str] = set()

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
            if key == "interview":
                node[key] = self.pad(value)
            elif key == "interviews" and isinstance(value, list):
                node[key] = [self.pad(v) for v in value]
                self.walk(node[key])
            else:
                self.walk(value)


def coerce_patch(patch: Any, width: int, report: Report) -> Json:
    """A bare interview number becomes a zero-padded ID, with a warning. Outcome IDs never: 2.10 as a number is
    2.1."""
    if patch is None:
        raise KbError("the patch file is empty", code="patch_empty")
    if not isinstance(patch, dict):
        raise KbError(f"the patch must be a JSON object with keys such as {', '.join(PATCH_SECTIONS)}",
                      code="patch_shape")
    reader = _PatchReader(width)
    reader.walk(patch)
    for proposal in patch.get("proposed_changes") or []:
        if isinstance(proposal, dict) and proposal.get("type") == "relink_interview":
            proposal["target"] = reader.pad(proposal.get("target"))
    if reader.fixed:
        report.warn(f"interview IDs were written as numbers and were read as {sorted(reader.fixed)}; write IDs as "
                    'text in quotes, like "01"', code="ids_unquoted")
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
    """Turns bare step and outcome IDs ("6", "6.3") into full ones ("A.6", "A.6.3"); done only with exactly one core
    job."""

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
    """Drop new groups the KB already holds (so a batch can re-run) or whose solutions all came from skipped
    interviews. A new group no solution goes into is refused. `wanted`: groups_wanted() before that drop."""
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
    """The provenance block with transcript references turned into interview IDs. An unknown reference is dropped
    with a warning (usually a file name, which carries a name); one naming a skipped interview, quietly."""
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
        if ctx.style.directions and not statement.startswith(tuple(ctx.style.directions)):
            names = [d.strip() for d in ctx.style.directions]
            starts = " or ".join([", ".join(names[:-1]), names[-1]] if len(names) > 1 else names)
            ctx.report.error(f"{label}: an outcome must start with {starts}", code="outcome_direction")
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
        if count_words(str(proposal.get("rationale", "")), ctx.style.language) > limit:
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
    """Fold a checked patch into the KB. Returns the changelog entry, or None when nothing is new. `stamp`: patch
    name, ts, run_id and provenance."""
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
    patch = coerce_patch(load_json(args.patch), id_width(kb), report)
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
    """Link an interview's own job to a core job, keeping the old link and reason in its history. Unlinking records
    why, so a linked person never shows as having no job."""
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
    data = load_json(path)
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
    """One theme of the file in a known shape, or None when it is not an object."""
    if not isinstance(item, dict):
        report.error(f"{label}: must be an object with label, need, why and outcomes", code="theme_shape")
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
    start = ctx.style.need_start
    if start and theme["need"] and not theme["need"].startswith(start):
        ctx.report.error(f"{label}: the need must start with '{start.strip()}', in the customer's voice: "
                         f"'{theme['need']}'", code="theme_need_form")
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
    """Replace the core job's themes and clear the stale flag. Returns how many hand-written themes were dropped."""
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
# One core job's study as a short story, written by `overview`. The layer holds only the assistant's sentences; the
# map counts the rest, and every quote must already be in the KB.
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
    """Quotes an overview may show: on the job's steps, outcomes and solution uses, and linked people's own words."""
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
    data = load_json(path)
    if not isinstance(data, dict) or not data.get("job"):
        raise KbError(f"{path} must be an object with `job` (a core job ID such as A) and the overview of that core "
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
    _ov_plain(ctx, text, f"{label} {key}")
    return text


def _ov_no_score(ctx: OverviewChecks, text: str, label: str) -> None:
    """Interviews show what people said, not how much it matters: an overview carries no score and no percentage."""
    if SCORE_WORDS.search(text):
        ctx.report.error(f"{label}: no percentages and no score words in an overview; say how many people said it: "
                         f"'{text}'", code="overview_score")


def _ov_plain(ctx: OverviewChecks, text: str, label: str) -> None:
    """A first-time reader must understand every sentence on first read: no words of the method, few buzzwords."""
    for pattern, word, hint in METHOD_TERMS:
        if pattern.search(text):
            ctx.report.error(f"{label}: '{word}' is a word of the method that readers do not know; write "
                             f"{hint}: '{text}'", code="overview_method_word")
    for pattern, word, hint in JARGON_TERMS:
        if pattern.search(text):
            ctx.report.warn(f"{label}: '{word}' is vague; {hint}, unless it is the customers' own word: '{text}'",
                            code="overview_jargon")


def _ov_mapping(ctx: OverviewChecks, data: Any, key: str, allowed: tuple[str, ...], label: str) -> Json:
    section = data.get(key) if isinstance(data, dict) else None
    if not isinstance(section, dict):
        ctx.report.error(f"{label}: {key} must be an object with {', '.join(allowed)}", code="overview_shape")
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


def _ov_executor(ctx: OverviewChecks, data: Json) -> Json:
    """Who the study is about: label, sentence, a drawable icon, and others in the story."""
    section = _ov_mapping(ctx, data, "executor", EXECUTOR_KEYS, "overview")
    out: Json = {"label": _ov_text(ctx, section, "label", "role", "executor"),
                 "text": _ov_text(ctx, section, "text", "who", "executor")}
    icon = str(section.get("icon") or "").strip()
    if section and icon not in ROLE_ICONS:
        ctx.report.error(f"executor: icon {f'{icon!r} is not one the map can draw' if icon else 'is missing'}; "
                         f"pick one of {', '.join(ROLE_ICONS)} (person when none fits)", code="overview_shape")
    out["icon"] = icon or "person"
    others = section.get("others")
    if others is None:
        return out
    if not isinstance(others, list) or not all(isinstance(x, str) and x.strip() for x in others):
        ctx.report.error(f"executor: others must be a list of at most {EXECUTOR_OTHERS} people, such as "
                         "'their clients'", code="overview_shape")
        return out
    items = [x.strip() for x in others]
    if len(items) > EXECUTOR_OTHERS:
        ctx.report.error(f"executor: others holds {len(items)} people; keep at most {EXECUTOR_OTHERS}",
                         code="overview_count")
    for text in items:
        clarity(text, "role", "executor others", ctx.style, ctx.report)
        _ov_plain(ctx, text, "executor others")
    if items:
        out["others"] = items
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
        ctx.report.error(f"{label}: must be an object with {', '.join(keys)}", code="overview_shape")
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
        if key != "words":  # the customers' own words stay as they said them
            _ov_plain(ctx, text, f"{label} {key}")
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
    extra = LEARN_PLAN if name == "learn" else ()
    track = _ov_mapping(ctx, data, name, ("status", "action", *fields, *extra), "next")
    out: Json = {"status": str(track.get("status") or ""), "action": _ov_text(ctx, track, "action", "action", label)}
    if out["status"] not in statuses:
        ctx.report.error(f"{label}: status must be one of {', '.join(statuses)}", code="overview_shape")
    for key in fields:
        out[key] = _ov_list(ctx, track, key, label) if key in NEXT_LISTS else \
            _ov_text(ctx, track, key, "rationale", label)
    if out.get("words"):
        _ov_words(ctx, out["words"], label)
    if any(key in track for key in extra):
        _ov_plan(ctx, track, out)
    return out


def _ov_refs(ctx: OverviewChecks, given: Any, allowed: set[str], most: int, label: str, *,
             least: int = 1) -> list[str]:
    if not isinstance(given, list) or not all(isinstance(x, str) for x in given):
        ctx.report.error(f"{label} must be a list of IDs", code="overview_shape")
        return []
    if not least <= len(given) <= most:
        ctx.report.error(f"{label} holds {len(given)} IDs; give {least} to {most}", code="overview_count")
    unknown = [ref for ref in given if ref not in allowed]
    if unknown:
        ctx.report.error(f"{label}: {', '.join(unknown)} is not a step, outcome or trait value of core job {ctx.job} "
                         "it may name", code="overview_ref")
    return list(given)


def _ov_traits(ctx: OverviewChecks, given: Any) -> list[Json]:
    """2 or 3 traits, each value with its people (none: not heard yet)."""
    if not isinstance(given, list) or not TRAIT_COUNT[0] <= len(given) <= TRAIT_COUNT[1]:
        ctx.report.error("next.learn: traits must be a list of 2 or 3 traits", code="overview_count")
    main = {str(r["id"]) for r in ctx.kb["interviews"] if main_job(r) == ctx.job}
    traits = []
    for trait in given if isinstance(given, list) else []:
        tid = str(trait.get("id") or "") if isinstance(trait, dict) else ""
        values = trait.get("values") if isinstance(trait, dict) else None
        if not TRAIT_ID.match(tid):
            ctx.report.error(f"next.learn: a trait needs an id like T1, not '{tid}'", code="overview_shape")
        if not isinstance(values, list) or not TRAIT_VALUES[0] <= len(values) <= TRAIT_VALUES[1]:
            ctx.report.error(f"next.learn {tid}: a trait has 2 to 5 values", code="overview_count")
        kept, seen = [], set()
        for value in values if isinstance(values, list) else []:
            vid = str(value.get("id") or "") if isinstance(value, dict) else ""
            if not (TRAIT_VALUE_ID.match(vid) and vid.startswith(f"{tid}.")):
                ctx.report.error(f"next.learn {tid}: value '{vid}' needs an id like {tid}.1", code="overview_shape")
            people = [str(i) for i in (value.get("interviews") or [] if isinstance(value, dict) else [])]
            if set(people) - main:
                ctx.report.error(f"next.learn {vid}: {', '.join(sorted(set(people) - main))} is no one whose main goal "
                                 f"is core job {ctx.job}", code="overview_ref")
            if seen & set(people):
                ctx.report.error(f"next.learn: {', '.join(sorted(seen & set(people)))} is in two values of {tid}",
                                 code="overview_shape")
            seen |= set(people)
            kept.append({"id": vid, "label": _ov_text(ctx, value, "label", "role", f"next.learn {vid}"),
                         "interviews": people})
        traits.append({"id": tid, "name": _ov_text(ctx, trait, "name", "role", f"next.learn {tid}"), "values": kept})
    for twice in _duplicates([t["id"] for t in traits] + [v["id"] for t in traits for v in t["values"]]):
        ctx.report.error(f"next.learn: {twice} is used twice", code="overview_shape")
    return traits


def _ov_question(ctx: OverviewChecks, item: Any, gaps: list[str], label: str) -> Json:
    item = _ov_mapping(ctx, {"question": item}, "question", ("ask", "listen", "gaps"), label)
    ask = _ov_text(ctx, item, "ask", "question", label)
    refs = _ov_refs(ctx, item.get("gaps"), set(gaps), ROUND_ITEMS, f"{label} gaps")
    stray = [ref for ref in refs if ref not in gaps]
    if stray:
        ctx.report.error(f"{label}: {', '.join(stray)} is not one of this entry's gaps", code="overview_shape")
    if ctx.style.english and LEADING.search(ask):
        ctx.report.warn(f"{label}: '{ask}' asks what they would do; ask about the last time they did it",
                        code="plan_leading")
    return {"ask": ask, "listen": _ov_text(ctx, item, "listen", "listen", label), "gaps": refs}


def _ov_round(ctx: OverviewChecks, given: Any, refs: set[str], values: set[str]) -> list[Json]:
    """Who to talk to next, in order, with the gaps each fills and the questions."""
    if not isinstance(given, list) or not given or len(given) > ROUND_MAX:
        count = len(given) if isinstance(given, list) else 0
        ctx.report.error(f"next.learn: round holds {count} entries; keep at most {ROUND_MAX}, at least 1",
                         code="overview_count")
    entries = []
    for n, raw in enumerate(given if isinstance(given, list) else [], 1):
        where = f"next.learn round {n}"
        entry = _ov_mapping(ctx, {"entry": raw}, "entry", ("kind", "count", "who", "traits", "gaps", "questions"),
                             where)
        count = entry.get("count")
        if entry.get("kind") != "new":
            ctx.report.error(f"{where}: kind must be new", code="overview_shape")
        if not (isinstance(count, int) and not isinstance(count, bool) and ROUND_COUNT[0] <= count <= ROUND_COUNT[1]):
            ctx.report.error(f"{where}: count must be 1 to 3 people", code="overview_shape")
        gaps = _ov_refs(ctx, entry.get("gaps"), refs, ROUND_ITEMS, f"{where} gaps")
        asks = entry.get("questions")
        if not isinstance(asks, list) or not 1 <= len(asks) <= ROUND_ITEMS:
            ctx.report.error(f"{where}: questions must be a list of 1 to {ROUND_ITEMS}", code="overview_count")
        out: Json = {"kind": "new", "count": count, "who": _ov_text(ctx, entry, "who", "plan_who", where)}
        if entry.get("traits"):
            out["traits"] = _ov_refs(ctx, entry["traits"], values, ROUND_ITEMS, f"{where} traits")
        out["gaps"] = gaps
        out["questions"] = [_ov_question(ctx, q, gaps, f"{where} question {i}")
                            for i, q in enumerate(asks if isinstance(asks, list) else [], 1)]
        entries.append(out)
    return entries


def _ov_plan(ctx: OverviewChecks, track: Json, out: Json) -> None:
    """The plan for the next round; every ref belongs to this core job."""
    traits = _ov_traits(ctx, track.get("traits"))
    values = {v["id"] for t in traits for v in t["values"]}
    steps = {step_key(s) for s in ctx.kb["job_map"]["steps"] if s.get("job") == ctx.job}
    outs = {str(o["id"]) for o in ctx.kb["desired_outcomes"]["outcomes"]
            if not o.get("merged_into") and job_of(str(o["step"])) == ctx.job}
    out["traits"] = traits
    out["rests_on"] = _ov_refs(ctx, track.get("rests_on"), outs, RESTS_ON_MAX, "next.learn rests_on")
    out["round"] = _ov_round(ctx, track.get("round"), steps | outs | values, values)
    gaps = open_gaps(ctx.kb, ctx.job, out)
    covered = {ref for entry in out["round"] for ref in entry["gaps"]}
    closed = sorted(covered - {g["ref"] for g in gaps})
    if closed:
        ctx.report.warn(f"next.learn round: {', '.join(closed)} is not an open gap any more; aim at what is thin",
                        code="plan_gap_closed")
    bare = [g["ref"] for g in gaps if g["main"] and g["ref"] not in covered]
    if bare:
        ctx.report.warn(f"next.learn round: the main finding rests on {', '.join(bare)}, which no entry covers",
                        code="plan_main_uncovered")
    if out["status"] == "enough" and any(g["main"] or g["kind"] == "step" for g in gaps):
        ctx.report.warn("next.learn: status is enough while thin steps or main-finding gaps remain", code="plan_status")


def build_overview(kb: Json, job: str, data: Json, report: Report) -> Json:
    """Check the file's overview against the KB and return it as the KB stores it."""
    ctx = OverviewChecks(kb, job, style_of(kb), report, _overview_pool(kb, job), id_width(kb))
    entry: Json = {"job": job, "executor": _ov_executor(ctx, data),
                   "bottom_line": _ov_text(ctx, data, "bottom_line", "headline", "overview"),
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


def _executor_label(entry: Json) -> str:
    """The label of whom an overview is about; empty for an overview written before it had one."""
    who = entry.get("executor")
    return str(who.get("label") or "") if isinstance(who, dict) else ""


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
    who = entry["executor"]
    lines = [f"OVERVIEW for core job {job}: {jobs_by_id(kb)[job]['statement']}",
             f"about: {who['label']} [{who['icon']}]: {who['text']}"
             + (f" (also in the story: {', '.join(who['others'])})" if who.get("others") else ""),
             f"bottom line: {entry['bottom_line']}", f"opening: {entry['opening']}"]
    lines += [f"{key}: {entry[key]['answer']}" for key in ("people", "today", "gaps", "needs", "focus")]
    lines += [f"   gap ({g['kind']}): {g['label']}" for g in entry["gaps"]["items"]]
    lines += [f"next, {name} ({track['status']}): {track['action']}" for name, track in entry["next"].items()]
    lines += [f"next, learn round: {e['count']} × {e['who']} (gaps {', '.join(e['gaps'])})"
              for e in entry["next"]["learn"].get("round", [])]
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
    learn, old = entry["next"]["learn"], learn_of(kb, job)
    if learn.get("round"):
        learn["at_write"] = round_snapshot(kb, learn)
        was = old.get("at_write") if isinstance(old.get("at_write"), dict) else {}
        moved = bool(was) and was.get("interviews") != learn["at_write"]["interviews"]  # a batch came in since
        if moved or isinstance(old.get("previous"), dict):
            learn["previous"] = was if moved else old["previous"]
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
    old = os.path.join(os.path.dirname(args.kb), OLD_KB_FILE)
    if os.path.isfile(old):
        raise KbError(f"{old} holds a study written by an earlier version; refusing to start another. Run "
                      f"`kb_tool.py migrate {old}` to keep working on it", code="kb_exists")
    if os.path.exists(args.kb):
        raise KbError(f"{args.kb} exists; refusing to overwrite", code="kb_exists")
    language = normalize_language(args.language) if args.language else ENGLISH
    kb = ensure({"meta": {"project": args.project, "language": language, "method": "Outcome-Driven Innovation (Ulwick)",
                          "interviewer": args.interviewer or "", "created": today(), "interview_count": 0}})
    kb["job_map"]["stages"] = [{"key": k, "name": k.capitalize()} for k in STAGES]
    kb["changelog"].append(changelog_entry(args.run, "init"))
    folder = os.path.dirname(os.path.abspath(args.kb))
    os.makedirs(folder, exist_ok=True)
    save_kb(kb, args.kb)
    args.run.note(written=True)
    note = git_note(args.kb)
    args.run.note(git=bool(note), language=language)
    print(f"created {args.kb} (language {language})" + (f"\n{note}" if note else ""))
    if base_language(language) != ENGLISH:  # a scripted start: the labels to write come with it
        labels_todo(kb, args, language)
    return 0


def _job_steps(kb: Json, job: str) -> list[Json]:
    by_step: dict[str, list[Json]] = {}
    for outcome in kb["desired_outcomes"]["outcomes"]:
        if not outcome.get("merged_into"):
            by_step.setdefault(str(outcome["step"]), []).append(outcome)
    steps = sorted((s for s in kb["job_map"]["steps"] if s.get("job") == job), key=lambda s: int(s["n"]))
    return [{"id": step_key(step), "stage": step.get("stage", ""), "statement": step["statement"],
             "coverage": step.get("coverage", 0), "voices": step.get("voices", 0),
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
             "analyst_note": r.get("analyst_note", ""), "tags": r.get("tags") or []}
            for r in kb["interviews"]]


def context_data(kb: Json) -> Json:
    jobs = [{"id": str(job["id"]), "statement": job["statement"], "status": job.get("status", ""),
             "job_executor": job.get("job_executor", ""), "interviews": job.get("interviews", []),
             "related_interviews": job.get("related_interviews", []), "steps": _job_steps(kb, str(job["id"]))}
            for job in kb["core_jobs"]]
    people = people_data(kb)
    return {"project": kb["meta"].get("project", ""), "language": study_language(kb),
            "interview_count": len(kb["interviews"]),
            "core_jobs": jobs, "people": people, "open_gaps": {j["id"]: open_gaps(kb, j["id"]) for j in jobs},
            "unlinked": [p["id"] for p in people if not p["job"]],
            "segments": {k: v.get("name", "") for k, v in (kb.get("clusters") or {}).items()},
            "processed_files": sorted(interviews_by_file(kb)),
            "pending_proposals": [{"id": p["id"], "type": p["type"], "target": p.get("target") or p.get("job") or "",
                                   "proposal": p.get("proposal", "")}
                                  for p in kb["proposed_changes"] if p.get("status") == "pending"],
            "current_solutions": solutions_data(kb), "value_themes": themes_data(kb),
            "overview": [{"job": str(o["job"]), "bottom_line": o.get("bottom_line", ""),
                          "executor": _executor_label(o), "written": o.get("written", "")}
                         for o in overviews_of(kb)],
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
        (f"; also {', '.join(also)}" if also else "") + (f" [{', '.join(person['tags'])}]" * bool(person["tags"]))


def _print_jobs(data: Json) -> None:
    print(f"PROJECT {data['project']}  language={data['language']}  interviews={data['interview_count']}  "
          f"core jobs={len(data['core_jobs'])}")
    if data.get("labels_missing"):
        print(f"LABELS: {data['labels_missing']} labels of the map and the review sheet have no {data['language']} "
              f"text yet; write them first: kb_tool labels {KB_HOME}")
    if not data["core_jobs"]:
        print("CORE JOB: (none yet: bootstrap)")
    for job in data["core_jobs"]:
        print(f"\nCORE JOB {job['id']}: {job['statement']}  [{job['status']}]")
        if job["job_executor"]:
            print(f"  EXECUTOR: {job['job_executor']}")
        main, also = ", ".join(job["interviews"]) or "none", ", ".join(job["related_interviews"]) or "none"
        print(f"  PEOPLE: main {main}; also {also}")
        for step in job["steps"]:
            print(f"STEP {step['id']} [{step['stage']}] {step['statement']}  (people {step['voices']})")
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
    kb = load_kb(args.kb)
    data = context_data(kb)
    data["labels_missing"] = study_labels(kb, args.kb)[1]
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        return 0
    _print_jobs(data)
    for job, gaps in data["open_gaps"].items():
        if gaps:
            sure = sure_level(kb, job)
            after = f"{sure['to_next']} more reach the next" if sure["to_next"] else "next: new ones stop adding needs"
            print(f"\nOPEN GAPS for core job {job} (main finding first; next.learn's round should cover the top ones)"
                  f"\n  level {sure['level']} of 3 after {sure['conversations']} conversations"
                  + f"; {after}" * (sure["level"] < 3))
        for g in gaps:
            who = f"people {len(g['people'])}: {', '.join(g['people'])}" if g["people"] else "nobody yet"
            print(f"  {g['ref']} [{g['kind']}{', main' * g['main']}] {g['text']}  ({who})")
    _print_solutions(data["current_solutions"])
    _print_themes(data["value_themes"], "value_themes" in data["stale"])
    if data["overview"]:
        old = "overview" in data["stale"] or any(not entry["executor"] for entry in data["overview"])
        print("\nOVERVIEW" + (" [out of date]" if old else ""))
        for entry in data["overview"]:
            about = f" (about: {entry['executor']})" if entry["executor"] else \
                " (written before the map showed who the study is about: write it again)"
            print(f"{entry['job']} written {entry['written']}: {entry['bottom_line']}{about}")
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
# Words come from labels; each table writes its keys in full so a test can check they exist.
PROPOSAL_LABELS = {"new_step": "review.proposal.new_step", "reword_step": "review.proposal.reword_step",
                   "reword_outcome": "review.proposal.reword_outcome",
                   "reword_core_job": "review.proposal.reword_core_job",
                   "merge_outcomes": "review.proposal.merge_outcomes", "move_outcome": "review.proposal.move_outcome",
                   "new_segment": "review.proposal.new_segment", "new_core_job": "review.proposal.new_core_job",
                   "confirm_core_job": "review.proposal.confirm_core_job", "move_step": "review.proposal.move_step",
                   "relink_interview": "review.proposal.relink_interview",
                   "merge_solutions": "review.proposal.merge_solutions",
                   "move_solution": "review.proposal.move_solution",
                   "reword_solution": "review.proposal.reword_solution",
                   "reword_solution_group": "review.proposal.reword_solution_group"}
STAGE_LABELS = {"define": "review.stage.define", "locate": "review.stage.locate", "prepare": "review.stage.prepare",
                "confirm": "review.stage.confirm", "execute": "review.stage.execute",
                "monitor": "review.stage.monitor", "modify": "review.stage.modify",
                "conclude": "review.stage.conclude"}
LAYER_LABELS = {"survey": "review.layer.survey", "simulation": "review.layer.simulation",
                "value_themes": "review.layer.value_themes", "overview": "review.layer.overview",
                "use_cases": "review.layer.use_cases"}


def describe_proposal(proposal: Json, text: Text | None = None) -> str:
    text = text or Text()
    kind = str(proposal.get("type"))
    if kind == "relink_interview" and not proposal.get("job"):
        return text("review.proposal.unlink_interview", target=proposal.get("target"))
    values = {key: proposal.get(key) for key in ("job", "target", "merge", "to_step", "to_job", "to_group")}
    return text(PROPOSAL_LABELS.get(kind, "review.proposal.other"), **values)


def kind_text(text: Text, kind: Any) -> str:
    return text(KIND_LABELS[str(kind)]) if str(kind) in KIND_LABELS else str(kind)


def _review_head(kb: Json, live_outcomes: list[Json], text: Text) -> list[str]:
    in_use = [s for s in live_solutions(kb) if s.get("interviews")]
    solutions = " · " + text("review.count.solutions_in_use", n=len(in_use)) if "current_solutions" in kb else ""
    project = kb["meta"]["project"] if "project" in kb["meta"] else text("review.project_default")
    counts = " · ".join([text("review.count.interviews", n=len(kb["interviews"])),
                         text("review.count.core_jobs", n=len(kb["core_jobs"])),
                         text("review.count.steps", n=len(kb["job_map"]["steps"])),
                         text("review.count.outcomes", n=len(live_outcomes))])
    updated = text("review.updated", date=today())
    lines = ["# " + text("review.title", project=project), "", f"{counts}{solutions} · {updated}", ""]
    if not kb["core_jobs"]:
        return lines + [f"**{text('review.core_job')}:** {text('review.not_set')}", ""]
    proposed = f" *({text('review.proposed')})*"
    for job in kb["core_jobs"]:
        name = text("review.core_job_id", id=job["id"])
        lines.append(f"- **{name}:** {job['statement']}" + (proposed if job.get("status") == "proposed" else ""))
    return lines + [""]


def _review_decisions(kb: Json, text: Text) -> list[str]:
    pending = [p for p in kb["proposed_changes"] if p.get("status") == "pending"]
    lines = ["## " + text("review.h.decisions"), ""]
    if not pending:
        return lines + [text("review.none"), ""]
    why = text("review.why")
    for proposal in pending:
        lines.append(f"- **{proposal['id']} · {describe_proposal(proposal, text)}:** {proposal['proposal']}. "
                     f"*{why}:* {proposal['rationale']}")
    return lines + ["", text("review.reply"), ""]


def _new_solution_lines(kb: Json, since: str, text: Text) -> list[str]:
    groups = groups_of(kb)
    lines = []
    for group in groups.values():
        if since and str(group.get("added", "")) >= since:
            name = "**" + str(group.get("name", "")) + ":**"
            lines.append(f"- {text('review.new_group', name=name)} {group.get('why', '')}")
    for solution in live_solutions(kb):
        if since and str(solution.get("added", "")) >= since:
            group = groups.get(str(solution.get("group")), {}).get("name", solution.get("group"))
            named = "**" + f"{solution['id']} {solution.get('name', '')}" + "**"
            lines.append("- " + text("review.new_solution", solution=named, kind=kind_text(text, solution.get("kind")),
                                     group=f"*{group}*"))
    return lines


def _review_new(kb: Json, since: str, new_outcomes: set[str], text: Text) -> list[str]:
    new_interviews = [i for i in kb["interviews"] if since and str(i.get("added", "")) >= since]
    solution_lines = _new_solution_lines(kb, since, text)
    if not (new_interviews or new_outcomes or solution_lines):
        return []
    lines = ["## " + text("review.h.new", date=since), ""]
    for record in new_interviews:
        job = main_job(record)
        link = text("review.core_job_ref", id=job) if job else text("review.no_core_job_yet")
        own = text("review.new_interview_job", job=f"*{record['core_functional_job']['statement']}*", link=link)
        lines.append(f"- **{record['id']} {record.get('name', '')}:** {record['job_executor']['statement']} {own}")
    for outcome in kb["desired_outcomes"]["outcomes"]:
        if outcome["id"] in new_outcomes:
            label = text("review.new_outcome", id=f"**{outcome['id']}:**")
            lines.append(f"- {label} {outcome['statement']}")
    return lines + solution_lines + [""]


def _review_map(kb: Json, live_outcomes: list[Json], new_outcomes: set[str], text: Text) -> list[str]:
    by_step: dict[str, list[Json]] = {}
    for outcome in live_outcomes:
        by_step.setdefault(str(outcome["step"]), []).append(outcome)
    lines: list[str] = []
    for index, job in enumerate(kb["core_jobs"]):
        lines += [f"## {text('review.core_job_id', id=job['id'])}: {job['statement']}", ""]
        if index == 0:
            lines += [text("review.map_hint"), ""]
        ordered = sorted((s for s in kb["job_map"]["steps"] if s.get("job") == job["id"]), key=lambda s: int(s["n"]))
        for stage in STAGES:
            steps = [s for s in ordered if s.get("stage") == stage]
            if not steps:
                continue
            lines.append("### " + text(STAGE_LABELS[stage]))
            for step in steps:
                lines.append(f"**{step_key(step)} {step['statement']}** [{step.get('voices', 0)}]")
                for outcome in by_step.get(step_key(step), []):
                    mark = "● " if outcome["id"] in new_outcomes else ""
                    count = outcome.get("interview_count", 0)
                    lines.append(f"- {mark}{outcome['id']} {outcome['statement']} [{count}]")
                lines.append("")
    return lines


def _solution_line(solution: Json, steps: dict[str, Json], names: dict[str, str], text: Text) -> str:
    sep = text("review.list_sep")
    used = sep.join(f"{steps[s]['statement']} ({s})" if s in steps else s for s in solution_steps(solution))
    people = sep.join(names.get(i, i) for i in solution.get("interviews", []))
    stopped = sep.join(names.get(i, i) for i in solution.get("stopped_by", []))
    mentions = text("review.count.mentions", n=solution.get("quote_count", 0))
    return (f"- **{solution['id']} {solution.get('name', '')}** ({kind_text(text, solution.get('kind'))}) "
            f"[{len(solution.get('interviews', []))}] {people or text('review.nobody_now')} · {mentions} · "
            + text("review.used_for", steps=used)
            + (" · " + text("review.stopped", people=stopped) if stopped else ""))


def plural(count: int, word: str) -> str:
    return f"{count} {word}{'' if count == 1 else 's'}"


def _review_solutions(kb: Json, text: Text) -> list[str]:
    solutions = live_solutions(kb)
    if not solutions:
        return []
    steps, names = steps_by_id(kb), {str(r["id"]): str(r.get("name", "")) for r in kb["interviews"]}
    lines = ["## " + text("review.h.solutions"), "", text("review.solutions_intro"), ""]
    why = text("review.why_grouped")
    for key, group in groups_of(kb).items():
        members = sorted((s for s in solutions if s.get("group") == key and s.get("interviews")),
                         key=lambda s: (-len(s.get("interviews", [])), -s.get("quote_count", 0)))
        if members:
            lines += [f"### {group.get('name', key)}", "", f"*{why}:* {group.get('why', '')}", ""]
            lines += [_solution_line(s, steps, names, text) for s in members] + [""]
    gone = [s for s in solutions if not s.get("interviews")]
    if gone:
        lines += ["### " + text("review.h.stopped"), "", text("review.stopped_intro"), ""]
        lines += [_solution_line(s, steps, names, text) for s in gone] + [""]
    return lines


def _review_themes(kb: Json, text: Text) -> list[str]:
    themes = themes_of(kb)
    if not themes:
        return []
    outcomes = outcomes_by_id(kb)

    def rows(ids: list[str]) -> list[str]:
        return [f"- {outcomes[o]['statement']} ({o}) [{outcomes[o].get('interview_count', 0)}]"
                for o in ids if o in outcomes]

    stale = " " + text("review.themes_stale") if "value_themes" in stale_layers(kb) else ""
    lines = ["## " + text("review.h.themes"), "", text("review.themes_intro") + stale, ""]
    many = len(kb["core_jobs"]) > 1
    for theme in sorted(themes, key=lambda t: (job_index(str(t["job"])), -t.get("interview_count", 0))):
        where = f" ({text('review.core_job_ref', id=theme['job'])})" if many else ""
        lines += [f"### {theme.get('label', '')} [{theme.get('interview_count', 0)}]{where}", "",
                  f"*{theme.get('need', '')}*", ""]
        lines += ([theme["why"], ""] if theme.get("why") else []) + rows(theme_outcomes(theme)) + [""]
    left = unassigned_outcomes(kb)
    if left:
        lines += ["### " + text("review.h.no_theme"), ""] + rows(left) + [""]
    return lines


def _review_people(kb: Json, text: Text) -> list[str]:
    jobs = jobs_by_id(kb)
    named = [r for r in kb["interviews"] if main_job(r) or related_links(r)] if len(jobs) > 1 else []
    sep, also_word = text("review.list_sep"), text("review.also")
    lines = []
    if named:
        lines += ["## " + text("review.h.people"), ""]
        for record in named:
            parts = [f"{jobs[j]['statement']} ({j})" for j in [main_job(record)] if j and j in jobs]
            also = [f"{jobs[j]['statement']} ({j})" for j in dict.fromkeys(related_links(record))
                    if j in jobs and j != main_job(record)]
            joint = f"{sep}{also_word} " if parts and also else f"{also_word} " if also else ""
            lines.append(f"- **{record['id']} {record.get('name', '')}:** {sep.join(parts)}{joint}{sep.join(also)}")
        lines.append("")
    unlinked = [r for r in kb["interviews"] if not main_job(r)]
    if unlinked:
        lines += ["## " + text("review.h.unlinked"), ""]
        for record in unlinked:
            note = unlinked_reason(record) or record.get("analyst_note") or record["core_functional_job"]["statement"]
            lines.append(f"- **{record['id']} {record.get('name', '')}:** {note}")
        lines.append("")
    return lines


NX_GROUP_MAX = 5
NX_GROUPS = (("main", "review.nx.g.main"), ("step", "review.nx.g.step"), ("need", "review.nx.g.need"),
             ("who", "review.nx.g.who"))
NX_LEVELS = ("review.nx.level.1", "review.nx.level.2", "review.nx.level.3")
PLAIN = ((r"Minimize the time (it takes )?to ", "Less time to "), (r"Minimize the likelihood that ", "Less risk that "),
         (r"Minimize the likelihood of ", "Less risk of "), (r"Minimize the number of ", "Fewer "),
         (r"Minimize (the amount of |the )?", "Less "), (r"(Maximize|Increase) (the )?", "More "),
         (r"Reduce (the )?", "Less "))


def plain_outcome(statement: str) -> str:
    """An English outcome as the map words it: "Less risk of", not "Minimize"."""
    for pattern, new in PLAIN:
        if re.match(pattern, statement, re.I):
            return re.sub(pattern, new, statement, count=1, flags=re.I)
    return statement


def _nx_where(kb: Json, job: str, text: Text) -> list[str]:
    sure, last = sure_level(kb, job), last_round(kb, job)
    after = text("review.nx.to_next", n=sure["to_next"], level=text(NX_LEVELS[sure["level"]])) if sure["to_next"] \
        else text("review.nx.keep_going") * (sure["level"] == 2)
    lines = [text("review.nx.where", level=text(NX_LEVELS[sure["level"] - 1]), next=after).strip()]
    if last:
        lines.append(" ".join([text("review.nx.last", closed=last["closed"], targeted=last["targeted"])]
                              + [text("review.nx.still_open", list=", ".join(last["open"]))] * bool(last["open"])))
    return [*lines, ""]


def _nx_round(kb: Json, learn: Json, text: Text, guide: bool) -> list[str]:
    names = {step_key(s): s["statement"] for s in kb["job_map"]["steps"]}
    names.update({str(o["id"]): plain_outcome(o["statement"]) if guide and text.language == ENGLISH else o["statement"]
                  for o in kb["desired_outcomes"]["outcomes"]})
    names.update({v["id"]: f"{t['name']}: {v['label']}" for t in learn["traits"] for v in t["values"]})
    lines = []
    for n, entry in enumerate(learn["round"], 1):
        talk = text("review.nx.talk", n=entry["count"], who=entry["who"])
        asks = [f"{i}. {q['ask']}  \n   *{text('review.nx.listen')}:* {q['listen']}"
                for i, q in enumerate(entry["questions"], 1)]
        if not guide:
            lines += [f"{n}. **{talk}** ({', '.join(entry['gaps'])})",
                      *("   " + a.replace("\n", "\n   ") for a in asks)]
            continue
        hints = [names[ref] for ref in entry.get("traits", [])]
        lines += [f"### {n}. {talk}", ""] + [f"**{text('review.guide.recruit')}:** "
                                             + text("review.list_sep").join(hints), ""] * bool(hints)
        checks = text("review.list_sep").join(f"{names.get(ref, '')} ({ref})" for ref in entry["gaps"])
        lines += [f"**{text('review.guide.ask')}**", "", *asks, "", f"**{text('review.guide.checks')}:** {checks}", ""]
    return lines


def next_lines(kb: Json, text: Text) -> list[str]:
    """review.md's Next interviews: where the study stands, the plan's round, and every open gap by group."""
    lines = ["## " + text("review.h.next"), ""]
    for job in kb["core_jobs"]:
        jid, learn = str(job["id"]), learn_of(kb, str(job["id"]))
        gaps = open_gaps(kb, jid)
        lines += [f"**{job['statement']} ({jid})**", ""] * (len(kb["core_jobs"]) > 1) + _nx_where(kb, jid, text)
        if learn and "overview" in stale_layers(kb):
            lines += [f"*{text('review.nx.stale')}*", ""]
        lines += [text("review.nx.enough")] if not gaps else _nx_round(kb, learn, text, False) if learn.get("round") \
            else [text("review.nx.no_plan")]
        for kind, key in NX_GROUPS:
            group = [g for g in gaps if (g["main"] if kind == "main" else not g["main"] and g["kind"] == kind)]
            lines += ["", f"**{text(key, thin=THIN_STEP)}**", ""] * bool(group)
            lines += [f"- {g['ref']} {g['text']} [{len(g['people'])}]" for g in group[:NX_GROUP_MAX]]
            lines += [f"- *{text('review.nx.more', n=len(group) - NX_GROUP_MAX)}*"] * (len(group) > NX_GROUP_MAX)
        lines.append("")
    return lines


def guide_lines(kb: Json, text: Text, job: str | None = None) -> list[str]:
    """interview-guide.md, or one core job's part of it (the map copies that): who to find and what to ask."""
    lines = ["# " + text("review.guide.title", project=kb["meta"].get("project", "")), "",
             text("review.guide.made", date=today(), n=len(kb["interviews"])), "", text("review.guide.how"), ""]
    for entry in [j for j in kb["core_jobs"] if job in (None, str(j["id"]))]:
        learn = learn_of(kb, str(entry["id"]))
        lines += [f"## {entry['statement']}", ""]
        lines += _nx_round(kb, learn, text, True) if learn.get("round") else [text("review.nx.no_plan"), ""]
    return lines


def _review_tail(kb: Json, text: Text) -> list[str]:
    lines = []
    stale = [text(LAYER_LABELS[k]) if k in LAYER_LABELS else k.replace("_", " ") for k in stale_layers(kb)]
    if stale:
        lines += [f"*{text('review.out_of_date', layers=text('review.list_sep').join(stale))}*", ""]
    footer = text("review.footer", brand_link=f"[{BRAND}]({REVIEW_LINK})", brand=BRAND,
                  site_link=f"[productweaver.com]({REVIEW_LINK})")
    lines += ["---", "", f"*{footer}*", ""]
    return lines


def review_lines(kb: Json, since: str, text: Text | None = None) -> list[str]:
    text = text or Text()
    live_outcomes = [o for o in kb["desired_outcomes"]["outcomes"] if not o.get("merged_into")]
    new_outcomes = {o["id"] for o in kb["desired_outcomes"]["outcomes"] if since and str(o.get("added", "")) >= since}
    return (_review_head(kb, live_outcomes, text) + _review_decisions(kb, text)
            + _review_new(kb, since, new_outcomes, text) + _review_map(kb, live_outcomes, new_outcomes, text)
            + _review_solutions(kb, text) + _review_themes(kb, text) + _review_people(kb, text)
            + next_lines(kb, text) + _review_tail(kb, text))


def labels_missing_note(args: argparse.Namespace, kb: Json, missing: int) -> None:
    """After review or map: say how many labels still show in English, so the assistant writes them."""
    if not missing:
        return
    report = Report()
    report.warn(f"labels: {missing} of {len(english_table()['labels'])} labels have no {study_language(kb)} text yet, "
                f"so they show in English. Run: kb_tool labels {args.kb}", code="labels_missing")
    args.run.add_report(report)
    args.run.note(labels={"missing": missing})
    print(report.warnings[0])


def cmd_review(args: argparse.Namespace) -> int:
    """Write a plain-language sheet for people who review the KB: what changed, what needs a decision, the map."""
    kb = load_kb(args.kb)
    text, missing = study_text(kb, args.kb)
    last = next((c for c in reversed(kb["changelog"]) if c.get("action") in ("merge", "init")), {})
    since = args.since or str(last.get("date", ""))
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.kb)), "review.md")
    guide = os.path.join(os.path.dirname(os.path.abspath(out)), "interview-guide.md")
    for path, lines in ((out, review_lines(kb, since, text)), (guide, guide_lines(kb, text))):
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
        print(f"wrote {path}")
    args.run.note(out=args.run.relative(out), since=since)
    labels_missing_note(args, kb, missing)
    return 0


# ---------- labels ----------
# `labels` hands the assistant a to-do file of every label still in English; `labels --add` checks the translation
# and keeps it in .pw-kb/labels.json.
NOTE_MARK = "#note"  # "<key>#note", just above a label in the to-do file, says what the label's {name}s hold
LABELS_HEADER = """The text of the discovery map and the review sheet, to write in the study's language: {language}.
- Replace each English text with the same text in that language, in plain everyday words, as a person who does \
not know the method would say it. Address the reader informally, as most apps in that language do.
- Keep every {{name}} exactly: the tool fills it in, and the "<key>{note}" entry just above a label says what it \
holds. A number in a {{name}} can be 1, so write the sentence to read right for any number, for example with the \
number after a colon.
- A plural label lists one text per plural form the language needs for it. Translate each; keep {{n}} in each.
- Pick one word for each idea that comes back, and use it in every label: the main goal (the review sheet calls it \
the core job), a step, a stage, a measure of success (the review sheet's outcome), a value theme, and a solution, \
which is what people use today.
- Words in quote marks that the reader types to their assistant are translated too. Keep ODI and the names of \
files and commands as they are.
- This is a JSON file: change only the texts, keep each one in double quotes, and write \\" for a quote mark \
inside a text. \\n inside a text is a line break: keep it. You may leave out "instructions" and the "{note}" entries.
A label you leave out stays in English. Then run: kb_tool labels {kb} --add <this file>"""
STUDY_LABELS_HEADER = ("Written by kb_tool labels: the study's own text for the discovery map and the review sheet. "
                       "Change it with kb_tool labels --add, not by hand.")


def _set_language(kb: Json, args: argparse.Namespace) -> None:
    """Set the study's language. Only while the study has no interviews: the statements are written in it."""
    language = normalize_language(args.language)
    if kb["meta"].get("language") == language:
        return
    if language == study_language(kb) and kb["interviews"]:
        return  # an older English study without the field, asked to stay English
    if kb["interviews"]:
        raise KbError(f"the study already holds interviews written in {study_language(kb)}, so its language cannot "
                      f"change to {language}", code="language_locked")
    args.run.note(backup=args.run.relative(backup(args.kb)))
    kb["meta"]["language"] = language
    save_kb(kb, args.kb)
    args.run.note(written=True)
    print(f"study language: {language}")


def _todo_path(kb_path: str, language: str) -> str:
    folder = os.path.join(os.path.dirname(kb_path) or ".", "patches")
    os.makedirs(folder, exist_ok=True)
    stem = os.path.join(folder, f"{today()}-labels-{language}")
    path, counter = f"{stem}.json", 2
    while os.path.exists(path):
        path, counter = f"{stem}-{counter}.json", counter + 1
    return path


def labels_todo(kb: Json, args: argparse.Namespace, language: str) -> int:
    """Write the file of labels the study still lacks, in English, for the assistant to write in its language."""
    table = english_table()
    own, _ = study_labels(kb, args.kb)
    todo = [key for key in table["labels"] if key not in own]
    args.run.note(labels={"missing": len(todo)})
    if not todo:
        print(f"every label has {language} text; nothing to write")
        return 0
    path = _todo_path(args.kb, language)
    labels: Json = {}
    for key in todo:
        if key in table["notes"]:
            labels[key + NOTE_MARK] = table["notes"][key]
        value = table["labels"][key]
        if isinstance(value, dict):  # one text per form the language needs, in English to start with
            value = {form: value.get(form) or value.get("one" if form == "one" else "other") or value["other"]
                     for form in needed_forms(language, value)}
        labels[key] = value
    header = LABELS_HEADER.format(language=language, kb=args.kb, note=NOTE_MARK)
    save_json({"generated_with": MADE_WITH, "instructions": header.splitlines(), "language": language,
               "labels": labels}, path)
    args.run.note(out=args.run.relative(path))
    print(f"wrote {path}: {len(todo)} of {len(table['labels'])} labels to write in {language}\n"
          f"Then run: kb_tool labels {args.kb} --add {path}")
    return 0


def _read_labels_file(path: str, language: str) -> Json:
    data = load_json(path)
    if not isinstance(data, dict) or not isinstance(data.get("labels"), dict):
        raise KbError(f"{path} must hold `language` and `labels`, an object of label keys to text",
                      code="labels_file")
    try:
        given = normalize_language(str(data.get("language") or ""))
    except KbError:
        given = str(data.get("language"))
    if given != language:
        raise KbError(f"{path} is for language '{data.get('language')}', but the study is written in {language}",
                      code="labels_language")
    return {str(key): value for key, value in data["labels"].items() if not str(key).endswith(NOTE_MARK)}


def _check_labels(given: Json, language: str, report: Report) -> Json:
    """The labels that can be kept. Every problem goes to the report."""
    english, good = english_table()["labels"], {}
    for key, value in given.items():
        if key not in english:
            report.error(f"{key}: no such label; copy the keys from the file `kb_tool labels` wrote",
                         code="labels_unknown")
            continue
        problem = label_problem(value, english[key])
        if problem:
            report.error(f"{key}: {problem[1]}", code=problem[0])
            continue
        if value == english[key] and re.search(r"[A-Za-z]{3}", PLACEHOLDER.sub("", wanted_text(english[key]))):
            report.warn(f"{key}: the same as the English text; fine for a name, otherwise write it in {language}",
                        code="labels_same")
        forms = needed_forms(language, english[key]) if isinstance(value, dict) else []
        lacking = [form for form in forms if form not in value]
        if lacking:
            report.warn(f"{key}: has no {', '.join(lacking)} form; numbers that take it in {language} show the "
                        "other form", code="labels_plural_form")
        good[key] = value
    return good


def _add_labels(kb: Json, args: argparse.Namespace, language: str) -> int:
    given = _read_labels_file(args.add, language)
    report = Report()
    good = _check_labels(given, language, report)
    args.run.add_report(report)
    result: Json = {"ok": not report.errors, "language": language, "added": 0, "run_id": args.run.id,
                    "errors": report.errors, "warnings": report.warnings}
    lines = [f"WARN {w}" for w in report.warnings]
    if report.errors:
        args.run.note(labels={"refused": len(report.errors)})
        lines += [f"\n{len(report.errors)} problem(s); nothing written:"] + [f"  - {e}" for e in report.errors]
    else:
        english = english_table()["labels"]
        kept = {k: v for k, v in stored_labels(kb, args.kb).items()
                if k in english and not label_problem(v, english[k])}
        kept.update(good)
        ordered = {key: kept[key] for key in english if key in kept}  # the English order: by area, not by letter
        save_json({"about": STUDY_LABELS_HEADER, "language": language, "labels": ordered}, labels_path(args.kb))
        missing = len(english) - len(ordered)
        result.update(added=len(good), missing=missing)
        args.run.note(labels={"added": len(good), "missing": missing}, out=args.run.relative(labels_path(args.kb)))
        lines.append(f"added {len(good)} labels in {language} to {labels_path(args.kb)}; "
                     + (f"{missing} still show in English: run kb_tool labels {args.kb} for the list"
                        if missing else "every label has its text"))
        lines.append("Run review and map again to show them.")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("\n".join(lines))
    return 0 if result["ok"] else 1


def cmd_labels(args: argparse.Namespace) -> int:
    """Set the study's language, write the labels it still lacks for the assistant, or take them back (--add)."""
    kb = load_kb(args.kb)
    if args.language:
        _set_language(kb, args)
    language = study_language(kb)
    args.run.note(language=language)
    if base_language(language) == ENGLISH:
        if args.add:
            raise KbError("the study is written in English; it needs no labels", code="labels_language")
        print(f"the study is written in {language}: no labels needed")
        return 0
    return _add_labels(kb, args, language) if args.add else labels_todo(kb, args, language)


# ---------- map ----------
MAP_KEYS = ["meta", "core_jobs", "job_map", "desired_outcomes", "current_solutions", "interviews", "clusters",
            "proposed_changes", "changelog"]
MAP_START, MAP_END = "/* @kb-data:start */", "/* @kb-data:end */"
MAP_SCHEMA = f"/* @kb-schema:{SCHEMA_VERSION} */"  # the template can draw a KB of this schema version
# English labels ship beside the template (size limit); `map` inlines them so each map works offline.
MAP_ASSETS = (LABELS_FILE,)


def inline_asset(template: str, template_path: str, name: str) -> str:
    """Inline a script shipped beside the template; a map made earlier already holds it."""
    tag = f'<script src="{name}"></script>'
    if tag not in template:
        return template
    beside = os.path.join(os.path.dirname(os.path.abspath(template_path)), name)
    path = beside if os.path.isfile(beside) else skill_file("assets", name)
    if not path:
        raise KbError(f"{name} not found: keep it next to discovery-map-template.html, as the skill ships them",
                      code="skill_file_missing")
    with open(path, encoding="utf-8") as handle:
        library = handle.read()
    if "</script" in library.lower():
        raise KbError(f"{path} must not contain a closing script tag", code="template_invalid")
    return template.replace(tag, f"<script>\n{library}</script>", 1)


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


def plugin_version() -> str | None:
    """The plugin's version from its manifest, or None outside the plugin folder."""
    here = pathlib.Path(os.path.abspath(__file__)).parents
    if len(here) < 4:
        return None
    root = here[3]  # <plugin>/skills/pw-discovery/scripts/kb_tool.py
    for manifest in (root / "plugin.json", root / ".claude-plugin" / "plugin.json"):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        version = str(data.get("version") or "") if isinstance(data, dict) else ""
        if data.get("name") == "productweaver" and re.fullmatch(r"\d+\.\d+\.\d+", version):
            return version
    return None


def map_stamp() -> Json:
    """When the map was made and by which version, for the note at the end of its Overview."""
    stamp: Json = {"at": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "tool": __version__}
    version = plugin_version()
    if version:
        stamp["plugin"] = version
    return stamp


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
    data["generated"] = map_stamp()
    own, missing = study_labels(kb, args.kb)
    data["generated"]["guides"] = {str(j["id"]): "\n".join(guide_lines(kb, Text(study_language(kb), own), str(j["id"])))
                                   for j in kb["core_jobs"]}
    labels = {key: value for key, value in own.items() if key.startswith("map.")}
    if labels:  # only a study in another language has any; the map shows English for the rest
        data["labels"] = labels
    payload = json.dumps(data, default=str, ensure_ascii=False)
    payload = payload.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    template_path = skill_file("assets", "discovery-map-template.html", args.template)
    if not template_path:
        raise KbError("map template not found: put discovery-map-template.html next to kb_tool.py, run the kb_tool.py "
                      "that sits in the skill's scripts/ folder, or pass --template (a discovery-map.html made by this "
                      "version also works)", code="skill_file_missing")
    with open(template_path, encoding="utf-8") as handle:
        template = handle.read()
    if MAP_SCHEMA not in template:
        raise KbError(f"the map template {template_path} is older than KB schema {SCHEMA_VERSION}; use "
                      "discovery-map-template.html from the skill", code="template_old")
    for name in MAP_ASSETS:
        template = inline_asset(template, template_path, name)
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
    labels_missing_note(args, kb, missing)
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


def _sibling(name: str) -> Any:
    """A module shipped beside this script, loaded without writing a bytecode cache into the plugin folder."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise KbError(f"{path} is missing; reinstall the plugin", code="file_missing")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    before, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = before
    return module


def cmd_migrate(args: argparse.Namespace) -> int:
    """Bring an older study up to date. The code is in kb_migrate.py, loaded only for this command."""
    return _sibling("kb_migrate").cmd_migrate(args, sys.modules[__name__])


# ---------- cli ----------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"kb_tool {__version__} (KB schema {SCHEMA_VERSION})")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def command(name: str, func: Callable[[argparse.Namespace], int], help_text: str) -> argparse.ArgumentParser:
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument("kb", help=f"the KB, {KB_HOME}")
        sp.set_defaults(func=func)
        return sp

    sp = command("init", cmd_init, "start an empty KB")
    sp.add_argument("--project", required=True)
    sp.add_argument("--interviewer")
    sp.add_argument("--language", help="the study's language, a BCP 47 code such as it or pt-BR; default en")
    sp = command("labels", cmd_labels, "set the study's language and write the map's and review sheet's text in it")
    sp.add_argument("--language", help="set the study's language, a BCP 47 code; only before the first interview")
    sp.add_argument("--add", help="a labels file written in the study's language, to check and keep")
    sp.add_argument("--json", action="store_true", help="with --add, print the result as one JSON object")
    sp = command("context", cmd_context, "compact view of the KB")
    sp.add_argument("--json", action="store_true", help="print the same information as JSON")
    sp = command("merge", cmd_merge, "check a patch and fold it into the KB")
    sp.add_argument("patch", help="the patch, a JSON file")
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
    sp.add_argument("themes", help="a JSON file with `job` and `themes`, the full set for that core job")
    sp.add_argument("--dry-run", action="store_true", help="run every check, write nothing")
    sp.add_argument("--json", action="store_true", help="print the result as one JSON object")
    sp = command("overview", cmd_overview, "check one core job's overview and write it")
    sp.add_argument("overview", help="a JSON file with `job` and the overview of that core job")
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
