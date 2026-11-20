"""`kb_tool survey`: make one core job's survey and keep it in the KB.

It lives apart from kb_tool.py so the main script stays under the directory's 256 KiB file limit. kb_tool loads it
for `survey` and hands it the kb_tool module (`kt`), whose helpers it uses.

The assistant writes every word a respondent reads. `--skeleton JOB` prints the file to fill in: each live need of
the core job with its plain wording, and each people trait of the plan with its values. `--write FILE` checks that
file and stores it as the job's survey. A change of words makes a new version. A change to `left_out`, or a write
that only clears the out-of-date flag, keeps the version. When nothing differs, nothing is written.

The estimate: `--evidence JOB` prints, for each person of the core job and each need of its survey, what that person
said on the need and what they said on its step or about a tool at that step. `--estimate FILE` checks and stores how
each person would rate each need, each rating resting on one of those quotes; it prints counts and IDs only.

`results()` computes the figures of an estimate and `status()` tells where a job's survey stands; kb_review shows both
in `context` and review.md, and the map draws them."""
from __future__ import annotations

import argparse
import copy
import math
import random
import re
from fractions import Fraction
from typing import Any

Json = dict[str, Any]
kt: Any = None  # the kb_tool module, set by kb_tool's _sibling() when it loads this file

MAX_NEEDS = 30  # a trial found 31 needs tiring
SECONDS_A_NEED = 16  # measured on a phone, one need on a screen
TEXT_CHARS = 160  # a question, a choice or a need as the respondent reads it
FRAME_CHARS = 120
EXPLAIN_WORDS = 25
FILE_KEYS = ("job", "frame", "gate", "profile", "needs", "left_out")
GATE_KEYS = ("text", "yes", "no", "explain")
NEED_KEYS = ("outcome", "text", "explain")
SKELETON_KEYS = {"step", "plain", "name"}  # help in the skeleton's file: accepted on --write and dropped
CELL_KEYS = ("interview", "outcome", "importance", "satisfaction", "basis", "quote", "why")
BASES = ("said", "context")
WHY_WORDS = 20
_DAY = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")  # how `created` and `made` are written
USAGE = ("Use: kb_tool survey <kb.json> --skeleton JOB, --evidence JOB, or --write FILE or --estimate FILE "
         "[--dry-run] [--json] [--no-publish] [--open]")


class _Parser(argparse.ArgumentParser):
    """The modes of `survey`. A mistake is a KbError, logged as survey_file, not argparse's exit."""

    def error(self, message: str) -> Any:  # argparse's own name
        raise kt.KbError(f"survey: {message}. {USAGE}", code="survey_file")


def _parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="kb_tool survey", add_help=False)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--skeleton", metavar="JOB")
    mode.add_argument("--write", metavar="FILE")
    mode.add_argument("--evidence", metavar="JOB")
    mode.add_argument("--estimate", metavar="FILE")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-publish", action="store_true")
    parser.add_argument("--open", action="store_true")
    return parser


def minutes(needs: int) -> int:
    """The time the page and the invitation state: 16 seconds a need, rounded up to a whole minute."""
    return math.ceil(needs * SECONDS_A_NEED / 60)


# ---------- what the study holds ----------
def _typed_need(need: Any) -> bool:
    return (isinstance(need, dict) and isinstance(need.get("outcome"), str) and isinstance(need.get("text"), str)
            and isinstance(need.get("explain", ""), str))


def _typed_cell(cell: Any) -> bool:
    return (isinstance(cell, dict) and isinstance(cell.get("interview"), str) and isinstance(cell.get("outcome"), str)
            and _rating(cell.get("importance")) and _rating(cell.get("satisfaction")) and cell.get("basis") in BASES)


def typed(entry: Any, key: str) -> bool:
    """True for an entry this version wrote: a string `job`, an integer `version`, and `needs` (a survey) or `cells`
    (an estimate), a list whose every item has the shape the write checks. Anything else, even half of it, is a survey
    made by hand before 0.18: the schema still accepts it, nothing reads it, and a write moves it to `legacy`."""
    if not (isinstance(entry, dict) and isinstance(entry.get("job"), str) and type(entry.get("version")) is int):
        return False
    items, check = (entry.get("cells"), _typed_cell) if key == "simulation" else (entry.get("needs"), _typed_need)
    return isinstance(items, list) and all(check(item) for item in items)


def _entry_of(kb: Json, key: str, job: str) -> Json | None:
    """One core job's entry in the layer `key` (`survey` or `simulation`), or None."""
    layer = kb.get(key)
    items = layer.get("jobs") if isinstance(layer, dict) else None
    found = [e for e in items if typed(e, key) and str(e.get("job")) == job] if isinstance(items, list) else []
    return found[0] if found else None


def survey_of(kb: Json, job: str) -> Json | None:
    """The stored survey of one core job, or None."""
    return _entry_of(kb, "survey", job)


def _steps(kb: Json, job: str) -> list[str]:
    """The core job's step IDs, in the job's order."""
    return [kt.step_key(s) for s in sorted((s for s in kb["job_map"]["steps"] if s.get("job") == job),
                                           key=lambda s: int(s["n"]))]


def _live_needs(kb: Json, job: str) -> list[Json]:
    """The core job's live outcomes, by step, in the KB's order inside a step."""
    steps = _steps(kb, job)
    live = [o for o in kb["desired_outcomes"]["outcomes"]
            if not o.get("merged_into") and str(o.get("step")) in steps]
    return sorted(live, key=lambda o: steps.index(str(o["step"])))


def _traits(kb: Json, job: str) -> list[Json]:
    """The people traits of the plan for the next round (overview `next.learn.traits`), each with its values."""
    traits = kt.learn_of(kb, job).get("traits")
    return [t for t in traits if isinstance(t, dict) and t.get("id") and isinstance(t.get("values"), list)
            ] if isinstance(traits, list) else []


def _check_job(kb: Json, job: str) -> str:
    if job not in kt.jobs_by_id(kb):
        raise kt.KbError(f"core job {job} is not in the KB; the core jobs are "
                         f"{', '.join(kt.jobs_by_id(kb)) or 'none yet'}", code="survey_file")
    return job


def skeleton(kb: Json, job: str) -> Json:
    """The file to fill in: every word empty, each need with its step and the map's plain wording to start from."""
    plain = kt._review().plain_outcome
    needs = [{"outcome": str(o["id"]), "step": str(o["step"]), "plain": plain(str(o["statement"])), "text": "",
              "explain": ""} for o in _live_needs(kb, job)]
    profile = [{"trait": str(t["id"]), "name": str(t.get("name", "")), "text": "", "other": "", "explain": "",
                "choices": [{"value": str(v.get("id")), "label": str(v.get("label", ""))}
                            for v in t["values"] if isinstance(v, dict)]} for t in _traits(kb, job)]
    return {"job": job, "frame": "", "gate": dict.fromkeys(GATE_KEYS, ""), "profile": profile, "needs": needs,
            "left_out": []}


# ---------- checks ----------
def _text(value: Any, label: str, report: Any, limit: int = TEXT_CHARS, empty: str = "survey_text") -> str:
    """One line a respondent reads: plain text, spaces tidied, at most `limit` characters."""
    if not isinstance(value, str) or not value.strip():
        report.error(f"{label}: write it; it is empty or not text", code=empty)
        return ""
    text = " ".join(value.split())
    if len(text) > limit:
        report.error(f"{label}: {len(text)} characters; at most {limit}", code="survey_text")
    if "<" in text or ">" in text:
        report.error(f"{label}: write plain text, with no < or >", code="survey_text")
    return text


def _explain(value: Any, label: str, report: Any) -> str:
    """The sentence behind "Explain": at most 25 words."""
    if not isinstance(value, str) or not value.strip():
        report.error(f"{label} explain: write one short sentence with an example", code="survey_explain")
        return ""
    text = " ".join(value.split())
    if len(text.split()) > EXPLAIN_WORDS:
        report.error(f"{label} explain: {len(text.split())} words; at most {EXPLAIN_WORDS}", code="survey_explain")
    if "<" in text or ">" in text:
        report.error(f"{label} explain: write plain text, with no < or >", code="survey_explain")
    return text


def _gate(value: Any, report: Any) -> Json:
    """The check question: "No" ends the survey there."""
    if not isinstance(value, dict) or set(value) != set(GATE_KEYS):
        wrong = sorted(set(GATE_KEYS) ^ set(value)) if isinstance(value, dict) else []
        report.error(f"gate: give {', '.join(GATE_KEYS)} and nothing else"
                     + (f" (check {', '.join(wrong)})" if wrong else ""), code="survey_gate")
        return {}
    gate = {key: _text(value[key], f"gate {key}", report, empty="survey_gate") for key in GATE_KEYS[:3]}
    return {**gate, "explain": _explain(value["explain"], "gate", report)}


def _choices(value: Any, trait: Json, label: str, report: Any) -> list[Json]:
    values = [str(v.get("id")) for v in trait["values"] if isinstance(v, dict)]
    if not isinstance(value, list) or not all(isinstance(c, dict) and set(c) == {"value", "label"} for c in value):
        report.error(f"{label}: choices must be a list of {{value, label}}", code="survey_profile")
        return []
    given = [str(c["value"]) for c in value]
    for ref in given:
        if ref not in values:
            report.error(f"{label}: {ref} is not a value of trait {trait['id']} ({', '.join(values)})",
                         code="survey_profile")
    twice = sorted({ref for ref in given if given.count(ref) > 1})
    if twice:
        report.error(f"{label}: {', '.join(twice)} has more than one choice", code="survey_profile")
    missing = [ref for ref in values if ref not in given]
    if missing:
        report.error(f"{label}: {', '.join(missing)} has no choice; give every value of the trait one",
                     code="survey_profile")
    order = {ref: i for i, ref in enumerate(values)}
    choices = [{"value": str(c["value"]), "label": _text(c["label"], f"{label} {c['value']}", report)} for c in value]
    return sorted(choices, key=lambda c: order.get(c["value"], len(order)))


def _profile(kb: Json, job: str, value: Any, report: Any) -> list[Json]:
    """One question for each people trait of the plan, its values as choices, and "Something else" (`other`)."""
    traits = {str(t["id"]): t for t in _traits(kb, job)}
    if not isinstance(value, list) or not all(isinstance(p, dict) for p in value):
        report.error("profile: give a list, one question for each people trait of the plan", code="survey_profile")
        return []
    given: dict[str, Json] = {}
    for item in value:
        ref, label = str(item.get("trait")), f"profile {item.get('trait')}"
        unknown = sorted(set(item) - {"trait", "text", "other", "explain", "choices"} - SKELETON_KEYS)
        if unknown:
            report.error(f"{label}: unknown key {', '.join(unknown)}", code="survey_profile")
        if ref not in traits:
            report.error(f"{label}: not a people trait of the plan ({', '.join(traits) or 'it has none'})",
                         code="survey_profile")
        elif ref in given:
            report.error(f"{label}: asked twice", code="survey_profile")
        else:
            given[ref] = {"trait": ref, "text": _text(item.get("text"), label, report),
                          "other": _text(item.get("other"), f"{label} other", report),
                          "explain": _explain(item.get("explain"), label, report),
                          "choices": _choices(item.get("choices"), traits[ref], label, report)}
    missing = [ref for ref in traits if ref not in given]
    if missing:
        report.error(f"profile: no question for trait {', '.join(missing)}; ask every people trait of the plan",
                     code="survey_profile")
    return [given[ref] for ref in traits if ref in given]


def _claim(kb: Json, job: str, ref: str, seen: list[str], *, label: str, report: Any) -> bool:
    """True when `ref` is a live need of the core job not named yet; it is then added to `seen`."""
    outcome = kt.outcomes_by_id(kb).get(ref, {})
    if ref in seen:
        report.error(f"{label}: need {ref} appears more than once", code="survey_needs")
    elif outcome.get("merged_into"):
        report.error(f"{label}: need {ref} was merged into {outcome['merged_into']}; use that one", code="survey_needs")
    elif ref in [str(o["id"]) for o in _live_needs(kb, job)]:
        seen.append(ref)
        return True
    else:
        report.error(f"{label}: {ref} is not a need of core job {job}", code="survey_needs")
    return False


def _needs(kb: Json, job: str, value: list[Any], left: list[Any], report: Any) -> tuple[list[Json], list[Json]]:
    """The needs asked and the needs left out: together, every live need of the core job once."""
    seen: list[str] = []
    needs: list[Json] = []
    for item in value:
        if not isinstance(item, dict) or set(item) - set(NEED_KEYS) - SKELETON_KEYS:
            report.error(f"needs: each need holds {', '.join(NEED_KEYS)} only", code="survey_file")
        elif _claim(kb, job, str(item.get("outcome")), seen, label="needs", report=report):
            ref = str(item["outcome"])
            needs.append({"outcome": ref, "text": _text(item.get("text"), f"need {ref}", report),
                          "explain": _explain(item.get("explain"), f"need {ref}", report)})
    left_out: list[Json] = []
    for item in left:
        if not isinstance(item, dict) or set(item) != {"outcome", "why"}:
            report.error("left_out: each entry holds outcome and why only", code="survey_file")
        elif _claim(kb, job, str(item["outcome"]), seen, label="left_out", report=report):
            left_out.append({"outcome": str(item["outcome"]),
                             "why": _text(item["why"], f"left_out {item['outcome']} why", report)})
    order = [str(o["id"]) for o in _live_needs(kb, job)]
    missing = [ref for ref in order if ref not in seen]
    if missing:
        report.error(f"need {', '.join(missing)} is in neither needs nor left_out: ask it, or leave it out with a "
                     "reason", code="survey_needs")
    if not needs:
        report.error("needs: the survey asks no need", code="survey_needs")
    if len(needs) > MAX_NEEDS:
        report.error(f"{len(needs)} needs; a survey asks at most {MAX_NEEDS}. Move {len(needs) - MAX_NEEDS} to "
                     "left_out: the needs the fewest people named, spread over the themes", code="survey_cap")
    return (sorted(needs, key=lambda n: order.index(n["outcome"])),
            sorted(left_out, key=lambda n: order.index(n["outcome"])))


def build_definition(kb: Json, data: Json, report: Any) -> Json | None:
    """The checked survey of one core job, without its version and date; None with the problems in `report`."""
    if not isinstance(data, dict):
        report.error(f"the file must hold one object with {', '.join(FILE_KEYS)}", code="survey_file")
        return None
    unknown = sorted(str(key) for key in set(data) - set(FILE_KEYS))
    missing = [key for key in FILE_KEYS[:5] if key not in data]
    if unknown or missing:
        report.error(f"the file holds {', '.join(FILE_KEYS)}: "
                     + "; ".join(([f"unknown key {', '.join(unknown)}"] if unknown else [])
                                 + ([f"missing {', '.join(missing)}"] if missing else [])), code="survey_file")
        return None
    job = str(data["job"])
    if job not in kt.jobs_by_id(kb):
        report.error(f"core job {job} is not in the KB", code="survey_file")
        return None
    if not isinstance(data["needs"], list) or not isinstance(data.get("left_out", []), list):
        report.error("needs and left_out must be lists", code="survey_file")
        return None
    frame = _text(data["frame"], "frame", report, limit=FRAME_CHARS)
    gate = _gate(data["gate"], report)
    profile = _profile(kb, job, data["profile"], report)
    needs, left_out = _needs(kb, job, data["needs"], data.get("left_out", []), report)
    if report.errors:
        return None
    return {"job": job, "frame": frame, "gate": gate, "profile": profile, "needs": needs, "left_out": left_out}


# ---------- storing ----------
def _words(entry: Json) -> Any:
    """What a respondent reads. A change here makes a new version; the order of the needs does not count."""
    needs = sorted((str(n.get("outcome")), n.get("text"), n.get("explain")) for n in entry.get("needs") or []
                   if isinstance(n, dict))
    return [entry.get("frame"), entry.get("gate"), entry.get("profile"), needs]


def _ordered(kb: Json, job: str, version: int, needs: list[Json]) -> list[Json]:
    """By step, in the job's order; inside a step, shuffled once for this version, so every respondent sees the
    same order."""
    shuffle = random.Random(f"{job}-{version}")
    out: list[Json] = []
    for step in _steps(kb, job):
        group = [n for n in needs if kt.step_of(n["outcome"]) == step]
        shuffle.shuffle(group)
        out += group
    return out


def check_entry(entry: Json, name: str, what: str) -> None:
    """Refuse an entry that breaks its definition in kb-schema.json: `survey_job` or `simulation_job`. The schema
    leaves `survey.jobs` and `simulation.jobs` open, so that a study made by hand before 0.18 still loads; what this
    command writes is held to the definition here."""
    schema = {"$ref": f"#/$defs/{name}", "$defs": kt.load_schema("kb-schema.json")["$defs"]}
    problems = kt.schema_errors(entry, schema, name)
    if problems:
        raise kt.KbError(f"{what} would break the KB structure; nothing written:\n  - " + "\n  - ".join(problems),
                         code="structure")


def store_survey(kb: Json, entry: Json, key: str = "survey") -> int:
    """Replace the core job's entry in the layer `key` (the survey, or the estimate in `simulation`) and clear the
    stale flag; the other jobs' entries stay as they are. What a survey made by hand before 0.18 left there (entries
    of another shape, `jobs` that is not a list, other keys) moves, unchanged, to the list `legacy`. Returns how many
    items moved there now."""
    layer = kb.get(key) if isinstance(kb.get(key), dict) else {}
    items = layer.get("jobs")
    aside = [e for e in items if not typed(e, key)] if isinstance(items, list) else ([items] if "jobs" in layer else [])
    rest = {k: v for k, v in layer.items() if k not in ("stale", "stale_reasons", "jobs", "legacy")}
    aside += [rest] if rest else []
    old = layer.get("legacy", [])
    legacy = (old if isinstance(old, list) else [old]) + aside
    kept = [e for e in items if typed(e, key) and str(e.get("job")) != entry["job"]] if isinstance(items, list) else []
    merged = sorted(kept + [entry], key=lambda e: kt.job_index(str(e.get("job"))))
    kb[key] = {"stale": False, "jobs": merged, **({"legacy": legacy} if legacy else {})}
    return len(aside)


def _aside_line(moved: int, what: str) -> list[str]:
    return [f"an older hand-made {what} was kept aside, unchanged, under `legacy`; this version does not read it"
            ] if moved else []


def _write(args: argparse.Namespace, path: str) -> int:
    """Check the file and store it. The dry run and the real run share every step up to the write."""
    kb = kt.load_kb(args.kb)
    report = kt.Report()
    data = kt.load_json(path)
    args.run.note(dry_run=bool(args.dry_run))
    if isinstance(data, dict) and isinstance(data.get("job"), str):
        args.run.note(job=data["job"])
    candidate = copy.deepcopy(kb)
    built = build_definition(candidate, data, report)
    result: Json = {"ok": False, "dry_run": bool(args.dry_run), "job": built["job"] if built else None,
                    "written": False, "run_id": args.run.id}
    if built is None:
        return kt.finish_write(args, report, result, [])
    job, needs = built["job"], built["needs"]
    old = survey_of(kb, job)
    old_version = old.get("version") if old and isinstance(old.get("version"), int) else 0
    same = bool(old) and _words(old) == _words(built)  # the version covers only what a respondent sees
    version = old_version if same else old_version + 1
    stale = bool(kb["survey"].get("stale")) if same else False  # a write clears it, even with the same words
    unchanged = same and not stale and old.get("left_out") == built["left_out"]
    steps = len({kt.step_of(n["outcome"]) for n in needs})
    lines = [f"survey: job {job}, version {version}, {kt.plural(len(needs), 'need')} in {kt.plural(steps, 'step')}, "
             f"about {kt.plural(minutes(len(needs)), 'minute')}"]
    if built["left_out"]:
        lines.append(f"left out: {len(built['left_out'])} ({', '.join(n['outcome'] for n in built['left_out'])})")
    args.run.note(counts={"survey_needs": len(needs)})
    result.update({"ok": True, "version": version, "needs": len(needs), "steps": steps,
                   "minutes": minutes(len(needs)), "left_out": [n["outcome"] for n in built["left_out"]]})
    if unchanged:
        args.run.note(nothing_new=True)
        result["nothing_changed"] = True
        lines.append(f"nothing changed: the survey of core job {job} is already version {version}; nothing written")
        return kt.finish_write(args, report, result, lines)
    created = old["created"] if same and _DAY.match(str(old.get("created") or "")) else kt.today()
    entry = {"job": job, "version": version, "created": created, "frame": built["frame"], "gate": built["gate"],
             "profile": built["profile"], "needs": _ordered(candidate, job, version, needs),
             "left_out": built["left_out"]}
    check_entry(entry, "survey_job", "this survey")
    lines += _aside_line(store_survey(candidate, entry), "survey")
    others = sorted({str(e.get("job")) for e in candidate["survey"]["jobs"] if isinstance(e, dict)} - {job},
                    key=kt.job_index)
    result["other_jobs"] = others
    if others:  # the layer has one out-of-date flag, and this write cleared it for them too
        lines.append(f"surveys of core job {', '.join(others)} were not touched; update them too if they are out "
                     "of date")
    summary = f"survey of core job {job}, version {version}"
    return kt.write_layer(args, report, result, lines, candidate, layer="survey", summary=summary, what="this survey",
                          checked="every need and every question passed the checks")


# ---------- the estimate ----------
# How each person of the core job would rate each need of its survey, each rating resting on one quote of theirs.
def estimate_of(kb: Json, job: str) -> Json | None:
    """The stored estimate of one core job, or None."""
    return _entry_of(kb, "simulation", job)


def _quote_key(quote: Any) -> str:
    """kb_tool's quote cleaning (`norm`, as `evidence_key` uses it), and a missing final full stop is no difference."""
    return kt.norm(str(quote)).rstrip(".").rstrip()


def _pools(kb: Json, entry: Json) -> dict[tuple[str, str], Json]:
    """For each (person, need of the survey): `said`, their quotes on the need, and `context`, their quotes on the
    need's step and on the live solutions used at that step. Each maps a cleaned quote to the KB's own text."""
    outcomes, steps = kt.outcomes_by_id(kb), kt.steps_by_id(kb)
    pools: dict[tuple[str, str], Json] = {}
    for need in entry.get("needs") or []:
        ref = str(need.get("outcome"))
        outcome = outcomes.get(ref, {})
        step = str(outcome.get("step"))
        around = list(steps.get(step, {}).get("evidence") or [])
        around += [e for s in kt.live_solutions(kb) for use in kt.uses_of(s) if str(use.get("step")) == step
                   for e in use.get("evidence") or []]
        for kind, items in (("said", outcome.get("evidence") or []), ("context", around)):
            for item in items:
                if isinstance(item, dict) and isinstance(item.get("quote"), str) and item["quote"].strip():
                    pool = pools.setdefault((str(item.get("interview")), ref), {"said": {}, "context": {}})
                    pool[kind].setdefault(_quote_key(item["quote"]), item["quote"])
    return pools


def _needs_survey(kb: Json, job: str) -> Json:
    entry = survey_of(kb, job)
    if entry is None:
        raise kt.KbError(f"core job {job} has no survey yet: write it first with `survey --write`; the estimate "
                         "rates the needs the survey asks", code="estimate_no_survey")
    return entry


def evidence(kb: Json, job: str) -> Json:
    """What the assistant reads to estimate: each person of the core job, and for each need of the survey their
    quotes on it (`said`) and around it (`context`). A need with neither is left out for that person."""
    entry = _needs_survey(kb, job)
    pools = _pools(kb, entry)
    names = {str(r.get("id")): str(r.get("name") or "") for r in kb["interviews"]}
    people = []
    for person in kt.job_people(kb, job):
        needs = []
        for need in entry["needs"]:
            pool = pools.get((person, str(need["outcome"])))
            if pool:
                needs.append({"outcome": str(need["outcome"]), "text": need.get("text", ""),
                              "said": list(pool["said"].values()), "context": list(pool["context"].values())})
        people.append({"interview": person, "name": names.get(person, ""), "needs": needs})
    return {"job": job, "people": people}


def _rating(value: Any) -> bool:
    return type(value) is int and 1 <= value <= 5  # not True or False, not 2.5


def _cell_shape(item: Json, label: str, ctx: Json, report: Any) -> None:
    """Everything of a cell but its quote: keys, person, need, ratings, basis, why, and no pair twice."""
    unknown = sorted(str(k) for k in set(item) - set(CELL_KEYS))
    if unknown:
        report.error(f"{label}: unknown key {', '.join(unknown)}", code="estimate_cell")
    person, ref = str(item.get("interview")), str(item.get("outcome"))
    if person not in ctx["people"]:
        report.error(f"{label}: {person} is not a person of core job {ctx['job']}", code="estimate_cell")
    if ref not in ctx["needs"]:
        report.error(f"{label}: {ref} is not a need of the survey of core job {ctx['job']}", code="estimate_cell")
    for key in ("importance", "satisfaction"):
        if not _rating(item.get(key)):
            report.error(f"{label}: {key} must be a whole number from 1 to 5", code="estimate_cell")
    if item.get("basis") not in BASES:
        report.error(f"{label}: basis must be said or context", code="estimate_cell")
    why = item.get("why")
    if not isinstance(why, str) or not why.strip():
        report.error(f"{label}: write the why, one short sentence", code="estimate_why")
    elif len(why.split()) > WHY_WORDS:
        report.error(f"{label}: the why has {len(why.split())} words; at most {WHY_WORDS}", code="estimate_why")
    if (person, ref) in ctx["seen"]:
        report.error(f"{label}: person {person} and need {ref} are rated twice", code="estimate_cell")
    ctx["seen"].add((person, ref))


def _cell_quote(item: Json, label: str, ctx: Json, report: Any) -> str | None:
    """The KB's own text of the cell's quote, when it is the person's and in the pool its basis names."""
    person, ref, quote = str(item["interview"]), str(item["outcome"]), item.get("quote")
    pool = ctx["pools"].get((person, ref), {"said": {}, "context": {}})
    key = _quote_key(quote) if isinstance(quote, str) else ""
    found = (pool["said"].get(key) or pool["context"].get(key)) if key else None
    if not found:
        report.error(f"{label}: the quote is not one of {person}'s on need {ref}, on its step, or on a tool used at "
                     "its step; copy it from `survey --evidence`", code="estimate_basis")
    elif (key in pool["said"]) != (item["basis"] == "said"):
        right = "said: the quote is on the need" if key in pool["said"] else \
            "context: the quote is on the step or a tool, not on the need"
        report.error(f"{label}: the basis is {right}", code="estimate_basis")
        found = None
    return found


def _cell(item: Any, label: str, ctx: Json, report: Any) -> Json | None:
    """One checked cell, its quote replaced by the KB's own text; None with the problems in `report`. The messages
    name the cell by person and need only: never its quote or its why."""
    if not isinstance(item, dict):
        report.error(f"{label}: each cell is an object with {', '.join(CELL_KEYS)}", code="estimate_cell")
        return None
    errors = len(report.errors)
    _cell_shape(item, label, ctx, report)
    known = str(item.get("interview")) in ctx["people"] and str(item.get("outcome")) in ctx["needs"]
    found = _cell_quote(item, label, ctx, report) if known and item.get("basis") in BASES else None
    if found is None or len(report.errors) > errors:
        return None
    return {"interview": str(item["interview"]), "outcome": str(item["outcome"]), "importance": item["importance"],
            "satisfaction": item["satisfaction"], "basis": item["basis"], "quote": found,
            "why": " ".join(item["why"].split())}


def build_estimate(kb: Json, data: Json, report: Any) -> Json | None:
    """The checked estimate of one core job, `{job, cells}` without its version and date; None with the problems
    in `report`."""
    if not isinstance(data, dict) or set(data) != {"job", "cells"}:
        report.error("the file must hold one object with job and cells, and nothing else", code="estimate_file")
        return None
    job = str(data["job"])
    if job not in kt.jobs_by_id(kb):
        report.error(f"core job {job} is not in the KB", code="estimate_file")
        return None
    if not isinstance(data["cells"], list) or not data["cells"]:
        report.error("cells must be a list with at least one cell", code="estimate_file")
        return None
    entry = survey_of(kb, job)
    if entry is None:
        report.error(f"core job {job} has no survey yet: write it first with `survey --write`",
                     code="estimate_no_survey")
        return None
    people, needs = kt.job_people(kb, job), [str(n["outcome"]) for n in entry["needs"]]
    ctx = {"job": job, "people": people, "needs": needs, "pools": _pools(kb, entry), "seen": set()}
    cells = [_cell(item, f"cell {i} ({item.get('interview')}, {item.get('outcome')})" if isinstance(item, dict)
                   else f"cell {i}", ctx, report) for i, item in enumerate(data["cells"], 1)]
    if report.errors:
        return None
    order = {(p, n): (i, j) for i, p in enumerate(people) for j, n in enumerate(needs)}
    return {"job": job, "cells": sorted((c for c in cells if c), key=lambda c: order[(c["interview"], c["outcome"])])}


def _share(part: int, whole: int) -> str:
    return f"{percent(part, whole)}%"


def _estimate(args: argparse.Namespace, path: str) -> int:
    """Check the estimate and store it in `simulation`. The dry run and the real run share every step up to the
    write. Every line holds counts, IDs and names only."""
    kb = kt.load_kb(args.kb)
    report = kt.Report()
    data = kt.load_json(path)
    args.run.note(dry_run=bool(args.dry_run))
    if isinstance(data, dict) and isinstance(data.get("job"), str):
        args.run.note(job=data["job"])
    candidate = copy.deepcopy(kb)
    built = build_estimate(candidate, data, report)
    result: Json = {"ok": False, "dry_run": bool(args.dry_run), "job": built["job"] if built else None,
                    "written": False, "run_id": args.run.id}
    if built is None:
        return kt.finish_write(args, report, result, [])
    job, cells = built["job"], built["cells"]
    version = survey_of(candidate, job)["version"]
    entry = {"job": job, "version": version, "made": kt.today(), "cells": cells}
    check_entry(entry, "simulation_job", "this estimate")
    moved = store_survey(candidate, entry, key="simulation")
    figures = results(candidate, job)
    # the counts results() gives, so the line and the Survey view agree: a need no longer live is not counted
    cover, possible = figures["coverage"], figures["possible"]
    lines = [f"estimate: {cover['cells']} of {possible} ratings have evidence ({_share(cover['cells'], possible)}): "
             f"{cover['said']} from the person's words ({_share(cover['said'], possible)}), {cover['context']} from "
             f"context ({_share(cover['context'], possible)})"]
    args.run.note(counts={"estimate_cells": len(cells)})
    result.update({"ok": True, "version": version, "cells": cover["cells"], "said": cover["said"],
                   "context": cover["context"], "possible": possible})
    lines += _figure_lines(figures) + _aside_line(moved, "estimate")
    result.update({key: figures.get(key) for key in ("unmet", "single", "weakest")})
    others = sorted({str(e.get("job")) for e in candidate["simulation"]["jobs"] if isinstance(e, dict)} - {job},
                    key=kt.job_index)
    result["other_jobs"] = others
    if others:  # the layer has one out-of-date flag, and this write cleared it for them too
        lines.append(f"estimates of core job {', '.join(others)} were not touched; update them too if they are out "
                     "of date")
    summary = f"estimate of core job {job}, survey version {version}"
    return kt.write_layer(args, report, result, lines, candidate, layer="simulation", summary=summary,
                          what="this estimate", checked="every cell passed the checks")


def _figure_lines(figures: Json) -> list[str]:
    """The estimate's lines after its coverage: IDs, counts and names only, never a quote or a why."""
    unmet = figures.get("unmet") or []
    weakest = figures.get("weakest") or []
    return [f"most unmet: {', '.join(unmet[:3])}" if unmet else
            f"most unmet: none yet (a need is ranked when {MIN_PEOPLE} or more people have a rating on it)",
            f"one person only: {kt.plural(figures.get('single', 0), 'need')}",
            "weakest: " + (", ".join(f"{p['interview']} {p['name']} ({p['share']}%)" for p in weakest) if weakest
                           else "none: every person has ratings for at least half the needs")]


# ---------- figures and state ----------
# Computed when read, never stored. Up to SHARE_ABOVE people with ratings, each rating's average goes on a 0-to-10
# scale, (average - 1) x 2.5; above it (the owner's call, 2026-11-19), the share of people who rate 4 or 5, x 10,
# as in classic ODI. One method for every need of a set, so the needs stay comparable. A need's figure is its
# importance plus the gap between importance and satisfaction when that gap is positive. Exact fractions all the
# way, rounded to 1 decimal only at the end.
MIN_PEOPLE = 2  # a need is ranked only with ratings from at least this many people
SHARE_ABOVE = 30  # more people than this with ratings: top-two-box shares instead of averages
UNMET_ABOVE = 10
UNMET_MAX = 10
WEAKEST_MAX = 2
HIGH = 4  # a rating of 4 or 5 "matters a lot" or "is satisfied"


def percent(part: int, whole: int) -> int:
    """A whole percent, half up; 0 of nothing is 0."""
    return math.floor(Fraction(100 * part, whole) + Fraction(1, 2)) if whole else 0


def _tenth(value: Fraction) -> float:
    """Rounded to 1 decimal, half up, from the exact value."""
    return math.floor(value * 10 + Fraction(1, 2)) / 10


def _scale(ratings: list[int], method: str) -> Fraction:
    if method == "share":
        return Fraction(10 * sum(1 for r in ratings if r >= HIGH), len(ratings))
    return (Fraction(sum(ratings), len(ratings)) - 1) * Fraction(5, 2)


def _figures(cells: list[Json], method: str) -> Json:
    """One need's figures from its cells; with no cell the four figures are None and the zone is "none"."""
    if not cells:
        return {"importance": None, "satisfaction": None, "figure": None, "zone": "none"}
    importance = _scale([c["importance"] for c in cells], method)
    satisfaction = _scale([c["satisfaction"] for c in cells], method)
    figure = importance + max(importance - satisfaction, 0)
    zone = "unmet" if figure > UNMET_ABOVE else "over" if satisfaction > importance else "served"
    return {"importance": _tenth(importance), "satisfaction": _tenth(satisfaction), "figure": _tenth(figure),
            "zone": zone}


def _need_result(need: Json, cells: list[Json], themes: dict[str, str], method: str) -> Json:
    ref = str(need["outcome"])
    said = sum(1 for c in cells if c.get("basis") == "said")
    out = {"outcome": ref, "text": need.get("text", ""), "step": kt.step_of(ref), "theme": themes.get(ref),
           "n": len(cells), "said": said, "context": len(cells) - said, **_figures(cells, method)}
    return {**out, "ranked": len(cells) >= MIN_PEOPLE,
            "matters": sum(1 for c in cells if c["importance"] >= HIGH),
            "satisfied": sum(1 for c in cells if c["satisfaction"] >= HIGH)}


def _weakest(kb: Json, people: list[str], cells: list[Json], needs: int) -> list[Json]:
    """The people with ratings for under half the needs, fewest first, at most 2."""
    names = {str(r.get("id")): str(r.get("name") or "") for r in kb["interviews"]}
    counts = {person: sum(1 for c in cells if c["interview"] == person) for person in people}
    thin = sorted((p for p in people if 2 * counts[p] < needs), key=lambda p: (counts[p], people.index(p)))
    return [{"interview": p, "name": names.get(p, ""), "share": percent(counts[p], needs)}
            for p in thin[:WEAKEST_MAX]]


def results(kb: Json, job: str) -> Json | None:
    """The figures of a core job's estimate, for its survey's needs that are still live and the job's people as they
    are now; None without a survey or an estimate. Cells of other needs or other people are left out."""
    entry, estimate = survey_of(kb, job), estimate_of(kb, job)
    if entry is None or estimate is None:
        return None
    live = {str(o["id"]) for o in _live_needs(kb, job)}
    needs = [n for n in entry.get("needs") or [] if isinstance(n, dict) and str(n.get("outcome")) in live]
    people = kt.job_people(kb, job)
    refs = {str(n["outcome"]) for n in needs}
    cells = [c for c in estimate.get("cells") or [] if isinstance(c, dict) and str(c.get("interview")) in people
             and str(c.get("outcome")) in refs]
    themes: dict[str, str] = {}
    for theme in kt.themes_of(kb, job):
        for ref in kt.theme_outcomes(theme):
            themes.setdefault(ref, str(theme["id"]))
    method = "share" if len({c["interview"] for c in cells}) > SHARE_ABOVE else "average"
    rows = [_need_result(n, [c for c in cells if c["outcome"] == n["outcome"]], themes, method) for n in needs]
    unmet = sorted((r for r in rows if r["ranked"] and r["zone"] == "unmet"), key=lambda r: (-r["n"], -r["figure"]))
    said = sum(1 for c in cells if c.get("basis") == "said")
    return {"job": job, "version": estimate.get("version"), "people": len(people), "method": method,
            "possible": len(people) * len(needs),
            "coverage": {"cells": len(cells), "said": said, "context": len(cells) - said}, "needs": rows,
            "unmet": [r["outcome"] for r in unmet[:UNMET_MAX]], "single": sum(1 for r in rows if r["n"] == 1),
            "weakest": _weakest(kb, people, cells, len(needs))}


def status(kb: Json, job: str) -> Json:
    """Where a core job's survey stands: "none", "ready" (a survey, no estimate) or "estimated", and what changed in
    the study since: live needs it neither asks nor leaves out, needs it asks that are no longer live, and whether
    the estimate is of another version or out of date. Every key is there in every state."""
    entry = survey_of(kb, job)
    if entry is None:
        return {"state": "none", "version": 0, "needs": 0, "minutes": 0, "new_needs": [], "gone_needs": [],
                "estimate_old": False}
    asked = [str(n.get("outcome")) for n in entry.get("needs") or [] if isinstance(n, dict)]
    left = [str(n.get("outcome")) for n in entry.get("left_out") or [] if isinstance(n, dict)]
    live = [str(o["id"]) for o in _live_needs(kb, job)]
    estimate = estimate_of(kb, job)
    old = estimate is not None and (estimate.get("version") != entry.get("version")
                                    or bool(kb["simulation"].get("stale")))
    return {"state": "estimated" if estimate else "ready", "version": entry.get("version", 0), "needs": len(asked),
            "minutes": minutes(len(asked)), "new_needs": [ref for ref in live if ref not in asked + left],
            "gone_needs": [ref for ref in asked if ref not in live], "estimate_old": old}


def cmd_survey(args: argparse.Namespace) -> int:
    """`kb_tool survey <kb> MODE`: one mode a run. The options are parsed here, so kb_tool.py holds only the hook."""
    rest = list(args.rest or [])
    args.rest = None  # the run log keeps the parsed options below, never a raw path
    if rest[:1] == ["--"]:
        rest = rest[1:]
    opts = _parser().parse_args(rest)
    args.dry_run, args.json, args.no_publish, args.open = opts.dry_run, opts.json, opts.no_publish, opts.open
    if opts.skeleton is not None:
        args.skeleton = opts.skeleton
        args.run.note(skeleton=True, job=opts.skeleton)
        kb = kt.load_kb(args.kb)
        print(kt.dump_json(skeleton(kb, _check_job(kb, opts.skeleton))))
        return 0
    if opts.evidence is not None:
        args.evidence = opts.evidence
        args.run.note(job=opts.evidence)
        kb = kt.load_kb(args.kb)
        print(kt.dump_json(evidence(kb, _check_job(kb, opts.evidence))))
        return 0
    if opts.estimate is not None:
        args.estimate = args.run.relative(opts.estimate)
        return _estimate(args, opts.estimate)
    args.write = args.run.relative(opts.write)
    return _write(args, opts.write)
