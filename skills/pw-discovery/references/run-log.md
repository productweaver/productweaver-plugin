# The run log

`kb_tool.py` appends one JSON line to `.pw-kb/logs/kb_tool.jsonl`, next to the KB, every time it runs. Successful runs, refused merges, dry runs and crashes all get a line. The log answers three questions the KB alone cannot: what was tried and failed, how long things take, and which assistant did what. Read it with any JSONL tool.

Set `KB_TOOL_LOG=0` to switch the log off. It is append-only and small: a line is under 1 KB, so a thousand runs are under 1 MB.

## What the log never holds

The KB, the map and the review sheet hold personal data: interviewees' names and their words. The log does not. A line holds IDs, counts, codes, hashes, versions and paths relative to the KB folder. It never holds a quote, an error message (messages can contain quotes), an interviewee's name, a transcript file name, the `--note` text of a decision, or an absolute path. A `--transcripts` root that is a single file is logged as `<file>`; the `notes` field of a patch's provenance is kept out. So the log can be shared with the skill's maintainers for debugging without a data-protection question.

## Fields

Every line has these fields. The order is stable, so lines are easy to compare.

| Field | Meaning |
|---|---|
| `run_id` | 12 hex characters, unique per run. Changelog entries the script writes carry the same value |
| `ts` | When the run started, ISO 8601 with timezone |
| `duration_ms` | How long the run took |
| `command` | `init`, `labels`, `context`, `merge`, `apply`, `themes`, `overview`, `review`, `map`, `validate` or `migrate` |
| `args` | The options given, with paths relative to the KB folder. `--note`, `--project`, `--interviewer` and the KB path are left out. `transcripts` lists the roots; a root that is a file shows as `<file>` |
| `exit_code` | 0 success, 1 refused or failed with a message, 2 crashed |
| `written` | True when the run changed the KB file |
| `tool_version`, `schema_version` | Which `kb_tool.py` ran, and which KB schema it writes |
| `python`, `os` | Python version and platform |
| `agent` | The assistant running the tool: `KB_TOOL_AGENT` if set, else `claude-code` or `gemini-cli` when their environment marker is present, else the terminal program, else null |
| `kb_sha256_before`, `kb_sha256_after` | Hash of the KB file before and after. Equal means nothing changed; a change between two runs means a hand edit |
| `kb` | Size of the KB after the run: `interviews`, `core_jobs`, `unlinked_interviews` (linked to no core job), `steps`, `thin_steps`, `outcomes` (live ones), `pending_proposals`, `solutions` (live ones), `solution_groups`, `themes` (value themes), `overviews` (core jobs with an overview) and the `stale` derived layers |
| `errors`, `warnings` | Codes with counts, such as `{"quote_not_found": 3}`. See Codes below |

Commands add their own fields:

| Field | Command | Meaning |
|---|---|---|
| `dry_run`, `nothing_new` | merge, themes, overview | Whether it was a dry run, and for merge whether the patch had nothing new |
| `patch_sha256` | merge | Hash of the patch file, so retries of the same patch can be counted |
| `bootstrap` | merge | True when the merge created the core job and job map |
| `counts` | merge | `interviews_added`, `interviews_skipped`, `outcomes_added`, `step_quotes`, `outcome_quotes`, `proposals_filed`, `transcripts_copied` (new transcripts copied into `.pw-kb/transcripts/`), `solutions_added`, `solution_groups_added`, `solution_quotes` (quotes added to solutions already in the KB) |
| `counts` | themes | `themes` (that core job's themes after the run), `theme_outcomes` (outcomes in at least one of them), `unassigned` (that job's outcomes in no theme) |
| `counts` | overview | `overview_gaps` (gaps in the overview just written), `overviews` (core jobs that have an overview after the run) |
| `provenance` | merge | The patch's provenance block without `notes`: `assistant`, `model`, `started`, `transcripts_read` as KB IDs |
| `backup` | merge, apply, themes, overview, labels, validate, migrate | The backup made before the write, relative to the KB folder |
| `job` | themes, overview | The core job whose value themes or overview the run was about |
| `proposal`, `proposal_type`, `decision` | apply | What was decided on and how. Logged even when the apply is refused |
| `out`, `since` | review, map, labels | The file written; for review, the date new items are counted from |
| `browser` | map | Only with `--open`: `opened`, `failed` (no browser could be started), `no_display` (a remote session or no display, so it did not try) or `off` (`KB_TOOL_OPEN=0`) |
| `structure_problems`, `outcome_quotes`, `drifted`, `rehash` | validate | Structure problems found, outcome quotes in the KB, transcripts whose content changed, whether `--rehash` was given |
| `schema_from` | migrate | The schema version the KB had before |
| `moved`, `transcripts_copied` | migrate | True when migrate moved a study made by an earlier version into `.pw-kb/`, and how many transcripts it copied there |
| `git` | init, migrate | True when `.pw-kb/` sits in a git repository and has no `.gitignore` of its own |
| `language` | init, labels | The study's language, a BCP 47 code such as `en`, `it` or `pt-BR` |
| `labels` | init, labels, review, map, migrate | Counts only, never a label's text: `missing` (labels that still show in English), `added` (labels `labels --add` kept), `refused` (problems that stopped `labels --add`). `migrated` (migrate: 1 when it turned `labels.yaml` into `labels.json`, else 0) |
| `exception` | any | The exception class when the tool crashed |

## Codes

Each problem has a short stable code. Errors block the command; warnings do not. Count codes across runs to see what trips assistants up: many `quote_not_found` errors mean quotes are being tidied, many `clarity_length` errors mean the word limits need explaining, many `proposal_ref` errors mean targets are being guessed instead of read from `context`.

### Errors that refuse a merge

| Code | Meaning |
|---|---|
| `patch_format` | The patch does not match `patch-schema.json` |
| `quote_not_found` | A quote is not in its transcript word for word |
| `quote_empty` | A quote is empty |
| `evidence_missing` | An item that needs evidence has none |
| `evidence_shape` | An evidence item is not an object with interview, source and quote |
| `source_invalid` | `source` is not transcript, quoted_in_notes or interviewer_notes |
| `interview_unresolved` | Evidence names an interview that is unknown, skipped or has no transcript |
| `clarity_length` | A statement is over the word limit for its kind |
| `clarity_banned` | A statement carries brackets, a semicolon, an example, an aside or a slash |
| `clarity_etc` | A statement ends a list with etc. |
| `rationale_length` | A proposal's rationale is over the word limit |
| `bootstrap_conflict` | A bootstrap was given but the KB already has a core job or job map |
| `job_order` | A bootstrap's core job IDs are not A, B, C… in order |
| `job_missing` | An interview's core job or related job links to a core job that does not exist |
| `ref_ambiguous` | A step or outcome ID has no job letter, and the KB has more than one core job |
| `key_duplicate` | A new interview key is used twice in the patch |
| `key_is_id` | A new interview key is already an interview ID in the KB |
| `transcript_missing` | A transcript file named in the patch or the KB is neither in `.pw-kb/transcripts/` nor under `--transcripts`. Also stops `validate` and `migrate` |
| `step_duplicate` | A bootstrap uses a step number twice in one core job |
| `step_missing` | A step named in the patch does not exist |
| `outcome_missing` | An outcome named in the patch does not exist |
| `outcome_merged` | An outcome named in the patch was merged into another |
| `outcome_direction` | A new outcome does not start with Minimize, Maximize, Increase or Reduce. Only in an English study, or when `meta.style.directions` sets the openings |
| `outcome_duplicate` | A new outcome repeats an existing one or another new one |
| `solution_missing` | `solution_evidence` names a solution that does not exist |
| `solution_merged` | `solution_evidence` names a solution that was merged into another |
| `solution_duplicate` | A new solution has the name, or an earlier name, of a solution in the KB or of another new one |
| `solution_group_missing` | A new solution names a group that is neither in the KB nor in `solution_groups` |
| `solution_group_duplicate` | A new group's key or name is already used |
| `solution_group_unused` | Nothing in the patch puts a solution in a new group: no new solution and no `move_solution` |
| `proposal_ref` | A proposal points at a step, outcome, core job, interview, segment, solution or solution group that does not fit |
| `structure` | The KB that would result, or the KB as it stands, breaks `kb-schema.json` or its cross-references |

### Errors that refuse an overview

`overview` reports these, together with the `clarity_` errors above for a sentence that is too long. Nothing is written.

| Code | Meaning |
|---|---|
| `overview_shape` | A part of the overview is missing or not in the right shape: a sentence, a section, a gap's kind or quote, a track's status, who the study is about or its icon, or an unknown key |
| `overview_quote` | A quote is not one the KB holds for that core job, or a phrase in `words` is not part of such a quote |
| `overview_solution` | A gap names a solution that is not a solution in use in the KB |
| `overview_count` | `ask`, `words` or the executor's `others` holds more items than allowed |
| `overview_score` | A sentence holds a percentage or a score word, such as "opportunity score" |
| `overview_method_word` | A sentence holds a word of the method that readers do not know, such as "core job" or "desired outcome" |

### Errors that refuse value themes

`themes` reports these, together with the `clarity_` errors above for a label, a need or a `why` that is too long. Nothing is written.

| Code | Meaning |
|---|---|
| `theme_shape` | A theme is not an object, lacks its label, need, `why` or outcomes, holds an unknown key, or has a highlight without kind, interview and quote |
| `theme_id` | A theme's `id` is not a theme of that core job, or two themes give the same `id` |
| `theme_outcome` | A theme cites an outcome that is not in the KB, was merged into another, or belongs to another core job |
| `theme_need_form` | A theme's need does not start with "Help me". Only in an English study, or when `meta.style.need_start` sets the opening |
| `theme_duplicate` | Two themes of one core job share a label |
| `theme_highlight` | A highlight quote is not on one of the theme's outcomes, nor on a solution used at their steps |

### Warnings

| Code | Meaning |
|---|---|
| `ids_unquoted` | Interview IDs were written as numbers and were read as zero-padded strings, such as `"07"` |
| `unknown_key` | A top-level key the patch format does not have was ignored |
| `ref_legacy` | A step or outcome ID without a job letter, or the older bootstrap form, was read as core job A in a KB with one core job |
| `job_unlinked` | A new interview is linked to no core job, has no `unlinked_reason` saying why, and is not listed in a `new_core_job` proposal |
| `bootstrap_repeated` | The bootstrap was already applied; ignored |
| `interview_skipped` | An interview is already in the KB, by file name or content hash |
| `evidence_dropped` | Patch items whose evidence came only from skipped interviews were dropped |
| `transcript_changed` | A transcript's content differs from when it was added. An error in `validate` |
| `transcripts_root_missing` | A `--transcripts` folder or file does not exist |
| `segment_unknown` | A new interview names a segment the KB does not have |
| `clarity_two_jobs` | A job or step statement may hold two jobs |
| `clarity_acronym` | A statement uses an abbreviation not on the study's list. Solution names are not checked, because product names keep their letters |
| `provenance_ref` | `provenance.transcripts_read` names something that is not an interview ID or a patch key |
| `solution_group_repeated` | A new solution group is already in the KB with the same name and reason; ignored |
| `theme_count` | A core job has more than one value theme per 3 outcomes, or a count outside 5 to 9 |
| `theme_size` | A theme gathers fewer than 3 outcomes, or more than a third of the job's outcomes |
| `theme_one_person` | Every outcome of a theme was voiced by the same one person |
| `theme_overlap` | An outcome sits in more than two themes, or a theme has no outcome of its own |
| `theme_names_solution` | A theme's label or need contains the name of a current solution |
| `theme_quotes` | A theme shows no highlight quotes, or more than 6 |
| `overview_count` | An overview lists more than 5 gaps |
| `labels_missing` | `review` or `map` used English for labels the study has no text for yet; run `labels` |
| `labels_same` | `labels --add`: a label's text is the same as the English one |
| `labels_plural_form` | `labels --add`: a plural label lacks a form the study's language uses |
| `overview_jargon` | A sentence of the overview holds a vague word, such as "pain point" or "workflow"; keep it only when it is the customers' own word |

### Errors that stop a command

| Code | Meaning |
|---|---|
| `file_missing` | The KB, the patch or another file given to the tool does not exist |
| `json_invalid` | The KB, the patch or another file given to the tool is not valid JSON, is not UTF-8, or writes a key twice in one object or NaN. The message gives the line and column |
| `yaml_invalid` | `migrate`: the KB of a study written in YAML is not valid YAML |
| `kb_shape` | The KB is not a JSON object |
| `kb_exists` | `init` refused to overwrite an existing KB or to start next to a study written in YAML, or `migrate` found a study in `.pw-kb/` already, or both `pw-kb.yaml` and `pw-kb.json` |
| `kb_location` | The KB is not `.pw-kb/pw-kb.json`. A study made by an earlier version is moved there with `migrate` |
| `move_conflict` | `migrate` would overwrite a file in `.pw-kb/`; nothing was moved |
| `overview_file` | The file given to `overview` is not an object with `job`, holds an unknown key, or names a core job the KB does not have |
| `themes_file` | The file given to `themes` does not hold `job` and `themes`, holds another key, or names a core job the KB does not have |
| `patch_empty` | The patch file is empty |
| `patch_shape` | The patch is not a JSON object |
| `schema_version` | The KB's schema version is not a number or is newer than the tool knows |
| `migrate_needed` | The KB uses an older schema version, or the study is still in YAML (`.pw-kb/pw-kb.yaml`); run `migrate` |
| `schema_unsupported` | A JSON Schema uses a keyword the built-in checker does not support |
| `skill_file_missing` | A schema, the map template or the file that ships beside it (`labels-en.js`) was not found |
| `skill_file_invalid` | `labels-en.js` is not a label table |
| `language_invalid` | `--language` is not a BCP 47 language code |
| `language_locked` | `labels --language` would change the language of a study that already holds interviews |
| `labels_file` | The file given to `labels --add` does not hold `language` and `labels`. As a warning, `migrate` could not read a study's `labels.yaml` and left it as it was |
| `labels_language` | The file given to `labels --add` is for another language than the study's, or the study is in English |
| `labels_unknown` | `labels --add`: a key is not a label of the map or the review sheet |
| `labels_empty` | `labels --add`: a label's text is empty or not text |
| `labels_placeholder` | `labels --add`: a label does not keep exactly the English label's `{name}` places |
| `labels_plural` | `labels --add`: a plural label is not an object of plural forms with `other`, or a form lacks `{n}` |
| `labels_markup` | `labels --add`: a label holds `<` or `>` |
| `template_invalid` | The map template has no place to put the KB |
| `template_old` | The map template is older than the KB schema; use the one in the skill |
| `style_invalid` | `meta.style` is not shaped as documented |
| `transcript_duplicate` | A transcript file name exists under two `--transcripts` roots |
| `transcript_unreadable` | A transcript could not be read |
| `transcript_type` | A transcript has an extension the tool does not read |
| `reader_missing` | pypdf is needed to read a `.pdf` transcript and is not installed (save the PDF's text as a `.txt` instead), or `migrate` needs PyYAML to read a study written in YAML |
| `proposal_missing` | `apply` named a proposal that is not in the KB |
| `proposal_decided` | `apply` named a proposal that was already approved or rejected |
| `proposal_stale` | The proposal's target no longer exists as it was raised; fix the KB or reject it |
| `crash` | The tool raised an unexpected exception. A bug; the traceback was printed |

## Reading the log with the changelog

A changelog entry in the KB and its log line share `run_id`. So for any change in the KB you can find how long the run took, what else it warned about, which backup it made and, for a merge, which patch and which assistant. The reverse also works: a merge line with `written: true` names the backup to restore if the batch turns out to be wrong.
