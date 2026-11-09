# Product Weaver plugin

Product management skills for the AI assistant you already use, from
[Product Weaver](https://www.productweaver.com).

The first skill, **distill-kb**, turns customer interview transcripts into an
Outcome-Driven Innovation (ODI) knowledge base: the jobs your customers are
trying to get done, the steps of each job, and the outcomes they measure
success by, each backed by verbatim quotes. Every quote is checked against its
transcript before it goes in, so the knowledge base never holds paraphrased
evidence. It grows with every batch of interviews.

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
  yourself: `python3 -m pip install pyyaml`.
- Transcripts as `.md`, `.txt`, `.docx` or `.pdf` files.

## Use it

Ask your assistant in plain words, for example:

- "Process this week's discovery interviews in the Interviews folder."
- "Start an ODI knowledge base for the Acme study from these transcripts."
- "Add these three calls to the knowledge base and show me what changed."

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

All files stay next to your knowledge base, usually in a `KB/` folder:

- `odi-kb.yaml`, the knowledge base;
- `review.md`, the review sheet;
- `discovery-map.html`, the interactive map, which works offline;
- `patches/`, one file per batch, the audit trail of what each batch added;
- `backups/`, copies of the knowledge base before each merge (the newest 20);
- `logs/kb_tool.jsonl`, one line per run, for debugging. It holds no quotes,
  names or file names.

The knowledge base, review sheet, map and patches contain interviewees' names
and words. They stay on your machine unless you share them.

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
