# Changelog

Changes to the productweaver plugin, newest first. Versions follow semantic
versioning.

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
