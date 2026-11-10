# Product Weaver plugin

Product management skills for the AI assistant you already use, from
[Product Weaver](https://www.productweaver.com).

The first skill, **distill-kb**, turns customer interview transcripts into an
Outcome-Driven Innovation (ODI) knowledge base: the jobs your customers are
trying to get done, the steps of each job, and the outcomes they measure
success by, each backed by verbatim quotes. Every quote is checked against its
transcript before it goes in, so the knowledge base never holds paraphrased
evidence. It grows with every batch of interviews. When the people you
interviewed do different jobs, it finds each core job and keeps track of who
does which. It also collects what people use today to get each step done, and
what they stopped using: their current solutions, grouped by the work they
compete for.

## Install

**Claude Code** (version 2.1.292 or later), in a terminal:

```sh
claude plugin install productweaver --marketplace productweaver/productweaver-plugin
```

Or inside a Claude Code session:

```
/plugin install productweaver --marketplace productweaver/productweaver-plugin
```

**Codex** (CLI and ChatGPT desktop app):

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

- Claude Code: terminal, VS Code, JetBrains and the desktop app.
- Codex CLI and the ChatGPT desktop app. The Codex IDE extension does not
  load plugins.
- GitHub Copilot CLI and VS Code.

Claude.ai and Claude Cowork will follow once the plugin is listed in
Anthropic's plugin directory.

## Support

Report bugs and ask questions in this repository's
[Issues](https://github.com/productweaver/productweaver-plugin/issues). To
report a security problem, follow [SECURITY.md](https://github.com/productweaver/productweaver-plugin/blob/main/SECURITY.md).

## License

Apache License 2.0, see [LICENSE](LICENSE). The discovery map includes js-yaml
under the MIT license, see [NOTICE](NOTICE).
