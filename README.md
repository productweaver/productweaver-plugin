# Product Weaver plugin

Product Weaver is a free, open-source plugin for Claude, ChatGPT and Codex, and
GitHub Copilot that turns customer interview transcripts into a
jobs-to-be-done knowledge base, with every quote checked word for word against
its transcript.

More on [productweaver.com](https://www.productweaver.com): the
[install guide](https://www.productweaver.com/plugin), an
[example study](https://www.productweaver.com/example), a guide to
[analyzing customer interviews with AI](https://www.productweaver.com/customer-interview-analysis)
and [jobs to be done, explained](https://www.productweaver.com/jobs-to-be-done).

The first skill, **pw-discovery**, turns customer interview transcripts into an
Outcome-Driven Innovation (ODI) knowledge base: the jobs your customers are
trying to get done, the steps of each job, and the outcomes they measure
success by, each backed by verbatim quotes. Every quote is checked against its
transcript before it goes in, so the knowledge base never holds paraphrased
evidence. It grows with every batch of interviews. When the people you
interviewed do different jobs, it finds each core job and keeps track of who
does which. It also collects what people use today to get each step done, and
what they stopped using: their current solutions, grouped by the work they
compete for. When you are ready for ideas, it groups the outcomes into a few
value themes, such as "Help me order what the week will really need", so a
team can sort ideas into a handful of needs. And it plans your next round of
interviews: who to talk to and what to ask, to back up what still rests on
too few people.

The second skill, **pw-start**, gets you going: it plans your first
interviews, or turns the ones you have into a discovery map, and says what to
do next.

Before version 0.5.0 this skill was called distill-kb.

## Install

**Claude desktop app (Cowork)**, no terminal needed:

1. Open **Customize**, then **Plugins**.
2. Choose **Add marketplace** and enter `productweaver/productweaver-plugin`.
3. Install `productweaver` from the list.
4. Start a task in **Cowork**, choose the folder with your transcripts, and
   ask in plain words.

If you use claude.ai in a browser, run the plugin in the desktop app: it works
with the files on your computer. You can add it on the web with the same steps
at [claude.ai/customize/plugins](https://claude.ai/customize/plugins); Claude
saves it to your account, so it is ready in Cowork.

**Claude Code** (version 2.1.292 or later), in a terminal:

```sh
claude plugin install productweaver --marketplace productweaver/productweaver-plugin
```

Or inside a Claude Code session:

```
/plugin install productweaver --marketplace productweaver/productweaver-plugin
```

**ChatGPT and Codex** (Codex CLI and the ChatGPT desktop app):

```sh
codex plugin marketplace add productweaver/productweaver-plugin
```

Then open `/plugins` in Codex and install `productweaver`.

**GitHub Copilot CLI:**

```sh
copilot plugin marketplace add productweaver/productweaver-plugin
copilot plugin install productweaver@productweaver-plugin
```

### Requirements

- Python 3.9 or newer. Nothing else to install: the skill's script uses only
  Python's standard library, so it also runs where packages cannot be
  downloaded.
- Transcripts as `.md`, `.txt`, `.docx` or `.pdf` files. To read a `.pdf`
  directly, the script needs pypdf (`python3 -m pip install pypdf==6.21.4`).
  Without it, the assistant first saves the PDF's text, word for word, as a
  `.txt` file in the study.

## Use it

New here? Say: **Help me get started with Product Weaver.** (In Claude Code
you can also type `/pw-start`.) If you have interview transcripts, the
assistant turns them into a discovery map. If you have none yet, it asks
three questions and writes a guide for your first interviews: who to talk to
and what to ask. When you come back to a study, ask "What should I do next?"
and it names one next step.

Once you know your way around, ask in plain words, for example:

- "Process this week's discovery interviews in the Interviews folder."
- "Start an ODI knowledge base for the Acme study from these transcripts."
- "Add these three calls to the knowledge base and show me what changed."
- "Do these interviews show more than one core job?"
- "What do people use today to find suppliers, and what did they give up?"

The assistant reads the transcripts, proposes what to add, and merges it into
the knowledge base. It then writes a review sheet with decisions waiting for
you and a discovery map you can open in any browser.

When the interviews are not in English, the assistant asks once, when the
study starts, whether to write the study in the interviews' language or in
English. Everything you read follows your answer: the findings, the review
sheet and the map's own buttons and help. Quotes always stay in the words
people used.

## What the plugin runs

One local Python script, `kb_tool.py`, inside the skill (its `migrate` command
also loads `kb_migrate.py`, next to it). It reads the files
you point it to and writes the files listed below. The plugin has no hooks, no
MCP servers and no background processes.

## What it sends and where

Nothing. The plugin makes no network calls and downloads nothing. Your
assistant itself works as it always does with the files it reads.

## Files it writes

All files go into one folder, `.pw-kb/`, at the root of your workspace. One
workspace holds one study.

- `pw-kb.json`, the knowledge base;
- `transcripts/`, a copy of each transcript the knowledge base quotes. Your own
  files are never changed;
- `review.md`, the review sheet;
- `interview-guide.md`, the plan for your next interviews, ready to take into
  the calls: who to find, what to ask and what to listen for;
- `discovery-map.html`, the interactive map, which works offline. The first
  time it is made, it opens in your browser;
- `labels.json`, only for a study in another language than English: the map's
  and the review sheet's own text in that language;
- `patches/`, one file per batch, the audit trail of what each batch added;
- `backups/`, copies of the knowledge base before each merge (the newest 20);
- `logs/kb_tool.jsonl`, one line per run, for debugging. It holds no quotes,
  names or file names.

The knowledge base, transcripts, review sheet, map and patches contain
interviewees' names and words. They stay on your machine unless you share
them. If your workspace is a git repository, the assistant asks once whether
to share the study through git.

A study made by version 0.7.0 or earlier is kept in YAML files, `pw-kb.yaml`
and `labels.yaml`. The assistant turns them into JSON once, the first time you
use the study, and keeps the YAML files in `backups/`. That one time, the
script needs PyYAML (`python3 -m pip install pyyaml==6.0.3`). A study made by
version 0.2.0 or earlier sits in a `KB/` folder; the assistant moves it into
`.pw-kb/` the same way.

## Where it works

- Cowork in the Claude desktop app.
- Claude Code: terminal, VS Code, JetBrains and the Code tab of the desktop
  app.
- Codex CLI and the ChatGPT desktop app. The Codex IDE extension does not
  load plugins.
- GitHub Copilot CLI and VS Code.

Chat on claude.ai in a browser is not tested yet. Use the desktop app for now.

## Support

Report bugs and ask questions in this repository's
[Issues](https://github.com/productweaver/productweaver-plugin/issues). To
report a security problem, follow [SECURITY.md](https://github.com/productweaver/productweaver-plugin/blob/main/SECURITY.md).

## License

Apache License 2.0, see [LICENSE](LICENSE). The plugin ships no third-party
code, see [NOTICE](NOTICE).
