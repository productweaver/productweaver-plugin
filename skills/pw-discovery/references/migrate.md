# Bringing an older study up to date

Read this when a command refuses the study with a message to run `migrate`, or when the study is not in `.pw-kb/pw-kb.json` yet. There are three cases. Find yours by where the study is, run its command once, then go on with the work you were doing.

Every command below runs from the root of the workspace, the user's own folder. Write the script's full path, as here, in every command. `migrate` keeps a backup of what it replaces in `.pw-kb/backups/`.

| Where the study is | Case |
|---|---|
| `.pw-kb/pw-kb.json`, and the message names a schema version | 1. An older schema |
| `.pw-kb/pw-kb.yaml` | 2. A study written in YAML |
| A `KB/` folder, with the transcripts in `Interviews/` next to it | 3. A study in a `KB/` folder |

## 1. An older schema

```
python3 <skill folder>/scripts/kb_tool.py migrate .pw-kb/pw-kb.json
```

When it says it migrated from schema version 1, tell the user: the core job is now core job A, and every step and outcome ID gained the letter, so `6.3` is now `A.6.3`. Cases 2 and 3 upgrade the schema in the same step, so say the same there when their output names schema version 1.

## 2. A study written in YAML

`.pw-kb/pw-kb.yaml` was made by plugin 0.7.0 or earlier. Every command refuses it with `migrate_needed`.

```
python3 <skill folder>/scripts/kb_tool.py migrate .pw-kb/pw-kb.yaml
```

It writes `.pw-kb/pw-kb.json` and, for a study in another language than English, `.pw-kb/labels.json`, and puts the YAML files in `.pw-kb/backups/`. The YAML files already in `.pw-kb/patches/` stay as history; write every new file in JSON.

Tell the user the study is now in `pw-kb.json`, and that everyone who works on it needs this version of the plugin.

## 3. A study in a `KB/` folder

A study made by an even earlier version sits in a `KB/` folder, with its transcripts in `Interviews/` next to it.

```
python3 <skill folder>/scripts/kb_tool.py migrate <study>/KB/<file>.yaml --to .pw-kb/pw-kb.json --transcripts <study>/Interviews
```

It copies the transcripts, moves the KB, patches, backups and logs into `.pw-kb/` and the review sheet, guide and map into `pw-output/`, writes the KB as `pw-kb.json` and keeps the old file as a backup. If a transcript is missing, or `.pw-kb/` already holds a study, it moves nothing and says why.

Then tell the user where the study is now and what was left in the old folder. When the output has a `git:` line, the workspace is a git repository: ask whether to share the study through git. `.pw-kb/` holds interviewees' names, their words and their transcripts. If the user does not want to share it, write `.pw-kb/.gitignore` containing the single line `*`. If they do, write it with the two lines `logs/` and `usage/`.

## When PyYAML is missing

Cases 2 and 3 read YAML this one time, which needs the PyYAML package. When it is missing, `migrate` stops with `reader_missing` and changes nothing. Install it with `python3 -m pip install pyyaml==6.0.3` (if pip refuses, in a virtual environment) and run `migrate` again, or ask the user to run it on a computer that has PyYAML.
