# The ODI knowledge base: field reference

*Made with [Product Weaver](https://productweaver.com).*

One JSON file, `.pw-kb/pw-kb.json` at the root of the workspace, holds a whole study. This page explains every field. The machine-checkable version is `kb-schema.json` (JSON Schema, draft 2020-12). `kb_tool.py validate` checks every KB against it, and `merge` refuses to write a KB that would break it.

**Who writes what.** The skill writes the statements, and the script stamps IDs, counts, dates and hashes. People decide on proposals. Fields marked *computed* are recalculated on every merge, so don't edit them by hand.

**Extra fields are allowed.** Anything not listed here is kept and ignored, so older files and your own notes keep loading.

**The file.** The script writes it in UTF-8 with two-space indents, and keeps each object that holds no list or object, such as an evidence item, on one line. A date is a string such as `"2026-03-05"`. A study written in YAML by plugin 0.7.0 or earlier, `.pw-kb/pw-kb.yaml`, becomes this file with `kb_tool.py migrate .pw-kb/pw-kb.yaml`.

## At a glance

```json
{
  "meta": {},
  "core_jobs": [],
  "clusters": {},
  "interviews": [],
  "job_map": {"steps": []},
  "desired_outcomes": {"outcomes": []},
  "current_solutions": {"groups": {}, "solutions": []},
  "proposed_changes": [],
  "changelog": [],
  "value_themes": {"themes": []},
  "overview": {"jobs": []}
}
```

- `meta`: about the study
- `core_jobs`: the core jobs the study found: A, B, C…
- `clusters`: segments of people, optional
- `interviews`: one record per conversation, linked to the core jobs
- `job_map.steps`: what people do, per core job, on the 8 ODI stages
- `desired_outcomes.outcomes`: how people judge each step
- `current_solutions`: what people use today for each step, optional
- `proposed_changes`: structural changes waiting for a decision
- `changelog`: what happened to the KB, and when
- `value_themes`: a few needs that group the outcomes, optional, built on request
- `overview`: the study as a short story with what to do next, optional
- `survey`, `simulation`, `use_cases`: other derived layers, rebuilt on request (not shown)

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
| `schema_version` | integer | no | Version of this schema; currently 3. `kb_tool.py migrate` raises it, and every command refuses an older or a newer one |
| `method` | string | no | Method used |
| `interviewer` | string | no | Who ran the interviews |
| `language` | string | no | The study's language, a BCP 47 code such as `en`, `it`, `pt-BR` or `zh-Hans`. Every statement is written in it, and the map and `review.md` show their own text in it from `.pw-kb/labels.json`. Missing means English. `init` writes it; `labels --language` changes it only while the study has no interviews. Quotes stay in the words people used |
| `created` | date | no | When the KB was started |
| `interview_count` | integer | no | *Computed.* Number of interviews |
| `date_range` | string | no | *Computed.* First to last interview date |
| `caveat` | string | no | A warning every reader should see, such as "sample interviews" |
| `generated_with` | string | no | *Computed.* Product Weaver credit |
| `tool_version` | string | no | *Computed.* Version of `kb_tool.py` that last wrote the file |
| `style` | object | no | Writing rules for this study that override the script's defaults, see below |

**`meta.style`**

| Field | Type | Meaning |
|---|---|---|
| `limits` | object of kind to integer | Maximum words per kind of statement: `executor` (16), `job` (10), `step` (10), `outcome` (16), `feeling` (12), `rationale` (30, also a solution group's `why`), `solution` (6, a solution's name), `group` (6, a solution group's name), `theme` (6, a value theme's label), `need` (25, a value theme's need), `headline` (20), `finding` (50) and `action` (20) for the overview's sentences, `role` (4, the overview's label for who the study is about) and `who` (25, the sentence under it) |
| `banned` | list of strings | Tokens a statement may not contain. Default: `(`, `;`, `e.g.`, `i.e.`, ` and/or `, `/`, and the full-width and Arabic forms `（`, `；`, `／`, `؛`. A Greek study (`el`) drops `;`, its question mark |
| `idioms` | list of strings | Phrases with "and" or "or" that are one idea. Default: `bread and butter`, `in and out` |
| `acronyms` | list of strings | Abbreviations every reviewer in this market knows. Default: `OTR`, `US`, `UK`, `EU` |
| `directions` | list of strings | How a new outcome must start, such as `Ridurre al minimo `. Default in an English study: `Minimize `, `Maximize `, `Increase `, `Reduce `; in another language none is checked |
| `need_start` | string | How a value theme's need must start, such as `Aiutami a `. Default in an English study: `Help me `; in another language none is checked |

Each key replaces the default list, or for `limits` the named entries, so copy the defaults you want to keep.

**Other languages.** In a study whose `meta.language` is not English, the default limits are a fifth higher, rounded up, because most languages need more words than English for the same statement. Chinese, Japanese, Thai, Lao, Khmer and Burmese are written without spaces, so their letters count instead: 2 to a word in Chinese, 2.5 in Japanese and 4 in the others, plus any word in Latin letters. Limits set in `limits` are used as written. The warning that a job or step may hold two jobs ("and", "or") is given in English studies only.

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

An object from a short segment code (`seq`, `fleet`) to an object with `name`, `description` and `interviews`. `interviews` is *computed* from each interview's `cluster`.

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
| `coverage` | integer | no | *Computed.* How many interviews are quoted on the step itself |
| `voices` | integer | no | *Computed.* How many distinct people are quoted on the step or on any of its outcomes. A step with fewer than 3 is thin |
| `history` | history | no | Earlier wordings |

## `desired_outcomes.outcomes[]`

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | `"<job>.<step>.<k>"` | yes | *Computed.* Outcome `A.6.3` is the third outcome of step A.6 |
| `step` | step ID | yes | The step it measures, such as `A.6` |
| `statement` | string | yes | In an English study, starts with Minimize, Maximize, Increase or Reduce; in another language, the same form in that language. At most 16 words |
| `evidence` | list of evidence items | no | Quotes showing people judge the step this way |
| `interviews`, `interview_count`, `quote_count` | | no | *Computed* |
| `added` | date | no | *Computed.* When it entered the KB |
| `merged_into` | outcome ID | no | Set when the outcome was merged into another. The record stays, so old references still resolve |
| `history` | history | no | Earlier wordings or IDs |

## `current_solutions`

What people use today to get a step done: products, everyday tools, other people and their own methods. Also what they stopped using, with the quote that says so. The section is optional. The first merge that adds a solution creates it, so a KB without solutions has none.

Each solution sits in one group. A group gathers the solutions that compete for the same work, the options a person would weigh against each other, and says why in one sentence. A group of one is fine: no alternative has been heard yet.

**`groups`**: an object from a short lowercase key (`send-orders`) to an object with:

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

One entry per thing that happened to the KB. Every entry has `date`, `action` and usually `summary`, a sentence for people. `action` is one of `init`, `merge`, `decide`, `rebuild`, `edit` or `migrate`. The script logs `init`, `merge`, `decide`, `migrate`, `edit` (when `validate --rehash` accepts changed transcripts) and `rebuild` (when `themes` writes value themes). Log `rebuild` yourself when another derived layer is rebuilt, and `edit` after a hand edit.

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
| `provenance` | object | Who extracted the batch: `assistant`, `model`, `started`, `transcripts_read`, `notes` |
| `proposals` | list of `P<n>` | Proposals this merge filed |
| `bootstrap` | boolean | Present and true when the merge created the core jobs and job map |

A `decide` entry carries `proposal` (the ID) and `decision` (`approved` or `rejected`). A `rebuild` entry written by `themes` carries `layer` (`value_themes`), `job` (the core job) and `themes` (the IDs of that job's themes after the run).

## Backups

Every write except `init` first copies the KB to `backups/` next to it, as `<name>.<date>-<time>-<microseconds>.json`. The newest 20 copies are kept. `migrate` keeps the YAML files of an older study there the same way, ending in `.yaml`.

## `value_themes`

A few needs, in the customer's voice, that group the desired outcomes of a core job so a team can sort ideas into them. The layer is optional and built on request. `kb_tool.py themes` writes it, one core job at a time, and checks it. The method is in `pw-rules.md`, "Value themes".

| Field | Type | Required | Meaning |
|---|---|---|---|
| `stale` | boolean | no | True when interviews, outcomes or approved proposals arrived after the themes were written. `themes` clears it |
| `stale_reasons` | list of strings | no | Why, one line per change, with its date |
| `themes` | list of themes | no | The themes of every core job, in ID order |
| `unassigned` | list of outcome IDs | no | *Computed.* Live outcomes that sit in no theme, for the core jobs that have themes |

**`value_themes.themes[]`**

| Field | Type | Required | Meaning |
|---|---|---|---|
| `id` | `"<job>.T<n>"` | yes | `A.T2` is the second theme of core job A. It stays the same when the theme is reworded |
| `job` | core job ID | yes | The core job whose outcomes it groups |
| `label` | string | yes | Starts with a verb. At most 6 words |
| `need` | string | yes | One sentence that starts with "Help me" in an English study, or the same request in the study's language. At most 25 words |
| `why` | string | no | What binds the outcomes, in one sentence of at most 30 words |
| `outcomes` | list of outcome IDs | yes | The outcomes it groups, all from its core job. An outcome may sit in two themes. When an outcome moves or is merged, the script updates the ID here |
| `highlights` | list | no | Quotes picked to show the need: `{kind, interview, source, quote, name}`. `kind` is `pain`, `struggle` or `desire`. Each is a copy of a quote on one of the theme's outcomes or on a solution used at their steps; `source` and `name` are filled in by the script |
| `added` | date | no | *Computed.* When the theme entered the KB |
| `interviews`, `interview_count`, `quote_count` | | no | *Computed.* Who is quoted on its outcomes, how many people that is, and how many quotes those outcomes hold |

The counts are a signal from interviews, not a survey score. A theme with no `id` was written by hand before the `themes` command existed. The script keeps it, does not check or count it, and drops it the first time `themes` writes that layer.

## `overview`

The study told as a short story for someone new to the method, with what to do next. It feeds the Overview view of the discovery map. The layer is optional. `kb_tool.py overview` writes it, one core job at a time, and checks it. The writing rules are in `pw-rules.md`, "Overview".

The layer holds only the sentences the assistant writes. The map counts the rest itself: how sure the findings are, the parts of the job, the solutions in use, the key unmet needs and the ranking of the value themes.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `stale` | boolean | no | True when interviews, outcomes or approved proposals arrived after an overview was written. `overview` clears it |
| `stale_reasons` | list of strings | no | Why, one line per change, with its date |
| `jobs` | list of overviews | no | One overview per core job, in job order |

**`overview.jobs[]`**

| Field | Type | Required | Meaning |
|---|---|---|---|
| `job` | core job ID | yes | The core job the overview is about |
| `executor` | object | yes for `overview` | Who the study is about, shown first: see below. An overview written before 0.9.0 has none; the map then shows the core job's `job_executor`, and `context` marks the overview out of date |
| `bottom_line` | string | yes | The main finding, in one sentence of at most 20 words |
| `why` | string | yes | Why the problem is still there. At most 30 words |
| `opening` | string | yes | Where a new solution fits. At most 30 words |
| `people` | object | yes | Who was listened to: `answer` (at most 20 words), optional `text` (at most 50 words) and optional `quote` |
| `today` | object | yes | How they get the job done today: `answer`, optional `text`. Every `answer` is at most 20 words and every `text` at most 50 |
| `gaps` | object | yes | Where today's way falls short: `answer` and `items`, 1 to 5 gaps |
| `needs` | object | yes | What they most want to get better: `answer`, optional `text`. The map lists the needs |
| `focus` | object | yes | Where a new solution should focus: `answer`, optional `text`. The map lists the themes |
| `next` | object | yes | What to do next, in three tracks: `learn`, `prototype`, `market`. Advice, not findings |
| `written` | date | no | *Computed.* When this overview was written |

**Who the study is about** (`executor`) holds:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `label` | string | yes | A short name for these people that a stranger can picture, at most 4 words: "Small-firm bookkeeper" |
| `text` | string | yes | Who they are and what they do, in one sentence of at most 25 words |
| `icon` | string | yes | The icon the map draws for them. One of `person`, `office`, `finance`, `shop`, `sales`, `support`, `manager`, `developer`, `designer`, `driver`, `warehouse`, `builder`, `repair`, `cook`, `health`, `care`, `teacher`, `student`, `farmer`, `legal`, `parent`. Use `person` when none fits |
| `others` | list of strings | no | Up to 3 other people who appear in the story but are not its focus, at most 4 words each: "their clients" |

**A gap** (`gaps.items[]`) holds `label` (at most 6 words), `text` (at most 30 words), `kind` (`pain`: it hurts today; `struggle`: a fix they tried did not work), optional `solutions` (IDs of the solutions it concerns) and `quote`.

**A quote** is `{interview, quote}`. It must be a quote the KB already holds for that core job: on one of its steps, outcomes or solution uses, or in what a person linked to it said about themselves. The script fills in `source` and `name`.

**A track** of `next` holds `status`, `action` (at most 20 words) and three more fields, each at most 30 words:

| Track | `status` | Other fields |
|---|---|---|
| `learn` | `now` or `enough` | `why`, `ask` (1 or 2 questions for the next conversations), `tip`, and the plan for the next round below |
| `prototype` | `ready` or `early` | `why`, `test` (how to try it with real people), `later` (what to leave out for now) |
| `market` | `ready` or `early` | `who` (whom to approach first), `words` (1 to 3 phrases in the customers' own words, each part of a quote in the KB), `unknown` (what is not known yet) |

**The plan for the next round** sits in `learn`. Its three fields come together or not at all, and every ID in them must be a step, an outcome or a trait value of the core job. The map's Next interviews view, `review.md` and `interview-guide.md` show it.

| Field | Type | Meaning |
|---|---|---|
| `traits` | list | 2 or 3 people traits that change how the job gets done: `{id: "T1", name, values}`, each value `{id: "T1.1", label, interviews}`. Names and labels are at most 4 words. A person sits in at most one value of a trait. A value with no interviews is a kind of person not heard from yet |
| `rests_on` | list of outcome IDs | 1 to 8 outcomes the main finding rests on. Their gaps rank first |
| `round` | list | 1 to 5 entries, in the order to do them: `kind` (`new`), `count` (1 to 3 people), `who` (at most 15 words), optional `traits` (value IDs), `gaps` (1 to 4 IDs it fills) and `questions` (1 to 4 `{ask, listen, gaps}`: a question of at most 25 words, what to listen for in at most 15, and which of the entry's gaps it checks) |
| `at_write` | object | *Computed.* When the plan was written: the round's targets and the people heard so far |
| `previous` | object | *Computed.* The `at_write` of the plan before the last batch, so the next plan can say how that round went |

## Other derived layers

`survey`, `simulation` and `use_cases` are built from the layers above, on request. Their content is free-form, but each may carry `stale: true` and `stale_reasons`. The script sets these when new evidence arrives, and a rebuild clears them.
