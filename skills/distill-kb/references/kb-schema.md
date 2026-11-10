# The ODI knowledge base: field reference

*Made with [Product Weaver](https://productweaver.com).*

One YAML file, `.pw-kb/pw-kb.yaml` at the root of the workspace, holds a whole study. This page explains every field. The machine-checkable version is `kb-schema.json` (JSON Schema, draft 2020-12). `kb_tool.py validate` checks every KB against it, and `merge` refuses to write a KB that would break it.

**Who writes what.** The skill writes the statements, and the script stamps IDs, counts, dates and hashes. People decide on proposals. Fields marked *computed* are recalculated on every merge, so don't edit them by hand.

**Extra fields are allowed.** Anything not listed here is kept and ignored, so older files and your own notes keep loading.

## At a glance

```yaml
meta:                 # about the study
core_jobs: []         # the core jobs the study found: A, B, C…
clusters:             # segments of people, optional
interviews: []        # one record per conversation, linked to the core jobs
job_map:
  steps: []           # what people do, per core job, on the 8 ODI stages
desired_outcomes:
  outcomes: []        # how people judge each step
current_solutions:    # what people use today for each step, optional
  groups: {}
  solutions: []
proposed_changes: []  # structural changes waiting for a decision
changelog: []         # what happened to the KB, and when
survey / simulation / value_themes / use_cases:   # derived layers, rebuilt on request
```

Required at the top level: `meta`, `core_jobs`, `interviews`, `job_map`, `desired_outcomes`.

## IDs

A study can hold more than one core job, so every step and outcome ID starts with its core job's letter.

| Thing | ID | Example | Meaning |
|---|---|---|---|
| Core job | a letter | `B` | The second core job. After `Z` come `AA`, `AB`… |
| Step | job letter + number | `B.2` | Step 2 of core job B. Steps are numbered from 1 inside each core job |
| Outcome | step ID + number | `B.2.3` | The third outcome of step B.2 |
| Interview | digits | `"07"` | The seventh conversation |
| Solution | `S` + number | `S3` | The third solution recorded. Study-wide: one solution can serve steps of several core jobs |
| Solution group | short lowercase key | `send-orders` | Chosen by whoever adds the group |

The letter is there even when the study has one core job (`A.6.3`), so no ID changes when a second job appears. IDs stay stable once published: a moved step or outcome gets a new ID and keeps the old one in `history`.

## Shared pieces

**Evidence item.** A quote that supports a step, an outcome or a proposal. It is used everywhere except inside an interview's own record.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `interview` | string of digits | yes | ID of the interview the quote comes from, such as `"07"` |
| `source` | `transcript`, `quoted_in_notes` or `interviewer_notes` | yes | The interviewee's words in a transcript, their words quoted in notes, or the interviewer's paraphrase |
| `quote` | string | yes | Exact words, copied character for character from the transcript |
| `name` | string | no | *Computed.* The interviewee's name, filled in for readability |

**Own statement.** A statement inside an interview record: `{statement, evidence}`, where each evidence item is `{source, quote}` because the interview is implied. An interview's core functional job and each related job may also carry `job`, the ID of the core job it rolls up to, and `history`. A core functional job with no `job` may carry `unlinked_reason`: why it rolls up to none of the study's core jobs.

**Stage.** One of `define`, `locate`, `prepare`, `confirm`, `execute`, `monitor`, `modify` or `conclude`.

**History.** A list of `{date, was}` (old wording, or a solution's or group's old name), `{date, was_id}` (old step or outcome ID), `{date, was_job, was_reason}` (the core job an interview's job was linked to before, `null` for none, and its `unlinked_reason` then, if it had one), `{date, was_group}` (the group a solution was in), `{date, was_kind}` (a solution's kind before it was corrected) or `{date, was_why}` (a group's reason before it was reworded), added when an approved proposal changes something.

## `meta`

| Field | Type | Required | Meaning |
|---|---|---|---|
| `project` | string | yes | Study or client name |
| `schema_version` | integer | no | Version of this schema; currently 2. `kb_tool.py migrate` raises it, and every command refuses an older or a newer one |
| `method` | string | no | Method used |
| `interviewer` | string | no | Who ran the interviews |
| `created` | date | no | When the KB was started |
| `interview_count` | integer | no | *Computed.* Number of interviews |
| `date_range` | string | no | *Computed.* First to last interview date |
| `caveat` | string | no | A warning every reader should see, such as "sample interviews" |
| `generated_with` | string | no | *Computed.* Product Weaver credit |
| `tool_version` | string | no | *Computed.* Version of `kb_tool.py` that last wrote the file |
| `style` | mapping | no | Writing rules for this study that override the script's defaults, see below |

**`meta.style`**

| Field | Type | Meaning |
|---|---|---|
| `limits` | mapping of kind to integer | Maximum words per kind of statement: `executor` (16), `job` (10), `step` (10), `outcome` (16), `feeling` (12), `rationale` (30, also a solution group's `why`), `solution` (6, a solution's name), `group` (6, a solution group's name) |
| `banned` | list of strings | Tokens a statement may not contain. Default: `(`, `;`, `e.g.`, `i.e.`, ` and/or `, `/` |
| `idioms` | list of strings | Phrases with "and" or "or" that are one idea. Default: `bread and butter`, `in and out` |
| `acronyms` | list of strings | Abbreviations every reviewer in this market knows. Default: `OTR`, `US`, `UK`, `EU` |

Each key replaces the default list, or for `limits` the named entries, so copy the defaults you want to keep.

## `core_jobs[]`

The core functional jobs the study found, abstracted from each interview's own core job. Most studies have one. A study whose people do different jobs, such as owner-operators and fleet maintenance managers, has one per job.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | letter | yes | *Computed* on approval: `A`, `B`, `C`… A bootstrap names them in that order |
| `statement` | string | yes | The core functional job: verb + object + context, no solution, at most 10 words |
| `job_executor` | string | no | Who carries out the job |
| `status` | `proposed` or `approved` | no | `proposed` until the team approves its `confirm_core_job`, or the `new_core_job` that added it |
| `history` | history | no | Earlier wordings |
| `interviews` | list of IDs | no | *Computed.* Interviews whose own core job rolls up to this one: its executors |
| `related_interviews` | list of IDs | no | *Computed.* Other interviews with a related job that rolls up to this one |
| `coverage` | integer | no | *Computed.* How many interviews are quoted on this job's steps and outcomes |

## `clusters`

A map from a short segment code (`seq`, `fleet`) to `{name, description, interviews}`. `interviews` is *computed* from each interview's `cluster`.

## `interviews[]`

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | string of digits | yes | *Computed.* Assigned on merge: `"01"`, `"02"`… |
| `name` | string | yes | Interviewee |
| `file` | string | yes | *Computed.* The study's copy of the transcript, `transcripts/<file name>`, relative to `.pw-kb/` |
| `sha256` | 64 hex characters | no | *Computed.* Content hash; catches a renamed copy of the same transcript |
| `date` | date | no | When the conversation happened |
| `added` | date | no | *Computed.* When it entered the KB |
| `format` | string | no | `Transcript`, `Notes` or `Transcript + notes` |
| `cluster` | string | no | Segment code from `clusters` |
| `tags` | list of strings | no | Details that don't belong in statements, such as city or years in business |
| `job_executor` | own statement | yes | Who they are, at most 16 words |
| `core_functional_job` | own statement | yes | Their own core job, at most 10 words. Its `job` is their main link: the core job this rolls up to. No `job` means they carry out none of the study's core jobs, and its `unlinked_reason` says why |
| `related_jobs` | list of own statements | no | Other jobs they do alongside. A related job's `job` links them to another core job they also do |
| `emotional_jobs` | list of own statements | no | How they want to feel |
| `social_jobs` | list of own statements | no | How they want to be seen |
| `analyst_note` | string | no | Anything else a reader must know, such as "answered for two sites" |

An empty list is a finding: the interview gave no evidence for that kind of job. So is a missing main link: `unlinked_reason` should say why.

## `job_map`

| Field | Type | Required | Meaning |
|---|---|---|---|
| `stages` | list of `{key, name}` | no | The 8 stages, for display |
| `steps` | list | yes | See below |

**`steps[]`**

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | step ID | no | *Computed.* `<job>.<n>`, such as `A.6` |
| `job` | letter | yes | The core job this step belongs to. Each step belongs to exactly one |
| `n` | integer | yes | Step number inside its core job. Stable once published, because outcome IDs depend on it |
| `stage` | stage | yes | Where the step sits in the job |
| `statement` | string | yes | Verb + object, at most 10 words |
| `covers` | string | no | One line on what the step includes |
| `evidence` | list of evidence items | no | Quotes of people doing this step |
| `interviews` | list of IDs | no | *Computed.* Who is quoted |
| `coverage` | integer | no | *Computed.* How many interviews are quoted |
| `history` | history | no | Earlier wordings |

## `desired_outcomes.outcomes[]`

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | `"<job>.<step>.<k>"` | yes | *Computed.* Outcome `A.6.3` is the third outcome of step A.6 |
| `step` | step ID | yes | The step it measures, such as `A.6` |
| `statement` | string | yes | Starts with Minimize, Maximize, Increase or Reduce. At most 16 words |
| `evidence` | list of evidence items | no | Quotes showing people judge the step this way |
| `interviews`, `interview_count`, `quote_count` | | no | *Computed* |
| `added` | date | no | *Computed.* When it entered the KB |
| `merged_into` | outcome ID | no | Set when the outcome was merged into another. The record stays, so old references still resolve |
| `history` | history | no | Earlier wordings or IDs |

## `current_solutions`

What people use today to get a step done: products, everyday tools, other people and their own methods. Also what they stopped using, with the quote that says so. The section is optional. The first merge that adds a solution creates it, so a KB without solutions has none.

Each solution sits in one group. A group gathers the solutions that compete for the same work, the options a person would weigh against each other, and says why in one sentence. A group of one is fine: no alternative has been heard yet.

**`groups`**: a map from a short lowercase key (`send-orders`) to:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `name` | string | yes | The work its solutions compete for, at most 6 words |
| `why` | string | yes | Why these solutions belong together, one sentence of at most 30 words |
| `added` | date | no | *Computed.* When it entered the KB |
| `history` | history | no | Earlier names and reasons |
| `solutions` | list of solution IDs | no | *Computed.* The live solutions in the group |

**`solutions[]`**

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | `S<n>` | yes | *Computed* on merge |
| `name` | string | yes | As people name it, at most 6 words. A role, never a private person's name |
| `kind` | `product`, `everyday_tool`, `people` or `own_method` | yes | A product or app they sign up to; a general tool bent to the job, such as a spreadsheet, paper or a phone; a person or firm who does it for them; or a habit, rule of thumb or doing it in their head |
| `group` | group key | yes | The group it sits in |
| `uses` | list | yes | The steps it is used for, see below. Empty once merged |
| `added` | date | no | *Computed.* When it entered the KB |
| `interviews` | list of IDs | no | *Computed.* Who is quoted on a current use: the people who use it now |
| `stopped_by` | list of IDs | no | *Computed.* Who is quoted only on stopped uses |
| `quote_count` | integer | no | *Computed.* How many different quotes mention it |
| `merged_into` | solution ID | no | Set when the solution was merged into another. The record stays, so its name is still recognised |
| `history` | history | no | Earlier names, groups and kinds |

**`uses[]`**: one per step and status.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `step` | step ID | yes | The step the solution is used for |
| `status` | `current` or `stopped` | yes | They use it now, or they used it for this step and stopped |
| `evidence` | list of evidence items | yes | The quotes that show it |

A person quoted on both a current and a stopped use counts as a current user. Solution quotes do not count toward a step's `coverage`.

## `proposed_changes[]`

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | `P<n>` | yes | *Computed* |
| `type` | `new_step`, `reword_step`, `reword_outcome`, `reword_core_job`, `merge_outcomes`, `move_outcome`, `new_segment`, `new_core_job`, `confirm_core_job`, `move_step`, `relink_interview`, `merge_solutions`, `move_solution`, `reword_solution`, `reword_solution_group` or `other` | yes | What kind of change |
| `target` | string | no | Step ID, outcome ID, core job ID, segment code, interview ID, solution ID or solution group key, depending on `type` |
| `stage` | stage | no | For `new_step`, and for `move_step` when the step changes stage |
| `merge` | outcome or solution ID | no | For `merge_outcomes`: the outcome folded into `target`. For `merge_solutions`: the solution folded into `target` |
| `to_step` | step ID | no | For `move_outcome` |
| `to_job` | letter | no | For `move_step`: the core job the step moves to |
| `to_group` | group key | no | For `move_solution`: the group the solution moves to |
| `kind` | solution kind | no | For `reword_solution`: the solution's corrected kind |
| `why` | string | no | For `reword_solution_group`: the group's new reason |
| `job` | letter or `null` | no | For `new_step`: the core job the step joins. For `relink_interview`: the core job to link to, or `null` to remove the link |
| `job_executor` | string | no | For `new_core_job`: who carries out the new job |
| `steps` | list of `{stage, statement, covers, evidence}` | no | For `new_core_job`: its first steps, numbered from 1 on approval |
| `interviews` | list of IDs | no | For `new_core_job`: interviews whose main link is set to the new job on approval |
| `related_job` | string | no | For `relink_interview`: the statement of the related job to link. Without it, the main link changes |
| `proposal` | string | yes | The new wording or name, or the change in one line |
| `rationale` | string | yes | Why, in one sentence of at most 30 words |
| `status` | `pending`, `approved` or `rejected` | yes | Decided with `kb_tool.py apply` |
| `raised`, `decided`, `note` | | no | When it was raised and decided, and the decision note |
| `evidence` | list of evidence items | no | The quotes behind it |

## `changelog[]`

One entry per thing that happened to the KB. Every entry has `date`, `action` and usually `summary`, a sentence for people. `action` is one of `init`, `merge`, `decide`, `rebuild`, `edit` or `migrate`. The script logs `init`, `merge`, `decide`, `migrate` and `edit` (when `validate --rehash` accepts changed transcripts). Log `rebuild` when a derived layer is rebuilt and `edit` after a hand edit.

Entries the script writes also carry `ts`, the time with timezone, and `run_id`, the ID of the run in `logs/kb_tool.jsonl` (see `run-log.md`), so a change can be traced to its log line and its backup. A `merge` entry may carry `provenance`, copied from the patch: `assistant`, `model`, `started`, `transcripts_read` (as KB interview IDs) and `notes`.

A `merge` entry also carries structured fields, so tools do not have to parse the sentence:

| Field | Type | Meaning |
|---|---|---|
| `patch` | string | File name of the patch |
| `added_interviews` | list of IDs | Interviews this merge added |
| `new_outcomes` | list of outcome IDs | Outcomes this merge added |
| `step_quotes`, `outcome_quotes` | integer | Quotes added to steps and to outcomes |
| `new_solutions`, `new_solution_groups` | lists | Solutions and solution groups this merge added. Present once the KB has a `current_solutions` section |
| `solution_quotes` | integer | Quotes added to solutions already in the KB. Present with the two above |
| `ts` | string | When the script wrote the entry, ISO 8601 with timezone |
| `run_id` | string | The run that wrote it; the same value is on its line in `logs/kb_tool.jsonl` |
| `provenance` | mapping | Who extracted the batch: `assistant`, `model`, `started`, `transcripts_read`, `notes` |
| `proposals` | list of `P<n>` | Proposals this merge filed |
| `bootstrap` | boolean | Present and true when the merge created the core jobs and job map |

A `decide` entry carries `proposal` (the ID) and `decision` (`approved` or `rejected`).

## Backups

Every write except `init` first copies the KB to `backups/` next to it, as `<name>.<date>-<time>-<microseconds>.yaml`. The newest 20 copies are kept.

## Derived layers

`survey`, `simulation`, `value_themes` and `use_cases` are built from the layers above, on request. Their content is free-form, but each may carry `stale: true` and `stale_reasons`. The script sets these when new evidence arrives, and a rebuild clears them.
