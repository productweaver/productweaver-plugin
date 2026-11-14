# Usage events

Only after the user says yes, the plugin records small usage events and sends them to Product Weaver (productweaver.com). The events show which parts of the plugin work and which do not, so they can be fixed. Each event is one JSON object. This file lists every event and every field, with the exact values each field may hold. A test keeps it in step with the code, as `run-log.md` is.

An event is sent at three moments: when the user says yes (`usage_on`), when a session starts and ends (`session_start`, `session_end`), and for each run of `kb_tool.py` after the yes (`tool_run`, made from the run log). Events wait in `.pw-kb/usage/waiting.jsonl` and move to `sent.jsonl` once they are sent. `sent.jsonl` holds each event exactly as it left.

To make events, `pw_usage.py` reads only the run log, `.pw-kb/logs/kb_tool.jsonl`, and two fields of `pw-kb.json`: `meta.language` and the `round` entries of each core job's plan (`overview.jobs[].next.learn.round`), as a count. To decide whether the run log is in git, it also reads `.pw-kb/.gitignore` and git's index file, and looks there for the run log's path only.

Before each send, every waiting event is checked again against the tables below and the study's ID in `settings.json`. An event that does not fit is deleted, never sent. An event counts as sent when www.productweaver.com took it (an answer of 2xx) or refused it for good (400 or 413). Any other answer, or none, keeps it waiting, for at most 90 days and 1,000 events.

## What is never sent

- Interviews, transcripts, names, quotes, prompts, notes or file names.
- Anything in `args`, and the `run_id`, `ts`, `backup`, `out`, `since` and `job` fields of the run log.
- KB hashes and patch hashes. The `patch_sha256` is only used on the machine to count `attempt`.
- `provenance.started` and `provenance.transcripts_read`. Only the numbers worked out from them leave: `batch_minutes` and `transcripts_read` (a count).
- Error and warning messages. Only codes and counts leave.
- The raw `os` and `agent` of the run log. Only the fixed values in the tables below leave.
- Anything when the user says no, or stops sharing.

The server adds no names, no e-mail and no IP address to an event. The `study` field is a random ID made at the yes, from nothing else.

## Types

Every event is checked against these types. A field that does not match is not sent.

- **int**: a whole number from 0 to 1,000,000.
- **bool**: `true` or `false`.
- **code**: a string matching `^[a-z][a-z0-9_]{0,39}$`.
- **counts map**: an object whose keys are codes and whose values are ints.
- **uuid4**: a lowercase UUID version 4 string.
- Every pattern must match the whole value (Python `re.fullmatch`, JavaScript `^...$` without the `m` flag), ASCII only. A trailing newline does not match.
- Optional fields are left out when they do not apply. They are never `null`. Only `plugin`, `tool` and `model` may be `null`.

## Envelope

Every event carries these fields, first, in this order.

| Field | Type or allowed values | Meaning |
|---|---|---|
| `v` | the integer `1` | The format version of this file |
| `id` | uuid4 | Random, made for each event. Lets the server drop a repeat when a send is retried |
| `event` | `usage_on`, `session_start`, `session_end` or `tool_run` | The event type |
| `at` | `YYYY-MM-DDTHH:MMZ`, UTC, to the minute | When it happened. For `tool_run`, the run log's `ts` converted to UTC, with the seconds dropped, not rounded |
| `study` | uuid4 | The random ID of this study. Made at the yes |
| `plugin` | `^[0-9]+\.[0-9]+\.[0-9]+$` or `null` | The plugin version |
| `tool` | `^[0-9]+\.[0-9]+\.[0-9]+$` or `null` | The `kb_tool.py` version (`tool_version` in the run log) |
| `assistant` | `claude-code`, `claude-cowork`, `claude-ai`, `chatgpt`, `codex`, `copilot-cli`, `vscode`, `cursor`, `gemini-cli`, `antigravity` or `other` | The assistant. Anything not in the list is `other`. Claude Desktop: `claude-cowork` in a Cowork task, `claude-code` in its Code tab, `claude-ai` in a chat |
| `model` | `^[a-z0-9][a-z0-9.-]{0,47}$` or `null` | The model ID, when the assistant gives it |
| `os` | `macos`, `windows`, `linux` or `other` | The operating system family |
| `python` | `^[0-9]+\.[0-9]+$` | Python major and minor version, such as `3.11` |

## Events

### `usage_on`

The yes. It reports the study as it is at that moment.

| Field | Type or allowed values | Meaning |
|---|---|---|
| `asked_at` | `new_study` or `existing_study` | Whether the question came at a study with no interviews or at one that already has some |
| `language` | `^[a-z]{2,3}(-[A-Z][a-z]{3})?(-([A-Z]{2}|[0-9]{3}))?$` | The study's language, a BCP 47 code such as `en`, `it` or `pt-BR`. The same pattern as `meta.language` in `kb-schema.json`. `en` when the study does not say. A language that does not match is left out of the event |
| `kb` | object, see `kb` below | The size of the KB at the yes |

### `session_start`

| Field | Type or allowed values | Meaning |
|---|---|---|
| `skill` | `pw-start` or `pw-discovery` | The skill that started |
| `path` | `transcripts`, `no_transcripts` or `existing_study` | `pw-start` only: how the person starts |
| `language` | same pattern as in `usage_on` | The study's language |

### `session_end`

| Field | Type or allowed values | Meaning |
|---|---|---|
| `skill` | `pw-start` or `pw-discovery` | The skill that ended |
| `guide_written` | bool | `pw-start` only: whether it wrote the guide for the person |
| `plan_entries` | int | How many round entries the plan in the KB holds |

### `tool_run`

One per run-log line after the yes. Fields marked "optional" are present only when the run log line has them.

| Field | Type or allowed values | Meaning |
|---|---|---|
| `command` | `init`, `labels`, `context`, `merge`, `apply`, `themes`, `overview`, `review`, `map`, `validate` or `migrate` | The command that ran |
| `exit_code` | int from 0 to 2 | 0 success, 1 refused or failed with a message, 2 crashed |
| `written` | bool | Whether the run changed the KB file |
| `duration_ms` | int from 0 to 86,400,000, rounded to the nearest 100 | How long the run took |
| `dry_run` | bool, optional | Whether it was a dry run |
| `nothing_new` | bool, optional | A merge whose patch had nothing new |
| `bootstrap` | bool, optional | The merge created the core job and job map |
| `rehash` | bool, optional | `validate` was given `--rehash` |
| `moved` | bool, optional | `migrate` moved a study into `.pw-kb/` |
| `git` | bool, optional | `.pw-kb/` sits in a git repository and has no `.gitignore` of its own |
| `errors` | counts map, optional | Error codes with counts, such as `{"quote_not_found": 1}` |
| `warnings` | counts map, optional | Warning codes with counts |
| `counts` | object, optional, see `counts` below | What a merge, themes or overview run changed |
| `kb` | object, optional, see `kb` below | The size of the KB after the run |
| `labels` | object, optional, see `labels` below | Counts of labels, never their text |
| `language` | same pattern as in `usage_on`, optional; left out when it does not match | The study's language (`init`, `labels`) |
| `browser` | `opened`, `failed`, `no_display` or `off`, optional | The result of `map --open` |
| `exception` | `^[A-Z][A-Za-z]{0,39}$`, optional | The exception class name when the tool crashed. Never the message |
| `schema_from` | int, optional | `migrate`: the schema version number the KB had before |
| `proposal_type` | code, optional | `apply`: the kind of proposal decided on |
| `decision` | `approve` or `reject`, optional | `apply`: what was decided |
| `structure_problems` | int, optional | `validate`: problems found |
| `outcome_quotes` | int, optional | `validate`: outcome quotes in the KB |
| `drifted` | int, optional | `validate`: transcripts whose content changed |
| `transcripts_copied` | int, optional | `migrate`: transcripts copied into `.pw-kb/` |
| `batch_minutes` | int, optional | `merge` with provenance: the minutes from `provenance.started` to the run's `ts`, rounded to the nearest minute |
| `attempt` | int, optional | `merge`: 1 plus the number of earlier lines of the run log with the same `patch_sha256` |
| `transcripts_read` | int, optional | `merge` with provenance: how many transcripts `provenance.transcripts_read` lists |

### `counts`

The keys are the ones `run-log.md` documents. Each value is an int. A key that the run log line does not have is left out.

| Field | Type or allowed values | Meaning |
|---|---|---|
| `interviews_added` | int | merge: new interviews |
| `interviews_skipped` | int | merge: interviews already in the KB |
| `outcomes_added` | int | merge: new outcomes |
| `step_quotes` | int | merge: quotes added to steps |
| `outcome_quotes` | int | merge: quotes added to outcomes |
| `proposals_filed` | int | merge: proposals filed |
| `transcripts_copied` | int | merge: transcripts copied into `.pw-kb/transcripts/` |
| `solutions_added` | int | merge: new solutions |
| `solution_groups_added` | int | merge: new solution groups |
| `solution_quotes` | int | merge: quotes added to solutions already in the KB |
| `themes` | int | themes: that core job's themes after the run |
| `theme_outcomes` | int | themes: outcomes in at least one theme |
| `unassigned` | int | themes: outcomes in no theme |
| `overview_gaps` | int | overview: gaps in the overview just written |
| `overviews` | int | overview: core jobs that have an overview after the run |

### `kb`

The size of the KB. Only these keys, each an int.

| Field | Type or allowed values | Meaning |
|---|---|---|
| `interviews` | int | Interviews |
| `core_jobs` | int | Core jobs |
| `unlinked_interviews` | int | Interviews linked to no core job |
| `steps` | int | Job steps |
| `thin_steps` | int | Steps with little evidence |
| `outcomes` | int | Live outcomes |
| `pending_proposals` | int | Proposals not yet decided |
| `solutions` | int | Live solutions |
| `solution_groups` | int | Solution groups |
| `themes` | int | Value themes |
| `overviews` | int | Core jobs with an overview |
| `stale` | int | How many derived layers are stale. In the run log this is a list of layer names; only its length is sent |

### `labels`

Counts only, never a label's text. Each an int.

| Field | Type or allowed values | Meaning |
|---|---|---|
| `missing` | int | Labels that still show in English |
| `added` | int | Labels `labels --add` kept |
| `refused` | int | Problems that stopped `labels --add` |
| `migrated` | int | 1 when `migrate` turned `labels.yaml` into `labels.json`, else 0 |

## Files in `.pw-kb/usage/`

- `.gitignore` holds `*`, so the folder never goes into git.
- `README.md` says in plain words what the folder is and how to stop.
- `settings.json` holds the choice, when it was given, the study ID, and where the converter stopped reading the run log. After a no, it keeps the study ID of an earlier yes, the key for a deletion request; a later yes makes a new one.
- `waiting.jsonl` holds events recorded but not yet sent.
- `sent.jsonl` holds each event exactly as it left, and when it left. It is never trimmed.

## Turning it off

- Say no, or ask to stop. Events that are waiting are deleted. `sent.jsonl` stays as the record of what left.
- Without the assistant: in `.pw-kb/usage/settings.json`, change `"share": true` to `"share": false`. Nothing is then recorded or sent for this study.
- Set `KB_TOOL_USAGE=0` or `DO_NOT_TRACK=1` in the environment. Nothing is recorded or sent, whatever the study says.
- Set `KB_TOOL_LOG=0`. This stops the run log, so it also stops the `tool_run` events.
