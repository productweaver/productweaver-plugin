"""`kb_tool review`: write pw-output/review.md, the plain sheet for the people who review a study, and
interview-guide.md, the plan for the next calls. Also `overview --skeleton`: the overview file the assistant fills in.

It lives apart from kb_tool.py so the main script stays under the directory's 256 KiB file limit. kb_tool loads it
for `review`, for the guides inside the map, for the rebuild after a write and for `overview --skeleton`, and hands it
the kb_tool module (`kt`), whose helpers it uses."""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
from typing import Any

Json = dict[str, Any]
kt: Any = None  # the kb_tool module, set by kb_tool's _review(), cmd_review() and cmd_skeleton()


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
KIND_LABELS = {"product": "review.kind.product", "everyday_tool": "review.kind.everyday_tool",
               "people": "review.kind.people", "own_method": "review.kind.own_method"}  # the review sheet's names
LAYER_LABELS = {"survey": "review.layer.survey", "simulation": "review.layer.simulation",
                "value_themes": "review.layer.value_themes", "overview": "review.layer.overview",
                "use_cases": "review.layer.use_cases"}


def describe_proposal(proposal: Json, text=None) -> str:
    text = text or kt.Text()
    kind = str(proposal.get("type"))
    if kind == "relink_interview" and not proposal.get("job"):
        return text("review.proposal.unlink_interview", target=proposal.get("target"))
    values = {key: proposal.get(key) for key in ("job", "target", "merge", "to_step", "to_job", "to_group")}
    return text(PROPOSAL_LABELS.get(kind, "review.proposal.other"), **values)


def kind_text(text, kind: Any) -> str:
    return text(KIND_LABELS[str(kind)]) if str(kind) in KIND_LABELS else str(kind)


def _review_head(kb: Json, live_outcomes: list[Json], text) -> list[str]:
    in_use = [s for s in kt.live_solutions(kb) if s.get("interviews")]
    solutions = " · " + text("review.count.solutions_in_use", n=len(in_use)) if "current_solutions" in kb else ""
    project = kb["meta"]["project"] if "project" in kb["meta"] else text("review.project_default")
    counts = " · ".join([text("review.count.interviews", n=len(kb["interviews"])),
                         text("review.count.core_jobs", n=len(kb["core_jobs"])),
                         text("review.count.steps", n=len(kb["job_map"]["steps"])),
                         text("review.count.outcomes", n=len(live_outcomes))])
    updated = text("review.updated", date=kt.today())
    lines = ["# " + text("review.title", project=project), "", f"{counts}{solutions} · {updated}", ""]
    if not kb["core_jobs"]:
        return lines + [f"**{text('review.core_job')}:** {text('review.not_set')}", ""]
    proposed = f" *({text('review.proposed')})*"
    for job in kb["core_jobs"]:
        name = text("review.core_job_id", id=job["id"])
        lines.append(f"- **{name}:** {job['statement']}" + (proposed if job.get("status") == "proposed" else ""))
    return lines + [""]


def _review_decisions(kb: Json, text) -> list[str]:
    pending = [p for p in kb["proposed_changes"] if p.get("status") == "pending"]
    lines = ["## " + text("review.h.decisions"), ""]
    if not pending:
        return lines + [text("review.none"), ""]
    why = text("review.why")
    for proposal in pending:
        lines.append(f"- **{proposal['id']} · {describe_proposal(proposal, text)}:** {proposal['proposal']}. "
                     f"*{why}:* {proposal['rationale']}")
        lines += [f"  - \"{reply}\"" for reply in decision_replies(kb, proposal, text)]
    return lines + ["", text("review.reply_confirm"), ""]


def decision_replies(kb: Json, proposal: Json, text) -> list[str]:
    """The two replies the map shows under a decision, to paste in the chat: they name the study, not a code."""
    change = str(proposal.get("proposal", ""))
    if proposal.get("type") == "confirm_core_job":
        goal = kt.jobs_by_id(kb).get(str(proposal.get("target")), {}).get("statement") or change
        return [text("map.decide.reply_yes_goal", brand=kt.BRAND, goal=goal),
                text("map.decide.reply_change_goal", brand=kt.BRAND) + " …"]
    return [text("map.decide.reply_yes", brand=kt.BRAND, change=change),
            text("map.decide.reply_no", brand=kt.BRAND, change=change)]


def _new_solution_lines(kb: Json, since: str, text) -> list[str]:
    groups = kt.groups_of(kb)
    lines = []
    for group in groups.values():
        if since and str(group.get("added", "")) >= since:
            name = "**" + str(group.get("name", "")) + ":**"
            lines.append(f"- {text('review.new_group', name=name)} {group.get('why', '')}")
    for solution in kt.live_solutions(kb):
        if since and str(solution.get("added", "")) >= since:
            group = groups.get(str(solution.get("group")), {}).get("name", solution.get("group"))
            named = "**" + f"{solution['id']} {solution.get('name', '')}" + "**"
            lines.append("- " + text("review.new_solution", solution=named, kind=kind_text(text, solution.get("kind")),
                                     group=f"*{group}*"))
    return lines


def _review_new(kb: Json, since: str, new_outcomes: set[str], text) -> list[str]:
    new_interviews = [i for i in kb["interviews"] if since and str(i.get("added", "")) >= since]
    solution_lines = _new_solution_lines(kb, since, text)
    if not (new_interviews or new_outcomes or solution_lines):
        return []
    lines = ["## " + text("review.h.new", date=since), ""]
    for record in new_interviews:
        job = kt.main_job(record)
        link = text("review.core_job_ref", id=job) if job else text("review.no_core_job_yet")
        own = text("review.new_interview_job", job=f"*{record['core_functional_job']['statement']}*", link=link)
        lines.append(f"- **{record['id']} {record.get('name', '')}:** {record['job_executor']['statement']} {own}")
    for outcome in kb["desired_outcomes"]["outcomes"]:
        if outcome["id"] in new_outcomes:
            label = text("review.new_outcome", id=f"**{outcome['id']}:**")
            lines.append(f"- {label} {outcome['statement']}")
    return lines + solution_lines + [""]


def _review_map(kb: Json, live_outcomes: list[Json], new_outcomes: set[str], text) -> list[str]:
    by_step: dict[str, list[Json]] = {}
    for outcome in live_outcomes:
        by_step.setdefault(str(outcome["step"]), []).append(outcome)
    lines: list[str] = []
    for index, job in enumerate(kb["core_jobs"]):
        lines += [f"## {text('review.core_job_id', id=job['id'])}: {job['statement']}", ""]
        if index == 0:
            lines += [text("review.map_hint"), ""]
        ordered = sorted((s for s in kb["job_map"]["steps"] if s.get("job") == job["id"]), key=lambda s: int(s["n"]))
        for stage in kt.STAGES:
            steps = [s for s in ordered if s.get("stage") == stage]
            if not steps:
                continue
            lines.append("### " + text(STAGE_LABELS[stage]))
            for step in steps:
                lines.append(f"**{kt.step_key(step)} {step['statement']}** [{step.get('voices', 0)}]")
                for outcome in by_step.get(kt.step_key(step), []):
                    mark = "● " if outcome["id"] in new_outcomes else ""
                    count = outcome.get("interview_count", 0)
                    lines.append(f"- {mark}{outcome['id']} {outcome['statement']} [{count}]")
                lines.append("")
    return lines


def _solution_line(solution: Json, steps: dict[str, Json], names: dict[str, str], text) -> str:
    sep = text("review.list_sep")
    used = sep.join(f"{steps[s]['statement']} ({s})" if s in steps else s for s in kt.solution_steps(solution))
    people = sep.join(names.get(i, i) for i in solution.get("interviews", []))
    stopped = sep.join(names.get(i, i) for i in solution.get("stopped_by", []))
    mentions = text("review.count.mentions", n=solution.get("quote_count", 0))
    return (f"- **{solution['id']} {solution.get('name', '')}** ({kind_text(text, solution.get('kind'))}) "
            f"[{len(solution.get('interviews', []))}] {people or text('review.nobody_now')} · {mentions} · "
            + text("review.used_for", steps=used)
            + (" · " + text("review.stopped", people=stopped) if stopped else ""))


def _review_solutions(kb: Json, text) -> list[str]:
    solutions = kt.live_solutions(kb)
    if not solutions:
        return []
    steps, names = kt.steps_by_id(kb), {str(r["id"]): str(r.get("name", "")) for r in kb["interviews"]}
    lines = ["## " + text("review.h.solutions"), "", text("review.solutions_intro"), ""]
    why = text("review.why_grouped")
    for key, group in kt.groups_of(kb).items():
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


def _review_themes(kb: Json, text) -> list[str]:
    themes = kt.themes_of(kb)
    if not themes:
        return []
    outcomes = kt.outcomes_by_id(kb)

    def rows(ids: list[str]) -> list[str]:
        return [f"- {outcomes[o]['statement']} ({o}) [{outcomes[o].get('interview_count', 0)}]"
                for o in ids if o in outcomes]

    stale = " " + text("review.themes_stale") if "value_themes" in kt.stale_layers(kb) else ""
    lines = ["## " + text("review.h.themes"), "", text("review.themes_intro") + stale, ""]
    many = len(kb["core_jobs"]) > 1
    for theme in sorted(themes, key=lambda t: (kt.job_index(str(t["job"])), -t.get("interview_count", 0))):
        where = f" ({text('review.core_job_ref', id=theme['job'])})" if many else ""
        lines += [f"### {theme.get('label', '')} [{theme.get('interview_count', 0)}]{where}", "",
                  f"*{theme.get('need', '')}*", ""]
        lines += ([theme["why"], ""] if theme.get("why") else []) + rows(kt.theme_outcomes(theme)) + [""]
    left = kt.unassigned_outcomes(kb)
    if left:
        lines += ["### " + text("review.h.no_theme"), ""] + rows(left) + [""]
    return lines


def _review_people(kb: Json, text) -> list[str]:
    jobs = kt.jobs_by_id(kb)
    named = [r for r in kb["interviews"] if kt.main_job(r) or kt.related_links(r)] if len(jobs) > 1 else []
    sep, also_word = text("review.list_sep"), text("review.also")
    lines = []
    if named:
        lines += ["## " + text("review.h.people"), ""]
        for record in named:
            parts = [f"{jobs[j]['statement']} ({j})" for j in [kt.main_job(record)] if j and j in jobs]
            also = [f"{jobs[j]['statement']} ({j})" for j in dict.fromkeys(kt.related_links(record))
                    if j in jobs and j != kt.main_job(record)]
            joint = f"{sep}{also_word} " if parts and also else f"{also_word} " if also else ""
            lines.append(f"- **{record['id']} {record.get('name', '')}:** {sep.join(parts)}{joint}{sep.join(also)}")
        lines.append("")
    unlinked = [r for r in kb["interviews"] if not kt.main_job(r)]
    if unlinked:
        lines += ["## " + text("review.h.unlinked"), ""]
        for record in unlinked:
            note = (kt.unlinked_reason(record) or record.get("analyst_note")
                    or record["core_functional_job"]["statement"])
            lines.append(f"- **{record['id']} {record.get('name', '')}:** {note}")
        lines.append("")
    return lines


NX_GROUP_MAX = 5
NX_GROUPS = (("main", "review.nx.g.main"), ("step", "review.nx.g.step"), ("need", "review.nx.g.need"),
             ("who", "review.nx.g.who"))
NX_LEVELS = ("review.nx.level.1", "review.nx.level.2", "review.nx.level.3")
GUIDE_STEPS = ("review.guide.step.1", "review.guide.step.2", "review.guide.step.3", "review.guide.step.4",
               "review.guide.step.5")
GUIDE_HELP = (("review.guide.invite.h", "review.guide.invite.1", "review.guide.invite.2"),
              ("review.guide.before.h", "review.guide.before.1", "review.guide.before.2"),
              ("review.guide.start.h", "review.guide.start.1", "review.guide.start.2"),
              ("review.guide.short.h", "review.guide.short.1", "review.guide.short.2"),
              ("review.guide.idea.h", "review.guide.idea.1"),
              ("review.guide.end.h", "review.guide.end.1", "review.guide.end.2"))
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


def last_round(kb: Json, job: str) -> Json | None:
    """How many of the last round's targets closed; a renamed kind of person is not counted."""
    learn = kt.learn_of(kb, job)
    if not isinstance(learn.get("previous"), dict):
        return None
    labels = {v.get("id"): v.get("label") for t in learn.get("traits") or [] for v in t.get("values") or []}
    known = {kt.step_key(s) for s in kb["job_map"]["steps"] if s.get("job") == job} | {
        str(o["id"]) for o in kb["desired_outcomes"]["outcomes"] if kt.job_of(str(o["step"])) == job}
    targets = [ref for t in learn["previous"].get("targets") or []  # a moved outcome's old ID is gone, not closed
               for ref in [str(t.get("ref")) if t.get("label") else kt.live_outcome(kb, str(t.get("ref")))]
               if (labels.get(ref) == t["label"] if t.get("label") else ref in known)]
    still = [ref for ref in targets if ref in {g["ref"] for g in kt.open_gaps(kb, job)}]
    return {"closed": len(targets) - len(still), "targeted": len(targets), "open": still}


def _nx_where(kb: Json, job: str, text) -> list[str]:
    sure, last = kt.sure_level(kb, job), last_round(kb, job)
    after = text("review.nx.to_next", n=sure["to_next"], level=text(NX_LEVELS[sure["level"]])) if sure["to_next"] \
        else text("review.nx.keep_going") * (sure["level"] == 2)
    lines = [text("review.nx.where", level=text(NX_LEVELS[sure["level"] - 1]), next=after).strip()]
    if last:
        lines.append(" ".join([text("review.nx.last", closed=last["closed"], targeted=last["targeted"])]
                              + [text("review.nx.still_open", list=", ".join(last["open"]))] * bool(last["open"])))
    return [*lines, ""]


def _nx_round(kb: Json, learn: Json, text, guide: bool) -> list[str]:
    names = {kt.step_key(s): s["statement"] for s in kb["job_map"]["steps"]}
    plain = guide and text.language == kt.ENGLISH
    names.update({str(o["id"]): plain_outcome(o["statement"]) if plain else o["statement"]
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
        lines += [f"### {n}. {talk}", ""]
        lines += [f"**{text('review.guide.fit')}**", "", *(f"- {h}" for h in hints), ""] * bool(hints)
        learns = [f"- {names[ref]}" for ref in entry["gaps"] if ref in names and ref not in entry.get("traits", [])]
        lines += [f"**{text('review.guide.ask')}**", "", *asks, ""]
        lines += [f"**{text('review.guide.learns')}**", "", *learns, ""] * bool(learns)
    return lines


def next_lines(kb: Json, text) -> list[str]:
    """review.md's Next interviews: where the study stands, the plan's round, and every open gap by group."""
    lines = ["## " + text("review.h.next"), ""]
    for job in kb["core_jobs"]:
        jid, learn = str(job["id"]), kt.learn_of(kb, str(job["id"]))
        gaps = kt.open_gaps(kb, jid)
        lines += [f"**{job['statement']} ({jid})**", ""] * (len(kb["core_jobs"]) > 1) + _nx_where(kb, jid, text)
        if learn and "overview" in kt.stale_layers(kb):
            lines += [f"*{text('review.nx.stale')}*", ""]
        lines += [text("review.nx.enough")] if not gaps else _nx_round(kb, learn, text, False) if learn.get("round") \
            else [text("review.nx.no_plan")]
        for kind, key in NX_GROUPS:
            group = [g for g in gaps if (g["main"] if kind == "main" else not g["main"] and g["kind"] == kind)]
            lines += ["", f"**{text(key, thin=kt.THIN_STEP)}**", ""] * bool(group)
            lines += [f"- {g['ref']} {g['text']} [{len(g['people'])}]" for g in group[:NX_GROUP_MAX]]
            lines += [f"- *{text('review.nx.more', n=len(group) - NX_GROUP_MAX)}*"] * (len(group) > NX_GROUP_MAX)
        lines.append("")
    return lines


GUIDE_MARK = "<!-- written by kb_tool: each rebuild writes it again -->"


def guide_lines(kb: Json, text, job: str | None = None) -> list[str]:
    """interview-guide.md, or one core job's part of it (the map copies that): who to find and what to ask."""
    lines = ["# " + text("review.guide.title", project=kb["meta"].get("project", "")), "",
             text("review.guide.made", date=kt.today(), n=len(kb["interviews"])), "",
             f"**{text('review.guide.use')}**", "",
             *(f"{i}. {text(key)}" for i, key in enumerate(GUIDE_STEPS, 1)), ""]
    for entry in [j for j in kb["core_jobs"] if job in (None, str(j["id"]))]:
        learn = kt.learn_of(kb, str(entry["id"]))
        lines += [f"## {entry['statement']}", ""]
        lines += _nx_round(kb, learn, text, True) if learn.get("round") else [text("review.nx.no_plan"), ""]
    lines += ["## " + text("review.guide.help"), ""]
    for head, *rest in GUIDE_HELP:
        lines += [f"**{text(head)}**", "", *(f"- {text(key)}" for key in rest), ""]
    return lines


def _review_tail(kb: Json, text) -> list[str]:
    lines = []
    stale = [text(LAYER_LABELS[k]) if k in LAYER_LABELS else k.replace("_", " ") for k in kt.stale_layers(kb)]
    if stale:
        lines += [f"*{text('review.out_of_date', layers=text('review.list_sep').join(stale))}*", ""]
    # fixed tags on the sheet's links, holding nothing from the study (the map's pwUrl does the same)
    link = (f"{kt.SITE}?utm_source=productweaver-plugin&utm_medium=review-sheet&utm_campaign=pw-discovery"
            "&utm_content=review-footer")
    footer = text("review.footer", brand_link=f"[{kt.BRAND}]({link})", brand=kt.BRAND,
                  site_link=f"[productweaver.com]({link})")
    lines += ["---", "", f"*{footer}*", ""]
    return lines


def review_lines(kb: Json, since: str, text=None) -> list[str]:
    text = text or kt.Text()
    live_outcomes = [o for o in kb["desired_outcomes"]["outcomes"] if not o.get("merged_into")]
    new_outcomes = {o["id"] for o in kb["desired_outcomes"]["outcomes"] if since and str(o.get("added", "")) >= since}
    return (_review_head(kb, live_outcomes, text) + _review_decisions(kb, text)
            + _review_new(kb, since, new_outcomes, text) + _review_map(kb, live_outcomes, new_outcomes, text)
            + _review_solutions(kb, text) + _review_themes(kb, text) + _review_people(kb, text)
            + next_lines(kb, text) + _review_tail(kb, text))


def cmd_review(args: argparse.Namespace, tool: Any) -> int:
    """Write a plain-language sheet for people who review the KB: what changed, what needs a decision, the map."""
    global kt  # noqa: PLW0603 - kb_tool hands itself over once, here
    kt = tool
    kb = kt.load_kb(args.kb)
    text, missing = kt.study_text(kb, args.kb)
    last = next((c for c in reversed(kb["changelog"]) if c.get("action") in ("merge", "init")), {})
    since = args.since or str(last.get("date", ""))
    out = args.out or os.path.join(kt.output_folder(args.kb), "review.md")
    guide = os.path.join(os.path.dirname(os.path.abspath(out)), "interview-guide.md")
    # the rebuild after a write keeps pw-start's first-round guide: the first overview's plan grows from it
    keep = getattr(args, "keep_guide", False) and not kt.overviews_of(kb) and os.path.isfile(guide)
    if keep:  # a guide kb_tool wrote has no plan to keep
        with open(guide, encoding="utf-8", errors="replace") as handle:
            keep = GUIDE_MARK not in handle.read()
    for path, lines in ((out, review_lines(kb, since, text)),
                        (guide, None if keep else [*guide_lines(kb, text), GUIDE_MARK, ""])):
        if lines is None:
            print(f"kept {path}: it is rebuilt when the study's first overview is written")
            continue
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))
        print(f"wrote {path}")
    args.run.note(out=args.run.relative(out), since=since)
    kt.labels_missing_note(args, kb, missing)
    return 0


# ---------- the overview's skeleton: the file the assistant fills in ----------
QUOTE = {"interview": "<an interview ID>", "quote": "<a quote the KB holds for this core job, copied exactly>"}
TRACK_WHATS = {"why": "why it matters", "tip": "a tip for the calls", "test": "how to test it",
               "later": "what waits until later", "who": "who to tell first", "unknown": "what is still unknown"}


def _skeleton_traits(kb: Json, job: str, word: Any, more: Any) -> list[Any]:
    """The traits of the job's last overview, each with the people sorted into none of its values; else an example."""
    main = [str(r["id"]) for r in kb["interviews"] if kt.main_job(r) == job]
    traits = copy.deepcopy(kt.learn_of(kb, job).get("traits") or [])
    for trait in traits:
        if not isinstance(trait, dict) or not isinstance(trait.get("values"), list):
            continue
        for value in trait["values"]:  # a person moved to another core job leaves this job's traits
            if isinstance(value, dict) and isinstance(value.get("interviews"), list):
                value["interviews"] = [i for i in value["interviews"] if str(i) in main]
        sorted_in = {str(i) for v in trait["values"] if isinstance(v, dict) for i in v.get("interviews") or []}
        left = [i for i in main if i not in sorted_in]
        trait["values"] += [f"<not sorted yet: {', '.join(left)}>"] * bool(left)
    if traits:
        return traits
    value = {"id": "T1.1", "label": word("one kind of person", "role"),
             "interviews": [f"<the IDs of the people of this kind, from {', '.join(main)}; none when nobody yet>"]}
    values = more(f"{kt.TRAIT_VALUES[0]} to {kt.TRAIT_VALUES[1]} values")
    return [{"id": "T1", "name": word("what sets the people apart", "role"), "values": [value, values]},
            more(f"{kt.TRAIT_COUNT[0]} or {kt.TRAIT_COUNT[1]} traits")]


def _skeleton_next(kb: Json, job: str, word: Any, more: Any) -> Json:
    """`next`: the three tracks, and the plan for the next round in `learn`."""
    tracks: Json = {}
    for name, (statuses, fields) in kt.NEXT_TRACKS.items():
        track: Json = {"status": f"<{' or '.join(statuses)}>", "action": word("what to do, starting with a verb",
                                                                               "action")}
        for key in fields:
            track[key] = (word(TRACK_WHATS[key], "rationale") if key not in kt.NEXT_LISTS
                          else [word("a question about the last time it happened", "rationale"),
                                more(f"1 to {kt.NEXT_LISTS[key]} questions")] if key == "ask"
                          else ["<words a customer said, part of a quote>", more(f"1 to {kt.NEXT_LISTS[key]}")])
        tracks[name] = track
    question = {"ask": word("a question about the last time", "question"),
                "listen": word("what to listen for", "listen"), "gaps": ["<the IDs of this entry's gaps it fills>"]}
    entry = {"kind": "new", "count": f"<how many people: a number from {kt.ROUND_COUNT[0]} to {kt.ROUND_COUNT[1]}>",
             "who": word("who to find", "plan_who"), "traits": ["<the trait value IDs they have; or delete this list>"],
             "gaps": [f"<1 to {kt.ROUND_ITEMS} step, outcome or trait value IDs this call fills>"],
             "questions": [question, more(f"1 to {kt.ROUND_ITEMS} questions")]}
    tracks["learn"].update(traits=_skeleton_traits(kb, job, word, more),
                           rests_on=[f"<1 to {kt.RESTS_ON_MAX} outcome IDs the main finding rests on>"],
                           round=[entry, more(f"1 to {kt.ROUND_MAX} kinds of people")])
    return tracks


def overview_skeleton(kb: Json, job: str, style: Any) -> Json:
    """The overview file to fill in: each sentence a <what, at most N words> with this study's own limit, each list
    one item and its count rule. Every <…> left in it is refused by `overview`."""
    def word(what: str, kind: str, drop: str = "") -> str:
        return f"<{what}, at most {style.limits.get(kind, 0)} words" + (f"; or delete this {drop}>" if drop else ">")

    def more(count: str) -> str:
        return f"<{count} in all: add each like the one above, then delete this line>"

    gap = {"label": word("what goes wrong", "theme"), "text": word("what happens then", "rationale"),
           "kind": f"<{' or '.join(kt.GAP_KINDS)}>",
           "solutions": ["<the solution IDs it is about; or delete this list>"], "quote": dict(QUOTE)}
    return {"job": job,
            "executor": {"label": word("what they call themselves", "role"), "text": word("who they are", "who"),
                         "icon": f"<one of: {', '.join(kt.ROLE_ICONS)}>",
                         "others": [word("someone else in the story", "role", "list")]},
            "bottom_line": word("the main finding", "headline"), "why": word("why it happens", "rationale"),
            "opening": word("what a product could change", "rationale"),
            "people": {"answer": word("who you talked to", "headline"),
                       "text": word("more about them", "finding", "line"),
                       "quote": {k: v[:-1] + "; or delete this quote>" for k, v in QUOTE.items()}},
            "today": {"answer": word("how they do it today", "headline"),
                      "text": word("more about it", "finding", "line")},
            "gaps": {"answer": word("where it breaks", "headline"),
                     "items": [gap, more(f"1 to {kt.GAP_MAX} gaps")]},
            "needs": {"answer": word("what they want most", "headline")},
            "focus": {"answer": word("what to build for first", "headline")},
            "next": _skeleton_next(kb, job, word, more)}


def cmd_skeleton(args: argparse.Namespace, kb: Json, tool: Any) -> int:
    """`overview --skeleton JOB`: what the overview needs from the study, then the file to fill in. Writes nothing."""
    global kt  # noqa: PLW0603 - kb_tool hands itself over once, here
    kt = tool
    job = args.skeleton
    if job not in kt.jobs_by_id(kb):
        raise kt.KbError(f"core job {job} is not in the KB", code="overview_file")
    args.run.note(skeleton=True, job=job)
    data = overview_skeleton(kb, job, kt.style_of(kb))
    if args.json:
        print(json.dumps({"ok": True, "job": job, "skeleton": data}, ensure_ascii=False, indent=2))
        return 0
    people = [f"  {r['id']} {r['job_executor']['statement']}" for r in kb["interviews"] if kt.main_job(r) == job]
    print("\n".join([f"CORE JOB {job}: {kt.jobs_by_id(kb)[job]['statement']}", *kt.gap_lines(kb, job),
                     "\nPEOPLE whose main goal it is, for the traits' values:", *people,
                     f"\nFILE TO FILL IN (save as {kt.KB_FOLDER}/patches/{kt.today()}-overview-{job}.json):",
                     json.dumps(data, ensure_ascii=False, indent=2)]))
    return 0
