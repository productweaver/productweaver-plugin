---
name: pw-start
description: Help someone start with Product Weaver, or decide what to do next. Use when the user has just installed the plugin, asks how to start, what Product Weaver can do, or how to begin customer discovery; when they have no interviews yet and want to plan their first ones; or when they come back to a study of customer interviews and ask where it stands or what to do next.
---

# pw-start: a first result, then one next step

*From [Product Weaver](https://www.productweaver.com).*

People install the plugin and then don't know what to say. They ask "Help me get started with Product Weaver", "What can this do?" or "What should I do next?". Your job: get them to one useful result in this conversation, then name the one thing to do after it.

The work itself is done by the `pw-discovery` skill, which turns interview transcripts into a study in `.pw-kb/` with a discovery map. This skill decides which result the user can get now, and hands over.

## When not to use this

If the request already names work `pw-discovery` does, use `pw-discovery` and say nothing about getting started. For example: "process the interviews in Interviews/", "add these calls to the study", "approve P1", "build value themes", "show me the map". Never give a welcome tour to someone who already said what they want.

## Look before you ask

Ask nothing yet. Look at the workspace (the folder the session started in) and at any files the user attached:

1. **A study.** `.pw-kb/pw-kb.json` means a study exists. `.pw-kb/pw-kb.yaml`, or a `KB/` folder with a study file and no `.pw-kb/pw-kb.json`, means a study made by an older version: bring it up to date with `pw-discovery`'s migrate step, without running `context` first.
2. **A first-round guide.** `.pw-kb/interview-guide.md` with no `pw-kb.json` beside it means the user planned their first interviews earlier.
3. **Transcripts.** Look for `.md`, `.txt`, `.docx` and `.pdf` files at the root and one folder down. Read only their names and first lines. Skip `.pw-kb/` and the files every project has: README, CHANGELOG, LICENSE, CONTRIBUTING, and docs or source code in a code repository. A transcript reads like a conversation or call notes, with names or speaker turns.
4. **Recordings.** Audio and video files (`.mp3`, `.m4a`, `.wav`, `.mp4`, `.mov`) are recordings, not transcripts.
5. **Attachments.** Files the user attached in this chat count too, wherever your host puts them. An attached zip or folder that holds `pw-kb.json` is a study they kept from an earlier chat. If `.pw-kb/` already exists, do not unpack: ask which study to keep. Otherwise unpack it so that `.pw-kb/pw-kb.json` exists afterwards (not `.pw-kb/.pw-kb/`), then take path C.

## Pick one path

| What you found | Path | The first result |
|---|---|---|
| Transcripts, no study | A | their discovery map, open |
| No transcripts, no study | B | a guide for their first round of interviews |
| A study | C | the one next step, with the words to say |
| No folder and nothing attached | D | how to give you the files, then path B |

Then run, from the root of the workspace, the command below, with `--path transcripts` (A), `--path no_transcripts` (B or D) or `--path existing_study` (C):

```
python3 <plugin folder>/skills/pw-discovery/scripts/pw_usage.py start .pw-kb --skill pw-start --path <path> --assistant <name> --model <id>
```

`<name>` and `<id>` are as in `pw-discovery`'s "Usage statistics", which also says what its output line means and how to ask the question. When no `.pw-kb/` folder is made (path D, or a sandbox that keeps nothing), skip it and everything below that mentions `pw_usage.py`. Every run that ran `start` runs `end` once, when its work is done, with the same options: path B adds `--guide-written`, path C runs it right before you give the next step, and path A hands over to `pw-discovery`, which skips `start` and runs `end` itself.

A first-round guide with no study: tell the user where it is (the full path). If transcripts are there now, take path A and do not ask the planning questions again. If not, ask how the interviews are going and say what to do when they have them: "When you have 3 or more, put the transcripts in one folder here and say: Add my interviews to the study." Never rewrite the guide unless they ask.

## How to answer

- Reply in the language the user writes to you in.
- Before any work starts, write at most about 8 lines.
- Ask at most one round of questions. Do not ask what the workspace already shows.
- Use plain words. Never say "ODI", "core job", "desired outcome", "JTBD" or "job step" to the user. Say "what they are trying to get done", "the steps of their work", "what they want to get better".
- Recommend one thing. Never give a menu. You may name one other choice in one line.
- End with the exact words the user can say next, in their language.
- No marketing lines. Give the link to the example study, https://www.productweaver.com/example, only when the user asks what the result looks like.

## Path A: transcripts, no study

Tell the user, in 3 lines at most:

- what will happen: you read every interview and build a study of what these people are trying to get done, where it goes wrong and what they use today;
- where it goes: a `.pw-kb/` folder in this workspace; their own files are not changed;
- how long: roughly a minute or two per interview;
- what they get: a discovery map that opens in their browser, and the one next step.

Then:

- If you are not sure the files are interviews, ask one yes-or-no question that names what you found ("I found 6 Word files in Calls/. Are these your interview transcripts?").
- **Fewer than 3 transcripts:** go ahead. Say the result is a first guess, and that it will say who to talk to next.
- **Only recordings:** say the plugin reads text. Most call tools (Zoom, Google Meet, Teams) save a transcript; ask them to export it into this folder. Offer path B for their next calls.
- Then follow the `pw-discovery` skill from its step 1. The questions in its step 4 are the only ones the user gets.

**Upload hosts.** When the files were attached to the chat and the workspace is a sandbox that is gone after the chat (ChatGPT, claude.ai), say so in your first lines. Do not promise that the map opens in their browser. At the end, `pw-discovery` hands back the map and the whole `.pw-kb/` folder, as a zip when your host needs one. Say: "Keep this folder. Next time, upload it with your new interviews."

## Path B: no transcripts yet

Plan their first round of interviews. Read `references/first-interviews.md` and follow it: ask up to 3 questions about who they want to learn from, then write `.pw-kb/interview-guide.md`, a guide they take into their first 5 to 8 conversations. In the chat, show who to find, the first 3 questions and the guide's full path, then the words to say when the calls are done. When `start` printed `usage: no-study`, ask the usage question in the same plain-text message as your questions about who to learn from, and never suggest an answer, not even in an example reply. Run `set` with the answer (`set .pw-kb yes` or `set .pw-kb no`) only after the guide is written: before `.pw-kb/` exists, `set` saves nothing. No answer to the usage question means `set .pw-kb no`. `set` and `end` take the same options as `start` (`--skill pw-start --path no_transcripts`). Then run `end --guide-written` (the command above with `end`, `--path no_transcripts` and `--guide-written`). With any other line, ask nothing, and run `end` without `--guide-written` if you wrote no new guide.

A sandbox that is gone after the chat counts as no folder: give the whole guide in the chat, or as a file to download, and ask the user to attach it next time with their transcripts.

## Path C: the one next step

Run, from the root of the workspace:

```
python3 <plugin folder>/skills/pw-discovery/scripts/kb_tool.py context .pw-kb/pw-kb.json
```

`<plugin folder>` is the folder that holds `skills/`: two levels above this file. Do not write plain `python`; on Windows, if `python3` is missing, use `py -3`.

Then go down this list. The first item that applies is the next step:

1. **The tool refuses the study.** `context` prints one `error:` line instead of the study.
   - It says to run `migrate`: the study is in an older format. Bring it up to date with `pw-discovery`'s migrate step.
   - It says "Update the pw-discovery skill": a newer version of the plugin wrote the study. Ask the user to update the plugin, and do nothing else.
   - Any other `error:` line: show it in one line, run `pw-discovery`'s `validate` to see what is wrong, and give no next step until that is fixed.
2. **New interviews.** Transcripts in the workspace whose names are not under `PROCESSED FILES:`. Compare names without their extension: a PDF read without pypdf is kept as a `.txt` copy. Say "Add the N new interviews to the study."
3. **Missing text.** A `LABELS:` line: the map's own text in the study's language is not complete. Finish it with `pw-discovery`'s labels steps.
4. **What the study is about is not confirmed.** A pending proposal of type `confirm_core_job`. Ask them to open the map's Overview, then to say "approve P1" or what to change.
5. **Decisions waiting.** Other proposals under `PENDING PROPOSALS:`. Say how many, and that `.pw-kb/review.md` lists them with the words to answer.
6. **An old summary.** No `OVERVIEW` block, or `OVERVIEW [out of date]`: update the overview and the map.
7. **Not sure enough yet.** Under `OPEN GAPS for core job X`, the line `level N of 3 after M conversations` with N of 1 or 2. Run the next round: how many more conversations, with which kinds of people, from the plan in `.pw-kb/interview-guide.md` and the map's Next interviews view.
8. **A clear pattern, no themes.** Level 3, and no `VALUE THEMES` block: group the needs into value themes, so a team can sort ideas into a few needs.
9. **Otherwise:** the overview's prototype step, or, once that is done, its market step. Say it is advice.

**When the level line is missing.** `context` prints it only for a core job that still has open gaps. Then read that job's `overview.jobs[].next.learn.status` in `.pw-kb/pw-kb.json`: `now` counts as item 7, `enough` means go on to items 8 and 9. Item 9 reads `next.prototype` and `next.market` there too.

**When the study has several core jobs.** Give one step, not one per job. The first item that applies to any job wins. For item 7, take the job at the lowest level; on a tie, the job with the first letter. Name the job by what the people do, never by its letter alone.

**How to answer.** Two lines at most on where the study stands, in plain words, then the step:

> 6 conversations so far. It is an early signal: a few needs keep coming back, but some kinds of people are missing.
> Next: talk to 2 more groomers who work from a van, about how they book the day. The questions are in your interview guide.
> Say "show me the interview guide", or, when the calls are done, "Add my interviews to the study".

For items 2 to 6 and 8, and a migrate in item 1, offer to do it now ("Shall I do it now?"). Level names in words: 1 is "a hunch", 2 is "an early signal", 3 is "a clear pattern".

`.pw-kb/` is a hidden folder, so the user cannot find its files by hand. When you point to one, give its full path. For the map, check that the file exists, then give a `file://` address made from that full path, with each space written as `%20`, such as `file:///Users/ana/My%20Study/.pw-kb/discovery-map.html`.

## Path D: no folder, nothing attached

Say in one line how to give you the files: attach the transcripts here, or open the folder that holds them (in Cowork, choose the folder when you start the task; in Codex or Claude Code, start in that folder). If they have no transcripts yet, take path B and give the guide in the chat, since there is no folder to save it in.
