#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml==6.0.3"]
# ///
"""kb_tool.py - keep an ODI knowledge base (one YAML file) growing from interview transcripts.

Part of the Product Weaver distill-kb skill · https://productweaver.com

Commands
  init      <kb.yaml> --project NAME [--interviewer NAME]     start an empty KB
  context   <kb.yaml> [--json]                                compact view of the KB to map new evidence against
  merge     <kb.yaml> <patch.yaml> --transcripts DIR [--transcripts DIR2] [--dry-run] [--json]
                                                              check every quote and reference, then fold the patch in
  apply     <kb.yaml> <proposal-id> --decision approve|reject [--note TEXT]
                                                              act on a proposed structural change
  review    <kb.yaml> [--since DATE] [--out FILE]             write review.md, a plain sheet for human reviewers
  map       <kb.yaml> [--template FILE] [--out FILE]          write discovery-map.html, the interactive map, KB inside
  validate  <kb.yaml> [--transcripts DIR] [--schema FILE] [--rehash]
                                                              check the structure, then every quote and transcript hash
  migrate   <kb.yaml>                                         bring an older KB up to the current schema version

Run it with no setup:   uv run --locked kb_tool.py <command> ...      (uv installs PyYAML in its cache the first time)
Or install PyYAML once: python3 -m pip install pyyaml==6.0.3
.docx transcripts need python-docx==1.2.0, .pdf transcripts need pypdf==6.21.4.

Every run, including a failed one or a dry run, appends one JSON line to logs/kb_tool.jsonl next to the KB:
what was asked, how it ended, error and warning codes, counts, versions. Never quotes, names or file names.
Set KB_TOOL_LOG=0 to switch the log off and KB_TOOL_AGENT=<assistant> to name the assistant that is running.
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import difflib
import glob
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import time
import uuid
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

__version__ = "0.3.0"
SCHEMA_VERSION = 1

BRAND = "Product Weaver"
SITE = "https://productweaver.com"
MADE_WITH = f"Made with {BRAND} · productweaver.com"

DERIVED = ["survey", "simulation", "value_themes", "use_cases"]
SOURCES = ("transcript", "quoted_in_notes", "interviewer_notes")
STAGES = ["define", "locate", "prepare", "confirm", "execute", "monitor", "modify", "conclude"]
PROPOSAL_TYPES = ["new_step", "reword_step", "reword_outcome", "reword_core_job",
                  "merge_outcomes", "move_outcome", "new_segment", "other"]
PATCH_SECTIONS = ("interviews", "bootstrap", "step_evidence", "outcome_evidence", "new_outcomes", "proposed_changes")
PATCH_KEYS = (*PATCH_SECTIONS, "provenance")  # every top-level key a patch may carry
PROVENANCE_KEYS = ("assistant", "model", "started", "transcripts_read", "notes")
LOG_FOLDER, LOG_FILE = "logs", "kb_tool.jsonl"
DIRECTION = re.compile(r"^(Minimize|Maximize|Increase|Reduce) ")
OUTCOME_ID = re.compile(r"^[0-9]+\.[0-9]+$")
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
    return {"interviews": len(kb.get("interviews") or []), "steps": len(steps),
            "thin_steps": len([s for s in steps if s.get("coverage", 0) < THIN_STEP]),
            "outcomes": len([o for o in outcomes if not o.get("merged_into")]),
            "pending_proposals": len([p for p in proposals if p.get("status") == "pending"]),
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
            public[key] = self.relative(value) if key in ("patch", "out", "template", "schema") else value
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

    def write(self, args: argparse.Namespace, code: int) -> None:
        """Append the line. A log that cannot be written must never fail the command itself."""
        if os.environ.get("KB_TOOL_LOG", "").strip() in ("0", "off", "false") or not os.path.isdir(self.folder):
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


KB_ORDER = ["meta", "market_core_job", "clusters", "interviews", "job_map", "desired_outcomes",
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


def backup(kb_path: str) -> str:
    """Copy the KB into backups/ next to it. Names carry microseconds, so two writes never collide.

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
    shutil.copy2(kb_path, target)
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


class Transcripts:
    """Finds transcript files under the given folders and reads each one the first time it is asked for.

    Files are keyed by base name, as interview records store them. A referenced name that exists in two
    places is refused, because the tool could not tell which one the evidence came from."""

    def __init__(self, roots: list[str]) -> None:
        self.index: dict[str, list[str]] = {}
        self.cache: dict[str, Transcript | None] = {}
        self.warnings: list[str] = []
        for root in roots:
            if os.path.isdir(root):
                paths = sorted(glob.glob(os.path.join(glob.escape(root), "**", "*"), recursive=True))
            elif os.path.isfile(root):
                paths = [root]
            else:
                self.warnings.append(f"--transcripts {root}: no such file or folder")
                continue
            for path in paths:
                if os.path.isfile(path) and os.path.splitext(path)[1].lower() in TRANSCRIPT_EXTS:
                    self.index.setdefault(os.path.basename(path), []).append(path)

    def has(self, name: str) -> bool:
        return os.path.basename(name) in self.index

    def get(self, name: str) -> Transcript | None:
        base = os.path.basename(name)
        if base in self.cache:
            return self.cache[base]
        paths = self.index.get(base, [])
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


def transcripts_for(roots: list[str], report: Report) -> Transcripts:
    """Index the transcript roots; a root that does not exist becomes a coded warning."""
    transcripts = Transcripts(roots)
    for warning in transcripts.warnings:
        report.warn(warning, code="transcripts_root_missing")
    return transcripts


# ---------- KB access ----------
def ensure(kb: Any, label: str = "the KB") -> Json:
    if kb is None:
        kb = {}
    if not isinstance(kb, dict):
        raise KbError(f"{label} is not a YAML mapping", code="kb_shape")
    kb.setdefault("meta", {})
    kb["meta"].setdefault("schema_version", SCHEMA_VERSION)
    kb["meta"].setdefault("generated_with", MADE_WITH)
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
    kb = ensure(load_yaml(path), path)
    version = check_version(kb, path)
    if version < SCHEMA_VERSION:
        raise KbError(f"{path} uses KB schema version {version}; run `kb_tool.py migrate {path}` first",
                      code="migrate_needed")
    return kb


def steps_by_n(kb: Json) -> dict[int, Json]:
    return {int(step["n"]): step for step in kb["job_map"]["steps"]}


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


def outcome_sort_key(outcome: Json) -> tuple[int, int]:
    return int(outcome["step"]), int(str(outcome["id"]).split(".")[1])


def next_outcome_id(kb: Json, step: int) -> str:
    used = [int(str(o["id"]).split(".")[1]) for o in kb["desired_outcomes"]["outcomes"] if int(o["step"]) == step]
    return f"{step}.{(max(used) if used else 0) + 1}"


def sort_outcomes(kb: Json) -> None:
    kb["desired_outcomes"]["outcomes"].sort(key=outcome_sort_key)


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


def recount(kb: Json) -> None:
    """Recompute every derived count and name. Run after any change."""
    names = {str(record["id"]): record.get("name", "") for record in kb["interviews"]}
    for step in kb["job_map"]["steps"]:
        for item in step.get("evidence", []):
            item["name"] = names.get(str(item.get("interview")), item.get("name", ""))
        ids = sorted({str(item.get("interview")) for item in step.get("evidence", [])})
        step["interviews"], step["coverage"] = ids, len(ids)
    for outcome in kb["desired_outcomes"]["outcomes"]:
        for item in outcome.get("evidence", []):
            item["name"] = names.get(str(item.get("interview")), item.get("name", ""))
        ids = sorted({str(item.get("interview")) for item in outcome.get("evidence", [])})
        outcome["interviews"], outcome["interview_count"] = ids, len(ids)
        outcome["quote_count"] = len(outcome.get("evidence", []))
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


# ---------- schema ----------
_SCHEMA_ANNOTATIONS = {"$schema", "$id", "$comment", "title", "description", "examples", "default", "$defs"}
_SCHEMA_KEYWORDS = {"$ref", "type", "enum", "required", "properties", "items", "pattern",
                    "minLength", "minimum", "minItems", "additionalProperties"}
_TYPE_NAMES = {dict: "mapping", list: "list", str: "string", bool: "boolean", int: "integer",
               float: "number", type(None): "null"}


def load_schema(name: str, given: str | None = None) -> Json:
    path = skill_file("references", name, given)
    if not path:
        raise KbError(f"{name} not found: keep it next to kb_tool.py or run the script from the skill folder",
                      code="skill_file_missing")
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


def structure_problems(kb: Json, schema_path: str | None = None) -> list[str]:
    """Schema check plus the cross-references a schema cannot express."""
    problems = schema_errors(kb, load_schema("kb-schema.json", schema_path))
    if problems:
        return problems
    steps, outcomes = steps_by_n(kb), outcomes_by_id(kb)
    ids = [str(o["id"]) for o in kb["desired_outcomes"]["outcomes"]]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        problems.append(f"outcome id {dup} is used more than once")
    numbers = [int(s["n"]) for s in kb["job_map"]["steps"]]
    for dup in sorted({n for n in numbers if numbers.count(n) > 1}):
        problems.append(f"step number {dup} is used more than once")
    for outcome in kb["desired_outcomes"]["outcomes"]:
        if int(outcome["step"]) not in steps:
            problems.append(f"outcome {outcome['id']}: step {outcome['step']} does not exist")
        if not str(outcome["id"]).startswith(f"{int(outcome['step'])}."):
            problems.append(f"outcome {outcome['id']}: its ID does not match step {outcome['step']}")
        target = outcome.get("merged_into")
        if target and target not in outcomes:
            problems.append(f"outcome {outcome['id']}: merged_into {target} does not exist")
    iv_ids = [str(r["id"]) for r in kb["interviews"]]
    for dup in sorted({i for i in iv_ids if iv_ids.count(i) > 1}):
        problems.append(f"interview id {dup} is used more than once")
    return problems


# ---------- clarity ----------
BANNED_NAMES = {"(": "brackets", ";": "a semicolon", "e.g.": "an example", "i.e.": "an aside",
                " and/or ": "and/or", "/": "a slash"}


@dataclass
class Style:
    """Writing rules the merge enforces. A study can override any of them in meta.style."""

    limits: dict[str, int] = field(default_factory=lambda: {
        "executor": 16, "job": 10, "step": 10, "outcome": 16, "feeling": 12, "rationale": 30})
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
    acronyms = [w for w in re.findall(r"\b[A-Z]{2,}\b", statement) if w not in style.acronyms]
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
def coerce_patch(patch: Any, width: int, report: Report) -> Json:
    """Read the YAML the way the writer meant it: dates become strings and a bare interview number
    becomes a zero-padded ID, with a warning. Outcome IDs are never coerced, because 2.10 would become 2.1."""
    if patch is None:
        raise KbError("the patch file is empty", code="patch_empty")
    if not isinstance(patch, dict):
        raise KbError(f"the patch must be a YAML mapping with keys such as {', '.join(PATCH_SECTIONS)}",
                      code="patch_shape")
    fixed: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in list(node.items()):
                if isinstance(value, (dt.date, dt.datetime)):
                    node[key] = value.isoformat()
                elif key == "interview" and isinstance(value, int) and not isinstance(value, bool):
                    node[key] = str(value).zfill(width)
                    fixed.add(node[key])
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(patch)
    if fixed:
        report.warn(f"interview IDs were not quoted and were read as {sorted(fixed)}; write IDs in quotes, like \"01\"",
                    code="ids_unquoted")
    unknown = sorted(set(patch) - set(PATCH_KEYS))
    if unknown:
        report.warn(f"unknown top-level key(s) {unknown} are ignored; a patch uses {list(PATCH_KEYS)}",
                    code="unknown_key")
    return patch


@dataclass
class MergePlan:
    """What a patch resolves to against the current KB."""

    new_interviews: list[Json] = field(default_factory=list)
    keymap: dict[str, str] = field(default_factory=dict)  # patch key or KB id -> KB id
    skipped: dict[str, str] = field(default_factory=dict)  # patch key -> why it was skipped
    texts: dict[str, str | None] = field(default_factory=dict)  # KB id -> normalized transcript
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
    if not (kb["job_map"]["steps"] or kb.get("market_core_job")):
        plan.bootstrap = bootstrap
        return
    steps = steps_by_n(kb)
    core_known = norm(bootstrap["market_core_job"]["statement"]) in _wordings(kb.get("market_core_job") or {})
    steps_known = all(int(s["n"]) in steps and norm(s["statement"]) in _wordings(steps[int(s["n"])])
                      for s in bootstrap["steps"])
    if core_known and steps_known:
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
            report.error(f"interview {key}: file '{name}' not found under --transcripts", code="transcript_missing")
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
        record["sha256"] = transcript.sha256 if transcript else ""
        record["added"] = today()
        plan.new_interviews.append(record)
    _drop_skipped_evidence(patch, plan, report)
    return plan


def _drop_skipped_evidence(patch: Json, plan: MergePlan, report: Report) -> None:
    for section in ("step_evidence", "outcome_evidence", "new_outcomes", "proposed_changes"):
        kept = []
        for item in patch.get(section, []):
            evidence = item.get("evidence")
            if isinstance(evidence, list) and evidence:
                live = [e for e in evidence if not (isinstance(e, dict) and str(e.get("interview")) in plan.skipped)]
                if not live:
                    plan.dropped += 1
                    continue
                item["evidence"] = live
            kept.append(item)
        if section in patch:
            patch[section] = kept
    if plan.dropped:
        report.warn(f"dropped {plan.dropped} patch item(s) whose evidence comes only from skipped interviews",
                    code="evidence_dropped")


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
                            "run validate --transcripts to re-check its quotes", code="transcript_changed")
        if plan.texts[kb_id] is None:
            return None, f"transcript for interview {kb_id} ({by_id[kb_id].get('file')}) not found under --transcripts"
        return plan.texts[kb_id], None

    return lookup


# ---------- merge: checks ----------
@dataclass
class Checks:
    """What the content checks need: the KB and its lookups, the study's style, and where to report."""

    kb: Json
    steps: dict[int, Json]
    outcomes: dict[str, Json]
    style: Style
    checker: QuoteChecker
    report: Report


def check_new_interviews(plan: MergePlan, ctx: Checks) -> None:
    key_of = {kb_id: key for key, kb_id in plan.keymap.items()}
    for record in plan.new_interviews:
        key, label = key_of[record["id"]], os.path.basename(str(record["file"]))
        for fld, kind in (("job_executor", "executor"), ("core_functional_job", "job")):
            clarity(record[fld]["statement"], kind, f"{label} {fld}", ctx.style, ctx.report)
            own = [{**e, "interview": key} for e in record[fld].get("evidence", [])]
            ctx.checker.check(own, f"{label} {fld}", ctx.report)
        for fld in ("related_jobs", "emotional_jobs", "social_jobs"):
            kind = "job" if fld == "related_jobs" else "feeling"
            for job in record.get(fld) or []:
                clarity(job.get("statement", ""), kind, f"{label} {fld}", ctx.style, ctx.report)
                own = [{**e, "interview": key} for e in job.get("evidence", [])]
                ctx.checker.check(own, f"{label} {fld}: {short(job.get('statement', ''), 40)}", ctx.report)
        cluster = record.get("cluster")
        if cluster and cluster not in (ctx.kb.get("clusters") or {}):
            ctx.report.warn(f"{label}: segment '{cluster}' is not in the KB; add a new_segment proposal",
                            code="segment_unknown")


def check_bootstrap(bootstrap: Json, ctx: Checks) -> None:
    clarity(bootstrap["market_core_job"]["statement"], "job", "market core job", ctx.style, ctx.report)
    numbers = [int(step["n"]) for step in bootstrap["steps"]]
    for dup in sorted({n for n in numbers if numbers.count(n) > 1}):
        ctx.report.error(f"bootstrap: step number {dup} is used more than once", code="step_duplicate")
    for step in bootstrap["steps"]:
        clarity(step.get("statement", ""), "step", f"step {step.get('n')}", ctx.style, ctx.report)


def check_step_evidence(patch: Json, ctx: Checks) -> None:
    for item in patch.get("step_evidence", []):
        if int(item["step"]) not in ctx.steps:
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
    seen = {norm(o["statement"]).lower(): str(o["id"]) for o in ctx.outcomes.values()}
    for item in patch.get("new_outcomes", []):
        statement = item["statement"]
        label = f"new outcome '{short(statement, 40)}'"
        if int(item["step"]) not in ctx.steps:
            ctx.report.error(f"{label}: step {item['step']} does not exist", code="step_missing")
        clarity(statement, "outcome", f"new outcome (step {item['step']})", ctx.style, ctx.report)
        if not DIRECTION.match(statement):
            ctx.report.error(f"{label}: an outcome must start with Minimize, Maximize, Increase or Reduce",
                             code="outcome_direction")
        normalized = norm(statement).lower()
        if normalized in seen:
            ctx.report.error(f"{label}: duplicates {seen[normalized]}; send it as outcome_evidence",
                             code="outcome_duplicate")
        seen[normalized] = "another new outcome in this patch"
        ctx.checker.check(item["evidence"], label, ctx.report)


class ProposalRefs:
    """Resolves the things a proposal points at. Each miss becomes one readable problem."""

    def __init__(self, kb: Json, steps: dict[int, Json], outcomes: dict[str, Json]) -> None:
        self.kb, self.steps, self.outcomes = kb, steps, outcomes
        self.problems: list[str] = []

    def outcome(self, value: Any, what: str) -> Json | None:
        key = str(value) if value is not None else ""
        if not OUTCOME_ID.match(key):
            self.problems.append(f"{what} must be an outcome ID such as \"6.3\", got {value!r}")
            return None
        outcome = self.outcomes.get(key)
        if not outcome:
            self.problems.append(f"{what}: outcome {key} does not exist")
        elif outcome.get("merged_into"):
            self.problems.append(f"{what}: outcome {key} was merged into {outcome['merged_into']}; use that one")
            return None
        return outcome

    def step(self, value: Any, what: str) -> int | None:
        if value is None or not re.fullmatch(r"\d+", str(value)):
            self.problems.append(f"{what} must be a step number, got {value!r}")
            return None
        if int(value) not in self.steps:
            self.problems.append(f"{what}: step {value} does not exist")
            return None
        return int(value)


def _refs_new_step(refs: ProposalRefs, proposal: Json) -> None:
    if proposal.get("stage") not in STAGES:
        refs.problems.append(f"new_step needs a stage, one of {STAGES}")


def _refs_reword_step(refs: ProposalRefs, proposal: Json) -> None:
    refs.step(proposal.get("target"), "target")


def _refs_reword_outcome(refs: ProposalRefs, proposal: Json) -> None:
    refs.outcome(proposal.get("target"), "target")


def _refs_reword_core_job(refs: ProposalRefs, proposal: Json) -> None:
    if not (refs.kb.get("market_core_job") or {}).get("statement"):
        refs.problems.append("reword_core_job: the KB has no core job yet")


def _refs_merge_outcomes(refs: ProposalRefs, proposal: Json) -> None:
    keep, drop = refs.outcome(proposal.get("target"), "target"), refs.outcome(proposal.get("merge"), "merge")
    if keep and drop and keep is drop:
        refs.problems.append("merge_outcomes: target and merge are the same outcome")


def _refs_move_outcome(refs: ProposalRefs, proposal: Json) -> None:
    outcome, step = refs.outcome(proposal.get("target"), "target"), refs.step(proposal.get("to_step"), "to_step")
    if outcome and step is not None and int(outcome["step"]) == step:
        refs.problems.append(f"move_outcome: outcome {outcome['id']} is already under step {step}")


def _refs_new_segment(refs: ProposalRefs, proposal: Json) -> None:
    target = proposal.get("target")
    if not isinstance(target, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", target):
        refs.problems.append("new_segment needs a short lowercase target key, such as fleet")
    elif target in (refs.kb.get("clusters") or {}):
        refs.problems.append(f"new_segment: segment '{target}' already exists")


PROPOSAL_CHECKS: dict[str, Callable[[ProposalRefs, Json], None]] = {
    "new_step": _refs_new_step,
    "reword_step": _refs_reword_step,
    "reword_outcome": _refs_reword_outcome,
    "reword_core_job": _refs_reword_core_job,
    "merge_outcomes": _refs_merge_outcomes,
    "move_outcome": _refs_move_outcome,
    "new_segment": _refs_new_segment,
}


def proposal_problems(kb: Json, proposal: Json, steps: dict[int, Json], outcomes: dict[str, Json]) -> list[str]:
    """Check that a proposal's references point at real things. Used at merge time and again before apply."""
    refs = ProposalRefs(kb, steps, outcomes)
    check = PROPOSAL_CHECKS.get(str(proposal.get("type")))
    if check:
        check(refs, proposal)
    return refs.problems


def check_proposals(patch: Json, ctx: Checks) -> None:
    kinds = {"new_step": "step", "reword_step": "step", "reword_core_job": "job", "reword_outcome": "outcome"}
    limit = ctx.style.limits.get("rationale", 30)
    for index, proposal in enumerate(patch.get("proposed_changes", [])):
        label = f"proposal {index + 1} ({proposal.get('type')})"
        kind = kinds.get(str(proposal.get("type")))
        if kind:
            clarity(proposal["proposal"], kind, label, ctx.style, ctx.report)
        if len(str(proposal.get("rationale", "")).split()) > limit:
            ctx.report.error(f"clarity: {label} rationale is over {limit} words; say why in one plain sentence",
                             code="rationale_length")
        for problem in proposal_problems(ctx.kb, proposal, ctx.steps, ctx.outcomes):
            ctx.report.error(f"{label}: {problem}", code="proposal_ref")
        if proposal.get("evidence"):
            ctx.checker.check(proposal["evidence"], label, ctx.report)


def check_patch(kb: Json, patch: Json, plan: MergePlan, transcripts: Transcripts, report: Report) -> None:
    steps = steps_by_n(kb)
    if not steps and plan.bootstrap:
        steps = {int(step["n"]): step for step in plan.bootstrap["steps"]}
    ctx = Checks(kb, steps, outcomes_by_id(kb), style_of(kb), QuoteChecker(make_lookup(kb, plan, transcripts, report)),
                 report)
    check_new_interviews(plan, ctx)
    if plan.bootstrap:
        check_bootstrap(plan.bootstrap, ctx)
    check_step_evidence(patch, ctx)
    check_outcome_evidence(patch, ctx)
    check_new_outcomes(patch, ctx)
    check_proposals(patch, ctx)


# ---------- merge: write ----------
def remap(items: list[Json], keymap: dict[str, str]) -> list[Json]:
    return [{**item, "interview": keymap.get(str(item["interview"]), str(item["interview"]))} for item in items]


def has_new_evidence(kb: Json, patch: Json, plan: MergePlan) -> bool:
    steps, outcomes = steps_by_n(kb), outcomes_by_id(kb)
    pairs = [(steps.get(int(i["step"])), i["evidence"]) for i in patch.get("step_evidence", [])]
    pairs += [(outcomes.get(str(i["outcome"])), i["evidence"]) for i in patch.get("outcome_evidence", [])]
    for target, evidence in pairs:
        have = {evidence_key(e) for e in (target or {}).get("evidence", [])}
        if any(evidence_key(e) not in have for e in remap(evidence, plan.keymap)):
            return True
    return False


def apply_patch(kb: Json, patch: Json, plan: MergePlan, stamp: Json) -> Json | None:
    """Fold a checked patch into the KB in place. Returns the changelog entry, or None when nothing is new.

    `stamp` is what the changelog entry records about the run itself: patch name, ts, run_id and provenance."""
    fresh = has_new_evidence(kb, patch, plan)
    anything = (plan.new_interviews or plan.bootstrap or fresh or patch.get("new_outcomes")
                or patch.get("proposed_changes"))
    if not anything:
        return None
    log: list[str] = []
    if plan.bootstrap:
        kb["market_core_job"] = {**plan.bootstrap["market_core_job"], "status": "proposed"}
        kb["job_map"].update({"core_job": kb["market_core_job"]["statement"], "status": "proposed",
                              "stages": [{"key": k, "name": k.capitalize()} for k in STAGES],
                              "steps": [{**step, "evidence": []} for step in plan.bootstrap["steps"]]})
        log.append(f"bootstrapped core job and {len(plan.bootstrap['steps'])} steps")
    kb["interviews"].extend(plan.new_interviews)
    added_ids = [record["id"] for record in plan.new_interviews]
    log.append(f"added interviews {', '.join(added_ids) or 'none'}")
    steps, outcomes = steps_by_n(kb), outcomes_by_id(kb)
    step_quotes = sum(add_evidence(steps[int(i["step"])], remap(i["evidence"], plan.keymap))
                      for i in patch.get("step_evidence", []))
    outcome_quotes = sum(add_evidence(outcomes[str(i["outcome"])], remap(i["evidence"], plan.keymap))
                         for i in patch.get("outcome_evidence", []))
    new_outcome_ids = []
    for item in patch.get("new_outcomes", []):
        step = int(item["step"])
        record = {"id": next_outcome_id(kb, step), "step": step, "statement": item["statement"], "added": today(),
                  "evidence": []}
        add_evidence(record, remap(item["evidence"], plan.keymap))
        kb["desired_outcomes"]["outcomes"].append(record)
        new_outcome_ids.append(record["id"])
    sort_outcomes(kb)
    numbers = [int(str(p["id"])[1:]) for p in kb["proposed_changes"] if re.fullmatch(r"P\d+", str(p.get("id", "")))]
    next_number = max(numbers, default=0) + 1
    proposal_ids = []
    for proposal in patch.get("proposed_changes", []):
        record = {"id": f"P{next_number}", "status": "pending", "raised": today(), **proposal}
        if record.get("evidence"):
            record["evidence"] = remap(record["evidence"], plan.keymap)
        kb["proposed_changes"].append(record)
        proposal_ids.append(record["id"])
        next_number += 1
    log += [f"{step_quotes} step quotes", f"{outcome_quotes} outcome quotes",
            f"new outcomes {', '.join(new_outcome_ids) or 'none'}", f"proposals {', '.join(proposal_ids) or 'none'}"]
    recount(kb)
    if added_ids or new_outcome_ids:
        mark_stale(kb, f"interviews {', '.join(added_ids) or '-'} and outcomes "
                       f"{', '.join(new_outcome_ids) or '-'} added")
    entry: Json = {"date": today(), "action": "merge", **stamp, "summary": "; ".join(log),
                   "added_interviews": added_ids, "new_outcomes": new_outcome_ids, "step_quotes": step_quotes,
                   "outcome_quotes": outcome_quotes, "proposals": proposal_ids}
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
                         "proposals_filed": len(changes.get("proposals") or [])},
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


def _merge_verdict(out: MergeOutput, entry: Json, candidate: Json) -> None:
    out.result.update({"ok": True, "changes": entry, "thin_steps": [int(s["n"]) for s in thin_steps(candidate)],
                       "stale": stale_layers(candidate)})
    if out.args.dry_run:
        out.verdict += ["dry run OK: every quote matches, every reference resolves and the KB structure stays valid",
                        f"would merge: {entry['summary']}"]
        return
    out.result["backup"] = backup(out.args.kb)
    save_kb(candidate, out.args.kb)
    out.result["written"] = True
    out.verdict += [f"merged: {entry['summary']}", f"backup: {out.result['backup']}"]
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
    if report.errors:
        return out.finish(1)
    transcripts = transcripts_for(args.transcripts, report)
    plan = resolve_interviews(kb, patch, transcripts, report)
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
    _merge_verdict(out, entry, candidate)
    return out.finish(0)


# ---------- apply ----------
def _history(obj: Json, **entry: Any) -> None:
    obj.setdefault("history", []).append({"date": today(), **entry})


def _apply_new_step(kb: Json, proposal: Json) -> str:
    number = max(steps_by_n(kb), default=0) + 1
    evidence = [{k: v for k, v in e.items() if k in ("interview", "source", "quote")}
                for e in proposal.get("evidence", [])]
    kb["job_map"]["steps"].append({"n": number, "stage": proposal["stage"], "statement": proposal["proposal"],
                                   "covers": proposal.get("covers", ""), "evidence": evidence})
    return f"added step {number}"


def _apply_reword(kb: Json, proposal: Json) -> str:
    kind = proposal["type"]
    if kind == "reword_step":
        target = steps_by_n(kb)[int(proposal["target"])]
    elif kind == "reword_outcome":
        target = outcomes_by_id(kb)[str(proposal["target"])]
    else:
        target = kb["market_core_job"]
    _history(target, was=target["statement"])
    target["statement"] = proposal["proposal"]
    if kind == "reword_core_job":
        kb["job_map"]["core_job"] = proposal["proposal"]
    return f"reworded {proposal.get('target') or 'the core job'}"


def _apply_merge_outcomes(kb: Json, proposal: Json) -> str:
    outcomes = outcomes_by_id(kb)
    keep, drop = outcomes[str(proposal["target"])], outcomes[str(proposal["merge"])]
    add_evidence(keep, drop.get("evidence", []))
    drop["merged_into"] = keep["id"]
    for other in kb["desired_outcomes"]["outcomes"]:  # anything that pointed at the dropped one now points at keep
        if other.get("merged_into") == drop["id"] and other is not drop:
            other["merged_into"] = keep["id"]
    return f"merged {drop['id']} into {keep['id']}"


def rename_outcome(kb: Json, old: str, new: str) -> None:
    """Point every reference to an outcome ID at its new ID: merged_into pointers and pending proposals."""
    for outcome in kb["desired_outcomes"]["outcomes"]:
        if outcome.get("merged_into") == old:
            outcome["merged_into"] = new
    for proposal in kb["proposed_changes"]:
        if proposal.get("status") == "pending":
            for key in ("target", "merge"):
                if str(proposal.get(key)) == old:
                    proposal[key] = new


def _apply_move_outcome(kb: Json, proposal: Json) -> str:
    outcome = outcomes_by_id(kb)[str(proposal["target"])]
    step = int(proposal["to_step"])
    old, new = str(outcome["id"]), next_outcome_id(kb, step)
    _history(outcome, was_id=old)
    outcome["id"], outcome["step"] = new, step
    rename_outcome(kb, old, new)
    sort_outcomes(kb)
    return f"moved {old} to {new} under step {step}"


def _apply_new_segment(kb: Json, proposal: Json) -> str:
    kb.setdefault("clusters", {})[proposal["target"]] = {"name": proposal["proposal"],
                                                          "description": proposal.get("rationale", "")}
    return f"added segment {proposal['target']}"


APPLY_HANDLERS: dict[str, Callable[[Json, Json], str]] = {
    "new_step": _apply_new_step,
    "reword_step": _apply_reword,
    "reword_outcome": _apply_reword,
    "reword_core_job": _apply_reword,
    "merge_outcomes": _apply_merge_outcomes,
    "move_outcome": _apply_move_outcome,
    "new_segment": _apply_new_segment,
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
        problems = proposal_problems(candidate, proposal, steps_by_n(candidate), outcomes_by_id(candidate))
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


# ---------- init, context ----------
def cmd_init(args: argparse.Namespace) -> int:
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
    print(f"created {args.kb}")
    return 0


def context_data(kb: Json) -> Json:
    core = kb.get("market_core_job") or {}
    by_step: dict[int, list[Json]] = {}
    for outcome in kb["desired_outcomes"]["outcomes"]:
        if not outcome.get("merged_into"):
            by_step.setdefault(int(outcome["step"]), []).append(outcome)
    steps = [{"n": n, "stage": step.get("stage", ""), "statement": step["statement"],
              "coverage": step.get("coverage", 0),
              "outcomes": [{"id": o["id"], "statement": o["statement"], "interview_count": o.get("interview_count", 0)}
                           for o in by_step.get(n, [])]}
             for n, step in sorted(steps_by_n(kb).items())]
    return {"project": kb["meta"].get("project", ""), "interview_count": len(kb["interviews"]),
            "core_job": core.get("statement"), "core_job_status": core.get("status", ""),
            "job_executor": core.get("job_executor", ""),
            "segments": {k: v.get("name", "") for k, v in (kb.get("clusters") or {}).items()},
            "steps": steps, "processed_files": sorted(interviews_by_file(kb)),
            "pending_proposals": [{"id": p["id"], "type": p["type"], "target": p.get("target", ""),
                                   "proposal": p.get("proposal", "")}
                                  for p in kb["proposed_changes"] if p.get("status") == "pending"],
            "stale": stale_layers(kb), "schema_version": kb["meta"].get("schema_version"),
            "tool_version": __version__}


def cmd_context(args: argparse.Namespace) -> int:
    data = context_data(load_kb(args.kb))
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2, default=str))
        return 0
    print(f"PROJECT {data['project']}  interviews={data['interview_count']}")
    print(f"CORE JOB: {data['core_job'] or '(none yet: bootstrap)'}  [{data['core_job_status']}]")
    if data["job_executor"]:
        print(f"EXECUTOR: {data['job_executor']}")
    if data["segments"]:
        print("SEGMENTS: " + "; ".join(f"{k}={v}" for k, v in data["segments"].items()))
    for step in data["steps"]:
        print(f"\nSTEP {step['n']} [{step['stage']}] {step['statement']}  (interviews {step['coverage']})")
        for outcome in step["outcomes"]:
            print(f"   {outcome['id']:>6}  {outcome['statement']}  (iv {outcome['interview_count']})")
    print("\nPROCESSED FILES: " + ", ".join(data["processed_files"]))
    if data["pending_proposals"]:
        pending = "; ".join(f"{p['id']} {p['type']} {p['target']}" for p in data["pending_proposals"])
        print(f"\nPENDING PROPOSALS: {pending}")
    if data["stale"]:
        print("\nSTALE LAYERS: " + ", ".join(data["stale"]))
    return 0


# ---------- review ----------
def describe_proposal(proposal: Json) -> str:
    return {"new_step": "Add a step", "reword_step": f"Reword step {proposal.get('target')}",
            "reword_outcome": f"Reword outcome {proposal.get('target')}", "reword_core_job": "Reword the core job",
            "merge_outcomes": f"Merge outcome {proposal.get('merge')} into {proposal.get('target')}",
            "move_outcome": f"Move outcome {proposal.get('target')} to step {proposal.get('to_step')}",
            "new_segment": "Add a segment"}.get(str(proposal.get("type")), "Change")


def _review_head(kb: Json, live_outcomes: list[Json]) -> list[str]:
    core = kb.get("market_core_job") or {}
    return [f"# {kb['meta'].get('project', 'ODI study')}: review sheet", "",
            f"{len(kb['interviews'])} interviews · {len(kb['job_map']['steps'])} job steps · "
            f"{len(live_outcomes)} outcomes · updated {today()}", "",
            f"**Core job:** {core.get('statement', 'not set yet')}"
            + (" *(proposed)*" if core.get("status") == "proposed" else ""), ""]


def _review_decisions(kb: Json) -> list[str]:
    pending = [p for p in kb["proposed_changes"] if p.get("status") == "pending"]
    lines = ["## Decisions waiting for you", ""]
    if not pending:
        return lines + ["None.", ""]
    for proposal in pending:
        lines.append(f"- **{proposal['id']} · {describe_proposal(proposal)}:** {proposal['proposal']}. "
                     f"*Why:* {proposal['rationale']}")
    return lines + ["", "Reply approve or reject for each, by ID.", ""]


def _review_new(kb: Json, since: str, new_outcomes: set[str]) -> list[str]:
    new_interviews = [i for i in kb["interviews"] if since and str(i.get("added", "")) >= since]
    if not (new_interviews or new_outcomes):
        return []
    lines = [f"## New since {since}", ""]
    for record in new_interviews:
        lines.append(f"- **{record['id']} {record.get('name', '')}:** {record['job_executor']['statement']} "
                     f"Core job: *{record['core_functional_job']['statement']}*")
    for outcome in kb["desired_outcomes"]["outcomes"]:
        if outcome["id"] in new_outcomes:
            lines.append(f"- New outcome **{outcome['id']}:** {outcome['statement']}")
    return lines + [""]


def _review_map(kb: Json, live_outcomes: list[Json], new_outcomes: set[str]) -> list[str]:
    by_step: dict[int, list[Json]] = {}
    for outcome in live_outcomes:
        by_step.setdefault(int(outcome["step"]), []).append(outcome)
    lines = ["## Job map", "",
             "Numbers in brackets show how many interviews support each line. ● marks what is new.", ""]
    ordered = sorted(kb["job_map"]["steps"], key=lambda s: int(s["n"]))
    for stage in STAGES:
        steps = [s for s in ordered if s.get("stage") == stage]
        if not steps:
            continue
        lines.append(f"### {stage.capitalize()}")
        for step in steps:
            lines.append(f"**{step['n']}. {step['statement']}** [{step.get('coverage', 0)}]")
            for outcome in by_step.get(int(step["n"]), []):
                mark = "● " if outcome["id"] in new_outcomes else ""
                lines.append(f"- {mark}{outcome['id']} {outcome['statement']} [{outcome.get('interview_count', 0)}]")
            lines.append("")
    return lines


def _review_tail(kb: Json) -> list[str]:
    lines = []
    thin = [f"{s['n']}. {s['statement']}" for s in thin_steps(kb)]
    if thin:
        lines += ["## Ask about these next", "", f"Fewer than {THIN_STEP} interviews support these steps:", ""]
        lines += [f"- {t}" for t in thin] + [""]
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
            + _review_map(kb, live_outcomes, new_outcomes) + _review_tail(kb))


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
MAP_KEYS = ["meta", "market_core_job", "job_map", "desired_outcomes", "interviews", "clusters", "proposed_changes",
            "changelog"]
MAP_START, MAP_END = "/* @kb-data:start */", "/* @kb-data:end */"


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


def cmd_map(args: argparse.Namespace) -> int:
    """Rebuild the interactive discovery map with the current KB embedded, so it opens with no setup."""
    kb = load_kb(args.kb)
    data = {key: kb[key] for key in MAP_KEYS if key in kb}
    payload = json.dumps(data, default=str, ensure_ascii=False)
    payload = payload.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    template_path = skill_file("assets", "discovery-map-template.html", args.template)
    if not template_path:
        raise KbError("map template not found: put discovery-map-template.html next to kb_tool.py, run the script from "
                      "the skill folder, or pass --template (a discovery-map.html made earlier also works)",
                      code="skill_file_missing")
    with open(template_path, encoding="utf-8") as handle:
        template = handle.read()
    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.kb)), "discovery-map.html")
    with open(out, "w", encoding="utf-8") as handle:
        handle.write(embed_kb(template, payload))
    args.run.note(out=args.run.relative(out))
    print(f"wrote {out} ({len(kb['interviews'])} interviews, {len(kb['desired_outcomes']['outcomes'])} outcomes); "
          "open it in any browser. It contains every name and quote in the KB, so treat it as personal data.")
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
            report.error(f"interview {kb_id}: file {record.get('file')} not found under --transcripts",
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
            checker.check(step["evidence"], f"step {step['n']}", report)
    for outcome in kb["desired_outcomes"]["outcomes"]:
        if outcome.get("evidence"):
            checker.check(outcome["evidence"], f"outcome {outcome['id']}", report)
    for proposal in kb["proposed_changes"]:
        if proposal.get("status") == "pending" and proposal.get("evidence"):
            checker.check(proposal["evidence"], f"proposal {proposal.get('id')}", report)


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
    kb = ensure(load_yaml(args.kb), args.kb)
    check_version(kb, args.kb)
    problems = structure_problems(kb, args.schema)
    args.run.note(structure_problems=len(problems))
    if problems:
        args.run.fail("structure", len(problems))
        print(f"structure: {len(problems)} problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("structure: matches kb-schema.json and every reference resolves")
    if not args.transcripts:
        return 0
    report = Report()
    transcripts = transcripts_for(args.transcripts, report)
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
                        "; if the change is intended, run validate --transcripts ... --rehash to accept it"),
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


MIGRATIONS: dict[int, Callable[[Json], None]] = {}  # from version -> function that upgrades the KB to version + 1


def cmd_migrate(args: argparse.Namespace) -> int:
    kb = ensure(load_yaml(args.kb), args.kb)
    version = check_version(kb, args.kb)
    args.run.note(schema_from=version)
    if version == SCHEMA_VERSION:
        print(f"nothing to do: {args.kb} already uses schema version {SCHEMA_VERSION}")
        return 0
    start = version
    while version < SCHEMA_VERSION:
        MIGRATIONS[version](kb)
        version += 1
        kb["meta"]["schema_version"] = version
    kb["changelog"].append(changelog_entry(args.run, "migrate",
                                           summary=f"migrated from schema version {start} to {SCHEMA_VERSION}"))
    made = backup(args.kb)
    save_kb(kb, args.kb)
    args.run.note(written=True, backup=args.run.relative(made))
    print(f"migrated {args.kb} from schema version {start} to {SCHEMA_VERSION}")
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
    sp.add_argument("--transcripts", required=True, action="append", help="folder or file; repeat for several")
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
    sp = command("validate", cmd_validate, "check the KB's structure, then its quotes")
    sp.add_argument("--transcripts", action="append",
                    help="folder or file; repeat for several; omit to check structure only")
    sp.add_argument("--schema", help="path to kb-schema.json, if it is not next to the script")
    sp.add_argument("--rehash", action="store_true",
                    help="accept transcripts whose content changed since they were added")
    command("migrate", cmd_migrate, "bring an older KB up to the current schema version")
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
