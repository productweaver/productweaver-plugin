# Changelog

Changes to the productweaver plugin, newest first. Versions follow semantic
versioning.

## 0.2.0 — 2026-11-10

A study can now hold more than one core job.

- When the people interviewed do different jobs, for example owner-operators
  who plan loads and fleet managers who keep trucks running, the skill finds
  each core job by abstracting from every interview's own job. Each core job
  gets a letter (A, B…) and its own job map.
- Every interview is linked to the core job its own job rolls up to. A related
  job can link the same person to another core job. People whose job fits none
  are listed with the reason, which moves to history once they are linked.
- After the first batch, each core job comes with a decision to confirm it
  ("approve P1"), saying how many people back it. Before, a first core job
  stayed "proposed" with no way to confirm it.
- New decisions for the team: add a core job, confirm one, move a step to
  another core job, and change which core job an earlier interview is linked
  to.
- The review sheet has a job map and a people section per core job. The
  discovery map has a core job switcher under the title and shows each
  person's jobs.
- **Step and outcome IDs now start with their core job's letter**: step `6`
  is now `A.6` and outcome `6.3` is now `A.6.3`, even in a study with one core
  job, so no ID changes when a second job appears.
- **Existing knowledge bases need one migration.** The assistant runs
  `kb_tool migrate` when the tool asks for it. It keeps a backup, turns the
  core job into core job A and adds the letter to every ID. Patches written
  for 0.1 still merge into a study with one core job. A discovery map made
  with 0.1 cannot be used as a template any more; the skill's own template is
  used instead.

## 0.1.2 — 2026-11-09

Changes for the Anthropic directory review. The plugin works as before.

- The Python packages the skill uses now have exact versions, and a lock file
  ships with the script, so uv installs the same packages on every machine.
- The discovery map now holds the readable build of js-yaml 4.1.0 instead of
  the minified one. The code is the same version, and each map file is about
  75 KB larger.

## 0.1.1 — 2026-11-09

Changes for the Anthropic directory review. The plugin works as before.

- `kb_tool.py` now names each environment variable it reads directly. It
  still makes no network calls, and the variables only tell the local run log
  which assistant ran the tool.
- The run log guide no longer includes a Python one-liner.
- The plugin's home and documentation links now point to this repository.

## 0.1.0 — 2026-11-09

First release.

- The **distill-kb** skill turns customer interview transcripts into an
  Outcome-Driven Innovation knowledge base in one YAML file. Every quote is
  checked against its transcript before a merge, and a merge that fails a
  check changes nothing.
- Each run can write a review sheet and an interactive discovery map that
  works offline.
- Every run adds a line to a local run log, which holds no quotes or names.
- Installs in Claude Code, Codex and GitHub Copilot from the marketplace
  `productweaver-plugin`.
