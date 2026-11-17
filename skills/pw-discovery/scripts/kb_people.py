"""Later conversations with someone already in the study: a follow-up call, an email or a chat with the same person.

A person keeps one record in `interviews`. Its own `file`, `sha256`, `date` and `format` are the first conversation;
each later one is an entry of its `interactions` list, numbered from 2 (`n`). A quote from a later conversation carries
`"interaction": n` and is checked against that conversation's file only, which this module finds under the reference
"<id>#<n>", such as "02#2".

A patch adds one under its `interactions` key: it names the person and the file, and evidence elsewhere in the patch
cites the entry's key. This module resolves and checks those entries for the merge. It also checks a planned one: a
`follow_up` entry of the overview's plan for the next round (`next.learn.round`), which asks someone in the study again.
And it checks every new interview of a patch: a name the study already holds (`same_person`), and an email or a chat
whose file still holds contact details (`contact_details`).

It lives apart from kb_tool.py so the main script stays under the directory's 256 KiB file limit. kb_tool loads it for
a study that holds later conversations, a patch that adds one or new interviews, and an overview that plans a
follow-up, and hands it the kb_tool module (`kt`), whose helpers it uses."""
from __future__ import annotations

import os
import re
import unicodedata
from typing import Any

Json = dict[str, Any]
kt: Any = None  # the kb_tool module, set by kb_tool's _people()

FORMATS = ("Transcript", "Notes", "Transcript + notes", "Email", "Chat")  # a conversation's format; patch-schema.json
PRIVATE = ("Email", "Chat")  # private messages: the study keeps only a copy with no address and no header line
STORED = ("n", "format", "date", "file", "sha256", "added", "changed")  # what a record's `interactions` item keeps
OWN_QUOTES = {"job_executor_evidence": "job_executor", "core_functional_job_evidence": "core_functional_job"}
FOLLOW_UP = ("kind", "interview", "gaps", "questions")  # a planned follow-up's keys, in the order the KB stores them
NOT_FOLLOW_UP = ("count", "who", "traits")  # a `new` entry's keys: they describe people still to find
ONE_PERSON = "a follow_up names one person in interview, with no count, who or traits"
_ADDRESS = re.compile(r"[^\s@<>()\"']+@[^\s@<>()\"']+\.[A-Za-z]{2,}")
_HEADER = re.compile(r"^[ \t>]*(?:from|to|cc|bcc|subject|sent):", re.IGNORECASE | re.MULTILINE)


def contact_problem(text: str) -> str | None:
    """What a saved email or chat must no longer hold: "an email address", else "a header line" (a line that starts
    with From:, To:, Cc:, Bcc:, Subject: or Sent:, in any case, after spaces and >), else None. A header in another
    language, such as Von:, is not on the list, but the address it carries is."""
    if _ADDRESS.search(text):
        return "an email address"
    return "a header line" if _HEADER.search(text) else None


def name_key(name: str) -> str:
    """A name as compared: accents and case ignored, runs of white space made one space."""
    plain = "".join(c for c in unicodedata.normalize("NFKD", str(name)) if not unicodedata.combining(c))
    return " ".join(plain.casefold().split())


def check_new_people(kb: Json, patch: Json, transcripts: Any, report: Any) -> None:
    """Check each new interview: a name already in the study (or earlier in this patch) is refused unless the entry
    says "same_name_ok": true, and an Email or Chat file must hold no address or header line. The entry's
    `same_name_ok` is removed, so the record never stores it. An entry whose file is already in the study is left
    to the merge, which skips it, so a batch can be re-run."""
    held = {mark for r in kb["interviews"] for i in kt.conversations(r)
            for mark in (os.path.basename(str(i.get("file", ""))), i.get("sha256")) if mark}
    names = {name_key(r.get("name", "")): f"interview {r['id']}" for r in kb["interviews"][::-1]}
    for entry in patch["interviews"]:
        ok, key, file = entry.pop("same_name_ok", None), str(entry.get("key")), str(entry.get("file", ""))
        name, transcript = os.path.basename(file), None
        if transcripts.has(name):
            transcript = transcripts.get(name)
        if name in held or (transcript and transcript.sha256 in held):
            continue
        who, label = name_key(entry.get("name", "")), str(entry.get("name"))
        if who in names and ok is not True:
            report.error(f"interview {key}: {label} is already in the study as {names[who]}; send this file under "
                         'interactions, or add "same_name_ok": true if it is another person', code="same_person")
        names.setdefault(who, f"interview {key}")
        problem = contact_problem(kt.read_text(transcript.path)) if transcript and entry.get("format") in PRIVATE \
            else None
        if problem:
            report.error(f"interview {key}: {name} still holds {problem}; save a copy without addresses and header "
                         f"lines in {kt.KB_FOLDER}/{kt.COPIES}/ and name that file", code="contact_details")


def _held(kb: Json, plan: Any) -> dict[str, str]:
    """Each file name and content hash that the study or this patch's new interviews hold, to its person's ID."""
    held: dict[str, str] = {}
    for record in kb["interviews"] + plan.new_interviews:
        for item in kt.conversations(record):
            for mark in (os.path.basename(str(item.get("file", ""))), item.get("sha256")):
                if mark:
                    held.setdefault(str(mark), str(record["id"]))
    return held


def resolve_interactions(kb: Json, patch: Json, transcripts: Any, plan: Any, report: Any) -> None:
    """Give each of the patch's later conversations its person and number (n), skip it when its file is already in
    the study, or refuse it. Runs in resolve_interviews, once the new interviews have their IDs. One that names a new
    interview the merge skipped, because the study already holds its file, goes to the person who holds it
    (plan.held_as), so a batch can be re-run with a follow-up added."""
    records = {str(r["id"]): r for r in kb["interviews"] + plan.new_interviews}
    keys, held, person_ref = {str(i.get("key")) for i in patch.get("interviews") or []}, _held(kb, plan), {}
    for entry in patch["interactions"]:
        key, ref = str(entry.get("key")), str(entry.get("interview"))
        name = os.path.basename(str(entry.get("file", "")))
        if key in keys:
            report.error(f"interaction key '{key}' is used twice in the patch", code="key_duplicate")
            continue
        keys.add(key)
        if key in records:
            report.error(f"interaction key '{key}' is already an interview ID; use a key such as f1", code="key_is_id")
            continue
        person = plan.keymap.get(ref) or plan.held_as.get(ref)
        if person is None:
            report.error(f"interaction {key}: interview {ref} is not in the KB or in this patch's interviews",
                         code="interaction_person")
            continue
        transcript = transcripts.get(name) if transcripts.has(name) else None
        if transcript is None:
            report.error(f"interaction {key}: file '{name}' not found in {kt.KB_FOLDER}/{kt.COPIES}/ or under "
                         "--transcripts", code="transcript_missing")
            continue
        owner = held.get(name) or held.get(transcript.sha256)
        if owner:
            plan.skipped[key] = f"already in the KB as interview {owner}"
            report.warn(f"skip {name}: {plan.skipped[key]}", code="interview_skipped")
            continue
        record, fmt, date = records[person], str(entry.get("format") or "Transcript"), str(entry.get("date"))
        mine = [x for x in plan.interactions if x["interview"] == person]
        had = {(str(x.get("date")), str(x.get("format") or "Transcript")) for x in kt.conversations(record) + mine}
        if (date, fmt) in had and entry.get("another") is not True:
            report.error(f"interaction {key}: {record.get('name')} already has a {fmt} on {date}; if this is another "
                         'conversation, add "another": true', code="same_interaction")
            continue
        problem = contact_problem(kt.read_text(transcript.path)) if fmt in PRIVATE else None
        if problem:
            report.error(f"interaction {key}: {name} still holds {problem}; save a copy without addresses and header "
                         f"lines in {kt.KB_FOLDER}/{kt.COPIES}/ and name that file", code="contact_details")
            continue
        numbers = [x.get("n") for x in (record.get("interactions") or []) + mine if kt._is_int(x.get("n"))]
        n = max([1, *numbers]) + 1
        plan.ix_keys[key], plan.texts[f"{person}#{n}"] = (person, n), transcript.text
        person_ref[key] = ref if ref in plan.keymap else person  # a skipped interview's key: the ID that holds it
        if not transcripts.is_copy(transcript):
            plan.copies.append(transcript.path)
        plan.interactions.append({"key": key, "interview": person, "n": n, "format": fmt, "date": date,
                                  "file": f"{kt.COPIES}/{name}", "sha256": transcript.sha256, "added": kt.today(),
                                  **({"changed": entry["changed"]} if entry.get("changed") else {})})
        held[name] = held[transcript.sha256] = person
    provenance = patch.get("provenance")
    if isinstance(provenance, dict) and isinstance(provenance.get("transcripts_read"), list):
        # the person as the patch names them (a KB ID, or a new interview's key), which resolve_provenance reads
        provenance["transcripts_read"] = [person_ref.get(str(r), r) for r in provenance["transcripts_read"]]


def settle_refs(patch: Json, plan: Any) -> None:
    """Cite each later conversation as the KB stores it: every item of the patch whose `interview` is an interaction
    key ("f1") names the person and the conversation's number instead ({"interview": "02", "interaction": 2})."""
    stack: list[Any] = [patch]
    while stack:
        node = stack.pop()
        if isinstance(node, list):
            stack.extend(node)
        elif isinstance(node, dict):
            if str(node.get("interview")) in plan.ix_keys:
                node["interview"], node["interaction"] = plan.ix_keys[str(node["interview"])]
            stack.extend(node.values())


def apply_interactions(kb: Json, patch: Json, plan: Any) -> list[Json]:
    """Write each later conversation into its person's record: the conversation itself (number, format, date, file,
    hash, when added and what changed), its new tags, and what it adds to the person's own statements, every quote
    marked with the conversation's number. Runs in apply_patch, once the new interviews are in the KB. Returns
    [{"interview": "02", "n": 2}, ...] for the changelog."""
    records = {str(r["id"]): r for r in kb["interviews"]}
    entries = {str(e.get("key")): e for e in patch.get("interactions") or []}
    for item in plan.interactions:
        record, entry = records[item["interview"]], entries[item["key"]]
        record.setdefault("interactions", []).append({k: item[k] for k in STORED if k in item})
        for tag in entry.get("tags") or []:
            if tag not in record.get("tags", []):
                record.setdefault("tags", []).append(tag)
        _add_statements(record, entry, item["n"])
    return [{"interview": item["interview"], "n": item["n"]} for item in plan.interactions]


def _add_statements(record: Json, entry: Json, n: int) -> None:
    """What conversation n adds to the person's own statements. A quote joins the statement it backs; a job or
    feeling that matches one the person already has (as normalized words) joins it, any other is added."""
    for fld, own in OWN_QUOTES.items():
        if entry.get(fld):
            _add_quotes(record[own], entry[fld], n)
    for fld in ("related_jobs", "emotional_jobs", "social_jobs"):
        for job in entry.get(fld) or []:
            said, mine = kt.norm(str(job.get("statement", ""))), record.setdefault(fld, [])
            same = next((j for j in mine if kt.norm(str(j.get("statement", ""))) == said), None)
            if same is None:
                same = {**job, "evidence": []}
                mine.append(same)
            _add_quotes(same, job.get("evidence"), n)


def _add_quotes(statement: Json, items: list[Json] | None, n: int) -> None:
    """Add quotes from conversation n to one of the person's own statements, except words it already holds."""
    have = {kt.norm(str(e.get("quote", ""))) for e in statement.setdefault("evidence", [])}
    for item in items or []:
        words = kt.norm(str(item.get("quote", "")))
        if words not in have:
            statement["evidence"].append({"source": item["source"], "quote": item["quote"], "interaction": n})
            have.add(words)


def lookup_ref(kb: Json, plan: Any, transcripts: Any, report: Any, reference: str) -> tuple[str | None, str | None]:
    """The normalized text a quote from a later conversation is checked against: (text, None), or (None, why). The
    reference is a key of this patch's interactions ("f1"), or a person with the conversation's number ("02#2")."""
    if reference in plan.ix_keys:
        person, n = plan.ix_keys[reference]
    else:
        who, _, n = reference.partition("#")
        if who in plan.skipped:
            return None, f"interview {who} was skipped ({plan.skipped[who]})"
        person = plan.keymap.get(who)
        if person is None:
            return None, f"unknown interview '{who}': not an ID in the KB and not a key in this patch's interviews"
    ref = f"{person}#{n}"
    if ref not in plan.texts:
        record = next((r for r in kb["interviews"] if str(r["id"]) == person), {})
        item = next((x for x in record.get("interactions") or [] if str(x.get("n")) == str(n)), None)
        if item is None:
            return None, f"interview {person} has no conversation {n}"
        transcript = transcripts.get(str(item.get("file", "")))
        plan.texts[ref] = transcript.text if transcript else None
        if transcript and item.get("sha256") and transcript.sha256 != item["sha256"]:
            report.warn(f"transcript for interview {person}, conversation {n} ({item.get('file')}) changed since it "
                        "was added; run validate to re-check its quotes", code="transcript_changed")
    if plan.texts[ref] is None:
        return None, (f"transcript for interview {person}, conversation {n} not found in "
                      f"{kt.KB_FOLDER}/{kt.COPIES}/ or under --transcripts")
    return plan.texts[ref], None


def check_interactions(patch: Json, plan: Any, ctx: Any) -> None:
    """Check what each later conversation adds (its wording, and its quotes against its own file), and that no
    interaction key stands where the patch must name a person."""
    for entry in patch.get("interactions") or []:
        key = str(entry.get("key"))
        if key not in plan.ix_keys:
            continue
        label = f"interaction {key}"
        if entry.get("changed"):
            kt.clarity(str(entry["changed"]), "rationale", f"{label} changed", ctx.style, ctx.report)
        for fld in OWN_QUOTES:
            if entry.get(fld):
                ctx.checker.check([{**e, "interview": key} for e in entry[fld]], f"{label} {fld}", ctx.report)
        for fld in ("related_jobs", "emotional_jobs", "social_jobs"):
            for job in entry.get(fld) or []:
                statement = str(job.get("statement", ""))
                kind = "job" if fld == "related_jobs" else "feeling"
                kt.clarity(statement, kind, f"{label} {fld}", ctx.style, ctx.report)
                ctx.checker.check([{**e, "interview": key} for e in job.get("evidence") or []],
                                  f"{label} {fld}: {kt.short(statement, 40)}", ctx.report)
                if fld == "related_jobs":
                    kt._check_link(job.get("job"), f"{label} related job", ctx)
    _check_key_places(patch, plan, ctx)


def _check_key_places(patch: Json, plan: Any, ctx: Any) -> None:
    """An interaction key names a conversation. Where a proposal needs a person (a new_core_job's interviews, a
    relink_interview target), it is refused, and the message names the person as the patch does."""
    refs = {str(e.get("key")): str(e.get("interview")) for e in patch.get("interactions") or []}
    for proposal in patch.get("proposed_changes") or []:
        named = list(proposal.get("interviews") or [])
        if proposal.get("type") == "relink_interview":
            named.append(proposal.get("target"))
        for ref in named:
            if str(ref) in plan.ix_keys:
                ctx.report.error(f"{ref} is a later conversation; name the person, interview {refs[str(ref)]}",
                                 code="interaction_ref")


def interaction_texts(kb: Json, transcripts: Any, report: Any) -> tuple[dict[str, str | None], dict[str, str]]:
    """Normalized text per later conversation ("02#2"), plus {"02#2": new sha256} for files that changed since they
    were added. A missing file is an error that names the person and the conversation."""
    texts: dict[str, str | None] = {}
    drifted: dict[str, str] = {}
    for record in kb["interviews"]:
        kb_id = str(record["id"])
        for item in record.get("interactions") or []:
            ref, name = f"{kb_id}#{item.get('n')}", str(item.get("file", ""))
            transcript = transcripts.get(name)
            texts[ref] = transcript.text if transcript else None
            if transcript is None:
                report.error(f"interview {kb_id}, conversation {item.get('n')}: file {name} not found in "
                             f"{kt.KB_FOLDER}/{kt.COPIES}/", code="transcript_missing")
            elif item.get("sha256") and transcript.sha256 != item["sha256"]:
                drifted[ref] = transcript.sha256
    return texts, drifted


def rehash(kb: Json, ref: str, digest: str) -> None:
    """Store the new content hash of the later conversation `ref` ("02#2") names, once its quotes still match."""
    kb_id, n = ref.split("#", 1)
    for record in kb["interviews"]:
        if str(record["id"]) == kb_id:
            for item in record.get("interactions") or []:
                if str(item.get("n")) == n:
                    item["sha256"] = digest


# ---------- a planned follow-up: the overview's plan asks someone in the study again ----------
def follow_up_entry(ctx: Any, raw: Json, where: str, refs: set[str]) -> Json:
    """A `follow_up` entry of next.learn.round, checked as `overview` checks a `new` one: one person of the core job
    (an ID that kt.job_people lists, padded as the overview's quotes are), 1 to 4 gaps among `refs`, and 1 to 4
    questions. It has no count, who or traits: those describe people still to find."""
    ref = raw.get("interview")
    person = str(ref).zfill(ctx.width) if kt._is_int(ref) else str(ref or "")
    if any(key in raw for key in NOT_FOLLOW_UP) or not person:
        ctx.report.error(f"{where}: {ONE_PERSON}", code="overview_shape")
    entry = kt._ov_mapping(ctx, {"entry": {k: v for k, v in raw.items() if k not in NOT_FOLLOW_UP}}, "entry",
                           FOLLOW_UP, where)
    if person and person not in kt.job_people(ctx.kb, ctx.job):
        ctx.report.error(f"{where}: interview {person} is not one of the people of core job {ctx.job}; take the ID "
                         "from `context`", code="overview_ref")
    gaps = kt._ov_refs(ctx, entry.get("gaps"), refs, kt.ROUND_ITEMS, f"{where} gaps")
    asks = entry.get("questions")
    if not isinstance(asks, list) or not 1 <= len(asks) <= kt.ROUND_ITEMS:
        ctx.report.error(f"{where}: questions must be a list of 1 to {kt.ROUND_ITEMS}", code="overview_count")
    return {"kind": "follow_up", "interview": person, "gaps": gaps,
            "questions": [kt._ov_question(ctx, q, gaps, f"{where} question {i}")
                          for i, q in enumerate(asks if isinstance(asks, list) else [], 1)]}


def warn_no_gain(ctx: Any, entries: list[Json], gaps: list[Json]) -> None:
    """Asking someone again backs up a gap only where they are not counted yet: it adds no second voice where they
    already are, and no kind of person the study has not heard yet (a trait value gap)."""
    open_gaps = {g["ref"]: g for g in gaps}
    names = {str(r["id"]): str(r.get("name") or r["id"]) for r in ctx.kb["interviews"]}
    for n, entry in enumerate(entries, 1):
        person = entry.get("interview")
        for ref in entry["gaps"] if entry["kind"] == "follow_up" and person else []:  # no person: already refused
            gap = open_gaps.get(ref)
            if gap and (gap["kind"] == "who" or person in gap["people"]):
                ctx.report.warn(f"next.learn round {n}: {names.get(person, person)} cannot back up {ref}; they are "
                                "already counted there, or it needs another kind of person", code="follow_up_no_gain")
