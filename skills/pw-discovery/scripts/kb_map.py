"""`kb_tool map`: build the interactive discovery map, the KB inside the template, and show it in a browser.

It lives apart from kb_tool.py so the main script stays under the directory's 256 KiB file limit. kb_tool loads it
for `map`, `context --batch` and after a merge, and hands it the kb_tool module (`kt`), whose helpers it uses.

A map opened from the user's folder stays live: `map` also writes pw-output/.map-live/status.js, which names the map's
build and what the assistant is doing, and the open map loads it again every few seconds (a page opened from disk may
load a script beside it, but not fetch a file). When the build changes, the map reloads itself and keeps its place."""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import math
import os
import pathlib
import platform
import re
import shutil
import sys
import time
import webbrowser
from typing import Any

Json = dict[str, Any]
kt: Any = None  # the kb_tool module, set by cmd_map()


MAP_KEYS = ["meta", "core_jobs", "job_map", "desired_outcomes", "current_solutions", "interviews", "clusters",
            "proposed_changes", "changelog"]
MAP_START, MAP_END = "/* @kb-data:start */", "/* @kb-data:end */"
LIVE_DIR, LIVE_FILE = ".map-live", "status.js"  # beside the map, hidden; its own .gitignore keeps it out of git
LIVE_MARK = "/* @live:1 */"  # in the template: a map that reloads itself when a newer one is written
MAP_FILE = "discovery-map.html"  # the status speaks for this file only: a copy beside it knows it is a copy


def inline_asset(template: str, template_path: str, name: str) -> str:
    """Inline a script shipped beside the template; a map made earlier already holds it."""
    tag = f'<script src="{name}"></script>'
    if tag not in template:
        return template
    beside = os.path.join(os.path.dirname(os.path.abspath(template_path)), name)
    path = beside if os.path.isfile(beside) else kt.skill_file("assets", name)
    if not path:
        raise kt.KbError(f"{name} not found: keep it next to discovery-map-template.html, as the skill ships them",
                         code="skill_file_missing")
    with open(path, encoding="utf-8") as handle:
        library = handle.read()
    if "</script" in library.lower():
        raise kt.KbError(f"{path} must not contain a closing script tag", code="template_invalid")
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
        raise kt.KbError("the template has no data markers and no single 'const SAMPLE = ' line; "
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


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def map_stamp() -> Json:
    """Which version made the map, for the note at the end of its Overview. `at` and `build` come in cmd_map."""
    stamp: Json = {"tool": kt.__version__}
    version = plugin_version()
    if version:
        stamp["plugin"] = version
    return stamp


def js_json(data: Any) -> str:
    """JSON that is safe inside a <script>: no closing tag, and no line ends that JavaScript reads as new lines."""
    text = json.dumps(data, default=str, ensure_ascii=False)
    return text.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def write_atomic(path: str, text: str) -> None:
    """Write a temporary file beside the target, then swap it in, so an open map never reads half a file. On Windows
    a browser may hold the old file for a moment: try again, then write in place as before."""
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        with contextlib.suppress(OSError):  # the map holds names and quotes: keep the mode the user gave it
            shutil.copymode(path, tmp)
        for attempt in range(3):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if attempt == 2:
                    with open(path, "w", encoding="utf-8", newline="\n") as handle:
                        handle.write(text)
                    return
                time.sleep(0.2)
    finally:
        with contextlib.suppress(OSError):
            os.remove(tmp)


# ---------- the live map: status.js beside the map ----------
def live_path(kb_path: str) -> str:
    """pw-output/.map-live/status.js for this study, worked out without making any folder."""
    workspace = os.path.dirname(os.path.dirname(os.path.abspath(kb_path)))
    return os.path.join(workspace, kt.OUTPUT, LIVE_DIR, LIVE_FILE)


def read_status(path: str) -> Json:
    """What status.js says, or {} when it is missing or cannot be read."""
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        data = json.loads(text[text.index("(") + 1:text.rindex(")")])
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_status(path: str, status: Json) -> bool:
    """Write status.js (and the .gitignore that keeps its folder out of git). False when it cannot be written."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        ignore = os.path.join(os.path.dirname(path), ".gitignore")
        if not os.path.isfile(ignore):
            write_atomic(ignore, "*\n")
        write_atomic(path, f"pwMapStatus({js_json({'v': 1, 'file': MAP_FILE, **status})});\n")
    except OSError:
        return False
    return True


def map_kind(path: str) -> str:
    """The map already at `path`: none, old (it does not reload itself; plugin 0.14 and earlier) or live."""
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            head = handle.read(1 << 20).split(MAP_START, 1)[0]
    except OSError:
        return "none"
    return "live" if LIVE_MARK in head else "old"


def minutes(n: int) -> int:
    """About how long reading a batch of n new transcripts takes (2026-11-11 benchmark: 1.5 minutes each, plus 2)."""
    return math.ceil(1.5 * n + 2)


def expired(work: Json, now: dt.datetime) -> bool:
    """A batch that has run past twice its estimate plus 5 minutes has stopped; the map then stops saying so too."""
    try:
        since = dt.datetime.fromisoformat(str(work["since"]))
        return (now - since).total_seconds() > 2 * float(work["expect_s"]) + 300
    except (KeyError, TypeError, ValueError):
        return True


def start_batch(args: argparse.Namespace, tool: Any) -> Json:
    """`context --batch N`: say how long reading N new transcripts takes, and tell an open map that the study is being
    updated. It never makes pw-output/: with no map yet there is nothing open to tell."""
    global kt  # noqa: PLW0603 - kb_tool hands itself over once, here
    kt = tool
    n = args.batch
    if n < 1:
        raise kt.KbError("--batch takes the number of new transcripts about to be read: 1 or more",
                         code="batch_invalid")
    path, now = live_path(args.kb), dt.datetime.now().astimezone()
    old = read_status(path)
    shown = "none"
    if old.get("build") and os.path.isfile(os.path.join(os.path.dirname(os.path.dirname(path)), MAP_FILE)):
        work = old.get("work") if isinstance(old.get("work"), dict) else {}
        again = work.get("n") == n and work.get("phase") == "reading" and not expired(work, now)
        work = {"phase": "reading", "n": n, "done": 0, "since": work["since"] if again else now_iso(),
                "expect_s": minutes(n) * 60}
        shown = "ok" if write_status(path, {**old, "work": work}) else "failed"
    args.run.note(live=shown)
    if not args.json:
        print(f"batch: {n} new transcript(s) to read, about {minutes(n)} minutes."
              + (" An open map now shows that the study is being updated." if shown == "ok" else ""))
    return {"n": n, "minutes": minutes(n), "map": shown}


def batch_merged(kb_path: str, added: int, tool: Any) -> bool:
    """After a merge: count the conversations in (new interviews and later conversations), and when the batch is in,
    tell an open map the overview comes next. True when this merge ended the batch's reading. Never fails the merge: a
    status that cannot be read or written is left as it is."""
    global kt  # noqa: PLW0603 - kb_tool hands itself over once, here
    kt = tool
    path = live_path(kb_path)
    old = read_status(path)
    work = old.get("work")
    if added < 1 or not isinstance(work, dict) or not isinstance(work.get("n"), int):
        return False
    done = work.get("done") if isinstance(work.get("done"), int) else 0
    done += added
    phase = "summary" if done >= work["n"] else "reading"
    return write_status(path, {**old, "work": {**work, "done": done, "phase": phase}}) and phase == "summary"


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
    "none": "Open the link in any browser.",
    "old": "Open the link in any browser. If the map is already open, reload it once: from then on it updates by "
           "itself.",
    "live": "Open the link in any browser. A map that is already open updates by itself within a few seconds.",
    "opened": "Opened in the default browser. If nothing appeared, open the link.",
    "failed": "Could not start a browser here. Open the link in any browser.",
    "no_display": "This machine has no browser to show it (a remote session, or no display). Download the file, "
                  "or open it from your editor's file tree.",
    "off": "Opening is switched off (KB_TOOL_OPEN=0). Open the link in any browser.",
}


def map_data(kb: Json, args: argparse.Namespace) -> tuple[Json, int]:
    """What the map embeds: the KB's parts it draws, the overview and themes, the stamp, the guides and the labels."""
    data = {key: kb[key] for key in MAP_KEYS if key in kb}
    if kt.themes_of(kb):  # a KB with no themes gives the map it always gave
        data["value_themes"] = kb["value_themes"]
    if kt.overviews_of(kb):  # the written findings of the Overview view; the map counts the rest itself
        data["overview"] = kb["overview"]
    data["generated"] = map_stamp()
    own, missing = kt.study_labels(kb, args.kb)
    text = kt.Text(kt.study_language(kb), own)
    data["generated"]["guides"] = {str(j["id"]): "\n".join(kt.guide_lines(kb, text, str(j["id"])))
                                   for j in kb["core_jobs"]}
    labels = {key: value for key, value in own.items() if key.startswith("map.")}
    if labels:  # only a study in another language has any; the map shows English for the rest
        data["labels"] = labels
    return data, missing


def read_template(args: argparse.Namespace) -> str:
    template_path = kt.skill_file("assets", "discovery-map-template.html", args.template)
    if not template_path:
        raise kt.KbError("map template not found: put discovery-map-template.html next to kb_tool.py, run the "
                         "kb_tool.py that sits in the skill's scripts/ folder, or pass --template (a "
                         "discovery-map.html made by this version also works)", code="skill_file_missing")
    with open(template_path, encoding="utf-8") as handle:
        template = handle.read()
    if kt.MAP_SCHEMA not in template:
        raise kt.KbError(f"the map template {template_path} is older than KB schema {kt.SCHEMA_NEWEST}; use "
                         "discovery-map-template.html from the skill", code="template_old")
    for name in kt.MAP_ASSETS:
        template = inline_asset(template, template_path, name)
    return template


def build_id(template: str, data: Json) -> str:
    """A hash of the map as it would be written, without its time. The guides say the day they were made: that day is
    left out too, so the first rebuild of a new day with no change keeps the build."""
    day = kt.today()
    same = {**data, "generated": {**data["generated"],
                                  "guides": {k: v.replace(day, "") for k, v in data["generated"]["guides"].items()}}}
    return hashlib.sha256(embed_kb(template, js_json(same)).encode("utf-8")).hexdigest()[:12]


def cmd_map(args: argparse.Namespace, tool: Any) -> int:
    """Rebuild the interactive discovery map with the current KB embedded, so it opens with no setup. The build is a
    hash of the map without its time: a rebuild that changes nothing keeps the build and the time, so an open map
    neither reloads nor says it was just updated."""
    global kt  # noqa: PLW0603 - kb_tool hands itself over once, here
    kt = tool
    kb = kt.load_kb(args.kb)
    data, missing = map_data(kb, args)
    template = read_template(args)
    build = build_id(template, data)
    live = not args.out  # a copy written elsewhere (--out) is not watched
    out = args.out or os.path.join(kt.output_folder(args.kb), MAP_FILE)  # after the template is read
    path = live_path(args.kb)
    old = read_status(path) if live else {}
    tab = map_kind(out)
    data["generated"] = {"at": old["at"] if old.get("build") == build and old.get("at") else now_iso(),
                         **data["generated"], "build": build}
    write_atomic(out, embed_kb(template, js_json(data)))  # first the map, then the status that names it
    args.run.note(out=args.run.relative(out))
    # a rebuild run by a write in the middle of a batch (release B1: merge, themes) keeps "being updated" on screen
    work = old.get("work") if getattr(args, "via", None) in ("merge", "themes") else None
    shown = ("ok" if write_status(path, {"build": build, "at": data["generated"]["at"], "work": work}) else "failed"
             ) if live else "off"
    args.run.note(live=shown, tab=tab)
    uri = pathlib.Path(os.path.abspath(out)).as_uri()
    browser = open_in_browser(uri) if args.open else None
    if browser:
        args.run.note(browser=browser)
    print(f"wrote {out} ({len(kb['interviews'])} interviews, {len(kb['desired_outcomes']['outcomes'])} outcomes)\n"
          f"link: {uri}\n{MAP_NEXT[browser or (tab if shown == 'ok' else None)]}\n"
          "It contains every name and quote in the KB, so treat it as personal data.")
    if shown == "failed":
        report = kt.Report()
        report.warn("status.js not written", code="map_status_failed")
        args.run.add_report(report)
        print(f"map: could not write {kt.OUTPUT}/{LIVE_DIR}/{LIVE_FILE}; an open map will not update by itself.")
    kt.labels_missing_note(args, kb, missing)
    return 0
