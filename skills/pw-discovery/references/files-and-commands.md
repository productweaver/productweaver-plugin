# Files and commands

SKILL.md, `pw-rules.md` and `survey-rules.md` are the method: they say what to do and what to write. This file is the binding: it says how it is done with the tool this version ships: the command to run, the file to write, where the study's files are, what the tool refuses and what each host needs. Read it once per session, before your first command. What comes after the heading "Work done on request" matters only when the user asks for that work. A part with a number goes with the step of that number in SKILL.md's workflow.

Every command runs from the root of the workspace. `kb_tool` stands for the full command line that "Running the script" gives. Write the script's full path in every command, as the "Survey" part does.

## Running the script

The script needs Python 3.9 or newer and nothing else: it uses only Python's standard library, so `kb_tool.py` installs nothing and needs no network. It finds its schemas and the map template next to itself, so run it from the root of the workspace, where the study lives:

```
python3 <skill folder>/scripts/kb_tool.py <command> ...
```

Below, `kb_tool` stands for that line. Do not write plain `python`; many machines do not have it. On Windows, if `python3` is missing, use `py -3`. If no command runs at all, because your host has no shell or no Python 3.9, stop: tell the user what is missing, extract nothing, and never write the KB or a study in the chat yourself.

Write the script's full path in every command: never put it in a shell variable (`S=<skill folder>`), never `cd` into the skill folder, and never run it in a `for` loop: write each command out. Claude Code cannot check such a command, so it asks the user or refuses it. Several `kb_tool` commands may share one call.

Transcripts can be `.md`, `.txt`, `.docx` or `.pdf`. The script reads `.docx` itself. It reads `.pdf` with pypdf when that package is installed. When it is not, the merge stops with `reader_missing`: read the PDF yourself, save its text word for word as `.pw-kb/transcripts/<name>.txt` (the PDF's name, ending in `.txt`), and name that file in the patch instead of the PDF. Say so in `provenance.notes`, and tell the user that the quotes were checked against your text copy of the PDF.

Work where the files live: if the transcripts and the KB are on the user's computer, run the commands in a shell on that computer. Copy the tool into `.pw-kb/tools/` only when that machine cannot reach the skill folder. Then copy every `.py` file in `scripts/`, `references/kb-schema.json`, `references/patch-schema.json`, `assets/discovery-map-template.html`, `assets/labels-en.js` and `assets/map-survey.js` together and keep them together. `kb_tool --version` shows which version a copy is, and every KB records the version that last wrote it in `meta.tool_version`.

## Where the study lives

Everything the skill makes goes into two folders at the root of the workspace: `.pw-kb/`, the study itself, and `pw-output/`, the files people read. One workspace holds one study. **The workspace is the user's own folder, whenever they gave you one:** in Claude Code, Codex and other coding tools, the folder the session started in; in Cowork, the folder connected to the task or to its project. Cowork's shell often starts in a temporary folder of its own; that folder is never the workspace. When several folders are connected, take the one that holds the transcripts, and ask only if that does not settle it. Only when no folder is connected and the transcripts were uploaded to the chat (claude.ai, ChatGPT, Claude Desktop's chat) is the workspace a sandbox that is gone after the chat; part 6 says what to hand back then.

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

- Never write the skill's files outside `.pw-kb/` and `pw-output/`. The user's own transcripts stay where they are; the merge copies them in.
- Run every command from the workspace root, with the paths as shown. The tool refuses a KB anywhere else.
- `.pw-kb/` is hidden in Finder and most file dialogs, because its name starts with a dot. `pw-output/` is not, so people find the map there by themselves.
- Every write (`merge`, `apply`, `themes`, `overview`) and the `review` and `map` commands write `pw-output/`. They give it the same `.gitignore` as `.pw-kb/`, so git treats both folders alike. The map also keeps a hidden `.map-live/` folder there, which tells an open map that a newer one is ready (git ignores it).
- The same commands remove the copies that plugin 0.11 and earlier left in `.pw-kb/`, and say so in one line that starts `moved:`.

**When the user gave you a folder, the study is files in that folder, never text in the chat.** If your shell can reach the folder, `cd` into it and run every command there. If it cannot, because the commands run on another machine and you reach the folder only with a file tool: first copy the folder's `.pw-kb/` (everything except `backups/`) to where the commands run; at the end, before your report, save every file the run created or changed into the user's `.pw-kb/` and `pw-output/`, with the same names and sub-folders. Name `pw-output/.gitignore` in that save too, because file tools may skip names that start with a dot. When a write, `review` or `map` printed a `moved:` line, also delete the old `review.md`, `interview-guide.md` and `discovery-map.html` from the user's `.pw-kb/`, if your tools can delete. Never paste the map, `review.md` or the KB into the chat. Never offer them as downloads instead, and never put them in a folder of your host's own, such as an outputs folder.

**When the link to the user's computer drops.** In Cowork, a task that runs in the cloud reaches the folder through the Claude desktop app, over a link that often drops for a few seconds and comes back by itself. So fetch every file the run needs in one request, when your tool takes several, and work on those copies; save them back in one request too. When a call that lists, fetches or saves files on the user's computer, or runs a command there, fails because the computer, the device or the app cannot be reached, is not connected or timed out, do not stop and do not tell the user yet: read `references/dropped-link.md` and retry as it says. A missing file, or a folder you are not allowed to open, is not a dropped link: do not retry those.

## 1. Find the study and the transcripts


First find the workspace, as "Where the study lives" says: in Cowork, the connected folder. Look there, not in the shell's starting folder, for `.pw-kb/pw-kb.json` and the transcripts. The KB is `.pw-kb/pw-kb.json`. Ask where the new transcripts are only if they cannot be found. Never look for transcripts in `pw-output/`, and a file named `review.md`, `interview-guide.md` or `discovery-map.html` is never a transcript, wherever it is: the skill wrote it.

**A study the user attached.** In a chat where files are attached, a zip or folder that holds `pw-kb.json` is the study you handed back last time. Open it before anything else, so new interviews join it instead of starting a new study. If `.pw-kb/` already exists, do not unpack: ask which study to keep. Otherwise unpack it so that `.pw-kb/pw-kb.json` exists afterwards (not `.pw-kb/.pw-kb/`).

Then, with the workspace found and any attached study unpacked, run `pw_usage.py start`, as "Usage statistics" says, unless `pw-start` already ran it in this conversation. Every run of this skill starts with it.

No KB yet:

1. Read the first lines of each new transcript, to see which language the interviews are in.
2. If `pw-output/interview-guide.md` is already there (or `.pw-kb/interview-guide.md`, from plugin 0.11 or earlier), the user planned these interviews with the `pw-start` skill before the study existed. Read it. The kinds of people under "Who to find" may become trait values in the first plan, including kinds nobody has been heard from yet. The study's first overview replaces the file with a guide built from the study; until then the rebuild after each write keeps it and says `kept`.
3. `kb_tool init .pw-kb/pw-kb.json --project "<name>"`. Add `--interviewer "<name>"` only when the user or the transcripts say who ran the interviews; never fill it in from anywhere else.
4. Ask what the start needs to know, in one question call of at most three questions: the study's language, unless every transcript is in English (see "Study language" in SKILL.md); when `init` printed a `git:` line, whether to share the study through git; and, when `pw_usage.py start` printed `usage: no-study`, the usage question (see "Usage statistics"). `.pw-kb/` holds interviewees' names, their words and their transcripts, and the `git:` line means the workspace is a git repository. If the user does not want to share it, write `.pw-kb/.gitignore` containing the single line `*`. If they do, write it with the two lines `logs/` and `usage/`. `pw-output/` follows the same answer: every rebuild copies that file into it. Then run `pw_usage.py set` with the answer. Do not ask any of these questions again later.
5. For a language other than English, run the `labels` steps of `references/study-language.md` before you extract.

When nobody can answer, as in a scripted run, pass `--language <code>` to `init` instead: it writes the labels file to fill in the same call. Do not touch git then, and run `pw_usage.py set .pw-kb no`.

**An older study.** A study in `.pw-kb/pw-kb.yaml`, a study in a `KB/` folder, and a KB with an older schema are each refused with a message to run `migrate`. Read `references/migrate.md` and do what it says before anything else.

## 2. Load the context


```
kb_tool context .pw-kb/pw-kb.json --batch 8  # 8: the transcripts in this batch; --json gives one JSON object, as in references/context-schema.json
```

- **The time.** With `--batch`, it first prints a `batch:` line. Use `--batch` only at the start of a batch. Tell the user its estimate in one plain sentence, such as "8 interviews: about 14 minutes. I'll tell you when your map is ready.", and when the line says an open map shows it, add "Your open map shows that it is being updated." When `pw-start` already gave the time in this conversation, pass on only the part about an open map.
- **The structure.** Then it prints the study's language, then each core job with its steps, outcomes and IDs, then the current solutions by group, every person with their own core job and the core job it links to, the segments, the files already processed, pending proposals and stale layers. Map new evidence against this, and write every statement in the study's language.
- **A file that is already in.** Skip any transcript whose file is in "processed files". The script also skips it, matching by file name and content hash, so re-running the same batch never double-counts.
- **A person who is already in.** A file or a pasted text from someone listed under `PEOPLE AND THEIR JOBS` is a later conversation with them: send it under `interactions`, as "The same person again" in `references/pw-rules.md` says. When you are not sure it is the same person, ask once with your question tool: "Is this the same Dana you talked to on 14 October?" (no question tool: one plain-text question).
- **The same conversation twice.** Skip an email or a chat with the same date and format as a conversation that person already has: a later one their line lists, or their first conversation, the `date` and `format` of their record in `.pw-kb/pw-kb.json`. The study holds a cleaned copy of it under another name. Only when the user says it is another one, send it with `"another": true`.

## 5. Send the batch


Write the patch to `.pw-kb/patches/<date>-<batch>.json`, a JSON file in the format of `references/patch-format.md`. Open it with `generated_with` and a `provenance` block: which assistant and model you are, when you started reading, which interviews you read (by ID or key, never by file name) and any note a later reader needs. The merge copies it into the KB's changelog, so every batch can be traced to who extracted it and how. Write every ID as a string, in double quotes: interviews `"01"`, core jobs `"B"`, steps `"B.2"`, outcomes `"B.2.3"`. A number is not an ID: the merge reads the number `7` as interview `"07"` and warns, but `2.10` reads as `2.1`, another outcome. Inside a text, write a straight quote mark as `\"`; a curly one needs nothing. Then:

```
kb_tool merge .pw-kb/pw-kb.json .pw-kb/patches/<file>.json --transcripts <folder with the new transcripts>
```

In the patch, `file` is the transcript's file name. `--transcripts` says where the new ones are; pass it once per folder, or leave it out when every file the patch names is already in `.pw-kb/transcripts/`. A file name that exists in two of those folders is refused. The KB's own copies in `.pw-kb/transcripts/` always come first, so the transcripts of earlier interviews are read from there. The real merge copies each new transcript into `.pw-kb/transcripts/` and records it as `transcripts/<file name>`; the user's originals are never changed. The script reads only the transcripts the KB and the patch cite. A corrected text copy of a PDF, with the hyphens of its broken lines mended, goes in `.pw-kb/transcripts/` as `<name>.txt`: name that file in the patch, not the PDF.

**Emails, chats and pasted text.** Never name an email or chat export in the patch: the merge would copy it as it is, with its addresses and headers. Text the user pastes or types in the chat, such as notes, needs a file too. Read `references/emails-and-chats.md`, save a cleaned text copy as it says, and name that copy. The merge refuses a copy that still holds an address or a header line (`contact_details`). Name a patch for one follow-up `<date>-follow-up-<id>.json`.

The merge runs every check before it writes anything, so a refused merge writes nothing: fix the patch and run the same command again. There is no need for a `--dry-run` first. Each check blocks the merge:

- **JSON:** a missing comma, a comma after the last item or a quote mark without its `\` gives `json_invalid`, with the line and column and the line itself. Fix that spot.
- **Patch format**, against `references/patch-schema.json`: a missing field, a list where an object belongs, or an ID written as a number gives one message that names the place in the patch.
- **Quote not found:** open the transcript, copy the exact span and fix the patch. Never loosen the check.
- **Reference:** a step, outcome, interview, core job link, proposal target or segment that does not exist, or an outcome that was merged into another. In a KB with several core jobs, an ID without its job letter (`6.3`) is refused too.
- **Clarity:** a statement is too long or carries brackets, examples or a semicolon. Rewrite it shorter, following "Write for the reviewer first". Treat the warnings ("may hold two jobs", abbreviations) as prompts to reread the statement.
- **Structure:** the KB that would result is checked against `kb-schema.json` before anything is written.

Warnings do not block: an interview skipped because it is already in the KB (its evidence is dropped), an interview ID written as a number that was read as `"01"`, an unknown top-level key, or a transcript whose content changed since it was added.

A merge first copies the new transcripts into `.pw-kb/transcripts/` and the current KB to `.pw-kb/backups/` (the newest 20 copies are kept), then writes the new KB, recounts all coverage numbers, marks derived layers stale and appends a changelog entry that lists what was added, stamped with the time and the `run_id` of the run. Then it rebuilds the review sheet and the map, as part 6 says. Keep the patch file: it is the audit trail of what each batch added. Re-running a batch that was merged already is a no-op. Add `--json` to get one JSON object with `ok`, `errors`, `warnings`, `run_id` and the changes, instead of text.

## 6. The review sheet and the map


`merge`, `apply`, `themes` and `overview` rebuild `review.md`, `interview-guide.md` and the map after each write, so reviewers never open a stale picture. Each prints the map's `link:` line and the `Open the link` line, which says what a map that is already open does. Do not run `review` and `map` after them.

After a merge that added interviews or later conversations, write the overview, as SKILL.md's "Write the overview" describes, also for a single follow-up. When the merge printed `batch: every transcript is in`, an open map says the study is being updated until the overview is written. The map opens on it, `review.md` and `interview-guide.md` show its plan for the next interviews, and a merge marks the old one out of date. On a first batch, the overview is the last write before your report, so add `--open` to it:

```
kb_tool overview .pw-kb/pw-kb.json .pw-kb/patches/<YYYY-MM-DD>-overview-<job>.json --open
```

`--open` shows the map in the user's default browser. Do not ask first. Leave it out on every other write, so the user does not get a new tab each time. When a first batch's overview could not be written, run `kb_tool map .pw-kb/pw-kb.json --open` once, so the user still gets the map; run it too when the user asks to see the map. `review` and `map` stay for a rebuild on request, and `--no-publish` on a write skips its rebuild. An open map reloads after the merge and again after the overview: that is expected, so say nothing about it.

- `pw-output/review.md` is a plain sheet listing decisions waiting, what is new since the last merge, the job map by stage with how many people back each step, and the next interviews: where the study stands, the plan and every thin spot.
- `pw-output/interview-guide.md` is that plan as a guide to take into the calls: who to find, what to ask, what to listen for. Every rebuild rewrites it once the study has an overview.
- `pw-output/discovery-map.html` is the interactive map, for people who do not know the method. It is one file with the KB inside: it opens in any browser and works offline. Its views are Overview, Map, Solutions, Value themes, Survey and Next interviews; a view shows once the study has something for it. An open map updates itself a few seconds after each rebuild and keeps the reader's place.

**Put the map in front of the user.** Read `references/open-files.md` once per session and do what it says for your host: one link, or the host's file card, that opens `pw-output/discovery-map.html`. The interview guide is in the map's Next interviews tab. The decisions waiting are near the top of its Overview, under "Decisions for you". Name the tab or the heading in words. Every write and `map` print a `link:` line with the map's `file://` address. When the commands ran on another machine (the address starts with a folder the user does not have, such as `/sessions/` or `/mnt/`), that address does not open for them, and `open-files.md` says what to give instead.

- When a write, `review` or `map` printed a `moved:` line or a `git:` line, do what `references/open-files.md` says under "A `moved:` or a `git:` line" before you report.
- After `--open`, say what the tool said: the map is open in their browser, or it could not be opened here and what to do instead. Never say it is open when the tool did not.
- After a rebuild without `--open` that moved no files, say the map is updated, and pass on what the tool's `Open the link` line says about a map that is already open: it updates by itself, or, once after the plugin was updated, it needs one reload.
- Do not run a command of your own to open the map (`open`, `xdg-open`, `start`). It would cost the user one more permission question.
- Only when no folder is connected and the transcripts were uploaded to the chat, so the study sits in a sandbox that is gone after the chat: put the map in front of the user as `references/open-files.md` says for your host, then hand back the whole `.pw-kb/` folder the way your host shares files, as a zip when it needs one, and say: "Keep this folder. Next time, upload it with your new interviews." Hand back `review.md` and `interview-guide.md` only when the user asks. Do not say the map is open in their browser.
- With a connected folder, as in Cowork, never hand back: check that `discovery-map.html` and `review.md` are in the user's own `pw-output/`, then report. If saving them there still fails after the retries in "When the link to the user's computer drops", never report the study as saved: say it is ready but not yet in their folder, and give the words to say: "Save the study".


`map` uses `assets/discovery-map-template.html` from this skill. A `discovery-map.html` made by the same version of the skill also works as a template (`--template`).

## 7. The report

The map comes last before the "Next:" line, as part 6 says: one link or file card that opens it, with words as its text, such as "Open your discovery map", never the file name; then at most three short lines: the interview guide is in its Next interviews tab, to print or copy; the decisions still waiting, when there are some, are near the top of its Overview, under "Decisions for you"; and where it is saved, in words a person can follow in Finder without the chat: their own folder's name, then pw-output, then the file, such as "It's saved in your Interviews folder, in pw-output: double-click discovery-map.html to open it again", never the word "workspace". Add that the map holds the interviewees' names and quotes.

## Overview

The rules are in `pw-rules.md`, "Overview". SKILL.md, "Write the overview", says when to write it.

1. Run, in place of a second `context`, with the core job's letter in place of `A`:

```
kb_tool overview .pw-kb/pw-kb.json --skeleton A
```

It writes nothing. It prints the job, its OPEN GAPS ranked, with who backs each one and the level line, the people whose main goal it is, with their IDs, and then the file to fill in, with each sentence's word limit for this study. Plan the next round from the OPEN GAPS. For the outcomes, the solutions and who stopped using them, use what `context` printed in this run, or run it when you have not. For quotes and who said what, read `.pw-kb/pw-kb.json` itself: the `evidence` lists of the steps, the outcomes, the solution uses and each person's own statements.
2. Save that file as `.pw-kb/patches/<YYYY-MM-DD>-overview-<job>.json` and fill it in, following `references/pw-rules.md`, "Overview". Replace every `<…>`; delete the ones that give a count rule, and those that say "or delete this" when you have nothing to put there. The tool refuses a file that still holds one. When the job already has an overview, its traits come filled in: sort the people listed as `<not sorted yet: …>` into their values.
3. Write it, adding `--open` on a first batch (part 6):

```
kb_tool overview .pw-kb/pw-kb.json .pw-kb/patches/<file>.json
```

The tool refuses a quote or a solution the KB does not hold, a sentence more than a quarter over its word limit, a percentage or a score word, a word of the method ("core job", "desired outcome"), an unknown icon, a missing part, a `<…>` left from the skeleton, and a plan ID that is not a step, outcome or trait value of the core job. A refused overview writes nothing: fix the file and run the same command again. A sentence over its limit by a quarter at most is written with a warning: shorten it anyway when you next write the overview. It warns on vague words such as "pain point" or "workflow": rewrite them in plain words unless they are the customers' own. It also warns when the round misses a thin spot the main finding rests on, or asks what people would do: fix those. It replaces that core job's overview, leaves other core jobs alone, and rebuilds the review sheet and the map.

The user changes the overview by telling you. Edit the file and run `overview` again.

`kb_tool overview .pw-kb/pw-kb.json --skeleton <job>` prints this file with a `<…>` in every place to fill in, and the word limits of the study. A filled-in example, for a study of small-restaurant owners:

```json
{
  "job": "A",
  "executor": {
    "label": "Small-restaurant owner",
    "text": "An owner who runs one restaurant and places every supplier order themselves.",
    "icon": "cook",
    "others": ["their suppliers"]
  },
  "bottom_line": "Owners throw away food every week because they order from memory, without numbers.",
  "why": "The stock apps they tried need a count nobody has time to do.",
  "opening": "Tell the owner what the week will need before the order goes out.",
  "people": {
    "answer": "5 owners of small restaurants who place the orders themselves.",
    "text": "They order 2 times a week, between services, and nobody checks the numbers.",
    "quote": {"interview": "02", "quote": "I order on Sunday night, half asleep."}
  },
  "today": {
    "answer": "Owners order from memory, with a paper stock sheet.",
    "text": "Owners fill in the sheet when they have time, so the order depends on what they remember."
  },
  "gaps": {
    "answer": "The stock sheet is out of date when owners place the second order.",
    "items": [
      {
        "label": "The sheet is wrong by Wednesday",
        "text": "Nobody updates the sheet during service, so owners guess the second order and throw food away.",
        "kind": "struggle",
        "solutions": ["S2"],
        "quote": {"interview": "03", "quote": "We threw out two cases of fish that week."}
      }
    ]
  },
  "needs": {"answer": "Owners most want to throw away less food at the end of the week."},
  "focus": {"answer": "Build first for ordering the right amount."},
  "next": {
    "learn": {
      "status": "now",
      "action": "Talk to 4 more owners, 2 of them with more than one site.",
      "why": "All 5 owners run one site. These calls show if a second site changes how they order.",
      "ask": ["Tell me about the last time you ran out of something. What did you do?"],
      "tip": "Ask what they did last time, not what they would like.",
      "traits": [
        {"id": "T1", "name": "Sites", "values": [
          {"id": "T1.1", "label": "One site", "interviews": ["01", "02", "03", "04", "05"]},
          {"id": "T1.2", "label": "Two or more sites", "interviews": []}]},
        {"id": "T2", "name": "Who counts stock", "values": [
          {"id": "T2.1", "label": "The owner", "interviews": ["01", "02", "04"]},
          {"id": "T2.2", "label": "A chef or manager", "interviews": ["03", "05"]}]}
      ],
      "rests_on": ["A.3.1", "A.3.2"],
      "round": [
        {"kind": "new", "count": 2, "who": "Owners who order for 2 or more sites",
         "traits": ["T1.2"], "gaps": ["T1.2", "A.3.2"],
         "questions": [{"ask": "Walk me through last Sunday's order, from the first item to sending it.",
                        "listen": "how they chose the amounts: a guess means they lack numbers", "gaps": ["A.3.2"]}]},
        {"kind": "new", "count": 1, "who": "An owner whose chef counts the stock",
         "traits": ["T2.2"], "gaps": ["A.4"],
         "questions": [{"ask": "Tell me about the last time the count and the shelf did not match.",
                        "listen": "what they threw away: wasted food means the count came too late", "gaps": ["A.4"]}]}
      ]
    },
    "prototype": {
      "status": "ready",
      "action": "Draw an order list built from last week's sales, on one page.",
      "why": "All 5 owners raised it, and 2 paid for a stock app and stopped using it.",
      "test": "Ask Ana and Luis to place one real order from the drawing. Build it if both finish without help.",
      "later": "Do not plan staff rotas yet."
    },
    "market": {
      "status": "early",
      "action": "Write to Ana and Luis, who asked to see it, and offer to show the drawing.",
      "who": "Owners who place the orders themselves.",
      "words": ["half asleep"],
      "unknown": "Nobody said what they would pay. Ask the first owner who wants it to pay for a trial."
    }
  }
}
```

Notes on the example:

- `executor` is who the study is about; the map shows it first, with the icon. Its `label` has at most 4 words, what they would call themselves. `icon` is one of the icons listed in `references/kb-schema.md`; use `person` when none fits. `others` is optional: people in the story who are not its focus.
- `text` and `quote` under `people` are optional.
- A gap's `kind` is `pain` (it hurts today) or `struggle` (a fix they tried did not work). Its `solutions` is optional: the solutions it concerns.
- `status` is `now` or `enough` for `learn`, and `ready` or `early` for `prototype` and `market`.
- `words` are the customers' own words, each part of a quote in the KB.
- `traits`, `rests_on` and `round` are the plan for the next round, and come together. Read `pw-rules.md`, "Plan the next round", first. Every ID is a step, an outcome or a trait value of this core job.

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
- `usage: no-study`: a new study. Ask the question with the other start questions (part 1, "No KB yet").
- `usage: on`, `usage: off`, `usage: disabled`: never ask. Only the line `start` prints decides; never ask because of what `set` or `end` print.

The question, in the user's language except the example line, with two choices in this order, neither marked recommended: "Yes, share" and "No, don't share". Never suggest an answer, not even in an example reply. Use the host's question tool, else one plain-text question that names both choices.

> Share anonymous usage statistics with Pancrazio at Product Weaver?
> Only events like this one:
> `{"event":"tool_run","command":"merge","exit_code":0,"counts":{"interviews_added":3},"at":"2026-11-13T10:42Z"}`
> Never your interviews, names, quotes, prompts or file names. Everything sent is in .pw-kb/usage/sent.jsonl. Stop any time.

Then run `set` with `yes` or `no` and the same options as `start` (and `--path` when `start` had one). No answer, a dismissed question or a scripted run: `no`. When the user asks to stop sharing ("stop sharing", in any words): run only `set .pw-kb no`, with no `start` or `end` before or after it, and say that `sent.jsonl` keeps the record of what was sent. Never ask for network access, never mention a failed send, never send anything yourself.

## What the script records

Every run appends one line to `.pw-kb/logs/kb_tool.jsonl`; `references/run-log.md` lists every field and every code. The log never holds a quote, an interviewee's name, a transcript file name or an absolute path. It belongs to the study: do not send it anywhere. `pw_usage.py` sends content-free events made from it, and only after the user's yes.

The script recognises Claude Code and Gemini CLI from their environment; in any other assistant, set `KB_TOOL_AGENT=<assistant>/<model>` before calling it so the log's `agent` field is right. `KB_TOOL_LOG=0` switches the log off.

## Branding

Every file this skill produces carries a light Product Weaver credit: the map's header and badge, the review sheet's footer, `generated_with` in the KB's metadata, and `generated_with` at the top of each patch file (`"generated_with": "Made with Product Weaver · productweaver.com"`). Keep these when you edit or rebuild files. They tell readers where the method and the tools come from. Do not add marketing lines to chat replies; the credit lives in the files. The links to productweaver.com in the map and the review sheet carry fixed tags (`utm_source=productweaver-plugin` and so on) that tell the site which file a visit came from. They never hold anything from the study; leave them as they are.

## Work done on request

The parts from here on are for work the user asks for: value themes, the survey, writing rules of the study's own, and a check of the KB.

## Value themes

The rules are in `pw-rules.md`, "Value themes".

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

Give `id` only for a theme that already exists; leave it out for a new one. The file holds `job` and `themes` only: the tool refuses any other key, `generated_with` too.

3. Write it:

```
kb_tool themes .pw-kb/pw-kb.json .pw-kb/patches/<file>.json
```

The tool refuses a theme that cites an outcome or a quote the KB does not hold, and warns about a set that is too large, too small or overlapping. A refused file writes nothing: fix what it refuses and run the same command again; weigh what it warns about. It replaces that core job's themes, keeps their IDs, leaves other core jobs alone, prints what changed and rebuilds the review sheet and the map.

The user changes themes by telling you. Edit the file and run `themes` again.

## Survey

The rules are in `survey-rules.md`. The parts below have its part numbers.

### Before you start

```
python3 <skill folder>/scripts/kb_tool.py context .pw-kb/pw-kb.json
```

### 1. Merge near-twins

1. Write `.pw-kb/patches/<date>-twins-<job>.json`, with `generated_with` and `provenance` as in every patch (`patch-format.md` shows them), and one `merge_outcomes` proposal for each pair: `{"type": "merge_outcomes", "target": "C.2.1", "merge": "C.2.4", "proposal": "One need: less time to find which supplier has an item in stock", "rationale": "A person could not rate these two differently."}`.
2. Merge it, with no `--transcripts`, then approve each proposal with its code, from the merge's line that ends `proposals P2`. Keep the path on the merge's `backup:` line: it is the study before any twin was merged, and the only way back.

```
python3 <skill folder>/scripts/kb_tool.py merge .pw-kb/pw-kb.json .pw-kb/patches/<date>-twins-<job>.json
python3 <skill folder>/scripts/kb_tool.py apply .pw-kb/pw-kb.json P2 --decision approve --note "near-twins, merged before the survey"
```

### Undo a twin merge

Undo a merge only while nothing else was written to the study since the survey and its estimate: no new interviews merged, no other proposal applied. Then

1. First copy `.pw-kb/pw-kb.json` to `.pw-kb/backups/pw-kb.before-undo-<date>-<time>.json`, with the time as hours, minutes and seconds, so the study as it is now is kept and two undos never overwrite each other. Then copy the file on the twins merge's `backup:` line over `.pw-kb/pw-kb.json`, with your file tool or `cp`.
2. Write `.pw-kb/patches/<date>-twins-<job>-2.json` with the other pairs only, merge it and approve its proposals, as in part 1. With no other pair, skip this step.
3. Check the study: `python3 <skill folder>/scripts/kb_tool.py validate .pw-kb/pw-kb.json --structure-only`.
4. Write the survey again with `--write`, and the estimate with `--estimate` when there was one, as in parts 3 and 4. The survey's version starts again from the one the restored study had: that is fine.

When something else was written since, or the file on that `backup:` line is no longer there (the tool keeps only the newest 20 backups), do not try. Say plainly that this version cannot split the two needs again, and that next time the user can ask for the undo before more work is added. Never edit `.pw-kb/pw-kb.json` by hand.

### 2. The skeleton

Run the skeleton, with the goal's letter. It writes nothing and prints the file to fill in:

```
python3 <skill folder>/scripts/kb_tool.py survey .pw-kb/pw-kb.json --skeleton C
```

Save what it prints as `.pw-kb/patches/<date>-survey-<job>.json`, with today's date and the goal's letter. A need left out of a survey that would be too long goes in `left_out`, as `{"outcome": "C.4.3", "why": "Named by one person only."}`.

### 3. Write the survey

```
python3 <skill folder>/scripts/kb_tool.py survey .pw-kb/pw-kb.json --write .pw-kb/patches/<date>-survey-<job>.json
```

The tool refuses a need text over 160 characters, an "Explain" over 25 words, a frame over 120 characters, an empty value, a need that is in neither `needs` nor `left_out`, and more than 30 needs. A refused file writes nothing: fix what it names and run the same command again. When it is written, it prints `survey: job C, version 1, 28 needs in 8 steps, about 8 minutes` and rebuilds the map.

### 4. The estimate

Run, with the goal's letter:

```
python3 <skill folder>/scripts/kb_tool.py survey .pw-kb/pw-kb.json --evidence C
```

It writes nothing. Save what it prints as `.pw-kb/patches/<date>-evidence-<job>.json`, never outside the study.

When every person is rated, write `.pw-kb/patches/<date>-estimate-<job>.json`:

```json
{
  "job": "C",
  "cells": [
    {"interview": "03", "outcome": "C.2.1", "importance": 5, "satisfaction": 2, "basis": "said",
     "quote": "I ring four suppliers before I find the gloves in stock.", "why": "She calls several suppliers for one item, every week."}
  ]
}
```

Then check and store it:

```
python3 <skill folder>/scripts/kb_tool.py survey .pw-kb/pw-kb.json --estimate .pw-kb/patches/<date>-estimate-<job>.json
```

The tool refuses a rating that is not a whole number from 1 to 5, a quote that is not that person's on that need, its step or a tool there, a wrong `basis`, a `why` over 20 words and the same person and need twice. A refused file writes nothing: fix the cells it names and run the same command again.

## Study-specific writing rules

A study overrides the defaults in `meta.style` of the KB, an object such as:

```json
{"limits": {"outcome": 14}, "acronyms": ["OTR", "ELD", "DOT"], "idioms": ["bread and butter", "in and out", "pick and pack"]}
```

`references/kb-schema.md` lists the keys.

## Checking a KB

```
kb_tool validate .pw-kb/pw-kb.json
```

First checks the KB's structure against `kb-schema.json`: required fields, ID formats, stages, source types and the references between steps and outcomes. Then it re-checks every stored quote against the study's copy of its transcript in `.pw-kb/transcripts/` and compares each copy with the content hash stored when it was added. A transcript that changed is reported; if the change is intended, add `--rehash` to accept the new content once every quote matches. Add `--structure-only` to skip the quotes. A copy that is missing is reported; put the transcript back in `.pw-kb/transcripts/` under the same name. Run it after any hand edit. `merge` runs the same structure check and refuses to write a KB that would break it.

Each KB records its schema version. Every command but `migrate` refuses an older KB with a message to migrate, as `references/migrate.md` says, and a KB written by a newer version of the tool with a message to update the skill.

The KB's fields are explained one by one in `references/kb-schema.md`. Read it before editing a KB by hand or building anything that reads one.
