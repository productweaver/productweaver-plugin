# Security policy

## Reporting a vulnerability

Please do not report security problems in a public issue.

Report them privately through GitHub instead: open the **Security** tab of
this repository and choose **Report a vulnerability**. Only the maintainers
can see the report. We will confirm that we received it and keep you
informed while we work on a fix.

## Supported versions

Only the latest release receives security fixes. Update with:

```sh
claude plugin update productweaver@productweaver-plugin
```

## What the plugin runs

This helps you judge the impact of a problem:

- The `pw-start` and `pw-discovery` skills run two local Python scripts. The
  first is `skills/pw-discovery/scripts/kb_tool.py` (its `migrate` command also loads
  `kb_migrate.py`, next to it), which reads the interview files you
  give it and writes the knowledge base, review sheet and discovery map next
  to them.
  The second is `skills/pw-discovery/scripts/pw_usage.py`, which keeps the
  user's answer about usage statistics in `.pw-kb/usage/` and, only after a
  yes, sends the events.
- `kb_tool.py` makes no network calls. `pw_usage.py` makes one kind of network
  call, to www.productweaver.com, only after the user has said yes to usage
  statistics for a study. It sends counts, codes and versions, never
  interviews, names, quotes, prompts or file names. The full list of fields is
  in `skills/pw-discovery/references/usage.md`. The plugin downloads
  nothing. Both scripts use only Python's standard library.
- The plugin has no hooks, no MCP servers and no commands that run on their
  own.
