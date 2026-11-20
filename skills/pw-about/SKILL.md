---
name: pw-about
description: Show which version of Product Weaver is installed and what it runs on - the plugin version and the folder it is loaded from, the assistant and model, the operating system and Python, the study in this folder, and whether usage statistics are on. Use when the user asks which version of Product Weaver or of the plugin they have, whether it is up to date, says "pw-about" or "about Product Weaver", or wants details to put in a bug report. Not for how to start or what the plugin can do (that is pw-start). From Product Weaver (productweaver.com).
---

# pw-about: which Product Weaver, on what

*From [Product Weaver](https://www.productweaver.com).*

The user wants facts, fast: which version they have, where it runs from, and what it runs on. Give them one short block. Ask nothing first.

## 1. Run the script

From the root of the workspace, run:

```
python3 <plugin folder>/skills/pw-discovery/scripts/pw_about.py --assistant <name> --model <id>
```

- `<plugin folder>` is the folder that holds `skills/`: two levels above this file. Write the full path in the command. Never put it in a shell variable and never `cd` into the plugin folder.
- `<name>` is your host: `claude-code`, `claude-cowork`, `claude-ai`, `chatgpt`, `codex`, `copilot-cli`, `vscode`, `cursor`, `gemini-cli`, `antigravity`, or `other`. `<id>` is your model ID, when you know it. Leave out `--model` when you do not.
- Add `--check` only when the user asks whether they are up to date, or asks to check for an update. It is the only option that goes online: one request to productweaver.com, with nothing about the user in it. Without it, the script makes no network call.
- Add `--report` when the user mentions a problem, a bug, an error or a report. It adds a block to paste into a bug report.
- On Windows, if `python3` is missing, use `py -3`.

The script only reads. It never changes the study and never records usage statistics. Run nothing else.

## 2. Show the result

- Put the summary in a code block, exactly as printed. If the user writes in another language, translate the labels (the words on the left) and the plain sentences. Keep versions, paths, names, commands and flags as they are.
- With `--report`, then show the block under "For a bug report:" exactly as printed, in English. Say: "Paste this into your report: it hides your home folder and login name, and holds no study content. Look at the path before you post." Bug reports go to https://github.com/productweaver/productweaver-plugin/issues.
- Without `--report`, end with one line: "Say 'pw-about for a bug report' to get a block to paste."

## 3. When a line starts with `!`

Each `!` line is a flag. For each flag, add one line after the block: what it means, and the one thing to do.

| Flag | Say |
|---|---|
| `versions-differ` | Parts of the plugin come from different versions. Update or reinstall the plugin. |
| `install-damaged` | Files of the plugin are missing. Reinstall it. |
| `python-too-old` | The plugin needs Python 3.9 or newer. Install it, then run pw-about again. |
| `study-needs-migrate` | The study in this folder was made by an older version. Ask pw-discovery to update the study. |
| `study-newer-than-plugin` | A newer version of the plugin wrote this study. Update the plugin. |
| `study-unreadable` | The study file cannot be read. Ask pw-discovery to open the study: it says what is wrong. |
| `update-available` | The summary already says how to update. Add nothing. |
| `check-failed` | The update check could not reach productweaver.com. Try again later, or see https://www.productweaver.com/plugin. |

## 4. When the script does not run

This covers three cases: your host cannot run commands at all, the command fails (for example, Python is missing), or the script prints "could not finish". Do not retry with other commands and do not guess the facts.

Read `<plugin folder>/plugin.json` and show the same block with what you know: the version, your assistant and model, and `Scripts: cannot run here` in place of the System line. Say in one line that the study and usage lines need the script to run. If the command failed, add the error it gave.
