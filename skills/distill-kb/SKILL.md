---
name: distill-kb
description: Turn raw customer interview transcripts into Outcome-Driven Innovation (ODI) knowledge and fold it into a YAML knowledge base that grows with every batch. Use whenever someone shares new interview transcripts or notes (md, txt, docx, pdf) and wants jobs-to-be-done extracted, job executors and core jobs identified, job steps or desired outcomes updated, the tools and workarounds people use today collected and grouped, evidence quotes attached, or an existing ODI/JTBD knowledge base updated or started. Also use for "add these interviews to the KB", "update the job map with the new calls", "process this week's discovery interviews", or starting an ODI study for a new client, even if the user doesn't say "ODI" or "YAML". From Product Weaver (productweaver.com).
---

# distill-kb: fold interviews into an ODI knowledge base

*A free skill from [Product Weaver](https://productweaver.com).*

One YAML file is the knowledge base (KB). Each run reads new transcripts, extracts ODI knowledge with verbatim evidence, and merges it into the KB through `scripts/kb_tool.py`. The script checks every quote against its transcript and refuses the whole merge if one does not match. That makes the KB safe to build on over many runs: nothing in it is paraphrased evidence or a duplicate.

## Running the script

The script needs Python 3.9 or newer and PyYAML. It finds its schemas and the map template next to itself, so run it from the root of the workspace, where the study lives:

```
uv run --locked <skill folder>/scripts/kb_tool.py <command> ...   # no setup: uv installs PyYAML the first time
python3 <skill folder>/scripts/kb_tool.py <command> ...           # when PyYAML is installed (python3 -m pip install pyyaml==6.0.3)
```

Below, `kb_tool` stands for either line. Do not write plain `python`; many machines do not have it. `.docx` transcripts need `python-docx` and `.pdf` transcripts need `pypdf`. Add them with `--with python-docx==1.2.0` or `--with pypdf==6.21.4`, for example `uv run --locked --with pypdf==6.21.4 <skill folder>/scripts/kb_tool.py ...`.

Work where the files live: if the transcripts and the KB are on the user's computer, run the commands in a shell on that computer. Copy the tool into `.pw-kb/tools/` only when that machine cannot reach the skill folder. Then copy `scripts/kb_tool.py`, `scripts/kb_tool.py.lock`, `references/kb-schema.json`, `references/patch-schema.json` and `assets/discovery-map-template.html` together and keep them together. `kb_tool --version` shows which version a copy is, and every KB records the version that last wrote it in `meta.tool_version`.

## What a run changes, and what it leaves alone

- **Writes (evidence layers):** interviews, job executor, core functional job, related, emotional and social jobs per interview, and each new interview's links to the study's core jobs; new evidence on existing job steps and outcomes; new outcomes; current solutions (what people use today for each step, and what they stopped using), with their groups.
- **Proposes, never applies:** anything that changes the shared structure. That covers a new core job, a new job step, a reworded step, outcome or core job, a merge of two outcomes, a moved outcome or step, a changed link of an earlier interview, a new segment, two solutions that are one, a solution in the wrong group, or a renamed solution or group. These go to `proposed_changes` with status `pending`. The user decides, then `kb_tool apply` acts.
- **Flags, never rewrites:** derived layers (`survey`, `simulation`, `value_themes`, `use_cases`). The script marks them `stale: true` with a reason. They are rebuilt on request, not on every run.

The exception is a brand-new KB with no core job yet. Then the run proposes the core job or jobs and their job maps as a `bootstrap`, marked `status: proposed`, so the user can review them. The merge also files one `confirm_core_job` decision per core job, saying how many people back it. Approving it marks the job approved.

## One core job or several

Most studies have one core job. When the people interviewed do different jobs, for example restaurant owners who order ingredients and kitchen managers who staff each shift, the study has several. Each core job has a letter (`A`, `B`…) and its own job map, so every step and outcome ID starts with its job's letter: step `B.2`, outcome `B.2.3`. The letter is there even with one job.

Every interview's own core functional job links to the core job it rolls up to (`job: "B"`). That is the person's main job. A related job may link to another core job, so one person can belong to several. An interview whose job fits none of them stays unlinked, with the reason in its core functional job's `unlinked_reason`. When the person is linked later, the tool moves that reason into history. How to decide whether two people share a core job is in `references/pw-rules.md`, "One job or several".

## Where the study lives

Everything the skill makes goes into one folder, `.pw-kb/`, at the root of the workspace: the folder the session started in (in Claude Code, the project folder). One workspace holds one study.

```
.pw-kb/
  pw-kb.yaml           the knowledge base (KB)
  transcripts/         a copy of every transcript the KB quotes; merge makes it
  patches/             one file per batch, the audit trail
  backups/             the KB before each write; the newest 20 are kept
  logs/kb_tool.jsonl   one line per run of the tool
  review.md            the review sheet
  discovery-map.html   the interactive map
```

Run every command from the workspace root, with the paths as shown. The tool refuses a KB anywhere else. Never write the skill's files outside `.pw-kb/`. The user's own transcripts stay where they are; the merge copies them in.

## Workflow

### 1. Find the KB and the transcripts

The KB is `.pw-kb/pw-kb.yaml`. Ask where the new transcripts are only if they cannot be found.

No KB yet: `kb_tool init .pw-kb/pw-kb.yaml --project "<name>"`. Add `--interviewer "<name>"` only when the user or the transcripts say who ran the interviews; never fill it in from anywhere else.

`.pw-kb/` holds interviewees' names, their words and their transcripts. When `init` prints a `git:` line, the workspace is a git repository: ask the user once whether to share the study through git. If they say no, write `.pw-kb/.gitignore` containing the single line `*`. Do not ask again later.

**A study made by an earlier version of the skill** sits in a `KB/` folder, with its transcripts in `Interviews/` next to it. The tool refuses it with a message to run `migrate`. Run, from the workspace root:

```
kb_tool migrate <study>/KB/<file>.yaml --to .pw-kb/pw-kb.yaml --transcripts <study>/Interviews
```

It copies the transcripts, moves the KB, patches, backups, logs, review sheet and map into `.pw-kb/`, renames the KB `pw-kb.yaml` and keeps the old file as a backup. If a transcript is missing, or `.pw-kb/` already holds a study, it moves nothing and says why. Then tell the user where the study is now and what was left in the old folder, and ask about git as above.

### 2. Load the current structure

```
kb_tool context .pw-kb/pw-kb.yaml            # add --json for the same information as one JSON object
```

This prints each core job with its steps, outcomes and IDs, then the current solutions by group, every person with their own core job and the core job it links to, the segments, the files already processed, pending proposals and stale layers. Map new evidence against this. Skip any transcript whose file is in "processed files". The script also skips it, matching by file name and content hash, so re-running the same batch never double-counts.

A KB with an older schema is refused with a message to run `kb_tool migrate .pw-kb/pw-kb.yaml`; moving an older study upgrades it in the same step. When either says it migrated from schema version 1, tell the user: the core job is now core job A, and every step and outcome ID gained the letter, so `6.3` is now `A.6.3`.

### 3. Read each new transcript in full, then extract

Read the whole transcript before writing anything. The rules for each statement are in `references/pw-rules.md`; read that file once per session, starting with "Write for the reviewer first". Founders, product managers, domain experts and architects will review these statements, so each one should be short, plain and land on the first read. The merge blocks statements that are too long or carry asides. In short:

- **Per interview:** the job executor (who they are, in this market), their core functional job (verb + object + context, no solution, no success words), related jobs, emotional jobs ("feel…", "avoid feeling…") and social jobs ("be seen as…"). Each needs 1 to 3 supporting quotes. If there is no evidence for a job type, use an empty list. Do not infer.
- **Which core job:** ask "why?" of the person's own core job until it meets one of the study's core jobs. Link it there with `job`. Link a related job too when it is another core job of the study. If none fits, leave `job` out and raise a `new_core_job` proposal that lists the interview, or, when the person carries out none of the study's jobs, say why in `unlinked_reason` on their `core_functional_job`. For example, a driver whose carrier picks the loads does not plan loads. Their quotes still count as evidence for the steps they do perform.
- **First batch:** decide the core jobs from all the interviews before you link anyone. Write each person's own core job, group the ones that meet, then settle each person left over, as in `references/pw-rules.md`, "The odd one out". Bootstrap every core job you found, each with its own steps. Letter them by how many people have the job as their main job, the most first: that one is `A`. On a tie, the job whose first interview comes first. Number each job's steps in stage order.
- **Against the shared structure:** a passage about *doing* a step goes to `step_evidence`, under the core job it serves. A passage about how they judge success or failure goes to `outcome_evidence` when an existing outcome covers it, and to `new_outcomes` only when none does. Prefer existing outcomes: compare by the object of control, not the wording. A near-duplicate outcome splits the evidence and weakens both.
- **Current solutions:** whenever someone says what they use to do a step, or what they stopped using, record it: a product, an everyday tool, other people or their own method. Name it as they do, link it to the step it serves and put it in the group of solutions that compete for the same work, with one sentence on why they belong together. Cite a solution `context` already lists by its ID. The rules are in `references/pw-rules.md`, "Current solutions".
- **Structural signals go to `proposed_changes`:** an activity no step covers, a step or outcome the new evidence shows is worded wrong, two outcomes that are really one, a step under the wrong core job, a core job the study lacks, an earlier interview linked to the wrong job, a new kind of executor or segment. Give each a rationale and evidence. Every target you name must exist in `context` output: the merge refuses a proposal that points at a missing step, outcome, core job or interview.

### 4. Quote exactly

Copy quotes character for character from the transcript. Trim to the shortest span that carries the point, but never stitch two spans together or tidy the grammar. The comparison ignores differences in whitespace, curly versus straight quotes, dashes, ellipses and markdown markers, so you do not need to reproduce those. Text pulled from a PDF often carries hyphens where lines were broken ("trans- port"); the check does not undo that, so quote the text as the PDF gives it, or save a corrected text copy in `.pw-kb/transcripts/` and name that file in the patch. Never edit the user's own transcripts. When a quote is refused, the message shows the closest span in the transcript, so the fix is usually one edit.

When a quote names someone who was not interviewed, such as a colleague or a family member, pick a span without the name if one still carries the point. If none does, keep the name and say so in your report: the map and the review sheet show every quote.

Tag the source honestly:

- `transcript` for the interviewee's words in a transcript
- `quoted_in_notes` for the interviewee's words inside quotation marks in notes
- `interviewer_notes` for the interviewer's own paraphrase, which is weaker evidence. A header or note line someone else wrote about the interview, such as "# Interview: Ana Lima, service writer", counts as this too. Quote it only when the person never says it in their own words

### 5. Write the patch, dry-run, merge

Write the patch to `.pw-kb/patches/<date>-<batch>.yaml`, using the format in `references/patch-format.md`. Open it with a `provenance` block: which assistant and model you are, when you started reading, which interviews you read (by ID or key, never by file name) and any note a later reader needs. The merge copies it into the KB's changelog, so every batch can be traced to who extracted it and how. Write every ID in quotes: interviews `"01"`, core jobs `"B"`, steps `"B.2"`, outcomes `"B.2.3"`. Unquoted, YAML reads an interview ID as a number. Then:

```
kb_tool merge .pw-kb/pw-kb.yaml .pw-kb/patches/<file>.yaml --transcripts <folder with the new transcripts> --dry-run
kb_tool merge .pw-kb/pw-kb.yaml .pw-kb/patches/<file>.yaml --transcripts <folder with the new transcripts>
```

In the patch, `file:` is the transcript's file name. `--transcripts` says where the new ones are; pass it once per folder, or leave it out when the patch adds no interview. A file name that exists in two of those folders is refused. The KB's own copies in `.pw-kb/transcripts/` always come first, so the transcripts of earlier interviews are read from there. The real merge copies each new transcript into `.pw-kb/transcripts/` and records it as `transcripts/<file name>`; the user's originals are never changed. The script reads only the transcripts the KB and the patch cite.

The dry run and the real merge run the same checks in the same order, so a clean dry run is never followed by a refused merge. Each check blocks the merge:

- **Patch format**, against `references/patch-schema.json`: a missing field, a list where a mapping belongs, or an unquoted ID gives one message that names the place in the patch.
- **Quote not found:** open the transcript, copy the exact span and fix the patch. Never loosen the check.
- **Reference:** a step, outcome, interview, core job link, proposal target or segment that does not exist, or an outcome that was merged into another. In a KB with several core jobs, an ID without its job letter (`6.3`) is refused too.
- **Clarity:** a statement is too long or carries brackets, examples or a semicolon. Rewrite it shorter, following "Write for the reviewer first". Treat the warnings ("may hold two jobs", abbreviations) as prompts to reread the statement.
- **Structure:** the KB that would result is checked against `kb-schema.json` before anything is written.

Warnings do not block: an interview skipped because it is already in the KB (its evidence is dropped), an unquoted interview ID that was read as `"01"`, an unknown top-level key, or a transcript whose content changed since it was added.

A real merge first copies the new transcripts into `.pw-kb/transcripts/` and the current KB to `.pw-kb/backups/` (the newest 20 copies are kept), then writes the new KB, recounts all coverage numbers, marks derived layers stale and appends a changelog entry that lists what was added, stamped with the time and the `run_id` of the run. Keep the patch file: it is the audit trail of what each batch added. Re-running a batch that was merged already is a no-op. Add `--json` to get one JSON object with `ok`, `errors`, `warnings`, `run_id` and the changes, instead of text.

### 6. Refresh the review sheet and the map

```
kb_tool review .pw-kb/pw-kb.yaml
kb_tool map .pw-kb/pw-kb.yaml
```

Run both after every merge or approved proposal, so reviewers never open a stale picture.

Add `--open` to `map` when it writes the study's first map, and whenever the user asks to see the map: the tool then shows it in the user's default browser. Do not ask first. Leave `--open` out on later rebuilds, so the user does not get a new tab after every merge.

- `.pw-kb/review.md` is a plain sheet listing decisions waiting, what is new since the last merge, the job map by stage with interview counts and the steps to ask about next.
- `.pw-kb/discovery-map.html` is an interactive map for people who do not know the method. It shows the goal, stages, steps and measures of success with plain labels, the quotes behind every item, what each conversation added, and where more conversations would help. When the study has current solutions, it counts them, can show them next to their steps, and has a Solutions view grouped by the work they compete for. It is one file with the KB inside: it opens in any browser and works offline.

A folder whose name starts with a dot is hidden in Finder and in most file dialogs, so the user cannot easily find the map by hand. `map` prints a `link:` line with a `file://` address. Give the user that address, exactly as printed, every time you point to the map, and give the full path of `review.md`.

- After `map --open`, say what the tool said: the map is open in their browser, or it could not be opened here and what to do instead. Never say it is open when the tool did not.
- After a rebuild without `--open`, say the map is updated and that an open tab must be reloaded.
- Do not run a command of your own to open the map (`open`, `xdg-open`, `start`). It would cost the user one more permission question.
- When the files are on a machine the user cannot reach, such as a remote sandbox, hand them the map the way your host shares files.

**The map contains personal data.** It embeds every interviewee's name and every quote. Before suggesting that anyone share it, say so, and let the user decide who may see it. The same goes for the KB file and `review.md`.

`map` uses `assets/discovery-map-template.html` from this skill. Any `discovery-map.html` made earlier also works as a template (`--template`).

### 7. Report to the user

The reader may be a founder or a domain expert, not an ODI specialist, so write in plain words. Lead with one sentence on what changed. Then keep it short:

- new interviews: name, who they are and their core job, and which of the study's core jobs it links to, one line each, plus any skipped as already processed
- when the study has several core jobs, name each by its statement with the letter after it ("Keep the trucks on the road (B)"), never by the letter alone
- what the new evidence strengthened: name the outcomes in words, with the ID after the text, never as a bare list of IDs. This holds for every mention, including a passing one in a closing remark: a reviewer cannot hold "1.1 and 5.1" in their head.
- new outcomes, each as its full statement
- decisions waiting: what and why in one line each, and how to answer ("approve P1")
- current solutions, briefly: each new group in one line with its why and its most used solutions, then what people stopped using and why. Point to the Solutions view in the map for the full list
- what to ask about next: per core job, the steps that fewest people support, at most 5, as `review.md` lists them under "Ask about these next"; and which derived layers are now out of date
- a pointer to `review.md` and the map's `file://` link, with the note that the map holds the interviewees' names and quotes

**After a first batch** everything is new, so that list would be the whole study. Report this instead, and leave the rest to `review.md` and the map:

- each core job by its statement, how many people have it as their main job, its number of steps and three of them in plain words; then ask the user to confirm each one ("approve P1") or say what to change
- each person in one line: who they are and the core job they are linked to, or why none
- the rest as counts, with the one or two findings that matter most: outcomes, current solutions and their groups, and what people stopped using
- what to ask about next, as above, and the pointer to `review.md` and the map, which `map --open` has just shown in their browser

Skip tool jargon such as "patch", "object of control" or "verbatim check" unless the user uses it. Say "every quote matches the transcript word for word". Flag anything that should change how the user reads the KB, such as a new interview that contradicts the core job, or a segment that keeps growing without a home.

### 8. Acting on proposals

When the user decides:

```
kb_tool apply .pw-kb/pw-kb.yaml P3 --decision approve --note "agreed in review"
```

`apply` re-checks that the proposal's target still exists before it acts. A proposal raised against an outcome that was since merged or moved is refused with a message, not applied blindly. Automatic actions exist for `new_step`, `reword_step`, `reword_outcome`, `reword_core_job`, `merge_outcomes`, `move_outcome`, `new_segment`, `new_core_job`, `confirm_core_job`, `move_step`, `relink_interview`, `merge_solutions`, `move_solution`, `reword_solution` and `reword_solution_group`. A rejected `confirm_core_job` changes nothing: ask the user what is wrong with the job, then propose `reword_core_job`, or `move_step` and `relink_interview`. Old wording and old links are kept in `history`. IDs stay stable: new steps get the next free number in their core job, and merged outcomes keep a `merged_into` pointer instead of being deleted. A moved outcome or step gets the next free ID where it lands, the old ID goes to `history`, and pending proposals that cited the old ID are updated. For `other`, edit the KB by hand, then run `validate`.

An approved `new_core_job` gets the next free letter, its steps are numbered from 1 and the interviews it lists are linked to it. It has no outcomes yet, because outcome IDs need the job to exist. Right after approval, reread those interviews and write a short follow-up patch that cites them by ID and adds the new job's outcomes and step evidence. Also check the people → jobs list in `context` for earlier interviews whose related job is the new core job, and propose `relink_interview` for them.

## When asked whether the study holds more than one job

Run `context` and read the people → jobs list. Ask "why?" of each person's own core job, as in `references/pw-rules.md`, "One job or several". Group the people whose jobs meet. For a group that no core job fits, propose `new_core_job` with its steps and people. Then propose `move_step` for steps that belong to the new job and `relink_interview` for people linked to the wrong one. Tell the user how many people support each job before they decide. Splitting a job is a big change to the map, so propose; never edit the KB by hand for it.

## When asked about current solutions or the competition

Run `context` and read the CURRENT SOLUTIONS block, or point the user to the Solutions view in the map. Groups grow batch by batch, so they drift. When a group holds solutions that do different work, or two groups do the same work, write a patch that proposes `move_solution` for each solution that should move. Add a new group in the same patch when none fits. Propose `reword_solution_group` when a group's name or why no longer fits its members, and `merge_solutions` when two solutions are the same thing under two names. Tell the user why each group holds what it holds. Never edit the KB by hand for it.

## When asked to rebuild a derived layer

Value themes, surveys and use cases are rebuilt only on request. When the study has several core jobs, build them per core job: a survey asks one job's executors about that job's outcomes. When you rebuild them, the reviewer rules still apply:
- theme names are verb-first and at most 6 words ("Know your numbers cold")
- each theme states its need in one sentence of at most 25 words
- each outcome is shown with its text, never as an ID alone
Then clear that layer's `stale` flag and add a changelog entry with `action: rebuild`.

## Study-specific writing rules

The word limits, the banned tokens, the idioms allowed to contain "and" or "or" and the acronyms that need no spelling out are defaults for any market. A study can override them in `meta.style` of the KB, for example:

```yaml
meta:
  style:
    limits: {outcome: 14}
    acronyms: [OTR, ELD, DOT]
    idioms: [bread and butter, in and out, pick and pack]
```

Set this when the user asks for different limits or when a market's everyday abbreviations keep tripping the acronym warning. `references/kb-schema.md` lists the keys.

## Branding

Every file this skill produces carries a light Product Weaver credit: the map's header and badge, the review sheet's footer, `generated_with` in the KB's metadata, and the first line of each patch file (`# Made with Product Weaver · productweaver.com`). Keep these when you edit or rebuild files. They tell readers where the method and the tools come from. Do not add marketing lines to chat replies; the credit lives in the files.

## What the script records

Every run appends one JSON line to `.pw-kb/logs/kb_tool.jsonl`: the command and its options, how it ended, error and warning codes with counts, what changed as counts, the versions in use, the assistant that ran it and a hash of the KB before and after. Refused merges, dry runs and crashes are logged too; they are what shows where the instructions or the patch format confuse an assistant. The log never holds a quote, an interviewee's name, a transcript file name or an absolute path, so it can be shared for debugging. `references/run-log.md` lists every field and every code.

Each changelog entry the script writes carries `ts` and `run_id`, so a change in the KB can be traced to its log line, its backup and its patch. The script recognises Claude Code and Gemini CLI from their environment; in any other assistant, set `KB_TOOL_AGENT=<assistant>/<model>` before calling it so the `agent` field is right. The `provenance` block in a patch does the same for merges. `KB_TOOL_LOG=0` switches the log off. The log belongs to the study: do not send it anywhere unless the user asks.

## Checking a KB

```
kb_tool validate .pw-kb/pw-kb.yaml
```

First checks the KB's structure against `kb-schema.json`: required fields, ID formats, stages, source types and the references between steps and outcomes. Then it re-checks every stored quote against the study's copy of its transcript in `.pw-kb/transcripts/` and compares each copy with the content hash stored when it was added. A transcript that changed is reported; if the change is intended, add `--rehash` to accept the new content once every quote matches. Add `--structure-only` to skip the quotes. A copy that is missing is reported; put the transcript back in `.pw-kb/transcripts/` under the same name. Run it after any hand edit. `merge` runs the same structure check and refuses to write a KB that would break it.

Each KB records its schema version. `kb_tool migrate .pw-kb/pw-kb.yaml` brings an older KB up to date, keeping a backup; every other command refuses an older KB with a message to migrate, and a KB written by a newer version of the tool with a message to update the skill.

The KB's fields are explained one by one in `references/kb-schema.md`. Read it before editing a KB by hand or building anything that reads one.

## Files in this skill

- `scripts/kb_tool.py`: init, context, merge (with format, quote, reference and clarity checks), apply, review, map, validate and migrate (which also moves a study made by an earlier version into `.pw-kb/`). Needs PyYAML, plus python-docx or pypdf for .docx or .pdf transcripts. Carries its own dependency list, so `uv run --locked` needs no setup.
- `scripts/kb_tool.py.lock`: the exact package versions `uv run --locked` installs. Keep it next to the script.
- `assets/discovery-map-template.html`: the interactive map viewer. `map` fills it with the KB. Opened on its own, it lets anyone load a KB file.
- `references/pw-rules.md`: how to write each kind of statement, with examples and common mistakes. Read it before extracting.
- `references/patch-format.md`: the patch format the merge accepts, with a worked example. Read it before writing a patch.
- `references/patch-schema.json`: the same format as a JSON Schema, checked first by every merge.
- `references/kb-schema.md`: every field of the KB, what it means and who writes it.
- `references/kb-schema.json`: the same model as a JSON Schema (draft 2020-12), checked by `validate`, `merge` and `apply`.
- `references/run-log.md`: what `.pw-kb/logs/kb_tool.jsonl` records, field by field, and every error and warning code.
