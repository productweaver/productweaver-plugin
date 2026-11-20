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
    again = [(r, x) for r in kb["interviews"] for x in r.get("interactions") or []
             if since and str(x.get("added", "")) >= since]
    if not (new_interviews or new_outcomes or solution_lines or again):
        return []
    lines = ["## " + text("review.h.new", date=since), ""]
    for record in new_interviews:
        job = kt.main_job(record)
        link = text("review.core_job_ref", id=job) if job else text("review.no_core_job_yet")
        own = text("review.new_interview_job", job=f"*{record['core_functional_job']['statement']}*", link=link)
        lines.append(f"- **{record['id']} {record.get('name', '')}:** {record['job_executor']['statement']} {own}")
    for record, item in again:  # no format is a Transcript, as the merge writes it; no date leaves it out
        fmt = item.get("format") or "Transcript"
        said = text("review.new_again", format=fmt, date=item["date"]) if item.get("date") \
            else text("review.new_again_undated", format=fmt)
        changed = f" {item['changed']}" if item.get("changed") else ""
        lines.append(f"- **{record['id']} {record.get('name', '')}:** {said}{changed}")
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


# ---------- the survey ----------
def _survey() -> Any:
    """kb_survey.py, which computes a survey's figures and state, with kb_tool handed to it."""
    module = kt._sibling("kb_survey")
    module.kt = kt
    return module


def _surveyed_jobs(kb: Json, survey: Any) -> list[str]:
    return [str(job["id"]) for job in kb["core_jobs"] if survey.survey_of(kb, str(job["id"]))]


def _review_unmet(kb: Json, figures: Json, text, mark: str) -> list[str]:
    """What looks unmet, from the estimate: each line says it is an estimate and for how many people."""
    labels = {str(t["id"]): str(t.get("label", "")) for t in kt.themes_of(kb)}
    needs = {n["outcome"]: n for n in figures["needs"]}
    lines = [f"{mark} " + text("review.sv.unmet_h"), ""]
    for ref in figures["unmet"]:
        need = needs[ref]
        where = text("review.list_sep").join([ref] + ([labels[need["theme"]]] if need["theme"] in labels else []))
        lines.append("- " + text("review.sv.unmet_line", need=need["text"], ref=where, n=need["satisfied"],
                                 matters=need["matters"], rated=need["n"], people=figures["people"]))
    if not figures["unmet"]:
        lines.append(text("review.sv.none_unmet"))
    lines.append("")
    return lines + ([text("review.sv.single", n=figures["single"]), ""] if figures["single"] else [])


def _review_questions(kb: Json, entry: Json, text, mark: str) -> list[str]:
    """What the survey asks, step by step (its needs are stored in the job's step order)."""
    steps = kt.steps_by_id(kb)
    lines = [f"{mark} " + text("review.sv.questions_h"), ""]
    last = None
    for need in entry.get("needs") or []:
        step = kt.step_of(str(need.get("outcome")))
        if step != last:
            title = f"{step} {steps.get(step, {}).get('statement', '')}".strip()
            lines += ([""] if last else []) + [f"**{title}**"]
            last = step
        lines.append(f"- {need.get('text', '')} ({need.get('outcome')})")
    return lines + [""]


def _review_survey_job(kb: Json, job: str, survey: Any, text, mark: str) -> list[str]:
    state, figures = survey.status(kb, job), survey.results(kb, job)
    if figures is None:
        lines = [text("review.sv.ready", n=state["needs"], version=state["version"]), ""]
    else:
        cover, possible = figures["coverage"], figures["possible"]
        share = {key: f"{survey.percent(cover[key], possible)}%" for key in ("cells", "said", "context")}
        # a part with no rating is not named: "all from the person's words", never "0% from context"
        key = "review.sv.coverage" if cover["said"] and cover["context"] else \
            "review.sv.coverage_said" if cover["said"] else "review.sv.coverage_context"
        lines = [f"*{text('review.sv.estimate_note', n=figures['people'])}* "
                 + text(key, share=share["cells"], said=share["said"], context=share["context"]), ""]
    new, gone = len(state["new_needs"]), len(state["gone_needs"])
    why = ([text("review.sv.new_needs", n=new)] if new else []) + \
        ([text("review.sv.gone_needs", n=gone)] if gone else []) + \
        ([text("review.sv.estimate_old")] if state["estimate_old"] and figures is not None else [])
    if why:  # only the reasons that apply, each its own sentence
        lines += [f"*{' '.join(why)}*", ""]
    if figures is not None:
        lines += _review_unmet(kb, figures, text, mark)
    return lines + _review_questions(kb, survey.survey_of(kb, job), text, mark)


def _review_survey(kb: Json, text: Any) -> list[str]:
    """The Survey section: a text copy of the map's Survey view. Need texts and counts only, never a quote or a why;
    an estimate says so on every line."""
    survey = _survey()
    jobs = _surveyed_jobs(kb, survey)
    if not jobs:
        return []
    lines = ["## " + text("review.h.survey"), ""]
    many = len(kb["core_jobs"]) > 1
    for job in jobs:
        if many:
            lines += ["### " + text("review.core_job_id", id=job), ""]
        lines += _review_survey_job(kb, job, survey, text, "####" if many else "###")
    return lines


def survey_context_lines(kb: Json) -> list[str]:
    """The SURVEY block of `context`: one line for each core job with a survey, what is out of date first."""
    survey = _survey()
    lines = []
    for job in _surveyed_jobs(kb, survey):
        state, figures = survey.status(kb, job), survey.results(kb, job)
        new, gone = len(state["new_needs"]), len(state["gone_needs"])
        why = ([f"{kt.plural(new, 'new need')} {'is' if new == 1 else 'are'} not in it"] if new else []) + \
            ([f"{kt.plural(gone, 'need')} of it {'is' if gone == 1 else 'are'} no longer in the study"]
             if gone else []) + (["the estimate is older than the study"] if state["estimate_old"] else [])
        facts = (f"version {state['version']}, {kt.plural(state['needs'], 'need')}, about "
                 f"{kt.plural(state['minutes'], 'minute')}, "
                 + (f"estimate for {kt.plural(figures['coverage']['cells'], 'rating')}" if figures
                    else "no estimate yet"))
        lines.append(f"SURVEY {job}{' [out of date]' if why else ''}: " + "; ".join([*why, facts]))
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


def _nx_person(kb: Json, person: str) -> tuple[str, str]:
    """The name of someone a follow-up asks again, and the date of their latest conversation ("" when unknown). As for
    who uses a solution now, dates decide only when each of their conversations has a YYYY-MM-DD date (kt.ix_dates);
    otherwise it is the highest-numbered conversation's date, as it is written."""
    record = next((r for r in kb["interviews"] if str(r.get("id")) == person), {})
    dates = [date for ref, date in kt.ix_dates(kb).items() if ref.split("#")[0] == person and date]
    if not dates:
        numbered = [(x.get("n") if x is not record else 1, str(x.get("date") or "")) for x in kt.conversations(record)
                    if isinstance(x, dict) and (x is record or kt._is_int(x.get("n")))]
        dates = [max(numbered)[1]]
    return str(record.get("name") or person), max(dates, default="")


def _nx_round(kb: Json, learn: Json, text, guide: bool) -> list[str]:
    names = {kt.step_key(s): s["statement"] for s in kb["job_map"]["steps"]}
    plain = guide and text.language == kt.ENGLISH
    names.update({str(o["id"]): plain_outcome(o["statement"]) if plain else o["statement"]
                  for o in kb["desired_outcomes"]["outcomes"]})
    names.update({v["id"]: f"{t['name']}: {v['label']}" for t in learn["traits"] for v in t["values"]})
    lines = []
    for n, entry in enumerate(learn["round"], 1):
        again = entry.get("kind") == "follow_up"  # asks someone in the study again: no count, who or traits
        name, date = _nx_person(kb, str(entry.get("interview"))) if again else ("", "")
        talk = text("review.nx.ask", name=name) if again else text("review.nx.talk", n=entry["count"], who=entry["who"])
        asks = [f"{i}. {q['ask']}  \n   *{text('review.nx.listen')}:* {q['listen']}"
                for i, q in enumerate(entry["questions"], 1)]
        if not guide:
            lines += [f"{n}. **{talk}** ({', '.join(entry['gaps'])})",
                      *("   " + a.replace("\n", "\n   ") for a in asks)]
            continue
        hints = [names[ref] for ref in entry.get("traits", [])]
        lines += [f"### {n}. {talk}", ""]
        lines += [text("review.guide.last_heard", date=date), ""] * bool(date)
        lines += [f"**{text('review.guide.fit')}**", "", *(f"- {h}" for h in hints), ""] * bool(hints)
        learns = [f"- {names[ref]}" for ref in entry["gaps"] if ref in names and ref not in entry.get("traits", [])]
        opening = [text("review.guide.again", n=len(entry["questions"])), "",
                   text("review.guide.again_record"), ""] * again  # a call asks to record first
        lines += [f"**{text('review.guide.ask')}**", "", *opening, *asks, ""]
        block = [*learns, ""] * bool(learns) + [text("review.guide.again_how", name=name), ""] * again
        lines += [f"**{text('review.guide.learns')}**", "", *block] * bool(block)
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
            + _review_solutions(kb, text) + _review_themes(kb, text) + _review_survey(kb, text)
            + _review_people(kb, text)
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
    print("\n".join([f"CORE JOB {job}: {kt.jobs_by_id(kb)[job]['statement']}", *gap_lines(kb, job),
                     "\nPEOPLE whose main goal it is, for the traits' values:", *people,
                     f"\nFILE TO FILL IN (save as {kt.KB_FOLDER}/patches/{kt.today()}-overview-{job}.json):",
                     json.dumps(data, ensure_ascii=False, indent=2)]))
    return 0


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


def person_line(person: Json) -> str:
    links = person["job"] or "no core job" + (f" ({person['unlinked_reason']})" if person["unlinked_reason"] else "")
    also = sorted({r["job"] for r in person["related"] if r["job"] and r["job"] != person["job"]})
    return f"  {person['id']} {person['name']}: {person['core_functional_job']} -> {links}" + \
        (f"; also {', '.join(also)}" if also else "") + (f" [{', '.join(person['tags'])}]" * bool(person["tags"])) + \
        ("; later: " + ", ".join(map(_later, person["interactions"])) if person.get("interactions") else "")


def _later(item: Json) -> str:
    """A later conversation on a person's line in `context`: "#2 Email 2026-04-05". No format is a Transcript, as the
    merge writes it; no date leaves it out."""
    date = f" {item['date']}" if item.get("date") else ""
    return f"#{item.get('n')} {item.get('format') or 'Transcript'}{date}"


def _print_jobs(data: Json) -> None:
    print(f"PROJECT {data['project']}  language={data['language']}  interviews={data['interview_count']}  "
          f"core jobs={len(data['core_jobs'])}")
    if data.get("labels_missing"):
        print(f"LABELS: {data['labels_missing']} labels of the map and the review sheet have no {data['language']} "
              f"text yet; write them first: kb_tool labels {kt.KB_HOME}")
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


def _print_overview(data: Json) -> None:
    if not data["overview"]:
        return
    old = "overview" in data["stale"] or any(not entry["executor"] for entry in data["overview"])
    print("\nOVERVIEW" + (" [out of date]" if old else ""))
    for entry in data["overview"]:
        about = f" (about: {entry['executor']})" if entry["executor"] else \
            " (written before the map showed who the study is about: write it again)"
        print(f"{entry['job']} written {entry['written']}: {entry['bottom_line']}{about}")


def gap_lines(kb: Json, job: str) -> list[str]:
    """One core job's OPEN GAPS, as `context` and `overview --skeleton` print them; none when nothing is open."""
    gaps = kt.open_gaps(kb, job)
    if not gaps:
        return []
    sure = kt.sure_level(kb, job)
    after = f"{sure['to_next']} more reach the next" if sure["to_next"] else "next: new ones stop adding needs"
    lines = ["", f"OPEN GAPS for core job {job} (main finding first; next.learn's round should cover the top ones)",
             f"  level {sure['level']} of 3 after {sure['conversations']} conversations"
             + f"; {after}" * (sure["level"] < 3)]
    for g in gaps:
        who = f"people {len(g['people'])}: {', '.join(g['people'])}" if g["people"] else "nobody yet"
        lines.append(f"  {g['ref']} [{g['kind']}{', main' * g['main']}] {g['text']}  ({who})")
    return lines


def print_context(kb: Json, data: Json) -> None:
    """The text `context` prints after its JSON branch."""
    _print_jobs(data)
    for job in data["open_gaps"]:
        lines = gap_lines(kb, job)
        if lines:
            print("\n".join(lines))
    _print_solutions(data["current_solutions"])
    _print_themes(data["value_themes"], "value_themes" in data["stale"])
    surveys = survey_context_lines(kb)
    if surveys:
        print("\n" + "\n".join(surveys))
    _print_overview(data)
    if data["segments"]:
        print("\nSEGMENTS: " + "; ".join(f"{k}={v}" for k, v in data["segments"].items()))
    if data["people"]:
        print("\nPEOPLE AND THEIR JOBS (their own core job -> the core job it rolls up to)")
        for person in data["people"]:
            print(person_line(person))
    print("\nPROCESSED FILES: " + ", ".join(data["processed_files"]))
    if data["pending_proposals"]:
        pending = "; ".join(f"{p['id']} {p['type']} {p['target']}" for p in data["pending_proposals"])
        print(f"\nPENDING PROPOSALS: {pending}")
    if data["stale"]:
        print("\nSTALE LAYERS: " + ", ".join(data["stale"]))
