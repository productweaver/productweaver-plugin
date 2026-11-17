# Patch format

A patch is one JSON file describing what a batch of transcripts adds. `kb_tool.py merge` checks it and folds it in. Every `quote` must appear verbatim in the named interview's transcript, or nothing is written. The machine-readable version of this format is `patch-schema.json`; the merge checks every patch against it before any other check, and its messages name the exact place in the patch (`patch.step_evidence[0]: missing 'step'`).

## JSON rules

A patch is plain JSON, written in UTF-8.

- Put double quotes around every key and every text.
- Inside a text, write a straight quote mark as `\"` and a line break as `\n`. A curly quote mark (“ ”) needs nothing.
- Put a comma between items, but none after the last one.
- Write no comments. The format has a field for each thing worth saying: `provenance.notes`, `analyst_note`, `rationale`.
- Write every ID as a text in quotes, even when it is all digits: `"07"`, `"A.6.3"`. A number is not an ID.

When the file is not valid JSON, the merge stops with `json_invalid`. Its message gives the line and column, and shows the line with a `^` under the spot. Fix that spot and run the merge again: a refused merge writes nothing.

## Referring to interviews, core jobs, steps and outcomes

Write every ID as a string, in quotes. Copy step and outcome IDs from `context` output, never from memory.

- A **new** interview gets a short `key` you choose (`"n1"`, `"n2"`). Cite it by that key anywhere in the patch. The merge assigns the real ID. A key must not look like an existing ID.
- An **existing** interview is cited by its KB `id`: `"07"`. Written as the number `7`, it loses its leading zero; the merge then reads it as `"07"` and warns.
- A **core job** is cited by its letter: `"A"`, `"B"`.
- A **step** is cited by its core job's letter and its number in that job: `"A.6"`.
- An **outcome** is cited by its step's ID and its number under that step: `"A.6.3"`. Written as a number, `2.10` would be `2.1`, another outcome, so the merge never fixes it.
- A **solution** is cited by its ID: `"S3"`. A **solution group** is cited by its key: `"send-orders"`.
- Every evidence item is an object with `interview`, `source` and `quote`. Inside an interview's own record, items have only `source` and `quote`, because the interview is implied.

`source` is one of `transcript`, `quoted_in_notes` or `interviewer_notes`.

**IDs without the job letter.** Patches written for schema 1 used `"6"` and `"6.3"`. While the KB has only one core job, the merge reads them as `"A.6"` and `"A.6.3"` and warns. Once the KB has two or more core jobs, an ID without its letter is refused.

## Top-level keys

All are optional, but a patch needs at least one of them. Any other top-level key is ignored with a warning, so a misspelled key cannot pass unnoticed.

```json
{
  "generated_with": "Made with Product Weaver · productweaver.com",
  "provenance": {
    "assistant": "claude-code",
    "model": "claude-opus-5-5",
    "started": "2026-11-08T14:02:00+01:00",
    "transcripts_read": ["n1", "07"],
    "notes": "Interview 07 is notes only; its quotes are the interviewer's paraphrase."
  },
  "interviews": [
    {
      "key": "n1",
      "name": "Amy Richardson",
      "file": "interview-19-amy-richardson.md",
      "date": "2026-03-05",
      "format": "Transcript",
      "cluster": "seq",
      "tags": ["Dry van", "Own authority", "OTR", "Columbus"],
      "job_executor": {
        "statement": "Solo high-mileage OTR dry-van owner-operator based in Columbus.",
        "evidence": [
          {"source": "transcript", "quote": "I run dry van, OTR. Been owner-operator for two years."}
        ]
      },
      "core_functional_job": {
        "statement": "Plan each load around the freight leaving its destination.",
        "job": "A",
        "evidence": [
          {"source": "transcript", "quote": "I check the outbound market from the destination before I commit to the inbound load."}
        ]
      },
      "related_jobs": [
        {
          "statement": "Collect payment for delivered loads.",
          "job": "B",
          "evidence": [
            {"source": "transcript", "quote": "..."}
          ]
        }
      ],
      "emotional_jobs": [
        {"statement": "...", "evidence": [{"source": "transcript", "quote": "..."}]}
      ],
      "social_jobs": [],
      "analyst_note": "Answered for her brother's truck as well."
    }
  ],
  "interactions": [
    {
      "key": "f1",
      "interview": "01",
      "file": "dana-second-call.md",
      "date": "2026-11-09",
      "format": "Transcript",
      "changed": "She now gets receipts through a client portal, not by email."
    }
  ],
  "step_evidence": [
    {
      "step": "A.6",
      "evidence": [
        {"interview": "n1", "source": "transcript", "quote": "..."}
      ]
    }
  ],
  "outcome_evidence": [
    {
      "outcome": "A.6.1",
      "evidence": [
        {"interview": "n1", "source": "transcript", "quote": "..."}
      ]
    }
  ],
  "new_outcomes": [
    {
      "step": "A.6",
      "statement": "Minimize the time it takes to ...",
      "evidence": [
        {"interview": "n1", "source": "transcript", "quote": "..."}
      ]
    }
  ],
  "solution_groups": [
    {
      "key": "send-orders",
      "name": "Ways to send the order",
      "why": "Each one gets the week's order to a supplier, and owners keep one per supplier."
    }
  ],
  "new_solutions": [
    {
      "name": "Supplier's ordering app",
      "kind": "product",
      "group": "send-orders",
      "uses": [
        {
          "step": "A.4",
          "evidence": [
            {"interview": "n1", "source": "transcript", "quote": "..."}
          ]
        },
        {
          "step": "A.5",
          "status": "stopped",
          "evidence": [
            {"interview": "n1", "source": "transcript", "quote": "..."}
          ]
        }
      ]
    }
  ],
  "solution_evidence": [
    {
      "solution": "S3",
      "step": "A.4",
      "evidence": [
        {"interview": "n1", "source": "transcript", "quote": "..."}
      ]
    }
  ],
  "proposed_changes": [
    {
      "type": "new_step",
      "job": "A",
      "stage": "conclude",
      "proposal": "Decide whether to keep running OTR or move to regional work",
      "rationale": "Two of 22 interviews weigh this choice; no step covers it.",
      "evidence": [
        {"interview": "n1", "source": "transcript", "quote": "..."}
      ]
    }
  ],
  "bootstrap": {
    "core_jobs": [
      {
        "id": "A",
        "statement": "Order ingredients for the coming week",
        "job_executor": "The person who decides what a restaurant orders from suppliers",
        "steps": [
          {"n": 1, "stage": "define", "statement": "Estimate how many covers the week will bring", "covers": "Bookings, events and weather"},
          {"n": 2, "stage": "locate", "statement": "..."}
        ]
      },
      {
        "id": "B",
        "statement": "...",
        "steps": [
          {"n": 1, "stage": "define", "statement": "..."}
        ]
      }
    ]
  }
}
```

What each key is for:

- `generated_with`: the Product Weaver credit. Keep it at the top.
- `provenance`: optional. Who extracted this batch and how; the merge copies it into the KB's changelog. `transcripts_read` names interviews by key or KB ID, never by file name.
- `interviews`: new interviews only. `file` is the file name, in `.pw-kb/transcripts/` or a `--transcripts` folder. `date` is written `YYYY-MM-DD`, so it can be compared with the dates of the person's later conversations. `format` is `Transcript`, `Notes` or `Transcript + notes`. `Email` and `Chat` are allowed for a first contact too, with the contact-details rule below: its copy is named `<key>-1-<date>.txt`. A `name` already in the study (case and accents ignored), or used twice in the patch, is refused (`same_person`): send a later conversation under `interactions`. Add `"same_name_ok": true` only when the user said it is another person with the same name; it is not stored. `cluster` is an existing segment key; leave it out when none fits.
- `core_functional_job.job`: the core job this rolls up to. If none fits, leave `job` out and write `"unlinked_reason": "Her carrier picks her loads."` instead, saying why none fits.
- `related_jobs`, `emotional_jobs`, `social_jobs`: each statement needs at least one quote. A related job's `job` is optional: use it when the related job is another core job of the study. `analyst_note` is optional, for anything else a reader must know.
- `interactions`: later conversations with someone already in the study, or with a new interview of this patch. See "A later conversation with someone already in the study" below.
- `step_evidence`: quotes showing someone doing an existing step.
- `outcome_evidence`: quotes supporting an existing outcome (ID from `context`).
- `new_outcomes`: only when no existing outcome has the same object of control.
- `solution_groups`: new groups only; see "Current solutions" below.
- `new_solutions`: only when no solution in `context` is the same thing. `kind` is `product`, `everyday_tool`, `people` or `own_method`. `group` is a group key from `context`, or one from `solution_groups` above. A use's `status` is `current` (the default) or `stopped`.
- `solution_evidence`: more quotes for a solution already in the KB (ID from `context`). Add `"status": "stopped"` when the person gave it up for that step, as a later conversation may say.
- `proposed_changes`: structural changes, stored as pending for the user to decide.
- `bootstrap`: ONLY for a KB that has no core job yet. One entry per core job, with the IDs `"A"`, `"B"`, `"C"`… in order. `A` is the job most people have as their main job, and each job's steps are numbered in stage order.

A bootstrap's core jobs and steps exist for the rest of the same patch: its new interviews may link to `"A"` and `"B"`, and its `step_evidence` and `new_outcomes` may cite `"A.2"` or `"B.1"`. Bootstrap steps carry no quotes of their own; put the quotes in `step_evidence`. Steps with no quote yet are allowed and show up as thin steps to ask about next.

## A later conversation with someone already in the study

A follow-up call, new notes, an email or a chat with someone the study already holds is a later conversation of that person. Send it under `interactions`, not under `interviews`: an entry in `interviews` is a new person. The person keeps one record, and the merge numbers their conversations: the first one is 1, the next one 2, and so on. What to take from it, and what to do when the merge refuses it, is in `pw-rules.md`, "The same person again". A patch for one follow-up is named `<date>-follow-up-<id>.json`, so no name reaches the changelog or the run log.

```json
{
  "interactions": [
    {
      "key": "f1",
      "interview": "01",
      "file": "dana-second-call.md",
      "date": "2026-11-09",
      "format": "Transcript",
      "changed": "She now gets receipts through a client portal, not by email.",
      "tags": ["Client portal"],
      "job_executor_evidence": [{"source": "transcript", "quote": "..."}],
      "core_functional_job_evidence": [],
      "related_jobs": [],
      "emotional_jobs": [],
      "social_jobs": []
    }
  ],
  "step_evidence": [
    {
      "step": "A.4",
      "evidence": [
        {"interview": "f1", "source": "transcript", "quote": "..."}
      ]
    }
  ]
}
```

- Only `key`, `interview`, `file` and `date` are needed.
- `key` is a short key you choose (`"f1"`, `"f2"`). Everywhere else in the patch, evidence from this conversation cites the key: `"interview": "f1"`. The merge stores such a quote as `"interview": "01", "interaction": 2`.
- `interview` is the person: a KB interview ID, or the key of a new interview in the same patch. So a first batch can hold someone's first call and their follow-up.
- `date` is written `YYYY-MM-DD`. Any other form is refused, because the latest conversation decides what a person does now.
- `format` is `Transcript` (the default), `Notes`, `Transcript + notes`, `Email` or `Chat`.
- `changed` is one sentence of at most 30 words. Write it only when the person's situation or answer differs from before.
- `related_jobs`, `emotional_jobs` and `social_jobs` are added to the person's record, with the same rules as on a new interview. `job_executor_evidence` and `core_functional_job_evidence` add quotes to the person's own statements. `tags` are added to the person's tags.
- A key names a conversation, not a person. Never put it where a person is meant: in a `new_core_job`'s `interviews`, or as a `relink_interview` target. Name the person there. In `provenance.transcripts_read`, a key is read as its person.

What the merge refuses or skips:

- **A file already in the study**, by name or content hash, is skipped, as for interviews, so a batch can be re-run. When the person's own interview is skipped because the study already holds it, their later conversation goes to the person in the study: it is skipped too when the study holds its file, and is added as their next conversation when the file is new.
- **The same conversation twice.** A second conversation with the same person on the same date and in the same format is refused (`same_interaction`). Check the person's conversations in `context` first. If it really is another conversation, add `"another": true`.
- **Contact details in an email or a chat.** The file of an `Email` or `Chat` conversation must hold no email address and no header line (`From:`, `To:`, `Cc:`, `Bcc:`, `Subject:` or `Sent:`). Never name the user's own email or chat file: save a cleaned text copy as `.pw-kb/transcripts/<id>-<n>-<date>.txt` and name that file. `<id>` is the person's ID (their key when they are new in this patch) and `<n>` the conversation's number, the next after the ones `context` lists (2 when it lists none). A first contact by email or chat is a new interview, and its copy is `.pw-kb/transcripts/<key>-1-<date>.txt`. Text the user pastes or types in the chat, such as notes, is saved the same way. Leave out the header lines, the signature and any legal footer. Inside a sentence, write `[address]` for an email address and `[phone]` for a phone number. Keep everything else word for word. A file that still holds an address or a header line is refused (`contact_details`).

**A conversation already in the study.** A later patch has no key for a conversation the study already holds, for example the patch after an approved `new_core_job`. There, a quote from it cites the person's ID and the conversation's number: `{"interview": "01", "interaction": 2, "source": "transcript", "quote": "..."}`. Without `interaction`, the quote is checked against the person's first conversation.

## Current solutions

A current solution is what someone uses today to get a step done: a product, an everyday tool, another person or their own method. How to spot, name and group them is in `pw-rules.md`, "Current solutions".

- **A solution already in the KB** is cited by its ID in `solution_evidence`: `"S3"`. Run `context` first; its CURRENT SOLUTIONS block lists every group and solution with its steps.
- **A new solution** goes in `new_solutions`, with its `kind`, its `group` and one use per step it serves. The merge gives it the next free ID. A name that matches a solution in the KB, now or in its history, is refused: send the quotes as `solution_evidence` instead.
- **A new group** goes in `solution_groups`, with a `key` you choose, a `name` and a `why`. Something in the same patch must put a solution in it: a new solution, or a `move_solution` proposal. A group repeated exactly from an earlier merge is ignored, so a batch can be re-run.
- **A use** names a step, never an outcome. When the quote shows the tool helps reach an outcome, use that outcome's step.
- **`"status": "stopped"`** marks a solution the person used for that step and gave up. Pick the quote that says why. Leave `status` out for what they use now.

Solution quotes do not count as evidence for the step. When the passage also shows the person doing the step, add it to `step_evidence` too.

## Linking interviews to core jobs

Each new interview's `core_functional_job` carries `job`: the core job its own job rolls up to. That is the person's main link. A related job may carry `job` too, when it is another core job of the study. One person can so be linked to several core jobs.

Leave `job` out when no core job fits. Then either raise a `new_core_job` proposal and list the interview in its `interviews`, or say in `unlinked_reason`, next to the statement, why the person carries out none of the study's jobs. An interview with no link, no `unlinked_reason` and no place in a `new_core_job` gets a warning. A `core_functional_job` with both `job` and `unlinked_reason` is refused. When the person is linked later, the tool moves the reason into the statement's `history`. Keep `analyst_note` for anything else a reader must know.

Links to existing interviews change only through a `relink_interview` proposal.

## Proposal types and what each one needs

Every proposal has `type`, `proposal` (the new wording, or the change in one line) and `rationale` (one sentence of at most 30 words). `evidence` is optional but expected for anything a reviewer must weigh. The merge checks that every target exists; `apply` checks again before it acts.

| `type` | Also needs | Meaning |
|---|---|---|
| `new_step` | `"job"`, `"stage"` | A step the core job's map lacks. `covers` is optional. Gets the next free number in that job when approved. `job` may be left out while the KB has one core job |
| `reword_step` | `"target": "<step id>"` | New wording for a step |
| `reword_outcome` | `"target": "<outcome id>"` | New wording for an outcome |
| `reword_core_job` | `"target": "<job id>"` | New wording for a core job. `target` may be left out while the KB has one core job |
| `merge_outcomes` | `"target": "<id to keep>"`, `"merge": "<id to fold in>"` | Two outcomes with one object of control, under the same core job |
| `move_outcome` | `"target": "<outcome id>"`, `"to_step": "<step id>"` | An outcome under the wrong step. The step may belong to another core job |
| `new_segment` | `"target": "<short lowercase key>"` | A kind of executor no segment describes. `proposal` is the segment's name |
| `confirm_core_job` | `"target": "<job id>"` | Confirm a core job that is still proposed. `proposal` is its statement. The merge files one for each core job of a bootstrap, so you rarely write one. Approved, the job becomes approved. Rejected, nothing changes |
| `new_core_job` | `"job_executor"`, `"steps"`, `"interviews"` | A core job the study has no place for. `proposal` is its statement. `steps` is a list of `{stage, statement, covers, evidence}`. `interviews` lists, by key or ID, the people whose own core job rolls up to it |
| `move_step` | `"target": "<step id>"`, `"to_job": "<job id>"` | A step under the wrong core job. Optional `stage`. Its outcomes move with it |
| `relink_interview` | `"target": "<interview id>"`, `"job": "<job id>"` or `"job": null` | Change an existing interview's main link. With `"related_job": "<statement>"`, change the link of that related job instead. Removing a main link stores `rationale` as the interview's `unlinked_reason` |
| `merge_solutions` | `"target": "<id to keep>"`, `"merge": "<id to fold in>"` | Two solutions that are the same thing under two names. The folded one's quotes move to `target` |
| `move_solution` | `"target": "<solution id>"`, `"to_group": "<group key>"` | A solution in the wrong group. The group may be one this patch adds |
| `reword_solution` | `"target": "<solution id>"` | A better name for a solution. `proposal` is the new name. Optional `kind` corrects its kind |
| `reword_solution_group` | `"target": "<group key>"` | A better name for a group. `proposal` is the new name. Optional `why` gives the group's new reason |
| `other` | nothing | Anything else. Applied by hand after approval |

A `new_core_job` gets the next free letter when approved, and its steps are numbered from 1. It carries no outcomes, because an outcome ID needs its step to exist. After approval, write a short follow-up patch for the linked interviews: they are already in the KB, so cite them by ID, and add outcomes and step evidence for the new job.

```json
{
  "proposed_changes": [
    {
      "type": "new_core_job",
      "proposal": "Staff each shift with enough cooks",
      "job_executor": "Kitchen managers who build the weekly rota",
      "rationale": "One of six interviews builds the rota, a job no core job covers.",
      "interviews": ["n4"],
      "steps": [
        {
          "stage": "define",
          "statement": "Estimate how many cooks each shift needs",
          "evidence": [
            {"interview": "n4", "source": "transcript", "quote": "..."}
          ]
        }
      ],
      "evidence": [
        {"interview": "n4", "source": "transcript", "quote": "..."}
      ]
    }
  ]
}
```

## Provenance

`provenance` says where the batch came from. The merge keeps `assistant`, `model`, `started`, `transcripts_read` and `notes`, copies them into the changelog entry of the merge and logs them, without `notes`, in `.pw-kb/logs/kb_tool.jsonl` (see `run-log.md`). `transcripts_read` names interviews by patch key or KB ID; the merge turns keys into IDs and drops anything that is neither with a warning, because a file name would carry the interviewee's name. A reference to an interview the merge skipped as already known is dropped quietly.

## What the merge does with it

1. Reads the file as JSON, checks the patch against `patch-schema.json`, reads interview IDs written as numbers the way they were meant, and gives IDs without a job letter the letter of the only core job (or refuses them when there are several).
2. Skips interviews and later conversations whose file name or content hash is already in the KB, and drops patch items whose evidence comes only from them.
3. Checks every quote against its transcript, every step, outcome, interview, core job link, solution, solution group and proposal target, every statement's clarity, outcome wording (it must start with a direction verb), exact duplicates of existing outcome statements under the same core job and solution names already in the KB.
4. Builds the new KB in memory and checks it against `kb-schema.json`.
5. On success: copies each new transcript into `.pw-kb/transcripts/` and the current KB to `.pw-kb/backups/`, adds interviews with new IDs, appends evidence without duplicates, numbers new outcomes (next free `<step>.<k>`) and new solutions (next free `S<n>`), files proposals as `P<n>` with status `pending` (after a bootstrap, first one `confirm_core_job` per core job), recounts coverage and who is linked to which core job, marks derived layers stale and writes a changelog entry with what was added, the time, the `run_id` and the provenance. Every run, successful or not, also gets one line in `.pw-kb/logs/kb_tool.jsonl`.

After a merge that wrote the KB, it rebuilds `review.md`, the interview guide and the map, as `review` and `map` do; `--no-publish` skips that. `--dry-run` runs steps 1 to 4 and reports the same verdict the real merge would, for scripts and tests. `--json` prints the result as one JSON object. Running the same patch twice changes nothing.
