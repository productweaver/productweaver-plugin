# Patch format

A patch is one YAML file describing what a batch of transcripts adds. `kb_tool.py merge` checks it and folds it in. Every `quote` must appear verbatim in the named interview's transcript, or nothing is written. The machine-readable version of this format is `patch-schema.json`; the merge checks every patch against it before any other check, and its messages name the exact place in the patch (`patch.step_evidence[0]: missing 'step'`).

## Referring to interviews, outcomes and steps

- A **new** interview gets a short `key` you choose (`n1`, `n2`). Cite it by that key anywhere in the patch. The merge assigns the real ID. A key must not look like an existing ID.
- An **existing** interview is cited by its KB `id`, in quotes: `"07"`. Unquoted, YAML reads `07` as the number 7; the merge then reads it as `"07"` and warns.
- An **outcome** is cited by its ID in quotes: `"6.3"`. Unquoted, YAML reads it as a number and the merge refuses it, because `6.10` would silently become `6.1`.
- A **step** is cited by its number, unquoted: `6`.
- Every evidence item is `{interview, source, quote}`. Inside an interview's own record, items are `{source, quote}`, because the interview is implied.

`source` is one of `transcript`, `quoted_in_notes` or `interviewer_notes`.

## Top-level keys

All are optional, but a patch needs at least one of them. Any other top-level key is ignored with a warning, so a misspelled key cannot pass unnoticed.

```yaml
# Made with Product Weaver · productweaver.com
provenance:            # optional: who extracted this batch and how; copied into the KB's changelog
  assistant: claude-code
  model: claude-opus-5-5
  started: 2026-11-08T14:02:00+01:00
  transcripts_read: [n1, "07"]           # by key or KB ID, never by file name
  notes: Interview 07 is notes only; its quotes are the interviewer's paraphrase.
interviews:            # new interviews only
  - key: n1
    name: Amy Richardson
    file: interview-19-amy-richardson.md   # file name inside a --transcripts folder
    date: 2026-03-05
    format: Transcript                     # Transcript | Notes | Transcript + notes
    cluster: seq                           # an existing segment key, or omit
    tags: [Dry van, Own authority, OTR, Columbus]
    job_executor:
      statement: Solo high-mileage OTR dry-van owner-operator based in Columbus.
      evidence:
        - {source: transcript, quote: "I run dry van, OTR. Been owner-operator for two years."}
    core_functional_job:
      statement: Plan each load around the freight leaving its destination.
      evidence:
        - {source: transcript, quote: "I check the outbound market from the destination before I commit to the inbound load."}
    related_jobs:   [{statement: ..., evidence: [...]}]   # each statement needs at least one quote
    emotional_jobs: [{statement: ..., evidence: [...]}]
    social_jobs:    []
    analyst_note: optional; e.g. "Not the executor of load booking; the carrier dispatches him."

step_evidence:         # quotes showing someone doing an existing step
  - step: 6
    evidence:
      - {interview: n1, source: transcript, quote: "..."}

outcome_evidence:      # quotes supporting an existing outcome (ID from `context`)
  - outcome: "6.1"
    evidence:
      - {interview: n1, source: transcript, quote: "..."}

new_outcomes:          # only when no existing outcome has the same object of control
  - step: 6
    statement: Minimize the time it takes to ...
    evidence:
      - {interview: n1, source: transcript, quote: "..."}

proposed_changes:      # structural changes; stored as pending for the user to decide
  - type: new_step
    stage: conclude
    proposal: Decide whether to keep running OTR or move to regional work
    rationale: Two of 22 interviews weigh this choice; no step covers it.
    evidence:
      - {interview: n1, source: transcript, quote: "..."}

bootstrap:             # ONLY for a KB that has no core job yet
  market_core_job:
    statement: Order ingredients for the coming week
    job_executor: The person who decides what a restaurant orders from suppliers
  steps:
    - {n: 1, stage: define, statement: Estimate how many covers the week will bring, covers: "..."}
    - {n: 2, stage: locate, statement: ...}
```

## Proposal types and what each one needs

Every proposal has `type`, `proposal` (the new wording, or the change in one line) and `rationale` (one sentence of at most 30 words). `evidence` is optional but expected for anything a reviewer must weigh. The merge checks that every target exists; `apply` checks again before it acts.

| `type` | Also needs | Meaning |
|---|---|---|
| `new_step` | `stage` | A step the map lacks. `covers` is optional. Gets the next free number when approved |
| `reword_step` | `target: <step number>` | New wording for a step |
| `reword_outcome` | `target: "<outcome id>"` | New wording for an outcome |
| `reword_core_job` | nothing | New wording for the market core job |
| `merge_outcomes` | `target: "<id to keep>"`, `merge: "<id to fold in>"` | Two outcomes with one object of control |
| `move_outcome` | `target: "<outcome id>"`, `to_step: <step number>` | An outcome under the wrong step |
| `new_segment` | `target: <short lowercase key>` | A kind of executor no segment describes. `proposal` is the segment's name |
| `other` | nothing | Anything else. Applied by hand after approval |

## Provenance

`provenance` says where the batch came from. The merge keeps `assistant`, `model`, `started`, `transcripts_read` and `notes`, copies them into the changelog entry of the merge and logs them, without `notes`, in `KB/logs/kb_tool.jsonl` (see `run-log.md`). `transcripts_read` names interviews by patch key or KB ID; the merge turns keys into IDs and drops anything that is neither with a warning, because a file name would carry the interviewee's name. A reference to an interview the merge skipped as already known is dropped quietly.

## What the merge does with it

1. Checks the patch against `patch-schema.json` and reads dates and unquoted interview IDs the way they were meant.
2. Skips interviews whose file name or content hash is already in the KB, and drops patch items whose evidence comes only from them.
3. Checks every quote against its transcript, every step, outcome, interview and proposal target, every statement's clarity, outcome wording (it must start with a direction verb) and exact duplicates of existing outcome statements.
4. Builds the new KB in memory and checks it against `kb-schema.json`.
5. On success: copies the current KB to `KB/backups/`, adds interviews with new IDs, appends evidence without duplicates, numbers new outcomes (next free `<step>.<k>`), files proposals as `P<n>` with status `pending`, recounts coverage, marks derived layers stale and writes a changelog entry with what was added, the time, the `run_id` and the provenance. Every run, successful or not, also gets one line in `KB/logs/kb_tool.jsonl`.

`--dry-run` runs steps 1 to 4 and reports the same verdict the real merge would. `--json` prints the result as one JSON object. Running the same patch twice changes nothing.
