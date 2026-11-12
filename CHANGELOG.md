# Changelog

Changes to the productweaver plugin, newest first. Versions follow semantic
versioning.

## 0.7.0 — 2026-11-12

- **A study can be in the interviews' language.** When a new study starts
  and the interviews are not in English, the assistant asks once, with your
  assistant's own question buttons, whether to write the study in the
  interviews' language or in English. The choices are named in their own
  language, for example "Italiano, come le interviste" and "English", and the
  question comes together with the git question, so you are asked once. Your
  answer is kept in the study (`meta.language`), and later batches follow it.
- **Everything you read follows that language.** The statements, the
  overview and the value themes are written in it, and so are the map's own
  buttons, headings and help, and the review sheet. The assistant translates
  the map's and the review sheet's text once, at the start of the study, and
  keeps it in `.pw-kb/labels.yaml`. Quotes stay in the words people used.
  Studies made before this version stay in English.
- The writing checks follow the language too: about a fifth more words in
  most languages, letters instead of words in Chinese, Japanese and Thai, and
  the English openings "Minimize…" and "Help me…" are checked in English
  studies only. A study can set its own openings in `meta.style`.
- The review sheet now writes "1 core job" and "1 interview", not "1 core
  jobs".
- `kb_tool` 0.10.0: `init --language`, and a new `labels` command that sets a
  new study's language, writes the text still to translate, and checks and
  keeps the translation (`--add`). The map's and the review sheet's English
  text ships as `assets/labels-en.js`; if you copied the tool into
  `.pw-kb/tools/`, copy it with the template.

## 0.6.0 — 2026-11-12

- **The Overview now starts with who the study is about.** A card at the top
  shows an icon, a short name such as "Small-firm bookkeeper", one sentence
  about them, the people you talked to, and who else appears in the story but
  is not its focus (for example "their clients"). The same name stays in view
  on the left while you scroll. The assistant writes it with the overview and
  picks the icon from 21 built in ones. An overview written before this
  version shows the core job's executor instead, and the assistant rewrites it
  on its next run.
- **Plainer words in the Overview.** The map's own labels are easier to read
  on first try: "The main finding so far", "What goes wrong for them today?",
  "What should you build for first?", "6 people" instead of "6 use one", and
  "the last 2 added no new needs" instead of "brought 0 needs nobody had
  named before". A gap that names a tool no longer reads "Hurts today: Client
  portal".
- **The map says when it was made, and by which version.** A small note at
  the end of the Overview reads, for example, "This file was made by the
  Product Weaver plugin 0.6.0 on Nov 12, 2026, 9:30 AM PST". The version
  comes from the plugin's own manifest.
- **Links to productweaver.com carry fixed tags.** The links in the map and
  in the review sheet tell the site which file and which link a visit came
  from (`utm_source=productweaver-plugin`, `utm_medium=discovery-map` or
  `review-sheet`, `utm_content` for the place). They never hold anything from
  your study. A map shown on productweaver.com itself links without them.
- The YAML reader the map uses (js-yaml) now ships as its own file,
  `assets/js-yaml.js`, so the map template stays under the plugin
  directory's size limit. `map` puts it inside each map as before: a map is
  still one file that works offline, and maps look the same. If you copied
  the tool into `.pw-kb/tools/`, copy `js-yaml.js` with the template.
- `kb_tool` 0.9.0. `overview` needs the new `executor` part, refuses words of
  the method such as "core job" or "desired outcome", and warns on vague words
  such as "pain point" or "workflow", each with a plain word to use. New
  writing rules ("The first-read test") in `pw-rules.md`.
- The plugin's home and documentation links now point to
  [productweaver.com/plugin](https://www.productweaver.com/plugin), with the
  install guide, an example study and a guide to analyzing customer
  interviews. New keywords (customer discovery, user research, interview
  analysis, JTBD, voice of the customer) help people find the plugin in
  directories.
- The README opens with one sentence that says what the plugin does.

## 0.5.1 — 2026-11-11

- **Calmer navigation in the discovery map.** Scrolling with a trackpad or a
  mouse wheel now moves the map. To zoom, pinch, or hold Ctrl or ⌘ while you
  scroll. The zoom follows how far you pinch, so one swipe no longer jumps
  from the smallest view to the biggest. Two-finger pinch works on phones and
  tablets, and the map can no longer be scrolled out of sight.
- **Each kind of box on the map has its own look.** A step is a white card
  with its number, a measure of success is a green box with a target, and a
  solution is a rounded pill with an icon for its kind. Under an open step, a
  caption names each group: "Measures of success" and "What they use today".
  The legend starts with a key that draws the three kinds. The green bar on
  the left now always means how many people said it.

## 0.5.0 — 2026-11-11

- **The skill is now called pw-discovery** (it was distill-kb). In Claude
  Code, call it with `/productweaver:pw-discovery`; in Copilot CLI, with
  `/pw-discovery`; in Codex, type `$` and pick pw-discovery. Asking in plain
  words works as before. Studies in `.pw-kb/` need no change.

## 0.4.0 — 2026-11-11

- **An Overview view in the discovery map, and the map opens on it.** It tells
  the study as a short story in six steps, for a person who does not know the
  method: who you listened to, what they try to get done, how they do it
  today, where that falls short, what they most want to get better, and where
  a new solution should focus. Each step has a question, a one-sentence answer
  and a link to the view with the detail.
- **What to do next.** On top of the story, a block that opens on a click
  gives three next steps: keep learning, prototype, and go to market. Each has
  a status, such as "Ready to sketch" or "Too early to sell", and the evidence
  it rests on. They are advice from the assistant, not findings.
- The view also shows how sure the findings are, on four levels from "A hunch"
  to "Confirmed by a survey", and the needs the most people raised with what
  they use today at that step. These are counted from the conversations. They
  are not a survey score.
- The assistant now writes the overview at the end of each run, with the new
  `kb_tool overview` command. It refuses a quote or a solution the knowledge
  base does not hold. New interviews mark the overview out of date.
- **Value themes.** Ask the assistant for value themes and it groups a core
  job's desired outcomes into a few needs in the customer's voice, such as
  "Help me order what the week will really need". A theme may gather outcomes
  from several job steps, and an outcome may sit in two themes. Use the themes
  to sort ideas into.
- The new `kb_tool themes` command checks and writes one core job's themes. It
  refuses an outcome or a quote the knowledge base does not hold, keeps each
  theme's ID when you reword it, and prints what changed. Themes follow an
  outcome when it moves or is merged.
- **A Value themes view in the discovery map.** One card per theme shows its
  outcomes, how many people voiced them, what people use today for it and who
  stopped, and quotes for the pain, the struggle and the desire. The counts are
  a signal from interviews, not a survey score.
- New interviews mark the themes out of date and list the new outcomes as "in
  no theme yet". The assistant updates the themes when you ask, and keeps your
  labels and groupings.
- `kb_tool` 0.8.0. `context`, `review.md` and `validate` cover value themes,
  and `context` and `validate` cover the overview.
  The knowledge base schema stays 2.

## 0.3.1 — 2026-11-10

- **The first discovery map opens by itself.** `kb_tool map --open` shows the
  map in your default browser, and the assistant uses it for a study's first
  map and whenever you ask to see the map. Later rebuilds open nothing; reload
  the tab. `map` always prints a `file://` link you can click. On a remote
  machine, or one with no display, it says so and opens nothing. Set
  `KB_TOOL_OPEN=0` to never open a browser.
- `kb_tool` 0.6.0. The run log gains a `browser` field for `map --open`.

## 0.3.0 — 2026-11-10

Everything a study needs now lives in one folder, `.pw-kb/`, at the root of
the workspace.

- **The knowledge base is `.pw-kb/pw-kb.yaml`**, with its patches, backups,
  log, review sheet and discovery map next to it. One workspace holds one
  study. The tool refuses a knowledge base anywhere else.
- Each merge copies the new transcripts into `.pw-kb/transcripts/`. Quotes are
  checked against these copies, so a study keeps working when the original
  files move. Your own transcripts are never changed. `kb_tool validate` no
  longer takes `--transcripts`; `--structure-only` skips the quotes.
- **Existing studies are moved once.** A study made by 0.2.0 or earlier lives in
  `KB/odi-kb.yaml`. The tool refuses it and asks the assistant to run
  `kb_tool migrate`, which copies the transcripts from `Interviews/`, moves the
  knowledge base, patches, backups, logs, review sheet and map into `.pw-kb/`,
  and keeps the old file as a backup. If a transcript is missing, or the
  workspace already holds a study, it moves nothing and says why.
- When `.pw-kb/` sits in a git repository, the assistant asks once whether to
  share the study through git. If not, it adds a `.gitignore` to the folder.
- No file or folder name says "odi" any more: the rules for writing statements
  are `references/pw-rules.md`, and the schema IDs are `pw-kb/v2` and
  `pw-patch/v2`.
- **Current solutions.** The skill now collects what people use today to get
  each step done: products, everyday tools such as spreadsheets, other people
  and their own methods. Each one is linked to the steps it serves, with the
  quotes that show it, and solutions people stopped using are kept with the
  reason they gave. The assistant groups solutions by the work they compete
  for and says why each group belongs together. The team can merge two
  solutions, move one to another group or rename them, through the usual
  decisions.
- The discovery map counts the solutions in use, can show them next to their
  steps, and has a Solutions view: each group with its reason, how often each
  solution was mentioned and by whom, and what people stopped using. The
  review sheet has a section for them too.
- "Ask about these next" in the review sheet and "Ask next" in the map name
  at most 5 steps per core job: the ones fewest people support. After a small
  first batch every step used to be listed.
- On phones, the map's People, Progress and Ask next tabs show again. They
  were squeezed out below 860 pixels.
- The merge refuses a patch where YAML split a value at a comma that was not
  in quotes. Before, the value was cut short without a word, even a quote.
- Clearer rules for the assistant. The report after a first batch is short
  and leaves the details to the review sheet and the map. Core job A is the
  job most people do as their main job, and a first map's steps are numbered
  in stage order. Someone who does parts of two jobs has the one they own
  from start to end as their main job. A task that is one step of a core job
  is evidence on that step, not a related job. An outcome raised at several
  steps goes where the person can prevent the failure. A transcript's header
  line counts as interviewer notes. A quote that names someone who was not
  interviewed is trimmed when it can be, and the user is told when it cannot.
- `kb_tool` 0.5.0. The knowledge base schema stays at version 2: the new
  `current_solutions` section is optional, and studies without it are
  unchanged.

## 0.2.0 — 2026-11-10

A study can now hold more than one core job.

- When the people interviewed do different jobs, for example owner-operators
  who plan loads and fleet managers who keep trucks running, the skill finds
  each core job by abstracting from every interview's own job. Each core job
  gets a letter (A, B…) and its own job map.
- Every interview is linked to the core job its own job rolls up to. A related
  job can link the same person to another core job. People whose job fits none
  are listed with the reason, which moves to history once they are linked.
- After the first batch, each core job comes with a decision to confirm it
  ("approve P1"), saying how many people back it. Before, a first core job
  stayed "proposed" with no way to confirm it.
- New decisions for the team: add a core job, confirm one, move a step to
  another core job, and change which core job an earlier interview is linked
  to.
- The review sheet has a job map and a people section per core job. The
  discovery map has a core job switcher under the title and shows each
  person's jobs.
- **Step and outcome IDs now start with their core job's letter**: step `6`
  is now `A.6` and outcome `6.3` is now `A.6.3`, even in a study with one core
  job, so no ID changes when a second job appears.
- **Existing knowledge bases need one migration.** The assistant runs
  `kb_tool migrate` when the tool asks for it. It keeps a backup, turns the
  core job into core job A and adds the letter to every ID. Patches written
  for 0.1 still merge into a study with one core job. A discovery map made
  with 0.1 cannot be used as a template any more; the skill's own template is
  used instead.

## 0.1.2 — 2026-11-09

Changes for the Anthropic directory review. The plugin works as before.

- The Python packages the skill uses now have exact versions, and a lock file
  ships with the script, so uv installs the same packages on every machine.
- The discovery map now holds the readable build of js-yaml 4.1.0 instead of
  the minified one. The code is the same version, and each map file is about
  75 KB larger.

## 0.1.1 — 2026-11-09

Changes for the Anthropic directory review. The plugin works as before.

- `kb_tool.py` now names each environment variable it reads directly. It
  still makes no network calls, and the variables only tell the local run log
  which assistant ran the tool.
- The run log guide no longer includes a Python one-liner.
- The plugin's home and documentation links now point to this repository.

## 0.1.0 — 2026-11-09

First release.

- The **distill-kb** skill turns customer interview transcripts into an
  Outcome-Driven Innovation knowledge base in one YAML file. Every quote is
  checked against its transcript before a merge, and a merge that fails a
  check changes nothing.
- Each run can write a review sheet and an interactive discovery map that
  works offline.
- Every run adds a line to a local run log, which holds no quotes or names.
- Installs in Claude Code, Codex and GitHub Copilot from the marketplace
  `productweaver-plugin`.
