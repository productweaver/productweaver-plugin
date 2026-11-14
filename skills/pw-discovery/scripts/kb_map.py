"""`kb_tool map`: build the interactive discovery map, the KB inside the template, and show it in a browser.

It lives apart from kb_tool.py so the main script stays under the directory's 256 KiB file limit. kb_tool loads it
only for `map` and hands it the kb_tool module (`kt`), whose helpers it uses."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import platform
import re
import sys
import webbrowser
from typing import Any

Json = dict[str, Any]
kt: Any = None  # the kb_tool module, set by cmd_map()


MAP_KEYS = ["meta", "core_jobs", "job_map", "desired_outcomes", "current_solutions", "interviews", "clusters",
            "proposed_changes", "changelog"]
MAP_START, MAP_END = "/* @kb-data:start */", "/* @kb-data:end */"


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


def map_stamp() -> Json:
    """When the map was made and by which version, for the note at the end of its Overview."""
    stamp: Json = {"at": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "tool": kt.__version__}
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


def cmd_map(args: argparse.Namespace, tool: Any) -> int:
    """Rebuild the interactive discovery map with the current KB embedded, so it opens with no setup."""
    global kt  # noqa: PLW0603 - kb_tool hands itself over once, here
    kt = tool
    kb = kt.load_kb(args.kb)
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
    payload = json.dumps(data, default=str, ensure_ascii=False)
    payload = payload.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    template_path = kt.skill_file("assets", "discovery-map-template.html", args.template)
    if not template_path:
        raise kt.KbError("map template not found: put discovery-map-template.html next to kb_tool.py, run the "
                         "kb_tool.py that sits in the skill's scripts/ folder, or pass --template (a "
                         "discovery-map.html made by this version also works)", code="skill_file_missing")
    with open(template_path, encoding="utf-8") as handle:
        template = handle.read()
    if kt.MAP_SCHEMA not in template:
        raise kt.KbError(f"the map template {template_path} is older than KB schema {kt.SCHEMA_VERSION}; use "
                         "discovery-map-template.html from the skill", code="template_old")
    for name in kt.MAP_ASSETS:
        template = inline_asset(template, template_path, name)
    out = args.out or os.path.join(kt.output_folder(args.kb), "discovery-map.html")  # after the template is read
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
    kt.labels_missing_note(args, kb, missing)
    return 0
