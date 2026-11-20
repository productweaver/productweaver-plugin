"""`kb_tool overview`: check one core job's overview and write it.

The overview is one core job's study as a short story, with what to do next. The layer holds only the assistant's
sentences; the map counts the rest, and every quote must already be in the KB.

It lives apart from kb_tool.py so the main script stays under the directory's 256 KiB file limit. kb_tool loads it
for `overview`, and kb_people loads it to check a planned follow-up. kb_tool hands it the kb_tool module (`kt`), whose
helpers and constants it uses. What every command reads of the layer (`overviews_of`) stays in kb_tool.py."""
from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
from typing import Any

Json = dict[str, Any]
kt: Any = None  # the kb_tool module, set by kb_tool's _sibling() when it loads this file


@dataclass
class OverviewChecks:
    """What the checks of one core job's overview need at hand."""

    kb: Json
    job: str
    style: kt.Style
    report: kt.Report
    pool: dict[tuple[str, str], Json]  # every quote the KB holds for this core job
    width: int


def _own_statements(record: Json) -> list[Json]:
    lists = [record.get(key) or [] for key in ("related_jobs", "emotional_jobs", "social_jobs")]
    items = [record.get("job_executor"), record.get("core_functional_job")] + [s for group in lists for s in group]
    return [s for s in items if isinstance(s, dict)]


def _overview_pool(kb: Json, job: str) -> dict[tuple[str, str], Json]:
    """Quotes an overview may show: on the job's steps, outcomes and solution uses, and linked people's own words."""
    steps = [s for s in kb["job_map"]["steps"] if str(s["job"]) == job]
    keys = {kt.step_key(s) for s in steps}
    items = [e for s in steps for e in s.get("evidence", [])]
    items += [e for o in kb["desired_outcomes"]["outcomes"]
              if not o.get("merged_into") and kt.job_of(o["step"]) == job for e in o.get("evidence", [])]
    items += [e for s in kt.live_solutions(kb) for use in kt.uses_of(s) if str(use.get("step")) in keys
              for e in use.get("evidence", [])]
    for record in kb["interviews"]:
        if kt.main_job(record) == job or job in kt.related_links(record):
            items += [{**e, "interview": str(record["id"])} for s in _own_statements(record)
                      for e in s.get("evidence") or [] if isinstance(e, dict)]
    return {kt.evidence_key(e): e for e in items if isinstance(e, dict)}


def read_overview_file(path: str, kb: Json) -> tuple[str, Json]:
    data = kt.load_json(path)
    if not isinstance(data, dict) or not data.get("job"):
        raise kt.KbError(f"{path} must be an object with `job` (a core job ID such as A) and the overview of that core "
                         f"job: {', '.join(kt.OVERVIEW_KEYS[1:])}", code="overview_file")
    unknown = sorted(str(key) for key in set(data) - set(kt.OVERVIEW_KEYS))
    if unknown:
        raise kt.KbError(f"{path}: unknown key {', '.join(unknown)}; the file holds {', '.join(kt.OVERVIEW_KEYS)}",
                         code="overview_file")
    job = str(data["job"])
    if job not in kt.jobs_by_id(kb):
        raise kt.KbError(f"{path}: core job {job} is not in the KB", code="overview_file")
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
    _ov_clarity(ctx, text, kind, f"{label} {key}")
    _ov_no_score(ctx, text, f"{label} {key}")
    _ov_plain(ctx, text, f"{label} {key}")
    return text


def _ov_clarity(ctx: OverviewChecks, text: str, kind: str, label: str) -> None:
    """An overview sentence a quarter over its limit at most (at least 1 word) is written, with a warning."""
    kt.clarity(text, kind, label, ctx.style, ctx.report, slack=max(1, ctx.style.limits.get(kind, 0) // 4))


def _ov_no_score(ctx: OverviewChecks, text: str, label: str) -> None:
    """Interviews show what people said, not how much it matters: an overview carries no score and no percentage."""
    if kt.SCORE_WORDS.search(text):
        ctx.report.error(f"{label}: no percentages and no score words in an overview; say how many people said it: "
                         f"'{text}'", code="overview_score")


def _ov_plain(ctx: OverviewChecks, text: str, label: str) -> None:
    """A first-time reader must understand every sentence on first read: no words of the method, few buzzwords."""
    for pattern, word, hint in kt.METHOD_TERMS:
        if pattern.search(text):
            ctx.report.error(f"{label}: '{word}' is a word of the method that readers do not know; write "
                             f"{hint}: '{text}'", code="overview_method_word")
    for pattern, word, hint in kt.JARGON_TERMS:
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
    key = {"interview": str(ref).zfill(ctx.width) if kt._is_int(ref) else str(ref), "quote": str(item["quote"])}
    found = ctx.pool.get(kt.evidence_key(key))
    if not found:
        ctx.report.error(f'{label}: the quote from interview {key["interview"]} is not in the KB for core job '
                         f'{ctx.job}; copy one from a step, an outcome, a solution or the person: '
                         f'"{kt.short(key["quote"])}"', code="overview_quote")
        return None
    return {"interview": str(found["interview"]), "source": found.get("source", "transcript"),
            "quote": found["quote"], **kt.ix_of(found)}


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
    section = _ov_mapping(ctx, data, "executor", kt.EXECUTOR_KEYS, "overview")
    out: Json = {"label": _ov_text(ctx, section, "label", "role", "executor"),
                 "text": _ov_text(ctx, section, "text", "who", "executor")}
    icon = str(section.get("icon") or "").strip()
    if section and icon not in kt.ROLE_ICONS:
        ctx.report.error(f"executor: icon {f'{icon!r} is not one the map can draw' if icon else 'is missing'}; "
                         f"pick one of {', '.join(kt.ROLE_ICONS)} (person when none fits)", code="overview_shape")
    out["icon"] = icon or "person"
    others = section.get("others")
    if others is None:
        return out
    if not isinstance(others, list) or not all(isinstance(x, str) and x.strip() for x in others):
        ctx.report.error(f"executor: others must be a list of at most {kt.EXECUTOR_OTHERS} people, such as "
                         "'their clients'", code="overview_shape")
        return out
    items = [x.strip() for x in others]
    if len(items) > kt.EXECUTOR_OTHERS:
        ctx.report.error(f"executor: others holds {len(items)} people; keep at most {kt.EXECUTOR_OTHERS}",
                         code="overview_count")
    for text in items:
        _ov_clarity(ctx, text, "role", "executor others")
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
    known = {str(s.get("id")) for s in kt.live_solutions(ctx.kb)}
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
    if gap["kind"] not in kt.GAP_KINDS:
        ctx.report.error(f"{label}: kind must be one of {', '.join(kt.GAP_KINDS)}", code="overview_shape")
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
    if len(gaps) > kt.GAP_MAX:
        ctx.report.warn(f"{len(gaps)} gaps; keep at most {kt.GAP_MAX}, the ones most people described",
                        code="overview_count")
    for dup in kt._duplicates([g["label"].lower() for g in gaps if g["label"]]):
        ctx.report.error(f"two gaps share the label '{dup}'", code="overview_shape")
    return {"answer": _ov_text(ctx, section, "answer", "headline", "gaps"), "items": gaps}


def _ov_list(ctx: OverviewChecks, track: Json, key: str, label: str) -> list[str]:
    given = track.get(key)
    if not isinstance(given, list) or not given or not all(isinstance(x, str) and x.strip() for x in given):
        ctx.report.error(f"{label}: {key} must be a list of 1 to {kt.NEXT_LISTS[key]} sentences", code="overview_shape")
        return []
    items = [x.strip() for x in given]
    if len(items) > kt.NEXT_LISTS[key]:
        ctx.report.error(f"{label}: {key} holds {len(items)} items; keep at most {kt.NEXT_LISTS[key]}",
                         code="overview_count")
    for text in items:
        _ov_clarity(ctx, text, "rationale", f"{label} {key}")
        _ov_no_score(ctx, text, f"{label} {key}")
        if key != "words":  # the customers' own words stay as they said them
            _ov_plain(ctx, text, f"{label} {key}")
    return items


def _ov_words(ctx: OverviewChecks, words: list[str], label: str) -> None:
    """The customers' words to reuse in messaging must be words a customer said."""
    said = [kt.norm(str(e.get("quote", ""))).lower() for e in ctx.pool.values()]
    for text in words:
        needle = kt.norm(text).lower().strip(" .!?\"'")
        if not any(needle in quote for quote in said):
            ctx.report.error(f'{label}: "{kt.short(text)}" is not part of a quote in the KB for core job {ctx.job}; '
                             "use the customers' exact words", code="overview_quote")


def _ov_track(ctx: OverviewChecks, data: Json, name: str) -> Json:
    statuses, fields = kt.NEXT_TRACKS[name]
    label = f"next.{name}"
    extra = kt.LEARN_PLAN if name == "learn" else ()
    track = _ov_mapping(ctx, data, name, ("status", "action", *fields, *extra), "next")
    out: Json = {"status": str(track.get("status") or ""), "action": _ov_text(ctx, track, "action", "action", label)}
    if out["status"] not in statuses:
        ctx.report.error(f"{label}: status must be one of {', '.join(statuses)}", code="overview_shape")
    for key in fields:
        out[key] = _ov_list(ctx, track, key, label) if key in kt.NEXT_LISTS else \
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
    if not isinstance(given, list) or not kt.TRAIT_COUNT[0] <= len(given) <= kt.TRAIT_COUNT[1]:
        ctx.report.error("next.learn: traits must be a list of 2 or 3 traits", code="overview_count")
    main = {str(r["id"]) for r in ctx.kb["interviews"] if kt.main_job(r) == ctx.job}
    traits = []
    for trait in given if isinstance(given, list) else []:
        tid = str(trait.get("id") or "") if isinstance(trait, dict) else ""
        values = trait.get("values") if isinstance(trait, dict) else None
        if not kt.TRAIT_ID.match(tid):
            ctx.report.error(f"next.learn: a trait needs an id like T1, not '{tid}'", code="overview_shape")
        if not isinstance(values, list) or not kt.TRAIT_VALUES[0] <= len(values) <= kt.TRAIT_VALUES[1]:
            ctx.report.error(f"next.learn {tid}: a trait has 2 to 5 values", code="overview_count")
        kept, seen = [], set()
        for value in values if isinstance(values, list) else []:
            vid = str(value.get("id") or "") if isinstance(value, dict) else ""
            if not (kt.TRAIT_VALUE_ID.match(vid) and vid.startswith(f"{tid}.")):
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
    for twice in kt._duplicates([t["id"] for t in traits] + [v["id"] for t in traits for v in t["values"]]):
        ctx.report.error(f"next.learn: {twice} is used twice", code="overview_shape")
    return traits


def _ov_question(ctx: OverviewChecks, item: Any, gaps: list[str], label: str) -> Json:
    item = _ov_mapping(ctx, {"question": item}, "question", ("ask", "listen", "gaps"), label)
    ask = _ov_text(ctx, item, "ask", "question", label)
    refs = _ov_refs(ctx, item.get("gaps"), set(gaps), kt.ROUND_ITEMS, f"{label} gaps")
    stray = [ref for ref in refs if ref not in gaps]
    if stray:
        ctx.report.error(f"{label}: {', '.join(stray)} is not one of this entry's gaps", code="overview_shape")
    if ctx.style.english and kt.LEADING.search(ask):
        ctx.report.warn(f"{label}: '{ask}' asks what they would do; ask about the last time they did it",
                        code="plan_leading")
    return {"ask": ask, "listen": _ov_text(ctx, item, "listen", "listen", label), "gaps": refs}


def _ov_round(ctx: OverviewChecks, given: Any, refs: set[str], values: set[str]) -> list[Json]:
    """Who to talk to next, in order, with the gaps each fills and the questions."""
    if not isinstance(given, list) or not given or len(given) > kt.ROUND_MAX:
        count = len(given) if isinstance(given, list) else 0
        ctx.report.error(f"next.learn: round holds {count} entries; keep at most {kt.ROUND_MAX}, at least 1",
                         code="overview_count")
    entries = []
    for n, raw in enumerate(given if isinstance(given, list) else [], 1):
        where = f"next.learn round {n}"
        if isinstance(raw, dict) and raw.get("kind") == "follow_up":  # asks someone in the study again
            entries.append(kt._people().follow_up_entry(ctx, raw, where, refs))
            continue
        entry = _ov_mapping(ctx, {"entry": raw}, "entry", ("kind", "count", "who", "traits", "gaps", "questions"),
                             where)
        count = entry.get("count")
        if entry.get("kind") != "new":
            ctx.report.error(f"{where}: kind must be new or follow_up", code="overview_shape")
        if not (kt._is_int(count) and kt.ROUND_COUNT[0] <= count <= kt.ROUND_COUNT[1]):
            ctx.report.error(f"{where}: count must be 1 to 3 people", code="overview_shape")
        gaps = _ov_refs(ctx, entry.get("gaps"), refs, kt.ROUND_ITEMS, f"{where} gaps")
        asks = entry.get("questions")
        if not isinstance(asks, list) or not 1 <= len(asks) <= kt.ROUND_ITEMS:
            ctx.report.error(f"{where}: questions must be a list of 1 to {kt.ROUND_ITEMS}", code="overview_count")
        out: Json = {"kind": "new", "count": count, "who": _ov_text(ctx, entry, "who", "plan_who", where)}
        if entry.get("traits"):
            out["traits"] = _ov_refs(ctx, entry["traits"], values, kt.ROUND_ITEMS, f"{where} traits")
        out["gaps"] = gaps
        out["questions"] = [_ov_question(ctx, q, gaps, f"{where} question {i}")
                            for i, q in enumerate(asks if isinstance(asks, list) else [], 1)]
        entries.append(out)
    return entries


def _ov_plan(ctx: OverviewChecks, track: Json, out: Json) -> None:
    """The plan for the next round; every ref belongs to this core job."""
    traits = _ov_traits(ctx, track.get("traits"))
    values = {v["id"] for t in traits for v in t["values"]}
    steps = {kt.step_key(s) for s in ctx.kb["job_map"]["steps"] if s.get("job") == ctx.job}
    outs = {str(o["id"]) for o in ctx.kb["desired_outcomes"]["outcomes"]
            if not o.get("merged_into") and kt.job_of(str(o["step"])) == ctx.job}
    out["traits"] = traits
    out["rests_on"] = _ov_refs(ctx, track.get("rests_on"), outs, kt.RESTS_ON_MAX, "next.learn rests_on")
    out["round"] = _ov_round(ctx, track.get("round"), steps | outs | values, values)
    gaps = kt.open_gaps(ctx.kb, ctx.job, out)
    if any(entry["kind"] == "follow_up" for entry in out["round"]):
        kt._people().warn_no_gain(ctx, out["round"], gaps)
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


def build_overview(kb: Json, job: str, data: Json, report: kt.Report) -> Json:
    """Check the file's overview against the KB and return it as the KB stores it."""
    ctx = OverviewChecks(kb, job, kt.style_of(kb), report, _overview_pool(kb, job), kt.id_width(kb))
    entry: Json = {"job": job, "executor": _ov_executor(ctx, data),
                   "bottom_line": _ov_text(ctx, data, "bottom_line", "headline", "overview"),
                   "why": _ov_text(ctx, data, "why", "rationale", "overview"),
                   "opening": _ov_text(ctx, data, "opening", "rationale", "overview"),
                   "people": _ov_section(ctx, data, "people", quote=True), "today": _ov_section(ctx, data, "today"),
                   "gaps": _ov_gaps(ctx, data), "needs": _ov_section(ctx, data, "needs"),
                   "focus": _ov_section(ctx, data, "focus")}
    steps = _ov_mapping(ctx, data, "next", tuple(kt.NEXT_TRACKS), "overview")
    entry["next"] = {name: _ov_track(ctx, steps, name) for name in kt.NEXT_TRACKS}
    entry["written"] = kt.today()
    return entry


def store_overview(kb: Json, entry: Json) -> None:
    """Replace the core job's overview, keep those of other core jobs and clear the layer's stale flag."""
    layer = kb.get("overview") if isinstance(kb.get("overview"), dict) else {}
    kept = [o for o in kt.overviews_of(kb) if str(o["job"]) != entry["job"]]
    rest = {k: v for k, v in layer.items() if k not in ("stale", "stale_reasons", "jobs")}
    kb["overview"] = {"stale": False, "jobs": sorted(kept + [entry], key=lambda o: kt.job_index(str(o["job"]))),
                      **rest}


def _overview_text(kb: Json, entry: Json, result: Json) -> list[str]:
    job = entry["job"]
    who = entry["executor"]
    lines = [f"OVERVIEW for core job {job}: {kt.jobs_by_id(kb)[job]['statement']}",
             f"about: {who['label']} [{who['icon']}]: {who['text']}"
             + (f" (also in the story: {', '.join(who['others'])})" if who.get("others") else ""),
             f"bottom line: {entry['bottom_line']}", f"opening: {entry['opening']}"]
    lines += [f"{key}: {entry[key]['answer']}" for key in ("people", "today", "gaps", "needs", "focus")]
    lines += [f"   gap ({g['kind']}): {g['label']}" for g in entry["gaps"]["items"]]
    lines += [f"next, {name} ({track['status']}): {track['action']}" for name, track in entry["next"].items()]
    lines += [f"next, learn round: {e['count']} × {e['who']} (gaps {', '.join(e['gaps'])})" if "who" in e else
              f"next, learn round: ask interview {e['interview']} again (gaps {', '.join(e['gaps'])})"
              for e in entry["next"]["learn"].get("round", [])]
    if result["other_jobs"]:
        lines.append(f"the overview of core job {', '.join(result['other_jobs'])} was not touched; update it too if "
                     "it is out of date")
    if result["missing_jobs"]:
        lines.append(f"core job {', '.join(result['missing_jobs'])} has no overview yet")
    return lines


def placeholders(data: Any, where: str = "") -> list[str]:
    """Where a file still holds a skeleton's <…>, such as next.learn.round[0].who."""
    if isinstance(data, dict):
        return [p for k, v in data.items() for p in placeholders(v, f"{where}.{k}" if where else str(k))]
    if isinstance(data, list):
        return [p for i, v in enumerate(data) for p in placeholders(v, f"{where}[{i}]")]
    text = data.strip() if isinstance(data, str) else ""
    return [where] if text.startswith("<") and text.endswith(">") else []


def cmd_overview(args: argparse.Namespace) -> int:
    """Check one core job's overview and write it. The dry run and the real run share every step up to the write."""
    kb = kt.load_kb(args.kb)
    if bool(args.overview) == bool(args.skeleton):
        raise kt.KbError("give overview the file to check and write, or --skeleton JOB for the file to fill in",
                         code="overview_file")
    if args.skeleton:
        return kt._review().cmd_skeleton(args, kb)
    report = kt.Report()
    job, data = read_overview_file(args.overview, kb)
    args.run.note(dry_run=bool(args.dry_run), job=job)
    for where in placeholders(data):
        report.error(f"{where} still holds a <…> of the skeleton: write it, or delete it where it says so",
                     code="overview_placeholder")
    candidate = copy.deepcopy(kb)
    entry = build_overview(candidate, job, data, report)
    result: Json = {"ok": False, "dry_run": bool(args.dry_run), "job": job, "written": False, "run_id": args.run.id}
    if report.errors:
        return kt.finish_write(args, report, result, [])
    learn, old = entry["next"]["learn"], kt.learn_of(kb, job)
    if learn.get("round"):
        learn["at_write"] = kt.round_snapshot(kb, learn)
        was = old.get("at_write") if isinstance(old.get("at_write"), dict) else {}
        moved = bool(was) and any(was.get(k) != learn["at_write"].get(k) for k in ("interviews", "interactions"))
        if moved or isinstance(old.get("previous"), dict):  # moved: a batch came in since
            learn["previous"] = was if moved else old["previous"]
    store_overview(candidate, entry)
    kt.recount(candidate)
    summary = f"overview of core job {job}"
    written = {str(o["job"]) for o in kt.overviews_of(candidate)}
    result.update({"ok": True, "overview": kt.overviews_of(candidate, job)[0], "other_jobs": sorted(written - {job}),
                   "missing_jobs": sorted(set(kt.jobs_by_id(candidate)) - written)})
    args.run.note(counts={"overview_gaps": len(entry["gaps"]["items"]), "overviews": len(written)})
    return kt.write_layer(args, report, result, _overview_text(candidate, entry, result), candidate, layer="overview",
                          summary=summary, what="this overview", checked="every quote and every solution is in the KB")
