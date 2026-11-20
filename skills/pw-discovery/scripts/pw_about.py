#!/usr/bin/env python3
"""pw_about.py - which Product Weaver is installed, and what it runs on. Used by the pw-about skill.

Part of the Product Weaver plugin · https://productweaver.com

  python3 pw_about.py [--assistant NAME] [--model ID] [--study PATH] [--json] [--report] [--check]

Prints a short summary: the plugin version and the folder it is loaded from, the assistant and model, the OS and
Python, the study in this folder and whether usage statistics are on. --report adds a block to paste into a bug
report, --json prints the same facts as one JSON object. Every path is shown with the home folder as ~ and the login
name as <user>, so all three are safe to paste in a public issue.

It writes no file, records no usage event and makes no network call. Only --check asks productweaver.com for the
newest version: one GET with no identifier. PW_ABOUT_ENDPOINT replaces that address; only the tests set it.
Exit code 0 always, except that bad arguments make argparse print its own help and exit 2.
Only the standard library is used.
"""
from __future__ import annotations

import argparse
import contextlib
import getpass
import importlib.util
import json
import os
import platform
import re
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parents[2]
HELP_URL = "https://www.productweaver.com/plugin"
ENDPOINT = "https://www.productweaver.com/api/plugin-version"
CHECK_TIMEOUT_S = 3.0
VERSION_RE = r"\d+\.\d+\.\d+"
UPDATE_HINTS = {"claude-code": "run `claude plugin update productweaver` in a terminal, then restart Claude Code"}
SAFE_TEXT = r"[^A-Za-z0-9._ -]"
MAX_ASSISTANT = 32
MIN_PYTHON = (3, 9)
LOG_NAME, LOG_TAIL_BYTES = "kb_tool.jsonl", 65_536
STUDY_FLAGS = {"needs-migrate": "study-needs-migrate", "newer-than-plugin": "study-newer-than-plugin",
               "unreadable": "study-unreadable"}
FLAGS = ("install-damaged", "versions-differ", "python-too-old", "study-needs-migrate", "study-newer-than-plugin",
         "study-unreadable", "update-available", "check-failed")


def load(name: str):
    """A script from beside this one (pw_usage, pw_base), or None when it is missing or broken (a damaged install)."""
    before, sys.dont_write_bytecode = sys.dont_write_bytecode, True  # this script writes no file
    try:
        spec = importlib.util.spec_from_file_location(name, HERE / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module  # a dataclass looks its module up there
        spec.loader.exec_module(module)
    except Exception:  # noqa: BLE001 - any failure here only means the install is damaged
        sys.modules.pop(name, None)
        return None
    finally:
        sys.dont_write_bytecode = before
    return module


# --- paths ---------------------------------------------------------------------------------------------------------

def default_home() -> list[str]:
    homes = []
    with contextlib.suppress(RuntimeError, KeyError):
        homes.append(str(Path.home()))
    profile = os.environ.get("USERPROFILE")
    if profile and profile not in homes:
        homes.append(profile)
    return homes


def default_users() -> list[str]:
    names = [os.environ.get("USER", ""), os.environ.get("USERNAME", ""), os.environ.get("LOGNAME", "")]
    with contextlib.suppress(Exception):  # getuser raises various errors when no name is known
        names.append(getpass.getuser())
    return [n for n in dict.fromkeys(names) if n]


def redact(path: str, home: str | list[str] | None = None, users: list[str] | None = None) -> str:
    """The path with the home folder as ~ and every whole segment equal to a login name of 3+ characters as <user>."""
    homes = default_home() if home is None else ([home] if isinstance(home, str) else list(home))
    names = default_users() if users is None else list(users)
    fold = sys.platform in ("win32", "darwin")
    text = path
    for base in sorted((h.rstrip("/\\") for h in homes if h and h.rstrip("/\\")), key=len, reverse=True):
        same = text.lower().startswith(base.lower()) if fold else text.startswith(base)
        if same and (len(text) == len(base) or text[len(base)] in "/\\"):
            text = "~" + text[len(base):]
            break
    wanted = {n.lower() if fold else n for n in names if len(n) >= 3}
    parts = re.split(r"([/\\])", text)
    return "".join("<user>" if (p.lower() if fold else p) in wanted else p for p in parts)


# --- facts ---------------------------------------------------------------------------------------------------------

def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, RecursionError):
        return None


def kb_tool_text() -> str:
    try:
        return (HERE / "kb_tool.py").read_text(encoding="utf-8")
    except (OSError, ValueError):
        return ""


def constant(text: str, pattern: str) -> str | None:
    found = re.search(pattern, text, re.M)
    return found.group(1) if found else None


def plugin_facts(tool_text: str, base) -> dict:
    """The versions the install gives, each read by pw_base as the other scripts read it; none without pw_base."""
    manifests = {name: base.manifest_version(PLUGIN_ROOT / name) if base else None
                 for name in ("plugin.json", ".claude-plugin/plugin.json")}
    manifests["kb_tool"] = base.tool_version(tool_text) if base else None
    skills = []
    with contextlib.suppress(OSError):
        skills = sorted(p.name for p in (PLUGIN_ROOT / "skills").iterdir() if (p / "SKILL.md").is_file())
    version = next((v for v in manifests.values() if v), None)
    return {"name": "productweaver", "version": version, "path": redact(str(PLUGIN_ROOT)), "manifests": manifests,
            "skills": skills}


def clean_text(value: str | None, limit: int) -> str | None:
    text = re.sub(SAFE_TEXT, "", value or "").strip()[:limit]
    return text or None


def host_facts(args: argparse.Namespace, usage) -> dict:
    assistant = args.assistant or os.environ.get("KB_TOOL_AGENT", "").strip()
    if not assistant:
        if os.environ.get("CLAUDECODE"):
            assistant = "claude-code"
        elif os.environ.get("GEMINI_CLI"):
            assistant = "gemini-cli"
        else:
            assistant = os.environ.get("TERM_PROGRAM", "").strip().lower()
    model_pattern = getattr(usage, "MODEL_PATTERN", r"[a-z0-9][a-z0-9.-]{0,47}")
    model = args.model if args.model and re.fullmatch(model_pattern, args.model) else None
    return {"assistant": clean_text(assistant, MAX_ASSISTANT), "model": model}


def system_facts() -> dict:
    family = {"darwin": "macos", "win32": "windows", "linux": "linux"}.get(sys.platform, "other")
    version = None
    with contextlib.suppress(Exception):  # platform probes can fail in odd sandboxes
        version = (platform.mac_ver()[0] if family == "macos" else platform.release()) or None
    return {"os": family, "os_version": version, "arch": platform.machine() or None,
            "python": platform.python_version(), "python_path": redact(sys.executable) if sys.executable else None}


def usage_facts(pw_kb: Path, usage) -> dict:
    if usage is None:
        return {"status": None, "reason": "pw_usage.py is missing"}
    if usage.disabled():
        variable = "DO_NOT_TRACK" if os.environ.get("DO_NOT_TRACK", "").strip().lower() in ("1", "true") \
            else "KB_TOOL_USAGE"
        return {"status": "disabled", "reason": variable}
    if not pw_kb.is_dir():
        return {"status": "no-study", "reason": "no study in this folder"}
    state, data = usage.read_settings(pw_kb)
    reason = {"ask": "not asked yet", "on": "you said yes"}.get(state)
    if state == "off":
        reason = "you said no" if data.get("share") is False else "settings file unreadable"
    return {"status": state, "reason": reason}


def last_log_line(path: Path, max_bytes: int = LOG_TAIL_BYTES) -> dict | None:
    """The last line of the run log that parses as a JSON object, reading at most its last max_bytes."""
    try:
        with path.open("rb") as handle:
            size = handle.seek(0, os.SEEK_END)
            handle.seek(max(0, size - max_bytes))
            tail = handle.read(max_bytes)
    except OSError:
        return None
    lines = tail.split(b"\n")
    if size > max_bytes:
        lines = lines[1:]  # the first line of the window is cut
    for raw in reversed(lines):
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError, RecursionError):
            continue
        if isinstance(data, dict):
            return data
    return None


def run_facts(line: dict | None) -> dict | None:
    if line is None:
        return None
    pick = {key: line.get(key) for key in ("ts", "command", "tool_version", "exit_code")}
    pick["ts"] = pick["ts"] if isinstance(pick["ts"], str) and re.match(r"\d{4}-\d\d-\d\dT\d\d:\d\d", pick["ts"]) \
        else None
    pick["command"] = clean_text(pick["command"], 20) if isinstance(pick["command"], str) else None
    pick["tool_version"] = pick["tool_version"] if isinstance(pick["tool_version"], str) and re.fullmatch(
        VERSION_RE, pick["tool_version"]) else None
    pick["exit_code"] = pick["exit_code"] if isinstance(pick["exit_code"], int) else None
    return pick


def study_facts(pw_kb: Path, tool_text: str) -> dict:
    """What a study says about itself: never its content or its folder's name, only its format, size and last run."""
    kb = pw_kb / "pw-kb.json"
    if not kb.is_file():
        if (pw_kb / "pw-kb.yaml").is_file() or (pw_kb.parent / "KB").is_dir():
            return {"state": "needs-migrate"}
        return {"state": "none"}
    current = int(constant(tool_text, r"^SCHEMA_VERSION = (\d+)") or 0) or None
    newest = int(constant(tool_text, r"^SCHEMA_NEWEST = (\d+)") or 0) or current
    facts = {"state": "unreadable", "schema_version": None, "reads_up_to": newest,
             "interviews": None, "core_jobs": None, "last_run": run_facts(last_log_line(pw_kb / "logs" / LOG_NAME))}
    data = read_json(kb)
    meta = data.get("meta", {}) if isinstance(data, dict) else None
    if not isinstance(meta, dict):
        return facts
    version = meta.get("schema_version", current)
    if not isinstance(version, int) or isinstance(version, bool):
        return facts
    interviews, jobs = data.get("interviews") or [], data.get("core_jobs") or []
    facts.update(schema_version=version, interviews=len(interviews) if isinstance(interviews, list) else None,
                 core_jobs=len(jobs) if isinstance(jobs, list) else None)
    if current and version < current:
        facts["state"] = "needs-migrate"
    elif newest and version > newest:
        facts["state"] = "newer-than-plugin"
    else:
        facts["state"] = "ok"
    return facts


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: ANN002, ANN003, ARG002 - refuse every redirect
        return None


def check_update(current: str | None, url: str = ENDPOINT, timeout: float = CHECK_TIMEOUT_S) -> dict:
    """Ask the site for the newest published version: one GET, no cookie, no identifier, no redirect."""
    failed = {"state": "failed", "latest": None, "date": None}
    request = urllib.request.Request(url, headers={"User-Agent": "productweaver-plugin", "Accept": "application/json"})
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
            if response.status != 200:
                return failed
            data = json.loads(response.read(4096).decode("utf-8"))
    except Exception:  # noqa: BLE001 - OSError, ValueError, and http.client errors from a broken answer
        return failed
    latest = data.get("latest") if isinstance(data, dict) else None
    if not (isinstance(latest, str) and re.fullmatch(VERSION_RE, latest)):
        return failed
    if not (isinstance(current, str) and re.fullmatch(VERSION_RE, current)):
        return failed  # never "up to date" for a version we could not read
    date = data.get("date") if isinstance(data.get("date"), str) and re.fullmatch(
        r"\d{4}-\d\d-\d\d", data["date"]) else None
    newer = tuple(map(int, latest.split("."))) > tuple(map(int, current.split(".")))
    return {"state": "available" if newer else "up-to-date", "latest": latest, "date": date}


def update_hint(assistant: str | None) -> str:
    return UPDATE_HINTS.get(assistant or "", f"update it where you installed it, as {HELP_URL} says")


def collect(args: argparse.Namespace, cwd: Path) -> dict:
    usage, base = load("pw_usage"), load("pw_base")
    tool_text = kb_tool_text()
    pw_kb = Path(args.study) if args.study else cwd / ".pw-kb"
    flags = []
    parts = {}
    for key, probe in (("plugin", lambda: plugin_facts(tool_text, base)), ("host", lambda: host_facts(args, usage)),
                       ("system", system_facts), ("study", lambda: study_facts(pw_kb, tool_text)),
                       ("usage", lambda: usage_facts(pw_kb, usage))):
        try:
            parts[key] = probe()
        except Exception:  # noqa: BLE001 - one broken probe must not stop the report
            parts[key] = {}
    if usage is None or base is None or not tool_text:
        flags.append("install-damaged")
    found = {v for v in (parts["plugin"].get("manifests") or {}).values() if v}
    if len(found) > 1:
        flags.append("versions-differ")
    if sys.version_info < MIN_PYTHON:
        flags.append("python-too-old")
    if parts["study"].get("state") in STUDY_FLAGS:
        flags.append(STUDY_FLAGS[parts["study"]["state"]])
    update = {"state": "not-run"}
    if args.check:
        url = os.environ.get("PW_ABOUT_ENDPOINT") or ENDPOINT
        try:
            update = check_update(parts["plugin"].get("version"), url)
        except Exception:  # noqa: BLE001 - the check must never cost the rest of the report
            update = {"state": "failed", "latest": None, "date": None}
        flags.append({"available": "update-available", "failed": "check-failed"}.get(update["state"], ""))
    return {"format": 1, **parts, "update": update, "flags": [f for f in flags if f]}


# --- output --------------------------------------------------------------------------------------------------------

def show(value) -> str:
    return "unknown" if value in (None, "") else str(value)


def line(label: str, value: str) -> str:
    return f"  {label:<14}{value}"


def os_name(system: dict) -> str:
    name = {"macos": "macOS", "windows": "Windows", "linux": "Linux"}.get(system.get("os"), "other OS")
    return " ".join(p for p in (name, system.get("os_version"), system.get("arch")) if p)


def plural(count, word: str) -> str:
    return f"{show(count)} {word}" + ("" if count == 1 else "s")


def study_line(study: dict, default_place: bool) -> str:
    state = study.get("state")
    if state == "none":
        return "none in this folder"
    parts = [".pw-kb/" if default_place else "the --study folder"]
    if study.get("schema_version") is not None:
        parts.append(f"format {study['schema_version']}")
    words = {"needs-migrate": "needs migrate", "newer-than-plugin": "made by a newer plugin: update the plugin",
             "unreadable": "cannot be read"}
    if state in words:
        parts.append(words[state])
    else:
        parts.append(f"{plural(study.get('interviews'), 'interview')}, {plural(study.get('core_jobs'), 'core job')}")
    last = study.get("last_run")
    if last and last.get("ts"):
        parts.append(f"last run {last['ts'][:10]} {last['ts'][11:16]} ({show(last.get('command'))})")
    return " · ".join(parts)


def update_lines(update: dict, current: str | None, assistant: str | None) -> list[str]:
    state = update.get("state")
    if state == "up-to-date":
        return [line("Update check", f"up to date (newest is {update['latest']})")]
    if state == "available":
        released = f" released {update['date']}" if update.get("date") else ""
        return [line("Update check", f"{update['latest']}{released} (you have {show(current)})"),
                line("", f"To update, {update_hint(assistant)}."),
                line("", "Your assistant's plugin store can take a day to get it.")]
    if state == "failed":
        return [line("Update check", "failed (offline?)")]
    return [line("Update check", 'not run (say "pw-about --check")')]


def render_summary(facts: dict, default_place: bool = True) -> str:
    plugin, host, system = facts.get("plugin", {}), facts.get("host", {}), facts.get("system", {})
    usage = facts.get("usage", {})
    assistant = show(host.get("assistant")) + (f" ({host['model']})" if host.get("model") else "")
    python = f"Python {show(system.get('python'))}" + (f" ({system['python_path']})" if system.get("python_path")
                                                       else "")
    usage_text = show(usage.get("status")) + (f" ({usage['reason']})" if usage.get("reason") else "")
    lines = [f"Product Weaver {show(plugin.get('version'))}",
             line("Loaded from", show(plugin.get("path"))),
             line("Skills", ", ".join(plugin.get("skills") or []) or "unknown"),
             line("Assistant", assistant),
             line("System", f"{os_name(system)} · {python}"),
             line("Study", study_line(facts.get("study", {}), default_place)),
             line("Usage stats", usage_text),
             *update_lines(facts.get("update", {}), plugin.get("version"), host.get("assistant")),
             line("Help", HELP_URL)]
    return "\n".join(lines + [f"  ! {flag}" for flag in facts.get("flags", [])])


def versions_note(manifests: dict) -> str:
    tool = manifests.get("kb_tool")
    found = {v for v in manifests.values() if v}
    note = f"kb_tool {show(tool)}, " + ("manifests agree" if len(found) <= 1 else "versions differ: " + ", ".join(
        f"{k} {show(v)}" for k, v in manifests.items()))
    if not manifests.get(".claude-plugin/plugin.json"):
        note += " (no .claude-plugin manifest)"
    return note


def report_study(study: dict) -> str:
    if study.get("state") in (None, "none"):
        return show(study.get("state"))
    text = f"{study['state']} · format {show(study.get('schema_version'))} (reads up to " \
           f"{show(study.get('reads_up_to'))}) · {plural(study.get('interviews'), 'interview')} · " \
           f"{plural(study.get('core_jobs'), 'core job')}"
    last = study.get("last_run")
    if last:
        text += (f" · last run {show((last.get('ts') or '')[:10])} kb_tool {show(last.get('tool_version'))} "
                 f"{show(last.get('command'))} exit {show(last.get('exit_code'))}")
    return text


def render_report(facts: dict) -> str:
    plugin, host, system = facts.get("plugin", {}), facts.get("host", {}), facts.get("system", {})
    study, usage = facts.get("study", {}), facts.get("usage", {})
    host_text = show(host.get("assistant")) + (f" / {host['model']}" if host.get("model") else "")
    system_text = " ".join(p for p in (system.get("os"), system.get("os_version"), system.get("arch")) if p)
    lines = [f"productweaver {show(plugin.get('version'))} ({versions_note(plugin.get('manifests') or {})})",
             f"host {host_text} · {system_text or 'unknown'} · python {show(system.get('python'))}",
             f"loaded from {show(plugin.get('path'))}",
             f"study: {report_study(study)}",
             f"usage: {show(usage.get('status'))}"]
    if facts.get("flags"):
        lines.append("flags: " + ", ".join(facts["flags"]))
    return "```\n" + "\n".join(lines) + "\n```"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pw_about.py", description="Which Product Weaver is installed, and what "
                                     "it runs on.")
    parser.add_argument("--assistant", help="your host, as in pw_usage.py: claude-code, codex, cursor, ...")
    parser.add_argument("--model", help="your model ID, when you know it")
    parser.add_argument("--study", help="the .pw-kb folder to read (default: ./.pw-kb)")
    parser.add_argument("--json", action="store_true", help="print the facts as one JSON object")
    parser.add_argument("--report", action="store_true", help="add a block to paste into a bug report")
    parser.add_argument("--check", action="store_true", help="ask productweaver.com for the newest version")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    with contextlib.suppress(AttributeError, ValueError):
        sys.stdout.reconfigure(errors="replace")
    try:
        facts = collect(args, Path.cwd())
        if args.json:
            print(json.dumps(facts, indent=2, ensure_ascii=False))
        else:
            print(render_summary(facts, default_place=not args.study))
            if args.report:
                print("\nFor a bug report:\n" + render_report(facts))
    except Exception as error:  # noqa: BLE001 - a diagnostic tool never ends in a traceback
        print(f"Product Weaver: pw_about.py could not finish ({type(error).__name__}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
