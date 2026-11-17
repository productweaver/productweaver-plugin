---
name: pw-discovery
description: Turn raw customer interview transcripts into Outcome-Driven Innovation (ODI) knowledge and fold it into a knowledge base, one JSON file, that grows with every batch. Use whenever someone shares new interview transcripts, notes or emails (md, txt, docx, pdf), also from someone already interviewed, and wants jobs-to-be-done extracted, job executors and core jobs identified, job steps or desired outcomes updated, the tools and workarounds people use today collected and grouped, evidence quotes attached, the outcomes grouped into a few value themes to guide ideation, or an existing ODI/JTBD knowledge base updated or started. Also use for "add these interviews to the KB", "add my follow-up call with Dana", or starting an ODI study for a new client, even if the user doesn't say "ODI" or "JTBD". Also use for answers to its decisions, such as "In my Product Weaver study, the goal is right", and when the user asks to stop sharing usage statistics. From Product Weaver (productweaver.com).
---

# pw-discovery: fold interviews into an ODI knowledge base

*A free skill from [Product Weaver](https://productweaver.com).*

One JSON file is the knowledge base (KB). Each run reads new transcripts, extracts ODI knowledge with verbatim evidence, and merges it into the KB through `scripts/kb_tool.py`. The script checks every quote against its transcript and refuses the whole merge if one does not match. That makes the KB safe to build on over many runs: nothing in it is paraphrased evidence or a duplicate.

## Running the script

The script needs Python 3.9 or newer and nothing else: it uses only Python's standard library, so `kb_tool.py` installs nothing and needs no network. It finds its schemas and the map template next to itself, so run it from the root of the workspace, where the study lives:

```
python3 <skill folder>/scripts/kb_tool.py <command> ...
```

Below, `kb_tool` stands for that line. Do not write plain `python`; many machines do not have it. On Windows, if `python3` is missing, use `py -3`.

Write the script's full path in every command: never put it in a shell variable (`S=<skill folder>`), never `cd` into the skill folder, and never run it in a `for` loop: write each command out. Claude Code cannot check such a command, so it asks the user or refuses it. Several `kb_tool` commands may share one call.

Transcripts can be `.md`, `.txt`, `.docx` or `.pdf`. The script reads `.docx` itself. It reads `.pdf` with pypdf when that package is installed. When it is not, the merge stops with `reader_missing`: read the PDF yourself, save its text word for word as `.pw-kb/transcripts/<name>.txt` (the PDF's name, ending in `.txt`), and name that file in the patch instead of the PDF. Say so in `provenance.notes`, and tell the user that the quotes were checked against your text copy of the PDF.

Work where the files live: if the transcripts and the KB are on the user's computer, run the commands in a shell on that computer. Copy the tool into `.pw-kb/tools/` only when that machine cannot reach the skill folder. Then copy `scripts/kb_tool.py`, `scripts/kb_map.py`, `scripts/kb_review.py`, `scripts/kb_people.py`, `scripts/kb_migrate.py`, `references/kb-schema.json`, `references/patch-schema.json`, `assets/discovery-map-template.html` and `assets/labels-en.js` together and keep them together. `kb_tool --version` shows which version a copy is, and every KB records the version that last wrote it in `meta.tool_version`.

## What a run changes, and what it leaves alone

- **Writes (evidence layers):** interviews, job executor, core functional job, related, emotional and social jobs per interview, and each new interview's links to the study's core jobs; new evidence on existing job steps and outcomes; new outcomes; current solutions (what people use today for each step, and what they stopped using), with their groups.
- **Proposes, never applies:** anything that changes the shared structure. That covers a new core job, a new job step, a reworded step, outcome or core job, a merge of two outcomes, a moved outcome or step, a changed link of an earlier interview, a new segment, two solutions that are one, a solution in the wrong group, or a renamed solution or group. These go to `proposed_changes` with status `pending`. The user decides, then `kb_tool apply` acts.
- **Flags, never rewrites:** derived layers (`survey`, `simulation`, `value_themes`, `overview`, `use_cases`). The script marks them `stale: true` with a reason. They are rebuilt on request, not on every run. Value themes are written with `kb_tool themes`, see "When asked for value themes". The overview is written with `kb_tool overview`, see "Write the overview".

The exception is a brand-new KB with no core job yet. Then the run proposes the core job or jobs and their job maps as a `bootstrap`, marked `status: proposed`, so the user can review them. The merge also files one `confirm_core_job` decision per core job, saying how many people back it. Approving it marks the job approved.

## One core job or several

Most studies have one core job. When the people interviewed do different jobs, for example restaurant owners who order ingredients and kitchen managers who staff each shift, the study has several. Each core job has a letter (`A`, `B`…) and its own job map, so every step and outcome ID starts with its job's letter: step `B.2`, outcome `B.2.3`. The letter is there even with one job.

Every interview's own core functional job links to the core job it rolls up to (`job: "B"`). That is the person's main job. A related job may link to another core job, so one person can belong to several. An interview whose job fits none of them stays unlinked, with the reason in its core functional job's `unlinked_reason`. When the person is linked later, the tool moves that reason into history. How to decide whether two people share a core job is in `references/pw-rules.md`, "One job or several".

## Where the study lives

Everything the skill makes goes into two folders at the root of the workspace: `.pw-kb/`, the study itself, and `pw-output/`, the files people read. One workspace holds one study. **The workspace is the user's own folder, whenever they gave you one:** in Claude Code, Codex and other coding tools, the folder the session started in; in Cowork, the folder connected to the task or to its project. Cowork's shell often starts in a temporary folder of its own; that folder is never the workspace. When several folders are connected, take the one that holds the transcripts, and ask only if that does not settle it. Only when no folder is connected and the transcripts were uploaded to the chat (claude.ai, ChatGPT, Claude Desktop's chat) is the workspace a sandbox that is gone after the chat; step 6 says what to hand back then.

```
.pw-kb/
  pw-kb.json           the knowledge base (KB)
  transcripts/         a copy of every transcript the KB quotes; merge makes it
  patches/             one file per batch, the audit trail
  backups/             the KB before each write; the newest 20 are kept
  logs/kb_tool.jsonl   one line per run of the tool
  labels.json          the map's and the review sheet's own text, for a study in another language than English
pw-output/
  discovery-map.html   the interactive map, the one file to open
  review.md            the review sheet, as text
  interview-guide.md   the plan for the next interviews, as text
```

`.pw-kb/` is hidden in Finder and most file dialogs, because its name starts with a dot. `pw-output/` is not, so people find the map there by themselves. Every write (`merge`, `apply`, `themes`, `overview`) and the `review` and `map` commands write it; the map also keeps a hidden `.map-live/` folder there, which tells an open map that a newer one is ready (git ignores it). They give it the same `.gitignore` as `.pw-kb/`, so git treats both folders alike. They also remove the copies that plugin 0.11 and earlier left in `.pw-kb/`, and say so in one line that starts `moved:`. Run every command from the workspace root, with the paths as shown. The tool refuses a KB anywhere else. Never write the skill's files outside `.pw-kb/` and `pw-output/`. The user's own transcripts stay where they are; the merge copies them in.

**When the user gave you a folder, the study is files in that folder, never text in the chat.** If your shell can reach the folder, `cd` into it and run every command there. If it cannot, because the commands run on another machine and you reach the folder only with a file tool: first copy the folder's `.pw-kb/` (everything except `backups/`) to where the commands run; at the end, before your report, save every file the run created or changed into the user's `.pw-kb/` and `pw-output/`, with the same names and sub-folders. Name `pw-output/.gitignore` in that save too, because file tools may skip names that start with a dot. When a write, `review` or `map` printed a `moved:` line, also delete the old `review.md`, `interview-guide.md` and `discovery-map.html` from the user's `.pw-kb/`, if your tools can delete. Never paste the map, `review.md` or the KB into the chat. Never offer them as downloads instead, and never put them in a folder of your host's own, such as an outputs folder.

**When the link to the user's computer drops.** In Cowork, a task that runs in the cloud reaches the folder through the Claude desktop app, over a link that often drops for a few seconds and comes back by itself. So fetch every file the run needs in one request, when your tool takes several, and work on those copies; save them back in one request too. When a call that lists, fetches or saves files on the user's computer, or runs a command there, fails because the computer, the device or the app cannot be reached, is not connected or timed out, do not stop and do not tell the user yet. Wait about 15 seconds (`sleep 15` in your own shell) and make the same call again; if it fails again, wait 30 seconds, then 60. Only when all three retries fail, tell the user in one or two lines that the link to their computer dropped, that nothing is lost, to check that the Claude app is open and the computer awake, and to say "Try again". When they do, go on from the call that failed: keep the files you fetched and the answers you got, and do not start over or ask again. A missing file, or a folder you are not allowed to open, is not a dropped link: do not retry those.

## Study language

Some users read English with difficulty. A study is written in one language, chosen when it starts and kept in `meta.language`. It covers everything the user reads: every statement you write, `review.md`, and the map's own text, such as its buttons, headings and help. Quotes always stay in the words people used. Your replies in the chat stay in the language the user writes to you in.

**When to ask.** Only when a study starts, right after `init`. If every new transcript is in English, do not ask: the study is in English. A KB without `meta.language` is in English. Never ask again: `context` prints the language (`language=it`), and later batches follow it.

**How to ask.** Use your host's tool for a question with choices the user clicks: `AskUserQuestion` in Claude Code and Cowork, `ask_user` in Gemini CLI and GitHub Copilot CLI, `request_user_input` in Codex's Plan mode. Other hosts, such as VS Code, Cursor and claude.ai, have one under their own name.

- Ask in the language the user writes to you in.
- Name each choice in its own language: "Italiano, come le interviste" and "English". When the interviews are in several languages, give one choice per language with its number of interviews, most first, then English: at most three choices in all, because some hosts allow no more.
- Put first, marked as recommended, the choice that matches the language the user writes to you in. If none does, the interviews' language.
- Do not add an "Other" choice. The host adds a free-text one, where the user can name another language.
- Ask the git question and the usage question of step 1 in the same call, so the user is interrupted once.
- With no such tool, ask one short question in plain text that names both choices, such as "Scrivo lo studio in italiano, come le interviste, o in inglese?", and wait for the answer.
- When nobody can answer, as in a scripted run, use the language the request is written in, or English when that is unclear, and say so in your report.

**Then.** For English, nothing more. For any other language:

1. `kb_tool labels .pw-kb/pw-kb.json --language <code>`, with a BCP 47 code such as `it`, `es`, `pt-BR` or `zh-Hans`. It sets the language and writes `.pw-kb/patches/<date>-labels-<code>.json`: the text of the map and the review sheet in English, with a `"<key>#note"` entry just above each label that needs a note.
2. Read that file and write it back in the study's language, as its `instructions` say. Keep every `{name}`, and translate each plural form it lists. There are about 540 labels: tell the user you are writing the map's text in their language, once, and that it takes a few minutes.
3. `kb_tool labels .pw-kb/pw-kb.json --add <that file>`. It refuses a label that lost a `{name}`, holds markup or is empty, and keeps the rest in `.pw-kb/labels.json`. Fix what it refuses and add the file again.

Write every statement in the study's language. `references/pw-rules.md`, "Writing in another language", has the rules. In a study that is not in English, the tool allows about a fifth more words, does not check the English openings "Minimize…" and "Help me…", and counts letters in Chinese, Japanese and Thai.

**When `context` prints a `LABELS:` line**, the study lacks text for some labels, usually because an update of the skill added them. Run `kb_tool labels .pw-kb/pw-kb.json`, write the file it gives and `--add` it before the next write. Until then those labels show in English, and the rebuild of the map says so.

A study's language cannot change once it has interviews, because its statements are written in it. If the user asks, say so: translating a study is not supported.

## Workflow

When the user only asks to stop sharing usage statistics, skip the workflow and follow "Usage statistics". When the user only answers a decision, such as "In my Product Weaver study, the goal is right: …", skip the workflow too: run `start`, then `context` to find the decision, act as item 3 of "Ask the decisions as a click" in step 7 says, then run `end`.

### 1. Find the KB and the transcripts

First find the workspace, as "Where the study lives" says: in Cowork, the connected folder. Look there, not in the shell's starting folder, for `.pw-kb/pw-kb.json` and the transcripts. The KB is `.pw-kb/pw-kb.json`. Ask where the new transcripts are only if they cannot be found. Never look for transcripts in `pw-output/`, and a file named `review.md`, `interview-guide.md` or `discovery-map.html` is never a transcript, wherever it is: the skill wrote it.

**A study the user attached.** In a chat where files are attached, a zip or folder that holds `pw-kb.json` is the study you handed back last time. Open it before anything else, so new interviews join it instead of starting a new study. If `.pw-kb/` already exists, do not unpack: ask which study to keep. Otherwise unpack it so that `.pw-kb/pw-kb.json` exists afterwards (not `.pw-kb/.pw-kb/`).

Once an attached study is unpacked, run `pw_usage.py start` (see "Usage statistics"), unless `pw-start` already ran it in this conversation.

No KB yet:

1. Read the first lines of each new transcript, to see which language the interviews are in.
2. If `pw-output/interview-guide.md` is already there (or `.pw-kb/interview-guide.md`, from plugin 0.11 or earlier), the user planned these interviews with the `pw-start` skill before the study existed. Read it. The kinds of people under "Who to find" may become trait values in the first plan, including kinds nobody has been heard from yet. The study's first overview replaces the file with a guide built from the study; until then the rebuild after each write keeps it and says `kept`.
3. `kb_tool init .pw-kb/pw-kb.json --project "<name>"`. Add `--interviewer "<name>"` only when the user or the transcripts say who ran the interviews; never fill it in from anywhere else.
4. Ask what the start needs to know, in one question call of at most three questions: the study's language, unless every transcript is in English (see "Study language"); when `init` printed a `git:` line, whether to share the study through git; and, when `pw_usage.py start` printed `usage: no-study`, the usage question (see "Usage statistics"). `.pw-kb/` holds interviewees' names, their words and their transcripts, and the `git:` line means the workspace is a git repository. If the user does not want to share it, write `.pw-kb/.gitignore` containing the single line `*`. If they do, write it with the two lines `logs/` and `usage/`. `pw-output/` follows the same answer: every rebuild copies that file into it. Then run `pw_usage.py set` with the answer. Do not ask any of these questions again later.
5. For a language other than English, run the `labels` steps in "Study language" before you extract.

When nobody can answer, as in a scripted run, pass `--language <code>` to `init` instead: it writes the labels file to fill in the same call. Do not touch git then, and run `pw_usage.py set .pw-kb no`.

**A study written in YAML**, `.pw-kb/pw-kb.yaml`, was made by plugin 0.7.0 or earlier. Every command refuses it with `migrate_needed`. Run, from the workspace root:

```
kb_tool migrate .pw-kb/pw-kb.yaml
```

It writes `.pw-kb/pw-kb.json` and, for a study in another language, `.pw-kb/labels.json`, and puts the YAML files in `.pw-kb/backups/`. Reading the YAML this one time needs PyYAML. When it is missing, migrate stops with `reader_missing` and changes nothing: install it with `python3 -m pip install pyyaml==6.0.3` (if pip refuses, in a virtual environment) and run migrate again, or ask the user to run it on a computer that has PyYAML. The YAML files already in `patches/` stay as history; write every new file in JSON. Tell the user the study is now in `pw-kb.json`, and that everyone who works on it needs this version of the plugin.

**A study made by an even earlier version** sits in a `KB/` folder, with its transcripts in `Interviews/` next to it. The tool refuses it with a message to run `migrate`. Run, from the workspace root:

```
kb_tool migrate <study>/KB/<file>.yaml --to .pw-kb/pw-kb.json --transcripts <study>/Interviews
```

It copies the transcripts, moves the KB, patches, backups and logs into `.pw-kb/` and the review sheet, guide and map into `pw-output/`, writes the KB as `pw-kb.json` and keeps the old file as a backup. It needs PyYAML too, as above. If a transcript is missing, or `.pw-kb/` already holds a study, it moves nothing and says why. Then tell the user where the study is now and what was left in the old folder, and ask about git as above.

### 2. Load the current structure

```
kb_tool context .pw-kb/pw-kb.json --batch 8  # 8: the transcripts in this batch; --json gives one JSON object
```

With `--batch`, it first prints a `batch:` line. Tell the user its estimate in one plain sentence, such as "8 interviews: about 14 minutes. I'll tell you when your map is ready.", and when the line says an open map shows it, add "Your open map shows that it is being updated." When `pw-start` already gave the time in this conversation, pass on only the part about an open map. Use `--batch` only at the start of a batch. Then it prints the study's language, then each core job with its steps, outcomes and IDs, then the current solutions by group, every person with their own core job and the core job it links to, the segments, the files already processed, pending proposals and stale layers. Write every statement in the study's language. Map new evidence against this. Skip any transcript whose file is in "processed files". The script also skips it, matching by file name and content hash, so re-running the same batch never double-counts.

A file or a pasted text from someone listed under `PEOPLE AND THEIR JOBS` is a later conversation with them: send it under `interactions`, as "The same person again" in `references/pw-rules.md` says. Skip an email or a chat with the same date and format as a conversation that person already has: a later one their line lists, or their first conversation, the `date` and `format` of their record in `.pw-kb/pw-kb.json`. The study holds a cleaned copy of it under another name. Only when the user says it is another one, send it with `"another": true`. When you are not sure it is the same person, ask once with your question tool: "Is this the same Dana you talked to on 14 October?" (no question tool: one plain-text question).

A KB with an older schema is refused with a message to run `kb_tool migrate .pw-kb/pw-kb.json`; moving an older study upgrades it in the same step. When either says it migrated from schema version 1, tell the user: the core job is now core job A, and every step and outcome ID gained the letter, so `6.3` is now `A.6.3`.

### 3. Read each new transcript in full, then extract

Read the whole transcript before writing anything. In a batch of 4 or more, when half the transcripts are read, say one short line, such as "4 of 8 read." The open map cannot show it: `merge` moves the batch on only at the end. The rules for each statement are in `references/pw-rules.md`; read that file once per session, starting with "Write for the reviewer first" and "Plain language for a second-language reader". Founders, product managers, domain experts and architects will review these statements, so each one should be short, plain and land on the first read. The merge blocks statements that are too long or carry asides. In short:

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

- `transcript` for the interviewee's words in a transcript. An email or chat message the person wrote is their own words, so tag it `transcript` too
- `quoted_in_notes` for the interviewee's words inside quotation marks in notes
- `interviewer_notes` for the interviewer's own paraphrase, which is weaker evidence. A header or note line someone else wrote about the interview, such as "# Interview: Ana Lima, service writer", counts as this too. Quote it only when the person never says it in their own words

### 5. Write the patch, merge

Write the patch to `.pw-kb/patches/<date>-<batch>.json`, a JSON file in the format of `references/patch-format.md`. Open it with `generated_with` and a `provenance` block: which assistant and model you are, when you started reading, which interviews you read (by ID or key, never by file name) and any note a later reader needs. The merge copies it into the KB's changelog, so every batch can be traced to who extracted it and how. Write every ID as a string, in double quotes: interviews `"01"`, core jobs `"B"`, steps `"B.2"`, outcomes `"B.2.3"`. A number is not an ID: the merge reads the number `7` as interview `"07"` and warns, but `2.10` reads as `2.1`, another outcome. Inside a text, write a straight quote mark as `\"`; a curly one needs nothing. Then:

```
kb_tool merge .pw-kb/pw-kb.json .pw-kb/patches/<file>.json --transcripts <folder with the new transcripts>
```

In the patch, `file` is the transcript's file name. `--transcripts` says where the new ones are; pass it once per folder, or leave it out when every file the patch names is already in `.pw-kb/transcripts/`. A file name that exists in two of those folders is refused. The KB's own copies in `.pw-kb/transcripts/` always come first, so the transcripts of earlier interviews are read from there. The real merge copies each new transcript into `.pw-kb/transcripts/` and records it as `transcripts/<file name>`; the user's originals are never changed. The script reads only the transcripts the KB and the patch cite.

**Emails and chats.** Never name an email or chat export in the patch: the merge would copy it as it is. Save a text copy as `.pw-kb/transcripts/<id>-<n>-<date>.txt` and name that copy, where `<n>` is the next number after the person's conversations in `context` (2 for their first later one); a new person's first contact is `<key>-1-<date>.txt`. Text the user pastes or types in the chat, such as notes, is saved the same way. In the copy, remove header lines, signature blocks and legal footers, write `[address]` and `[phone]` for an email address or a phone number inside a sentence, and keep everything else word for word, with who wrote each part. The merge refuses a copy that still holds an address or a header line (`contact_details`). Tell the user the kinds and counts you removed, such as "4 header lines and a signature", never the removed text, and never in `provenance.notes`. The first time, say in one sentence that the study now holds the text of private messages, and that it travels with the study folder. Name a patch for one follow-up `<date>-follow-up-<id>.json`.

The merge runs every check before it writes anything, so a refused merge writes nothing: fix the patch and run the same command again. There is no need for a `--dry-run` first. Each check blocks the merge:

- **JSON:** a missing comma, a comma after the last item or a quote mark without its `\` gives `json_invalid`, with the line and column and the line itself. Fix that spot.
- **Patch format**, against `references/patch-schema.json`: a missing field, a list where an object belongs, or an ID written as a number gives one message that names the place in the patch.
- **Quote not found:** open the transcript, copy the exact span and fix the patch. Never loosen the check.
- **Reference:** a step, outcome, interview, core job link, proposal target or segment that does not exist, or an outcome that was merged into another. In a KB with several core jobs, an ID without its job letter (`6.3`) is refused too.
- **Clarity:** a statement is too long or carries brackets, examples or a semicolon. Rewrite it shorter, following "Write for the reviewer first". Treat the warnings ("may hold two jobs", abbreviations) as prompts to reread the statement.
- **Structure:** the KB that would result is checked against `kb-schema.json` before anything is written.

Warnings do not block: an interview skipped because it is already in the KB (its evidence is dropped), an interview ID written as a number that was read as `"01"`, an unknown top-level key, or a transcript whose content changed since it was added.

A merge first copies the new transcripts into `.pw-kb/transcripts/` and the current KB to `.pw-kb/backups/` (the newest 20 copies are kept), then writes the new KB, recounts all coverage numbers, marks derived layers stale and appends a changelog entry that lists what was added, stamped with the time and the `run_id` of the run. Then it rebuilds the review sheet and the map, as step 6 says. Keep the patch file: it is the audit trail of what each batch added. Re-running a batch that was merged already is a no-op. Add `--json` to get one JSON object with `ok`, `errors`, `warnings`, `run_id` and the changes, instead of text.

### 6. The review sheet and the map

`merge`, `apply`, `themes` and `overview` rebuild `review.md`, `interview-guide.md` and the map after each write, so reviewers never open a stale picture. Each prints the map's `link:` line and the line about a map that is already open. Do not run `review` and `map` after them.

After a merge that added interviews or later conversations, write the overview, as "Write the overview" describes, also for a single follow-up. When the merge printed `batch: every transcript is in`, an open map says the study is being updated until the overview is written. The map opens on it, `review.md` and `interview-guide.md` show its plan for the next interviews, and a merge marks the old one out of date. On a first batch, the overview is the last write before your report, so add `--open` to it:

```
kb_tool overview .pw-kb/pw-kb.json .pw-kb/patches/<YYYY-MM-DD>-overview-<job>.json --open
```

`--open` shows the map in the user's default browser. Do not ask first. Leave it out on every other write, so the user does not get a new tab each time. When a first batch's overview could not be written, run `kb_tool map .pw-kb/pw-kb.json --open` once, so the user still gets the map; run it too when the user asks to see the map. `review` and `map` stay for a rebuild on request, and `--no-publish` on a write skips its rebuild. An open map reloads after the merge and again after the overview: that is expected, so say nothing about it.

- `pw-output/review.md` is a plain sheet listing decisions waiting, what is new since the last merge, the job map by stage with how many people back each step, and the next interviews: where the study stands, the plan and every thin spot.
- `pw-output/interview-guide.md` is that plan as a guide to take into the calls: who to find, what to ask, what to listen for. Every rebuild rewrites it once the study has an overview.
- `pw-output/discovery-map.html` is an interactive map for people who do not know the method. It shows the goal, stages, steps and measures of success with plain labels, the quotes behind every item, what each conversation added, and where more conversations would help. When the study has current solutions, it counts them, can show them next to their steps, and has a Solutions view grouped by the work they compete for. It opens on an Overview view, the study as a short story with what to do next; see "Write the overview". When decisions wait for the user, the Overview shows them right under the main finding, as "Decisions for you", each with two replies to copy, written out in full; Next interviews and the Progress tab list them too. Its Next interviews view shows the plan for the next round: who to talk to, what to ask, who has not been heard from yet, and what is still thin. When the study has value themes, it has a Value themes view: one card per theme with its outcomes, what people use today and the quotes. It is one file with the KB inside: it opens in any browser and works offline. The end of its Overview says which plugin version made it, when, and the folder it is saved in. An open map updates itself a few seconds after each rebuild and keeps the reader's place. Its title bar says when it last changed, or that the study is being updated, and New badges mark what the reader has not seen yet.

**Put the map in front of the user.** Read `references/open-files.md` once per session and do what it says for your host: one link, or the host's file card, that opens `pw-output/discovery-map.html`. The interview guide is in the map's Next interviews tab. The decisions waiting are near the top of its Overview, under "Decisions for you". Name the tab or the heading in words. Every write and `map` print a `link:` line with the map's `file://` address. When the commands ran on another machine (the address starts with a folder the user does not have, such as `/sessions/` or `/mnt/`), that address does not open for them, and `open-files.md` says what to give instead.

- When a write, `review` or `map` printed a `moved:` line, the files left `.pw-kb/` in this run. Say so once, in one plain sentence, such as "Your map and review sheet now live in the pw-output folder, where Finder shows them", and give the new link. In that run, skip the tool's line about an open tab: a tab still open shows the old copy, which is gone.
- When a write, `review` or `map` printed a `git:` line (the study sits in a git repository and `.pw-kb/` has no `.gitignore`) and `pw-output/` has none either, run `git check-ignore -q .pw-kb/pw-kb.json` once. Only when it succeeds, the user keeps the study out of git some other way, such as the repository's own `.gitignore`: then write `pw-output/.gitignore` with the single line `*`, so the map stays out of git too.
- After `--open`, say what the tool said: the map is open in their browser, or it could not be opened here and what to do instead. Never say it is open when the tool did not.
- After a rebuild without `--open` that moved no files, say the map is updated, and pass on what the tool's `Open the link` line says about a map that is already open: it updates by itself, or, once after the plugin was updated, it needs one reload.
- Do not run a command of your own to open the map (`open`, `xdg-open`, `start`). It would cost the user one more permission question.
- Only when no folder is connected and the transcripts were uploaded to the chat, so the study sits in a sandbox that is gone after the chat: put the map in front of the user as `references/open-files.md` says for your host, then hand back the whole `.pw-kb/` folder the way your host shares files, as a zip when it needs one, and say: "Keep this folder. Next time, upload it with your new interviews." Hand back `review.md` and `interview-guide.md` only when the user asks. Do not say the map is open in their browser.
- With a connected folder, as in Cowork, never hand back: check that `discovery-map.html` and `review.md` are in the user's own `pw-output/`, then report. If saving them there still fails after the retries in "When the link to the user's computer drops", never report the study as saved: say it is ready but not yet in their folder, and give the words to say: "Save the study".

**The map contains personal data.** It embeds every interviewee's name and every quote. Before suggesting that anyone share it, say so, and let the user decide who may see it. The same goes for the KB file and `review.md`. `interview-guide.md` and the printed kit name each person to ask again.

`map` uses `assets/discovery-map-template.html` from this skill. A `discovery-map.html` made by the same version of the skill also works as a template (`--template`).

### 7. Report to the user

The reader may be a founder or a domain expert, not an ODI specialist, so write in plain words and short sentences, as "Plain language for a second-language reader" in `references/pw-rules.md` says, in the language the user writes to you in. Lead with one sentence on what changed. Then keep it short:

- new interviews: name, who they are and their core job, and which of the study's core jobs it links to, one line each, plus any skipped as already processed
- later conversations, one line each: who, how (a call, notes, an email or a chat), and "Ruth changed: …" when you wrote `changed`
- when the study has several core jobs, name each by its statement with the letter after it ("Keep the trucks on the road (B)"), never by the letter alone
- what the new evidence strengthened: name the outcomes in words, with the ID after the text, never as a bare list of IDs. This holds for every mention, including a passing one in a closing remark: a reviewer cannot hold "1.1 and 5.1" in their head.
- new outcomes, each as its full statement
- decisions waiting: ask them as a click, as "Ask the decisions as a click" says, never as a list of codes to type
- current solutions, briefly: each new group in one line with its why and its most used solutions, then what people stopped using and why. Point to the Solutions view in the map for the full list
- the next interviews, in 3 to 5 lines (1 or 2 per core job when there are several): who to talk to, the top questions, and where the full plan is: the map's Next interviews tab, where the guide can be printed or copied; and which derived layers are now out of date
- who the overview says the study is about, its bottom line and its three next steps, one line each, every step starting with a verb, the steps marked as advice
- the map, last before the "Next:" line, as step 6 says: one link or file card that opens it, with words as its text, such as "Open your discovery map", never the file name; then at most three short lines: the interview guide is in its Next interviews tab, to print or copy; the decisions still waiting, when there are some, are near the top of its Overview, under "Decisions for you"; and where it is saved, in words a person can follow in Finder without the chat: their own folder's name, then pw-output, then the file, such as "It's saved in your Interviews folder, in pw-output: double-click discovery-map.html to open it again", never the word "workspace". Add that the map holds the interviewees' names and quotes

**After a first batch** everything is new, so that list would be the whole study. Report this instead, and leave the rest to the map:

- each person in one line: who they are and the core job they are linked to, or why none
- the language the study is written in, in one line, and that it stays that way
- the rest as counts, with the one or two findings that matter most: outcomes, current solutions and their groups, and what people stopped using
- the next interviews, as above, and the map, as above. When `--open` showed it in their browser, say so, and still give the link for later
- last, after the map and right before the question that confirms it: each core job as a goal, in the words of its statement, how many people have it as their main goal, how many steps it has, and three of the steps in plain words. Then ask, as "Ask the decisions as a click" says

**End every report**, the first one too, with one line that starts "Next:" and names one step, the first that applies: confirm what the study is about (after a first batch), decide the changes waiting, run the next round (how many people, of which kind), or, once the study shows a clear pattern, group the needs into value themes. Give it as words the user can say. When you ask a decision, the question takes the place of this line, and the "Next:" line ends your message after the answer. When the goal still waits because nobody answered: `Next: tell me if the goal is right. Reply "yes", or say what to change.` Once it is confirmed, for example: `Next: talk to 3 more restaurant owners who order for two sites. Say "show me the interview guide" for the questions.`

**Ask the decisions as a click.** A decision is a proposal that `context` lists under `PENDING PROPOSALS:`. After a first batch, the first one is whether each goal (core job) is right. The rest of the study rests on it, so ask it in the chat at once, as a click. The user may also answer in their own words, with a code such as "approve P1", or with a reply copied from the map or the review sheet: "In my Product Weaver study, the goal is right: …", "…change the goal to: …", "…make this change: …" or "…don't make this change: …". Find the decision under `PENDING PROPOSALS:` by its words and act on it the same way. Never ask them to type a code.

1. Right before the question, show each goal in plain words with three of its steps, as the first-batch report says.
2. Ask with your host's question tool, as in "Study language": `AskUserQuestion` in Claude Code and Cowork, `ask_user` in Gemini CLI and GitHub Copilot CLI, `request_user_input` in Codex's Plan mode. Use one call with at most 3 questions: one per goal to confirm (`confirm_core_job`), then other decisions, oldest first; the others stay in the map. Ask in the language the user writes to you in. Mark no choice as recommended, and add no "Other" choice: the host adds one for the user's own words.
   - A goal: "These 5 people are all trying to: Order what the kitchen needs for the week. Is that right?", with the choices "Yes, that's it" and "Close, but change it". With one person, start with "This person is trying to:".
   - Any other decision: the change in plain words, then "Should the study change like this?", with the choices "Yes, change it" and "No, keep it".
3. Act on the answer right away. On "Yes, that's it" or "Yes, change it", run `kb_tool apply .pw-kb/pw-kb.json P1 --decision approve --note "confirmed in the chat"`, with that decision's code in place of `P1`. It rebuilds the map: say in one line that it is done, with what it said about a map that is already open. On "No, keep it", the same with `--decision reject`. On "Close, but change it", or words of their own, never reject the goal's decision: leave it waiting. If they did not say what to change, ask once, in plain text. Then propose the change in a small patch, as step 8 says (`reword_core_job`, or `move_step` and `relink_interview`; the format is in `references/patch-format.md`), and merge it without `--transcripts`. Show the change in plain words as one more question, with the choices "Yes, use it" and "Change it again". On yes, approve that proposal, then the goal's decision. On "Change it again", ask what to change and propose again.
4. With no question tool, as in Codex's default mode, ask the same question in plain text, one goal per line, and end with "Reply yes, or tell me what to change." This message ends your turn.
5. When nobody can answer, as in a scripted run, or the user closes the question, leave the decision waiting. Say in one line that it is near the top of the map's Overview, under "Decisions for you".

### 8. Acting on proposals

When the user decides, with a click in the chat or in their own words:

```
kb_tool apply .pw-kb/pw-kb.json P3 --decision approve --note "agreed in review"
```

`apply` re-checks that the proposal's target still exists before it acts. A proposal raised against an outcome that was since merged or moved is refused with a message, not applied blindly. Automatic actions exist for `new_step`, `reword_step`, `reword_outcome`, `reword_core_job`, `merge_outcomes`, `move_outcome`, `new_segment`, `new_core_job`, `confirm_core_job`, `move_step`, `relink_interview`, `merge_solutions`, `move_solution`, `reword_solution` and `reword_solution_group`. A rejected `confirm_core_job` changes nothing: ask the user what is wrong with the job, then propose `reword_core_job`, or `move_step` and `relink_interview`. Old wording and old links are kept in `history`. IDs stay stable: new steps get the next free number in their core job, and merged outcomes keep a `merged_into` pointer instead of being deleted. A moved outcome or step gets the next free ID where it lands, the old ID goes to `history`, and pending proposals that cited the old ID are updated. For `other`, edit the KB by hand, then run `validate`.

An approved `new_core_job` gets the next free letter, its steps are numbered from 1 and the interviews it lists are linked to it. It has no outcomes yet, because outcome IDs need the job to exist. Right after approval, reread those interviews and write a short follow-up patch that cites them by ID and adds the new job's outcomes and step evidence. Also check the people → jobs list in `context` for earlier interviews whose related job is the new core job, and propose `relink_interview` for them.

## When asked whether the study holds more than one job

Run `context` and read the people → jobs list. Ask "why?" of each person's own core job, as in `references/pw-rules.md`, "One job or several". Group the people whose jobs meet. For a group that no core job fits, propose `new_core_job` with its steps and people. Then propose `move_step` for steps that belong to the new job and `relink_interview` for people linked to the wrong one. Tell the user how many people support each job before they decide. Splitting a job is a big change to the map, so propose; never edit the KB by hand for it.

## When asked about current solutions or the competition

Run `context` and read the CURRENT SOLUTIONS block, or point the user to the Solutions view in the map. Groups grow batch by batch, so they drift. When a group holds solutions that do different work, or two groups do the same work, write a patch that proposes `move_solution` for each solution that should move. Add a new group in the same patch when none fits. Propose `reword_solution_group` when a group's name or why no longer fits its members, and `merge_solutions` when two solutions are the same thing under two names. Tell the user why each group holds what it holds. Never edit the KB by hand for it.

## Write the overview

The discovery map opens on its Overview view: who the study is about, then the study as a short story in six steps, with a "What to do next" block on top. It is made for a person who does not know the method, often a founder starting discovery. The map counts what it can from the KB. The sentences are yours, and without them the view says "No written findings yet".

Write the overview for each core job that got new evidence, at the end of every run that merged interviews or later conversations, right after the merge (and `themes`, when you rebuild them). Also write it when the user asks, and when `context` shows `OVERVIEW [out of date]`. Read `references/pw-rules.md`, "Overview", first: it holds the writing rules, with the first-read test and the "so what" test every sentence must pass, and a worked example of the file. Write it in the study's language.

1. Run, in place of a second `context`, with the core job's letter in place of `A`:

```
kb_tool overview .pw-kb/pw-kb.json --skeleton A
```

It writes nothing. It prints the job, its OPEN GAPS ranked, with who backs each one and the level line, the people whose main goal it is, with their IDs, and then the file to fill in, with each sentence's word limit for this study. Plan the next round from the OPEN GAPS. For the outcomes, the solutions and who stopped using them, use what `context` printed in this run, or run it when you have not. For quotes and who said what, read `.pw-kb/pw-kb.json` itself: the `evidence` lists of the steps, the outcomes, the solution uses and each person's own statements.
2. Save that file as `.pw-kb/patches/<YYYY-MM-DD>-overview-<job>.json` and fill it in, following `references/pw-rules.md`, "Overview". Replace every `<…>`; delete the ones that give a count rule, and those that say "or delete this" when you have nothing to put there. The tool refuses a file that still holds one. When the job already has an overview, its traits come filled in: sort the people listed as `<not sorted yet: …>` into their values.
3. Write it, adding `--open` on a first batch (step 6):

```
kb_tool overview .pw-kb/pw-kb.json .pw-kb/patches/<file>.json
```

The tool refuses a quote or a solution the KB does not hold, a sentence more than a quarter over its word limit, a percentage or a score word, a word of the method ("core job", "desired outcome"), an unknown icon, a missing part, a `<…>` left from the skeleton, and a plan ID that is not a step, outcome or trait value of the core job. A refused overview writes nothing: fix the file and run the same command again. A sentence over its limit by a quarter at most is written with a warning: shorten it anyway when you next write the overview. It warns on vague words such as "pain point" or "workflow": rewrite them in plain words unless they are the customers' own. It also warns when the round misses a thin spot the main finding rests on, or asks what people would do: fix those. It replaces that core job's overview, leaves other core jobs alone, and rebuilds the review sheet and the map.

4. In your report, say who the study is about, give the bottom line and the three next steps in one line each, every step starting with a verb, and point to the Overview view and the Next interviews view. The next steps are advice: say so. Never call a count a score.

The user changes the overview by telling you ("the bottom line is too strong", "we are ready to prototype"). Edit the file and run `overview` again; there is no proposal step.

## When asked for value themes

Value themes turn a long list of outcomes into a few needs a team can sort ideas into, such as "Help me order what the week will really need". Build them only on request, one core job at a time, in the study's language. Read `references/pw-rules.md`, "Value themes", first: it holds the method.

1. Run `context`. It prints every outcome with its ID and, once themes exist, the VALUE THEMES block with the outcomes in no theme yet.
2. Write `.pw-kb/patches/<date>-themes-<job>.json` with the full set of themes for that core job:

```json
{
  "job": "A",
  "themes": [
    {
      "id": "A.T1",
      "label": "Order the right amount",
      "need": "Help me order what the week will really need",
      "why": "Each one decides how close the order comes to what gets sold.",
      "outcomes": ["A.2.1", "A.4.2", "A.6.3"],
      "highlights": [
        {"kind": "pain", "interview": "03", "quote": "We threw out two cases of fish that week."}
      ]
    }
  ]
}
```

Give `id` only for a theme that already exists; leave it out for a new one.

3. Write it:

```
kb_tool themes .pw-kb/pw-kb.json .pw-kb/patches/<file>.json
```

The tool refuses a theme that cites an outcome or a quote the KB does not hold, and warns about a set that is too large, too small or overlapping. A refused file writes nothing: fix what it refuses and run the same command again; weigh what it warns about. It replaces that core job's themes, keeps their IDs, leaves other core jobs alone, prints what changed and rebuilds the review sheet and the map.

4. Report each theme with its label, its need and its outcomes in words, how many people voiced them, and the outcomes left in no theme. Point to the Value themes view in the map, and say what to do with the themes: put every idea under one theme, and build first for the theme most people raised. The counts are a signal from interviews, not an opportunity score: say so, and never call them a score.

The user changes themes by telling you ("merge these two", "rename that one"). Edit the file and run `themes` again; there is no proposal step. When new interviews arrive, the themes are marked out of date. Update them only when asked, and keep the labels and groupings the team already uses.

## When asked to rebuild another derived layer

Surveys and use cases are rebuilt only on request. When the study has several core jobs, build them per core job: a survey asks one job's executors about that job's outcomes. Show each outcome with its text, never as an ID alone. Then clear that layer's `stale` flag and add a changelog entry with `action: rebuild`.

## Study-specific writing rules

The word limits, the banned tokens, the idioms allowed to contain "and" or "or" and the acronyms that need no spelling out are defaults for any market. A study can override them in `meta.style` of the KB, an object such as:

```json
{"limits": {"outcome": 14}, "acronyms": ["OTR", "ELD", "DOT"], "idioms": ["bread and butter", "in and out", "pick and pack"]}
```

Set this when the user asks for different limits or when a market's everyday abbreviations keep tripping the acronym warning. `references/kb-schema.md` lists the keys.

## Branding

Every file this skill produces carries a light Product Weaver credit: the map's header and badge, the review sheet's footer, `generated_with` in the KB's metadata, and `generated_with` at the top of each patch file (`"generated_with": "Made with Product Weaver · productweaver.com"`). Keep these when you edit or rebuild files. They tell readers where the method and the tools come from. Do not add marketing lines to chat replies; the credit lives in the files. The links to productweaver.com in the map and the review sheet carry fixed tags (`utm_source=productweaver-plugin` and so on) that tell the site which file a visit came from. They never hold anything from the study; leave them as they are.

## Usage statistics

Product Weaver learns which parts of the plugin work from small usage events, sent only after the user says yes. `references/usage.md` lists every event. Run from the workspace root:

```
python3 <skill folder>/scripts/pw_usage.py start .pw-kb --skill pw-discovery --assistant <name> --model <id>
python3 <skill folder>/scripts/pw_usage.py set .pw-kb yes --skill pw-discovery --assistant <name> --model <id>
python3 <skill folder>/scripts/pw_usage.py end .pw-kb --skill pw-discovery --assistant <name> --model <id>
```

For a no, write `no` in place of `yes`. `--assistant` is your host: `claude-code`, `claude-cowork`, `claude-ai`, `chatgpt`, `codex`, `copilot-cli`, `vscode`, `cursor`, `gemini-cli`, `antigravity`, or `other` for any other; `--model` is your model ID, when you know it. It prints one line, `usage: on`, `usage: off`, `usage: ask`, `usage: disabled` or `usage: no-study`.

Claude Desktop is `claude-cowork` in a Cowork task, `claude-code` in its Code tab and `claude-ai` in a chat, as on claude.ai.

- **Start** of every run of this skill: `start`, unless `pw-start` already ran it in this conversation. After a hand-off from `pw-start`, `set` and `end` repeat the `--skill` and `--path` that its `start` used.
- **End:** `end`, once, after the last `kb_tool` command (and after `set`, when you asked) and before your final message, so the message stays your last line. A decision asked with the question tool comes back in the same turn: ask, run `apply` and the rebuild, then `end`, then your last message. A question in plain text ends your turn, so run `end` before it. When the user answers later in the conversation, run `apply` and the rebuild without `start` or `end`: those runs are sent with the next session.
- `usage: ask`: an existing study that was never asked. Ask the question below now, on its own.
- `usage: no-study`: a new study. Ask the question in step 4 with the other start questions.
- `usage: on`, `usage: off`, `usage: disabled`: never ask. Only the line `start` prints decides; never ask because of what `set` or `end` print.

The question, in the user's language except the example line, with two choices in this order, neither marked recommended: "Yes, share" and "No, don't share". Never suggest an answer, not even in an example reply. Use the host's question tool, else one plain-text question that names both choices.

> Share anonymous usage statistics with Pancrazio at Product Weaver?
> Only events like this one:
> `{"event":"tool_run","command":"merge","exit_code":0,"counts":{"interviews_added":3},"at":"2026-11-13T10:42Z"}`
> Never your interviews, names, quotes, prompts or file names. Everything sent is in .pw-kb/usage/sent.jsonl. Stop any time.

Then run `set` with `yes` or `no` and the same options as `start` (and `--path` when `start` had one). No answer, a dismissed question or a scripted run: `no`. When the user asks to stop sharing ("stop sharing", in any words): run only `set .pw-kb no`, with no `start` or `end` before or after it, and say that `sent.jsonl` keeps the record of what was sent. Never ask for network access, never mention a failed send, never send anything yourself.

## What the script records

Every run appends one JSON line to `.pw-kb/logs/kb_tool.jsonl`: the command and its options, how it ended, error and warning codes with counts, what changed as counts, the versions in use, the assistant that ran it and a hash of the KB before and after. Refused merges, dry runs and crashes are logged too; they are what shows where the instructions or the patch format confuse an assistant. The log never holds a quote, an interviewee's name, a transcript file name or an absolute path, so it can be shared for debugging. `references/run-log.md` lists every field and every code.

Each changelog entry the script writes carries `ts` and `run_id`, so a change in the KB can be traced to its log line, its backup and its patch. The script recognises Claude Code and Gemini CLI from their environment; in any other assistant, set `KB_TOOL_AGENT=<assistant>/<model>` before calling it so the `agent` field is right. The `provenance` block in a patch does the same for merges. `KB_TOOL_LOG=0` switches the log off. The log belongs to the study: do not send it anywhere. `pw_usage.py` sends content-free events made from it, and only after the user's yes.

## Checking a KB

```
kb_tool validate .pw-kb/pw-kb.json
```

First checks the KB's structure against `kb-schema.json`: required fields, ID formats, stages, source types and the references between steps and outcomes. Then it re-checks every stored quote against the study's copy of its transcript in `.pw-kb/transcripts/` and compares each copy with the content hash stored when it was added. A transcript that changed is reported; if the change is intended, add `--rehash` to accept the new content once every quote matches. Add `--structure-only` to skip the quotes. A copy that is missing is reported; put the transcript back in `.pw-kb/transcripts/` under the same name. Run it after any hand edit. `merge` runs the same structure check and refuses to write a KB that would break it.

Each KB records its schema version. `kb_tool migrate .pw-kb/pw-kb.json` brings an older KB up to date, keeping a backup; every other command refuses an older KB with a message to migrate, and a KB written by a newer version of the tool with a message to update the skill.

The KB's fields are explained one by one in `references/kb-schema.md`. Read it before editing a KB by hand or building anything that reads one.

## Files in this skill

- `scripts/kb_tool.py`: init, labels (the study's language and the map's and review sheet's text in it), context, merge (with format, quote, reference and clarity checks), apply, themes, review, map, validate and migrate (which also turns a study written in YAML into JSON, and moves a study made by an earlier version into `.pw-kb/`). Uses only Python's standard library. When they are installed, pypdf reads `.pdf` transcripts and PyYAML lets `migrate` read a study written in YAML.
- `scripts/kb_map.py`, `scripts/kb_review.py`, `scripts/kb_people.py` and `scripts/kb_migrate.py`: the `map` command (it fills the template with the KB, opens it, and writes `pw-output/.map-live/status.js`, which an open map reads to update itself; `context --batch` and `merge` update that file too), the review sheet, the interview guide and the overview's skeleton (`overview --skeleton`), later conversations with someone already in the study, and the `migrate` command. `kb_tool` loads each only for the commands that need it.
- `assets/discovery-map-template.html`: the interactive map viewer. `map` fills it with the KB. Opened on its own, it lets anyone load a KB file, `pw-kb.json`.
- `assets/labels-en.js`: the English text of the map and the review sheet, the source of every study's own text. The template loads it from beside itself and `map` puts it inside each map, with the study's own labels. The template opened on its own shows English.
- `references/pw-rules.md`: how to write each kind of statement, with examples and common mistakes. Read it before extracting.
- `references/patch-format.md`: the patch format the merge accepts, with a worked example. Read it before writing a patch. `references/patch-schema.json` is the same format as a JSON Schema, checked first by every merge.
- `references/kb-schema.md`: every field of the KB, what it means and who writes it. `references/kb-schema.json` is the same model as a JSON Schema (draft 2020-12), checked by `validate`, `merge` and `apply`.
- `references/run-log.md`: what `.pw-kb/logs/kb_tool.jsonl` records, field by field, and every error and warning code.
- `scripts/pw_usage.py`, `assets/usage-readme.md`, `references/usage.md`: the opt-in usage statistics, their README for the study folder and every event they send.
