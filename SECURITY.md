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

- The `distill-kb` skill runs one local Python script,
  `skills/distill-kb/scripts/kb_tool.py`, which reads the interview files you
  give it and writes the knowledge base, review sheet and discovery map next
  to them.
- The plugin makes no network calls of its own. The only download is the
  Python packages that `uv` fetches the first time the script runs.
- The plugin has no hooks, no MCP servers and no commands that run on their
  own.
