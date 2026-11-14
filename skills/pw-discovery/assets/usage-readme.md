# Usage statistics

This folder holds your answer to one question: do you share usage statistics with Product Weaver?
`settings.json` shows your answer. Nothing is sent unless it says `"share": true`.

Git ignores this folder. Each person who works on a study answers for themselves.
Your answer travels with the study folder. Delete the `usage/` folder before you hand a study to someone else.

Two settings in your environment switch usage statistics off for every study on your machine.
They are `KB_TOOL_USAGE=0` and `DO_NOT_TRACK=1`. With either one, nothing is recorded or sent.

More: https://www.productweaver.com/privacy

## If you said yes

What is sent: small events that show which parts of the plugin work and which do not. They hold counts, codes and
versions. They never hold interviews, transcripts, names, quotes, notes or file names. They never hold your prompts,
the text of labels, the arguments of a command or the paths of your files.
To make them, the plugin reads the run log, `.pw-kb/logs/kb_tool.jsonl`, and two things in `pw-kb.json`:
the study's language and how many entries its plan for the next interviews holds. To tell whether git tracks the
run log, it also reads `.pw-kb/.gitignore` and git's index, and looks there for the run log's path only.

Each event carries a random study number. It is made when you say yes, from nothing else. It is in `settings.json`.

Where it goes: to www.productweaver.com, which passes the events on to PostHog. Claude Code's sandbox may ask you
to allow www.productweaver.com. Allow it, or the events stay in this folder.

In Claude Desktop, a Cowork task can reach www.productweaver.com only after you allow it. Open Settings, then
Capabilities. Keep Allow network egress on, add `www.productweaver.com` under Additional allowed domains, then start a
new conversation. Until then the events wait here. They leave from the next session where the network is open, for
example Claude Code on your computer. Or run this in a terminal, from the folder that holds `.pw-kb`:
`python3 <plugin folder>/skills/pw-discovery/scripts/pw_usage.py end .pw-kb --skill pw-discovery`

The files:
- `waiting.jsonl`: events not sent yet.
- `sent.jsonl`: every event exactly as it left. Open it to see what was sent.

To stop: tell your assistant to stop sharing. This deletes the events that are waiting.
Or stop it yourself: in `settings.json`, change `"share": true` to `"share": false`. Nothing is then recorded or
sent for this study. Delete `waiting.jsonl` too, if you like. The two settings above stop it on your whole machine.

To have your events deleted: write to privacy@productweaver.com with the study number from `settings.json`.
We then stop accepting events for that study and ask PostHog to delete the ones it holds.
Anything that remains is deleted after 2 years.
Note the study number before you delete this folder. It is the only key for a deletion request.

If you share the study through git: tool events are sent only while `.pw-kb/.gitignore` lists `logs/` and git
does not track the run log, `.pw-kb/logs/`. A study shared through git before this version may have its run log
in git. Then do both: run `git rm -r --cached .pw-kb/logs`, and add `logs/` to `.pw-kb/.gitignore`.

## If you said no

Nothing is recorded or sent for this study.
If you change your mind, delete this folder. The assistant will ask again at the next session.

If you said yes before, `settings.json` still holds that study number, the key for a deletion request (see above).
Note it before you delete this folder: a new yes makes a new study number.
