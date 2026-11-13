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

- The `pw-discovery` skill runs one local Python script,
  `skills/pw-discovery/scripts/kb_tool.py` (its `migrate` command also loads
  `kb_migrate.py`, next to it), which reads the interview files you
  give it and writes the knowledge base, review sheet and discovery map next
  to them.
- The plugin makes no network calls and downloads nothing. The script uses
  only Python's standard library.
- The plugin has no hooks, no MCP servers and no commands that run on their
  own.
