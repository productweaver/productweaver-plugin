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
team can sort ideas into a handful of needs.

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

- Python 3.9 or newer.
- [uv](https://docs.astral.sh/uv/), which installs the one Python package the
  skill needs (PyYAML) the first time it runs. Without uv, install it once
  yourself: `python3 -m pip install pyyaml==6.0.3`.
- Transcripts as `.md`, `.txt`, `.docx` or `.pdf` files.

## Use it

Ask your assistant in plain words, for example:

- "Process this week's discovery interviews in the Interviews folder."
- "Start an ODI knowledge base for the Acme study from these transcripts."
- "Add these three calls to the knowledge base and show me what changed."
- "Do these interviews show more than one core job?"
- "What do people use today to find suppliers, and what did they give up?"

The assistant reads the transcripts, proposes what to add, and merges it into
the knowledge base. It then writes a review sheet with decisions waiting for
you and a discovery map you can open in any browser.

## What the plugin runs

One local Python script, `kb_tool.py`, inside the skill. It reads the files
you point it to and writes the files listed below. The plugin has no hooks, no
MCP servers and no background processes.

## What it sends and where

Nothing. The plugin makes no network calls of its own. The only download is
PyYAML, which uv fetches from PyPI the first time the script runs. Your
assistant itself works as it always does with the files it reads.

## Files it writes

All files go into one folder, `.pw-kb/`, at the root of your workspace. One
workspace holds one study.

- `pw-kb.yaml`, the knowledge base;
- `transcripts/`, a copy of each transcript the knowledge base quotes. Your own
  files are never changed;
- `review.md`, the review sheet;
- `discovery-map.html`, the interactive map, which works offline. The first
  time it is made, it opens in your browser;
- `patches/`, one file per batch, the audit trail of what each batch added;
- `backups/`, copies of the knowledge base before each merge (the newest 20);
- `logs/kb_tool.jsonl`, one line per run, for debugging. It holds no quotes,
  names or file names.

The knowledge base, transcripts, review sheet, map and patches contain
interviewees' names and words. They stay on your machine unless you share
them. If your workspace is a git repository, the assistant asks once whether
to share the study through git.

A study made by version 0.2.0 or earlier sits in a `KB/` folder. The assistant
moves it into `.pw-kb/` the first time you use it, and keeps a backup.

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

Apache License 2.0, see [LICENSE](LICENSE). The discovery map includes js-yaml
under the MIT license, see [NOTICE](NOTICE).
