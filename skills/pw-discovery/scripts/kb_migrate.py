"""`kb_tool migrate`: bring a study made by an earlier version up to date.

It lives apart from kb_tool.py so the main script stays under the directory's 256 KiB file limit. kb_tool loads it
only for `migrate` and hands it the kb_tool module (`kt`), whose helpers it uses."""
from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import os
import shutil
from typing import Any, Callable

Json = dict[str, Any]
kt: Any = None  # the kb_tool module, set by cmd_migrate()


def _prefixed(value: Any, job: str) -> Any:
    """A schema 1 step number or outcome ID with the job letter in front: 6 -> "A.6", "6.3" -> "A.6.3"."""
    if kt._is_int(value) or (isinstance(value, str) and (value.isdigit() or kt.BARE_OUTCOME_ID.match(value))):
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
    kt.mark_stale(kb, "step and outcome IDs gained the job letter A, so text that cites old IDs is out of date")
    kt.recount(kb)
    if job["status"] == "proposed":
        kt.file_proposal(kb, kt.confirmation(kb, "A", "Set up before a core job could be confirmed."))
    return "the core job is now core job A; step and outcome IDs gained the prefix A. (6.3 is now A.6.3)"


def _migrate_2(kb: Json) -> str:
    """Schema 2 -> 3: the same data, now kept in a JSON file."""
    return f"the KB is now a JSON file, {kt.KB_FILE}"


MIGRATIONS: dict[int, Callable[[Json], str]] = {1: _migrate_1, 2: _migrate_2}  # from version -> to version + 1


def _upgrade(kb: Json, version: int) -> list[str]:
    """Run the schema migrations from `version` up to the current one. Returns one note per step."""
    notes = []
    while version < kt.SCHEMA_VERSION:
        notes.append(MIGRATIONS[version](kb))
        version += 1
        kb["meta"]["schema_version"] = version
    return notes


def _old_transcripts(kb: Json, kb_path: str, roots: list[str], report: kt.Report) -> list[str]:
    """Point each interview of an old-layout study at the copy the move will make; return the paths to copy.
    Without roots, looks in <study>/Interviews/."""
    study = os.path.dirname(os.path.dirname(os.path.abspath(kb_path)))
    transcripts = kt.transcripts_for(roots or [os.path.join(study, kt.OLD_TRANSCRIPTS)], report)
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
        record["file"] = f"{kt.COPIES}/{os.path.basename(transcript.path)}"
        found.append(transcript.path)
    return found


def _clashes(old_folder: str, new_folder: str, sources: list[str]) -> list[str]:
    """What the move would overwrite in .pw-kb/: a file or folder of the same name, or a different transcript."""
    found = [name for name in kt.MOVED_ON_MIGRATE
             if os.path.exists(os.path.join(old_folder, name)) and os.path.exists(os.path.join(new_folder, name))]
    for source in sources:
        target = os.path.join(new_folder, kt.COPIES, os.path.basename(source))
        if os.path.exists(target) and kt.file_sha256(target) != kt.file_sha256(source):
            found.append(f"{kt.COPIES}/{os.path.basename(source)}")
    return found


def _move_study(old: str, new: str, kb: Json, sources: list[str]) -> str:
    """Copy transcripts into .pw-kb/, move the study's files there, write the KB, remove the old one. Backups keep
    their time stamps. Returns the old KB's backup."""
    old_folder, new_folder = os.path.dirname(os.path.abspath(old)), os.path.dirname(os.path.abspath(new))
    os.makedirs(new_folder, exist_ok=True)
    kt.copy_transcripts(new, sources)
    for name in kt.MOVED_ON_MIGRATE:
        if os.path.exists(os.path.join(old_folder, name)):
            shutil.move(os.path.join(old_folder, name), os.path.join(new_folder, name))
    old_stem, new_stem = (os.path.splitext(os.path.basename(p))[0] for p in (old, new))
    backups = os.path.join(new_folder, "backups")
    for name in sorted(os.listdir(backups)) if os.path.isdir(backups) and old_stem != new_stem else []:
        if name.startswith(f"{old_stem}."):
            os.replace(os.path.join(backups, name), os.path.join(backups, new_stem + name[len(old_stem):]))
    made = kt.backup(new, source=old)
    kt.save_kb(kb, new)
    os.remove(old)
    with contextlib.suppress(OSError):
        os.rmdir(old_folder)  # only when nothing else is left in it
    return made


def _plain(node: Any) -> Any:
    """What PyYAML read, as JSON holds it: dates become text, and every key a string."""
    if isinstance(node, dict):
        return {str(key): _plain(value) for key, value in node.items()}
    if isinstance(node, list):
        return [_plain(value) for value in node]
    return node.isoformat() if isinstance(node, (dt.date, dt.datetime)) else node


def read_old_yaml(path: str) -> Any:
    """A file written in YAML by version 0.10.0 or earlier. Only migrate reads one, with PyYAML when it is there."""
    try:
        import yaml  # noqa: PLC0415  (PyYAML, optional: only to migrate a study written in YAML)
    except ImportError:
        raise kt.KbError(f"{path} was written in YAML by an earlier version, and reading it this once needs PyYAML, "
                      "which is not installed here. Nothing changed. Install it (python3 -m pip install "
                      "pyyaml==6.0.3; if pip refuses, in a virtual environment) and run migrate again, or migrate "
                      "the study on a computer that has it", code="reader_missing") from None
    try:
        with open(path, encoding="utf-8") as handle:
            return _plain(yaml.safe_load(handle))
    except FileNotFoundError:
        raise kt.KbError(f"file not found: {path}", code="file_missing") from None
    except yaml.YAMLError as exc:
        raise kt.KbError(f"{path} is not valid YAML: {exc}", code="yaml_invalid") from None


def read_kb_any(path: str) -> Json:
    """A KB to migrate: JSON, or YAML from version 0.10.0 or earlier (whose last schema was 2)."""
    if os.path.splitext(path)[1].lower() in (".yaml", ".yml"):
        return kt.ensure(read_old_yaml(path), path, newest=2)
    return kt.ensure(kt.load_json(path), path)


def _migrate_labels(kb_path: str, report: kt.Report) -> str | None:
    """Turn the study's labels.yaml into labels.json, as it is. Returns the backup of the YAML file, or None."""
    old = os.path.join(os.path.dirname(kb_path), kt.OLD_STUDY_LABELS)
    if not os.path.isfile(old):
        return None
    try:
        data = read_old_yaml(old)
    except kt.KbError as exc:
        report.warn(f"{old} could not be read and is left as it is: {exc}", code="labels_file")
        return None
    if not isinstance(data, dict) or not isinstance(data.get("labels"), dict):
        report.warn(f"{old} holds no labels and is left as it is", code="labels_file")
        return None
    kt.save_json({"about": kt.STUDY_LABELS_HEADER, "language": data.get("language"), "labels": data["labels"]},
              kt.labels_path(kb_path))
    made = kt.backup(kt.labels_path(kb_path), source=old)
    os.remove(old)
    return made


def _migrate_format(args: argparse.Namespace, old: str) -> int:
    """Turn a YAML study (0.10.0 or earlier) into JSON in place; the YAML files go to backups/."""
    new = os.path.join(os.path.dirname(old), kt.KB_FILE)
    if os.path.exists(new):
        raise kt.KbError(f"{os.path.dirname(old) or '.'}/ holds both {kt.OLD_KB_FILE} and {kt.KB_FILE}. Nothing "
                         f"changed. Keep the study you work on and move the other file out of {kt.KB_FOLDER}/",
                         code="kb_exists")
    kb = read_kb_any(old)
    version = kt.check_version(kb, old)
    args.run.note(schema_from=version)
    notes = _upgrade(kb, version)
    summary = f"migrated from schema version {version} to {kt.SCHEMA_VERSION}: " + "; ".join(notes)
    kb["changelog"].append(kt.changelog_entry(args.run, "migrate", summary=summary))
    problems = kt.structure_problems(kb)
    if problems:
        raise kt.KbError("the migrated KB would break the KB structure; nothing written. Fix these first:\n  - "
                      + "\n  - ".join(problems), code="structure")
    made = kt.backup(new, source=old)
    kt.save_kb(kb, new)
    os.remove(old)
    args.run.moved(new)
    report = kt.Report()
    labels = _migrate_labels(new, report)
    args.run.add_report(report)
    args.run.note(written=True, backup=args.run.relative(made), labels={"migrated": int(bool(labels))})
    lines = [f"WARN {warning}" for warning in report.warnings]
    lines.append(f"{summary}. The KB is now {new}" + (f" and the labels {kt.labels_path(new)}" if labels else "")
                 + f"; the YAML files are in {kt.KB_FOLDER}/backups/")
    print("\n".join(lines))
    return 0


def _migrate_move(args: argparse.Namespace) -> int:
    """Move a study made by an earlier version (the KB in <study>/KB/, transcripts in <study>/Interviews/) into
    .pw-kb/pw-kb.json."""
    new = args.to or kt.KB_HOME
    if not kt.at_home(new):
        raise kt.KbError(f"--to must be {kt.KB_HOME} at the root of the workspace, not {new}", code="kb_location")
    if os.path.exists(new) or kt.old_yaml(new):
        raise kt.KbError(f"{os.path.dirname(new)}/ already holds a study, and a workspace holds one study. Nothing "
                         "moved. Open the old study in a workspace of its own, or move the other one out first",
                         code="kb_exists")
    kb = read_kb_any(args.kb)
    version = kt.check_version(kb, args.kb)
    args.run.note(schema_from=version, moved=True)
    report = kt.Report()
    sources = _old_transcripts(kb, args.kb, args.transcripts or [], report)
    for clash in _clashes(os.path.dirname(os.path.abspath(args.kb)), os.path.dirname(os.path.abspath(new)), sources):
        report.error(f"{kt.KB_FOLDER}/{clash} exists already and would be overwritten; move it out of the way first",
                     code="move_conflict")
    args.run.add_report(report)
    lines = [f"WARN {warning}" for warning in report.warnings]
    if report.errors:
        print("\n".join(lines + [f"{len(report.errors)} problem(s); nothing moved:"]
                        + [f"  - {e}" for e in report.errors]))
        return 1
    notes = _upgrade(kb, version)
    summary = f"moved the study into {kt.KB_FOLDER}/ and copied its {len(sources)} transcript(s) there"
    if notes:
        summary += f"; migrated from schema version {version} to {kt.SCHEMA_VERSION}: " + "; ".join(notes)
    kb["changelog"].append(kt.changelog_entry(args.run, "migrate", summary=summary))
    problems = kt.structure_problems(kb)
    if problems:
        raise kt.KbError("the migrated KB would break the KB structure; nothing moved. Fix these first:\n  - "
                      + "\n  - ".join(problems), code="structure")
    old_folder = os.path.dirname(os.path.abspath(args.kb))
    made = _move_study(args.kb, new, kb, sources)
    args.run.moved(new)
    args.run.note(written=True, backup=args.run.relative(made), transcripts_copied=len(sources))
    left = sorted(n for n in os.listdir(old_folder) if not n.startswith(".")) if os.path.isdir(old_folder) else []
    lines.append(f"{summary}. The KB is now {new}; the old file is in {kt.KB_FOLDER}/backups/")
    if left:
        lines.append(f"left in {old_folder}: {', '.join(left)}")
    note = kt.git_note(new)
    args.run.note(git=bool(note))
    print("\n".join(lines + ([note] if note else [])))
    return 0


def cmd_migrate(args: argparse.Namespace, tool: Any) -> int:
    """`tool` is the kb_tool module that loaded this file."""
    global kt  # noqa: PLW0603 - kb_tool hands itself over once, here
    kt = tool
    old = kt.old_yaml(args.kb)
    if old:
        return _migrate_format(args, old)
    done = os.path.join(os.path.dirname(args.kb), kt.KB_FILE)  # a second run, after the YAML became JSON
    if os.path.basename(args.kb) == kt.OLD_KB_FILE and kt.at_home(done) and os.path.isfile(done):
        args.kb = done
    if not kt.at_home(args.kb):
        return _migrate_move(args)
    kb = kt.ensure(kt.load_json(args.kb), args.kb)
    version = kt.check_version(kb, args.kb)
    args.run.note(schema_from=version)
    if version == kt.SCHEMA_VERSION:
        print(f"nothing to do: {args.kb} already uses schema version {kt.SCHEMA_VERSION}")
        return 0
    start, notes = version, _upgrade(kb, version)
    summary = f"migrated from schema version {start} to {kt.SCHEMA_VERSION}: " + "; ".join(notes)
    kb["changelog"].append(kt.changelog_entry(args.run, "migrate", summary=summary))
    problems = kt.structure_problems(kb)
    if problems:
        raise kt.KbError("the migrated KB would break the KB structure; nothing written. Fix these first:\n  - "
                      + "\n  - ".join(problems), code="structure")
    made = kt.backup(args.kb)
    kt.save_kb(kb, args.kb)
    args.run.note(written=True, backup=args.run.relative(made))
    print(f"migrated {args.kb} {summary[len('migrated '):]}")
    return 0
