# Product Weaver

Product Weaver is a plugin for AI assistants like Claude, ChatGPT/Codex, and Copilot that turns customer interview transcripts into a
consolidated and growing knowledge base, with every quote checked word for word against its transcript.

Free, under the Apache 2.0 license. It runs on your computer, needs only
Python, and sends nothing unless you say yes.

[![The discovery map of the example study: who the study is about, the main finding and what to do next](https://www.productweaver.com/example/discovery-map-overview.png)](https://www.productweaver.com/example)

*The discovery map of the example study, made from 6 interviews.
[Open the live map](https://www.productweaver.com/example).*

## What you get

You give your assistant a folder of interview transcripts and ask in plain
words. You get back a discovery map you can open in any browser. It shows

- **what your customers are trying to get done**: their jobs, the steps of
  each job, and the outcomes they measure success by;
- **the proof**: every finding is backed by quotes in the words people used.
  Each quote is checked against its transcript before it goes in, so the
  study never holds paraphrased evidence;
- **who does which job**, when the people you interviewed do different jobs;
- **what people use today** to get each step done, and what they stopped
  using;
- **value themes**: the outcomes grouped into a few needs, such as "Help me
  order what the week will really need", so your team can sort ideas;
- **your next interviews**: who to talk to and what to ask, to back up what
  still rests on too few people;
- **a survey of the needs**: for each need, how much it matters and how well
  it is served today, with a first estimate from your interviews of which
  needs look unmet.

Leave the map open while you work: it updates itself a few seconds after
each run, keeps your place, says what changed, and marks what is new. While
your assistant reads a batch, the map says so and about how long is left.

The study grows with every batch of interviews you add. The method is
Outcome-Driven Innovation (ODI), a way to do jobs-to-be-done research. You
do not need to know it to start.

## Try it in 10 minutes

You do not need your own interviews to try it.

1. **Install the plugin** in your assistant:
   [Claude desktop app](#claude-desktop-app-cowork),
   [Claude Code](#claude-code), [ChatGPT and Codex](#chatgpt-and-codex) or
   [GitHub Copilot CLI](#github-copilot-cli).
2. **Get some interviews.** Use a folder with your own transcripts
   (`.md`, `.txt`, `.docx` or `.pdf`). Or
   [download 6 sample interviews](https://www.productweaver.com/example/bookkeeper-interviews.zip)
   and unzip the file. You get a folder called `bookkeeper-interviews`.
3. **Open your assistant in that folder** (in Cowork, choose the folder) and
   say

   > Help me get started with Product Weaver.

What happens next

- The assistant reads the interviews. This takes about a minute or two for
  each interview, so about 10 minutes for the 6 samples.
- The discovery map opens in your browser.
- The assistant asks you in the chat, with a click, whether it got right
  what these people are trying to get done.
- It names one next step.

No interviews yet? Say the same sentence in an empty folder. The assistant
asks 3 questions and writes a guide for your first interviews: who to talk to
and what to ask.

## Install

### Claude desktop app (Cowork)

No terminal needed.

1. Open **Customize** in the left menu.
2. Choose **Plugins**, then **Yours**.
3. Click **Add**, then **Add marketplace**.
4. Choose **Add from repository**.
5. Type `productweaver/productweaver-plugin`.
6. Turn on **Sync automatically**.
7. Click **Sync**.
8. In the list, find **Product Weaver** and click **Add**.

Then start a task in **Cowork**, choose the folder with your transcripts, and
ask in plain words.

If you use claude.ai in a browser, run the plugin in the desktop app: it works
with the files on your computer. You can add it on the web with the same steps
at [claude.ai/customize/plugins](https://claude.ai/customize/plugins); Claude
saves it to your account, so it is ready in Cowork.

### Claude Code

Version 2.1.292 or later. In a terminal:

```sh
claude plugin install productweaver --marketplace productweaver/productweaver-plugin
```

Or inside a Claude Code session:

```
/plugin install productweaver --marketplace productweaver/productweaver-plugin
```

### ChatGPT and Codex

For Codex CLI and the ChatGPT desktop app:

```sh
codex plugin marketplace add productweaver/productweaver-plugin
```

Then open `/plugins` in Codex and install `productweaver`.

### GitHub Copilot CLI

```sh
copilot plugin marketplace add productweaver/productweaver-plugin
copilot plugin install productweaver@productweaver-plugin
```

### Requirements

- Python 3.9 or newer. To check, run `python3 --version` in a terminal.
  Nothing else to install: the skill's scripts use only Python's standard
  library, so it also runs where packages cannot be downloaded.
- Transcripts as `.md`, `.txt`, `.docx` or `.pdf` files. To read a `.pdf`
  directly, the script needs pypdf (`python3 -m pip install pypdf==6.21.4`).
  Without it, the assistant first saves the PDF's text, word for word, as a
  `.txt` file in the study.

The [install guide](https://www.productweaver.com/plugin) on
productweaver.com has the same steps.

## What to say

To start, or when you come back to a study and do not know what to do

- "Help me get started with Product Weaver." (In Claude Code you can also
  type `/pw-start`.)
- "What should I do next?" The assistant names one next step.
- "Which version of Product Weaver do I have?" `pw-about` shows the version,
  where it is loaded from and what it runs on. Add "for a bug report" to get
  a block to paste, or "am I up to date?" to check for a newer version.

Once you know your way around, ask in plain words, for example

- "Process this week's discovery interviews in the Interviews folder."
- "Start an ODI knowledge base for the Acme study from these transcripts."
- "Add these three calls to the knowledge base and show me what changed."
- "Do these interviews show more than one core job?"
- "What do people use today to find suppliers, and what did they give up?"

The assistant reads the transcripts, proposes what to add, and merges it into
the knowledge base. It then writes a review sheet and a discovery map you can
open in any browser.

Once the study shows a clear pattern and has value themes, check which needs
matter most

- "Create the survey." The assistant writes a survey from the needs of one
  goal, at most 30. For each need, a person says how much it matters and how
  well it is served today. Needs that mean the same thing are merged first,
  and the assistant names each merge.
- "Estimate the answers." The assistant rates each need as each person you
  interviewed would. Each rating rests on one real quote of that person. When
  the interviews say nothing about a need, the rating stays empty.

The map's Survey view shows the questions and, with the estimate, which
needs look unmet. The survey and the estimate are made on your machine, from
your interviews. The estimate is always marked as an estimate: it is not
survey answers. Sending the survey to real people is not in this version.

When the interviews are not in English, the assistant asks once, when the
study starts, whether to write the study in the interviews' language or in
English. Everything you read follows your answer: the findings, the review
sheet and the map's own buttons and help. Quotes always stay in the words
people used.

The plugin has two skills. **pw-start** gets you going: it plans your first
interviews, or turns the ones you have into a discovery map, and says what to
do next. **pw-discovery** does the work on the interviews. You do not need to
name them: the assistant picks the right one from what you ask.

## Can you trust it?

Interviews hold people's names and words, so here is what the plugin does
with them.

- **It runs on your computer.** The plugin is two local Python scripts
  inside the skill. `kb_tool.py` (with `kb_map.py`, `kb_review.py`,
  `kb_people.py`, `kb_migrate.py`, `kb_survey.py`, `kb_overview.py` and
  `kb_themes.py`, next to it, which it loads for some of its commands) reads the files you point it to and writes
  the files listed under [Files it writes](#files-it-writes); it makes no
  network calls. `pw_usage.py` keeps your answer about usage statistics
  and, only after a yes, sends the events. Both load `pw_base.py`, a small
  file that reads the plugin's version and replaces a file in one step; it
  makes no network calls.
- **It has no hooks, no MCP servers and no background processes**, and it
  downloads nothing. An open map stays current by reading one small file
  beside it on your disk every few seconds; it holds no names or quotes.
- **It sends nothing unless you turn on usage statistics** for a study, and
  even then never your interviews, names, quotes, prompts or file names.
  The full list is under [What it sends and where](#what-it-sends-and-where).
- **Your own files are never changed.** The study keeps a copy of each
  transcript it quotes.
- **Every quote is checked** word for word against its transcript before it
  goes into the study.
- **You can read all of it.** The code is open source under the Apache 2.0
  license and ships no third-party code.

Your assistant itself works as it always does with the files it reads.

## If something goes wrong

- **Claude says it can't reach your files.** A Cowork task runs in the
  cloud and reaches your folder through the desktop app. That link
  sometimes drops for a few seconds, and the plugin tells Claude to wait
  and try again by itself. If the link stays down, check that the Claude
  app is open and your computer is awake, then say "Try again". Nothing is
  lost: Claude goes on from where it stopped.
- **You use the Codex IDE extension.** It does not load plugins. Use Codex
  CLI or the ChatGPT desktop app.
- **You use chat on claude.ai in a browser.** It is not tested yet. Use the
  desktop app for now.
- **You can't find the study folder.** `.pw-kb/` is hidden in Finder and
  most file dialogs, because its name starts with a dot. What you read is
  in `pw-output/`.
- **You closed the map.** Open `pw-output/discovery-map.html` with a
  double-click. It works offline.
- **The map does not update by itself.** Reload it once: a map made by
  plugin 0.14 or earlier does not know how. A copy saved somewhere else, or
  one shown inside a chat, never updates, and says so at the top right:
  open the one in `pw-output/` instead.

Still stuck? Ask in this repository's
[Issues](https://github.com/productweaver/productweaver-plugin/issues).

## What it sends and where

The plugin sends nothing unless you turn on usage statistics for a study, and
even then never your interviews, names, quotes, prompts or file names. It
downloads nothing.

**The update check runs only when you ask.** When you ask `pw-about` whether
you are up to date, it sends one request to
`https://www.productweaver.com/api/plugin-version` to read the newest
version number. The request holds no cookie, ID, name or file name, and it
is made even when `DO_NOT_TRACK` is set, because you asked for it. Nothing
else in `pw-about` goes online.

**Usage statistics are opt-in.** The first time you work on a study, the
assistant asks once whether to share them. Each person who gets the study
through git answers for themselves. The choice stays with the folder: it
travels with a study you zip or sync, so delete `.pw-kb/usage/` before you hand
a study over (note the study number first). Without your yes, nothing is
recorded or sent.

- **What is sent:** small events that show which parts of the plugin work and
  which do not: which steps ran and when, how long they took, whether they
  worked, and how many tries a batch took; yes-or-no facts about a run, such as
  whether it was only a trial; whether you approved or rejected a suggested
  change, and its kind; how you started (with interviews, without them, or
  with a study you had), whether you were asked at a new or an existing study,
  whether an interview guide was written, and whether the map opened in your
  browser; counts (such as how many interviews a study holds), error and
  warning codes, the class name of a crash, the study's language, the format
  version a study was upgraded from, whether the study folder is in git, the
  assistant and model, the plugin, script and Python versions, the operating
  system family (macOS, Windows, Linux or other), and a random ID for each
  event. Never interviews, transcripts, names, quotes, prompts, notes or file
  names. [`references/usage.md`](skills/pw-discovery/references/usage.md)
  lists every field and the values it may hold.
- **Where it goes:** to www.productweaver.com, which passes the events on to
  PostHog in the US. We keep them for 2 years. Each event carries a random
  study number, made when you say yes.
- **See what was sent:** open `.pw-kb/usage/sent.jsonl`. It holds every event
  exactly as it left.
- **Stop:** tell your assistant to stop sharing. Without the assistant, change
  `"share": true` to `"share": false` in `.pw-kb/usage/settings.json`. Or set
  `KB_TOOL_USAGE=0` or `DO_NOT_TRACK=1` in your environment: with either,
  nothing is recorded or sent, for every study on your machine.
- **Have your events deleted:** write to privacy@productweaver.com with the
  study number from `.pw-kb/usage/settings.json`. We then stop accepting events
  for that study at once and ask PostHog to delete the ones it holds. Anything
  that remains is deleted after 2 years.

More on https://www.productweaver.com/privacy.

## Files it writes

Files go into two folders at the root of your workspace. One workspace
holds one study.

`pw-output/` holds what you read

- `discovery-map.html`, the interactive map, which works offline. The first
  time it is made, it opens in your browser; after that, open it with a
  double-click, or with the link the assistant gives at the end of each run;
- `review.md`, the review sheet, as text;
- `interview-guide.md`, the plan for your next interviews, as text, ready to
  take into the calls: who to find, what to ask and what to listen for. The
  map's Next interviews tab shows it too, to copy, or to print as an interview
  kit with one sheet per call;
- `.map-live/`, a hidden folder that git ignores. Its `status.js` tells an
  open map that a newer one is ready, or that your assistant is working on a
  batch. It holds no names or quotes.

The survey and the estimate add no new file to `pw-output/`. The map shows
them in its Survey view, and `review.md` in a Survey section.

`.pw-kb/` holds the study itself. Finder and most file dialogs hide it,
because its name starts with a dot

- `pw-kb.json`, the knowledge base. The survey and its estimate live inside
  it too;
- `transcripts/`, a copy of each transcript the knowledge base quotes. Your own
  files are never changed. An email or a chat you paste, or send as a file, is
  also saved here as text. Your assistant saves emails and chats without
  headers, addresses, phone numbers or signatures, and the merge refuses a
  copy that still holds an email address or a header line;
- `labels.json`, only for a study in another language than English: the map's
  and the review sheet's own text in that language;
- `patches/`, one file per batch, the audit trail of what each batch added.
  The survey and estimate files the assistant writes go here too;
- `backups/`, copies of the knowledge base before each merge (the newest 20);
- `logs/kb_tool.jsonl`, one line per run, for debugging. It holds no quotes,
  names or file names;
- `usage/`, your answer about usage statistics, ignored by git: `.gitignore`,
  `README.md`, `settings.json` (your answer and the study number),
  `waiting.jsonl` (events not sent yet), `sent.jsonl` (every event exactly as
  it left) and `.lock`. It travels with the folder, so delete it before you
  hand a study over (note the study number first).

The knowledge base, transcripts, review sheet, map and patches contain
interviewees' names and words. They stay on your machine unless you share
them. If your workspace is a git repository, the assistant asks once whether
to share the study through git, and `pw-output/` follows the same answer.

## Where it works

- Cowork in the Claude desktop app.
- Claude Code: terminal, VS Code, JetBrains and the Code tab of the desktop
  app.
- Codex CLI and the ChatGPT desktop app. The Codex IDE extension does not
  load plugins.
- GitHub Copilot CLI and VS Code.

Chat on claude.ai in a browser is not tested yet. Use the desktop app for now.

## Coming from an older version

You have nothing to do: the assistant brings an older study up to date the
first time you use it.

- A study made by version 0.7.0 or earlier is kept in YAML files,
  `pw-kb.yaml` and `labels.yaml`. The assistant turns them into JSON once
  and keeps the YAML files in `backups/`. That one time, the script needs
  PyYAML (`python3 -m pip install pyyaml==6.0.3`).
- A study made by version 0.2.0 or earlier sits in a `KB/` folder; the
  assistant moves it into `.pw-kb/` and `pw-output/` the same way.
- Version 0.11 and earlier kept the map and the sheets in `.pw-kb/`; the
  next run moves them to `pw-output/`.
- Before version 0.5.0 the pw-discovery skill was called distill-kb.
- From version 0.17.0 a person can have later conversations, and the plan can
  hold a follow-up. Once a study holds a later conversation or a planned
  follow-up, everyone who works on it needs 0.17.0: older versions refuse the
  study and ask to update.

What changed in each version is in the [changelog](CHANGELOG.md).

## Learn more

On [productweaver.com](https://www.productweaver.com): an
[example study](https://www.productweaver.com/example), a guide to
[analyzing customer interviews with AI](https://www.productweaver.com/customer-interview-analysis)
and [jobs to be done, explained](https://www.productweaver.com/jobs-to-be-done).

## Support

Report bugs and ask questions in this repository's
[Issues](https://github.com/productweaver/productweaver-plugin/issues). To
report a security problem, follow [SECURITY.md](https://github.com/productweaver/productweaver-plugin/blob/main/SECURITY.md).

## License

Apache License 2.0, see [LICENSE](LICENSE). The plugin ships no third-party
code, see [NOTICE](NOTICE).
