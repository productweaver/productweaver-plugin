# A study in another language than English

Read this when a new study's transcripts are not all in English, and when `context` prints a `LABELS:` line. A study in English needs none of it. Below, `kb_tool` stands for the full command line that `files-and-commands.md` gives under "Running the script".

## How to ask

Ask only when the study starts, right after `init`, and never again. Use your host's tool for a question with choices the user clicks: `AskUserQuestion` in Claude Code and Cowork, `ask_user` in Gemini CLI and GitHub Copilot CLI, `request_user_input` in Codex's Plan mode. Other hosts, such as VS Code, Cursor and claude.ai, have one under their own name.

- Ask in the language the user writes to you in.
- Name each choice in its own language: "Italiano, come le interviste" and "English". When the interviews are in several languages, give one choice per language with its number of interviews, most first, then English: at most three choices in all, because some hosts allow no more.
- Put first, marked as recommended, the choice that matches the language the user writes to you in. If none does, the interviews' language.
- Do not add an "Other" choice. The host adds a free-text one, where the user can name another language.
- Ask the git question and the usage question of `files-and-commands.md`, part 1, in the same call, so the user is interrupted once.
- With no such tool, ask one short question in plain text that names both choices, such as "Scrivo lo studio in italiano, come le interviste, o in inglese?", and wait for the answer.
- When nobody can answer, as in a scripted run, use the language the request is written in, or English when that is unclear, and say so in your report.

## Write the map's text in the study's language

For English, nothing more. For any other language:

1. `kb_tool labels .pw-kb/pw-kb.json --language <code>`, with a BCP 47 code such as `it`, `es`, `pt-BR` or `zh-Hans`. It sets the language and writes `.pw-kb/patches/<date>-labels-<code>.json`: the text of the map and the review sheet in English, with a `"<key>#note"` entry just above each label that needs a note.
2. Read that file and write it back in the study's language, as its `instructions` say. Write each label yourself, as a whole sentence in the language: never with a script or a word list that swaps words one by one, which leaves half the text in English. Keep every `{name}`, and translate each plural form it lists. There are about 830 labels: tell the user you are writing the map's text in their language, once, and that it takes a few minutes.
3. `kb_tool labels .pw-kb/pw-kb.json --add <that file>`. It refuses a label that lost a `{name}`, holds markup, is empty or still reads as English, and keeps the rest in `.pw-kb/labels.json`. Fix what it refuses and add the file again.

## When `context` prints a `LABELS:` line

The study lacks text for some labels, usually because an update of the skill added them. Run `kb_tool labels .pw-kb/pw-kb.json`, write the file it gives and `--add` it before the next write. Until then those labels show in English, and the rebuild of the map says so.
