"""`kb_tool themes`: check one core job's value themes and write them.

Value themes are a few needs that group a core job's outcomes, for ideation. Every highlight must be a quote the KB
already holds.

It lives apart from kb_tool.py so the main script stays under the directory's 256 KiB file limit. kb_tool loads it
only for `themes` and hands it the kb_tool module (`kt`), whose helpers and constants it uses. What every command
reads of the layer (`themes_of`, the recount) stays in kb_tool.py."""
from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
from typing import Any

Json = dict[str, Any]
kt: Any = None  # the kb_tool module, set by kb_tool's _sibling() when it loads this file


@dataclass
class ThemeChecks:
    """What the checks of one core job's value themes need at hand."""

    kb: Json
    job: str
    outcomes: dict[str, Json]
    style: kt.Style
    report: kt.Report
    solutions: list[str]  # names of the live solutions: a theme names a need, never one of these


def read_themes_file(path: str, kb: Json) -> tuple[str, list[Any]]:
    data = kt.load_json(path)
    if not isinstance(data, dict) or not isinstance(data.get("themes"), list) or not data.get("job"):
        raise kt.KbError(f"{path} must hold `job` (a core job ID such as A) and `themes` (a list: the full set of "
                         "value themes for that core job)", code="themes_file")
    unknown = sorted(str(key) for key in set(data) - {"job", "themes"})
    if unknown:
        raise kt.KbError(f"{path}: unknown key {', '.join(unknown)}; the file holds `job` and `themes` only",
                         code="themes_file")
    job = str(data["job"])
    if job not in kt.jobs_by_id(kb):
        raise kt.KbError(f"{path}: core job {job} is not in the KB", code="themes_file")
    return job, data["themes"]


def _clean_highlights(items: Any, label: str, width: int, report: kt.Report) -> list[Json]:
    if items is None:
        return []
    if not isinstance(items, list):
        report.error(f"{label}: highlights must be a list", code="theme_shape")
        return []
    clean = []
    for item in items:
        if not (isinstance(item, dict) and item.get("kind") in kt.HIGHLIGHT_KINDS and item.get("interview") is not None
                and str(item.get("quote") or "").strip()):
            report.error(f"{label}: each highlight needs kind ({', '.join(kt.HIGHLIGHT_KINDS)}), interview and quote",
                         code="theme_shape")
            continue
        ref = item["interview"]
        clean.append({"kind": item["kind"], "interview": str(ref).zfill(width) if kt._is_int(ref) else str(ref),
                      "quote": str(item["quote"])})
    return clean


def _clean_theme(item: Any, label: str, width: int, report: kt.Report) -> Json | None:
    """One theme of the file in a known shape, or None when it is not an object."""
    if not isinstance(item, dict):
        report.error(f"{label}: must be an object with label, need, why and outcomes", code="theme_shape")
        return None
    unknown = sorted(str(key) for key in set(item) - set(kt.THEME_KEYS))
    if unknown:
        report.error(f"{label}: unknown key {', '.join(unknown)}; a theme holds {', '.join(kt.THEME_KEYS)}",
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


def _number_themes(themes: list[Json], before: list[Json], job: str, report: kt.Report) -> None:
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
    number = max([kt.theme_number(t) for t in before], default=0)
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
        elif kt.job_of(oid) != ctx.job:
            ctx.report.error(f"{label}: outcome {oid} belongs to core job {kt.job_of(oid)}; a theme groups the "
                             f"outcomes of one core job, here {ctx.job}", code="theme_outcome")


def _check_theme_text(ctx: ThemeChecks, theme: Json, label: str) -> None:
    kt.clarity(theme["label"], "theme", f"{label} label", ctx.style, ctx.report)
    kt.clarity(theme["need"], "need", f"{label} need", ctx.style, ctx.report)
    kt.clarity(theme["why"], "rationale", f"{label} why", ctx.style, ctx.report)
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
    outcomes = kt.outcomes_by_id(kb)
    members = [outcomes[o] for o in outcome_ids if o in outcomes]
    steps = {str(o.get("step")) for o in members}
    items = [e for o in members for e in o.get("evidence", [])]
    items += [e for s in kt.live_solutions(kb) for use in kt.uses_of(s) if str(use.get("step")) in steps
              for e in use.get("evidence", [])]
    return {kt.evidence_key(e): e for e in items}


def _check_highlights(ctx: ThemeChecks, theme: Json, label: str) -> None:
    """Every highlight must be a quote the KB already holds, so a theme never shows words nobody said."""
    pool = _highlight_pool(ctx.kb, theme["outcomes"])
    kept = []
    for item in theme["highlights"]:
        found = pool.get(kt.evidence_key(item))
        if not found:
            ctx.report.error(f'{label}: highlight quote from interview {item["interview"]} is not on one of its '
                             f'outcomes, nor on a solution used at their steps: "{kt.short(item["quote"])}"',
                             code="theme_highlight")
            continue
        kept.append({"kind": item["kind"], "interview": str(found["interview"]), "source": found["source"],
                     "quote": found["quote"], **kt.ix_of(found)})
    theme["highlights"] = kept
    if not theme["highlights"] or len(kept) > kt.THEME_HIGHLIGHTS:
        ctx.report.warn(f"{label} shows {len(kept)} quotes; pick 3 to {kt.THEME_HIGHLIGHTS} that show the pain, the "
                        "struggle and the desire", code="theme_quotes")


def _check_theme_count(ctx: ThemeChecks, themes: list[Json], live: int) -> None:
    low, high = kt.THEME_COUNT
    count, most = len(themes), max(live // kt.THEME_MIN_OUTCOMES, 1)
    if count > most:
        ctx.report.warn(f"{count} value themes for {kt.plural(live, 'outcome')} in core job {ctx.job}: keep at most "
                        f"one theme per {kt.THEME_MIN_OUTCOMES} outcomes, here {most}", code="theme_count")
    elif count > high or (count < low and live >= low * kt.THEME_MIN_OUTCOMES):
        ctx.report.warn(f"{count} value themes in core job {ctx.job}: aim for {low} to {high}, few enough to hold in "
                        "mind and enough to tell needs apart", code="theme_count")


def _check_theme_sizes(ctx: ThemeChecks, themes: list[Json], live: int) -> None:
    for theme in themes:
        size, label = len(theme["outcomes"]), f"theme {theme['id']} '{theme['label']}'"
        if size < kt.THEME_MIN_OUTCOMES:
            ctx.report.warn(f"{label} gathers {kt.plural(size, 'outcome')}; a theme with fewer than "
                            f"{kt.THEME_MIN_OUTCOMES} is often one outcome reworded", code="theme_size")
        elif live >= kt.THEME_COUNT[0] * kt.THEME_MIN_OUTCOMES and size * kt.THEME_MAX_SHARE > live:
            ctx.report.warn(f"{label} gathers {size} of the job's {live} outcomes; split a theme that holds more "
                            f"than one in {kt.THEME_MAX_SHARE}", code="theme_size")
        people = {i for o in theme["outcomes"] for i in ctx.outcomes.get(o, {}).get("interviews", [])}
        if len(people) == 1:
            ctx.report.warn(f"{label} rests on one person; say so when you present it", code="theme_one_person")


def _check_theme_overlap(ctx: ThemeChecks, themes: list[Json]) -> None:
    homes: dict[str, list[str]] = {}
    for theme in themes:
        for oid in theme["outcomes"]:
            homes.setdefault(oid, []).append(theme["id"])
    for oid, where in homes.items():
        if len(where) > kt.THEME_MAX_PER_OUTCOME:
            ctx.report.warn(f"outcome {oid} sits in {len(where)} themes ({', '.join(where)}); keep it in at most "
                            f"{kt.THEME_MAX_PER_OUTCOME}", code="theme_overlap")
    for theme in themes:
        if theme["outcomes"] and all(len(homes[o]) > 1 for o in theme["outcomes"]):
            ctx.report.warn(f"theme {theme['id']} '{theme['label']}' has no outcome of its own; merge it into the "
                            "themes that share its outcomes", code="theme_overlap")


def _check_theme_set(ctx: ThemeChecks, themes: list[Json]) -> None:
    labels = [theme["label"].lower() for theme in themes if theme["label"]]
    for dup in kt._duplicates(labels):
        ctx.report.error(f"two value themes of core job {ctx.job} share the label '{dup}'", code="theme_duplicate")
    live = len([o for o in ctx.outcomes.values() if not o.get("merged_into") and kt.job_of(o["id"]) == ctx.job])
    if themes:
        _check_theme_count(ctx, themes, live)
    _check_theme_sizes(ctx, themes, live)
    _check_theme_overlap(ctx, themes)


def build_themes(kb: Json, job: str, items: list[Any], before: list[Json], report: kt.Report) -> list[Json]:
    """Check the file's themes against the KB and return them as the KB stores them."""
    solutions = [str(s.get("name")) for s in kt.live_solutions(kb) if s.get("name")]
    ctx = ThemeChecks(kb, job, kt.outcomes_by_id(kb), kt.style_of(kb), report, solutions)
    width = kt.id_width(kb)
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
             "outcomes": t["outcomes"], "highlights": t["highlights"], "added": added.get(t["id"]) or kt.today()}
            for t in themes]


def store_themes(kb: Json, job: str, themes: list[Json]) -> int:
    """Replace the core job's themes and clear the stale flag. Returns how many hand-written themes were dropped."""
    layer = kb.get("value_themes") if isinstance(kb.get("value_themes"), dict) else {}
    old = layer.get("themes") if isinstance(layer.get("themes"), list) else []
    kept = [t for t in kt.themes_of(kb) if str(t.get("job")) != job]
    rest = {k: v for k, v in layer.items() if k not in ("stale", "stale_reasons", "themes", "unassigned")}
    merged = sorted(kept + themes, key=lambda t: (kt.job_index(str(t["job"])), kt.theme_number(t)))
    kb["value_themes"] = {"stale": False, "themes": merged, **rest}
    return len(old) - len(kt.themes_of({"value_themes": layer}))


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
        joined = [o for o in theme["outcomes"] if o not in kt.theme_outcomes(was)]
        left = [o for o in kt.theme_outcomes(was) if o not in theme["outcomes"]]
        if joined or left:
            lines.append(f"{tid} {theme['label']}:" + (f" added {', '.join(joined)}" if joined else "")
                         + (f" removed {', '.join(left)}" if left else ""))
    return lines + [f"removed {tid} {theme.get('label', '')}" for tid, theme in old.items() if tid not in new]


def _themes_text(kb: Json, job: str, themes: list[Json], result: Json) -> list[str]:
    outcomes = kt.outcomes_by_id(kb)
    lines = [f"VALUE THEMES for core job {job}: {kt.jobs_by_id(kb)[job]['statement']}"]
    for theme in themes:
        lines.append(f"{theme['id']} {theme['label']}: {theme['need']}  "
                     f"({kt.plural(len(theme['outcomes']), 'outcome')}, people {theme.get('interview_count', 0)})")
        lines += [f"   {oid:>7}  {outcomes[oid]['statement']}" for oid in theme["outcomes"] if oid in outcomes]
    if result["unassigned"]:
        lines.append(f"IN NO THEME ({len(result['unassigned'])})")
        lines += [f"   {oid:>7}  {outcomes[oid]['statement']}" for oid in result["unassigned"]]
    if result["changes"]:
        lines += ["CHANGES"] + [f"  {line}" for line in result["changes"]]
    if result["legacy_dropped"]:
        lines.append(f"dropped {kt.plural(result['legacy_dropped'], 'theme')} written by hand before this command "
                     "existed; the backup still has them")
    if result["other_jobs"]:
        lines.append(f"themes of core job {', '.join(result['other_jobs'])} were not touched; update them too if "
                     "they are out of date")
    return lines


def cmd_themes(args: argparse.Namespace) -> int:
    """Check one core job's value themes and write them. The dry run and the real run share every step up to the
    write."""
    kb = kt.load_kb(args.kb)
    report = kt.Report()
    job, items = read_themes_file(args.themes, kb)
    args.run.note(dry_run=bool(args.dry_run), job=job)
    candidate = copy.deepcopy(kb)
    before = kt.themes_of(kb, job)
    built = build_themes(candidate, job, items, before, report)
    result: Json = {"ok": False, "dry_run": bool(args.dry_run), "job": job, "written": False, "run_id": args.run.id}
    if report.errors:
        return kt.finish_write(args, report, result, [])
    legacy = store_themes(candidate, job, built)
    kt.recount(candidate)
    themes = kt.themes_of(candidate, job)
    unassigned = [o for o in candidate["value_themes"].get("unassigned", []) if kt.job_of(o) == job]
    summary = f"value themes of core job {job}: {', '.join(t['id'] for t in themes) or 'none'}"
    result.update({"ok": True, "themes": themes, "unassigned": unassigned, "legacy_dropped": legacy,
                   "changes": theme_changes(before, themes),
                   "other_jobs": sorted({str(t["job"]) for t in kt.themes_of(candidate)} - {job})})
    args.run.note(counts={"themes": len(themes), "theme_outcomes": len({o for t in themes for o in t["outcomes"]}),
                          "unassigned": len(unassigned)})
    return kt.write_layer(args, report, result, _themes_text(candidate, job, themes, result), candidate,
                          layer="value_themes", summary=summary, what="these themes",
                          checked="every outcome and every quote is in the KB", themes=[t["id"] for t in themes])
