# Changelog

Changes to the productweaver plugin, newest first. Versions follow semantic
versioning. Releases after 0.8.0 group their changes under What's new, What's
improved and What's fixed.

## 0.13.2 — 2026-11-15

### What's improved

- **A clearer first paragraph in the README.** It now says in plain words
  that Product Weaver is a plugin for AI assistants such as Claude,
  ChatGPT/Codex and Copilot, and that it builds one knowledge base from your
  interviews that grows with every batch. Nothing in the plugin's behaviour
  changed.

## 0.13.1 — 2026-11-15

### What's improved

- **A README that shows the result first.** The plugin's front page now opens
  with a picture of the discovery map and what you get, then a 10-minute way
  to try it with 6 sample interviews, so you can see it work before you use
  your own. Install steps come next, one section per assistant, and the
  steps for the Claude desktop app now follow its menus one by one. Under
  "Can you trust it?" you find what runs on your computer and what is sent.
  A short list of fixes for common problems follows. Nothing in the plugin's
  behaviour changed.

## 0.13.0 — 2026-11-15

### What's new

- **Confirm what your study is about with one click, in the chat.** After
  your first interviews, the assistant shows what these people are trying to
  get done, with three of its steps, and asks: "Is that right?" Choose
  "Yes, that's it", or say what to change, and the map updates at once. You
  no longer have to find a code in the map and type "approve P1". Other
  decisions are asked the same way, at most three at a time.
- **With no interviews yet, see where your calls lead.** Next to the guide
  for your first interviews, pw-start now links to the example study, so you
  can see the map you will have after your calls.

### What's improved

- **Findings you understand at first reading, and next steps you can start
  this week.** The assistant now writes the Overview, the value themes and
  the interview guide for people who read in a second language: short
  sentences that start with the people, common words, no idioms, digits
  for numbers. The main finding says what the problem costs these people.
  Each next step starts with a verb and names how many people, of which
  kind. A test says what result tells you to go on. Interview questions
  are short enough to say aloud, and each "listen for" line says what to
  write down and what it shows.
- **An interview guide a first-time interviewer can follow.** The guide now
  starts with five short steps, "How to use this guide", from finding the
  people to giving the transcript to your assistant. Under each kind of
  person it lists what to check before you book the call, and what the
  study learns from the call, in plain words with no codes. It ends with
  "More help for your calls": a message to ask for a call, how to get a
  transcript, the words to open and end the call, what to ask when an
  answer is short, and what to say if they ask what you are building. If your study
  is in another language, the assistant writes these new lines in your
  language the next time it updates the map.
- **The map opens on what you learned and what to do now.** Under the main
  finding, the Overview now shows "Decisions for you": each one as a plain
  question, why it is asked, how many people back it, and two replies
  written out in full, such as "In my Product Weaver study, the goal is
  right: …", each with a Copy button, so you see what you will say. No
  codes to look up. The review sheet lists the same replies under each
  decision. Next interviews and the
  Progress tab list the same decisions with the same words. "What to do
  next" is open from the start, and the step to start with is marked.
- **One name and one verb.** The chat, the map and the review sheet all say
  "Decisions for you", and they ask you to confirm. The line under the
  map's title, "This goal waits for you to confirm it", takes you to the
  decision.
- **A quieter map.** "Open a study file" moved from the top of the map to
  How it was built; dropping a study file on the map still works. In the
  details panel, the method's own words, such as the formal statement, sit
  behind a small "Method details" toggle, after the plain words.
- In a study that is not in English, the assistant writes the 13 new labels
  of the map and the review sheet in your language the next time it runs.
  Until then they show in English.

### What's fixed

- **No crash when the output is cut short.** When the assistant read only
  the first lines of a long `kb_tool` output, for example with `| head`,
  the tool showed an error and logged a crash. Now it stops quietly and
  logs `output_closed`.
- **Confirming the goal no longer marks your findings out of date.** After
  a click on "Yes, that's it", the map said the findings were written
  before the latest conversations. Confirming changes nothing the overview
  says, so it now stays as it was.

## 0.12.0 — 2026-11-14

### What's improved

- **Your map, review sheet and interview guide are in a folder you can
  see.** They now go to `pw-output/`, next to the study's `.pw-kb/` folder,
  which Finder and most file dialogs hide because its name starts with a
  dot. Open `pw-output/discovery-map.html` with a double-click. The end of
  the map's Overview says which folder it is saved in.
- **One click in the chat opens the map.** Each run ends with one link, or
  a file card where your app shows one, that opens the map. The interview
  guide and the decisions waiting are in the map's Next interviews tab,
  where you can print or copy the guide. `review.md` and
  `interview-guide.md` stay in `pw-output/` as text copies.
- **The map keeps your place.** Reload it after an update and it stays on
  the view you were reading.
- **Your study moves over by itself.** The next run removes the old copies
  from `.pw-kb/` and says once that the files moved. `pw-output/` follows
  your git choice: kept out of git when the study is, shared when it is.
  Everyone who works on a shared study should update the plugin, so the
  files are not written back into `.pw-kb/`.

## 0.11.4 — 2026-11-14

### What's fixed

- **In Cowork, a short drop of the link to your computer no longer stops
  the study.** A Cowork task runs in the cloud and reaches your folder
  through the Claude desktop app, over a link that sometimes drops for a
  few seconds. The assistant used to stop at the first failed call and say
  it could not read your interviews, until you asked it to retry. Now it
  waits and tries again by itself, up to three times. If the link stays
  down, it says so in one or two lines, asks you to check that the app is
  open and the computer awake, and goes on from where it stopped when you
  say "Try again". It also fetches your files once and saves them back
  once, so the run depends less on the link, and it never says the study
  is saved when saving failed.

## 0.11.3 — 2026-11-14

### What's fixed

- **In Cowork, the study is saved in your folder.** With a folder connected
  to a Cowork task or to its project, the map, the review sheet and the
  study now go into that folder's `.pw-kb/`. Before, the assistant could
  build the study in Cowork's temporary folder and show the map and the
  review sheet in the chat. A later task in the same project now finds the
  study there and adds to it. The study is handed back in the chat only
  when the interviews were uploaded to the chat, as on claude.ai or
  ChatGPT.

## 0.11.2 — 2026-11-13

### What's improved

- **Claude Desktop is named correctly in usage statistics.** The skill now
  says which name Claude Desktop uses: `claude-cowork` in a Cowork task,
  `claude-code` in its Code tab and `claude-ai` in a chat. An assistant in a
  Cowork task had passed `claude-ai`.
- **The usage README says how to let Claude Desktop send.** A Cowork task
  reaches www.productweaver.com only after you allow it under Settings,
  Capabilities, Additional allowed domains. Until then the events wait in
  the study folder and leave from the next session where the network is
  open.

### What's fixed

- **The usage README now says it also reads git's index.** To tell whether
  git tracks the run log, the plugin reads `.pw-kb/.gitignore` and git's
  index, looking only for the run log's path. The README had said it reads
  only the run log and two things in `pw-kb.json`.

## 0.11.1 — 2026-11-13

### What's fixed

- **No more crash where an old jsonschema is installed.** Where Python had
  the jsonschema package older than 4.0 (one Claude Desktop sandbox had
  3.2), merging interviews, checking the study and other commands stopped
  with an `AttributeError`. The tool now uses its own built-in check there,
  as it already did where jsonschema is missing. `kb_tool` 0.12.1; the KB
  schema stays 3.

## 0.11.0 — 2026-11-13

### What's new

- **Usage statistics, only if you say yes.** The first time you work on a
  study, the assistant asks once whether to share usage statistics with
  Product Weaver. Each person who gets the study through git answers for
  themselves; the choice stays with the folder, so delete `.pw-kb/usage/`
  before you hand a study over. Without a yes, nothing is recorded or sent.
  - **What is sent:** small events that show which parts of the plugin work and
    which do not: which steps ran, how long they took, counts, error codes and
    versions. Each event carries a random study number, made when you say yes.
    Never your interviews, names, quotes, prompts or file names.
  - **Where to see it:** `.pw-kb/usage/sent.jsonl` holds every event exactly as
    it left.
  - **How to stop:** say "stop sharing" to your assistant, or set
    `KB_TOOL_USAGE=0` or `DO_NOT_TRACK=1` in your environment.

  The plugin sends nothing unless you turn on usage statistics for a study. The
  new files are in `.pw-kb/usage/`. The details are on
  https://www.productweaver.com/privacy.

## 0.10.0 — 2026-11-13

### What's new

- **Get started.** A new skill, pw-start. Say "Help me get started with
  Product Weaver" (in Claude Code, `/pw-start`), and it looks at your folder
  and gets you to one useful result:
  - **with interview transcripts:** your discovery map, built and opened;
  - **with none yet:** three questions, then a guide for your first round of
    interviews, `.pw-kb/interview-guide.md`. It says who to talk to, how to
    ask for a talk, how to record it, what to ask and what to listen for;
  - **with a study already:** ask "What should I do next?" and it names one
    step, with the words to say.

  In Codex it is the plugin's setup skill, with three starter prompts.

### What's improved

- **Every report ends with one next step**, a "Next:" line with the words to
  say.
- **Your first study builds on your plan.** When you planned your first
  interviews with pw-start, the first batch reads that guide. Kinds of people
  you planned but have not talked to yet show up as gaps.
- **Chats that forget their files keep your study.** In a chat where you
  attach the transcripts and the files are gone afterwards, such as ChatGPT,
  the assistant hands back the whole study folder with the map. Upload it
  with your next interviews and the study keeps growing.

## 0.9.0 — 2026-11-13

### What's new

- **Next interviews.** The discovery map has a new view that plans your next
  round of conversations. It shows:
  - how sure you can be now, and how many more conversations reach the
    next level;
  - who to talk to next, as one card per kind of person, each with the
    thin spots it backs up and the questions to ask;
  - a grid of the kinds of people you have heard from, with the missing
    ones marked;
  - every gap that still rests on few voices, with the ones under the main
    finding first.

  Your assistant writes the plan with the overview; the map counts the gaps
  itself. The view replaces the "Ask next" tab. Proposals and people linked
  to no main goal move to the Progress tab, under "Waiting for the team".
- **Interview guide.** `review` also writes `.pw-kb/interview-guide.md`: who
  to find, what to ask and what to listen for, ready to take into the calls.
  The map can copy it, or print the plan.
- **How the last round went.** After a new batch, the plan says how many of
  the last round's gaps it closed.

### What's improved

- **The Progress tab starts with how sure you can be.** A card at the top
  shows the level, how many more conversations reach the next one, and a
  button that opens the interview guide: the fewest conversations that would
  make you surer, and what to ask. It is amber until the study shows a clear
  pattern.
- **review.md's "Next interviews"** replaces "Ask about these next": where
  the study stands, the plan, and every thin spot by group. It is always
  there, even when no step is thin.
- **The chat report** gives the next interviews in a few lines: who to talk
  to and the top questions.
- **`context`** lists the open gaps of each main goal, ranked, with who backs
  each one, how far the next level is, and each person's tags, so your
  assistant plans the next round from them.
- **A step's count of people** now includes those quoted on its measures of
  success, as the map always counted. The review sheet and `context` show the
  same number as the map.
- **`kb_tool.py` has room to grow.** The code of `migrate` moved into
  `scripts/kb_migrate.py`, which `kb_tool.py` loads only for that command.
  `kb_tool` 0.12.0; the KB schema stays 3.

### What's fixed

- **The Progress chart no longer covers the text under it.** In the map's
  Progress tab, the "Measures of success heard so far" chart drew over its
  explanation on most screens.
- **Map header lines up.** In the first line of the discovery map, "Product
  Weaver" and "Customer discovery map" now sit on one baseline. The brand
  name was about 3 pixels higher.

## 0.8.0 — 2026-11-12

- **Runs with Python alone.** The skill's script now uses only Python's
  standard library: no uv, no PyYAML, nothing to download. It works in
  assistants whose sandbox cannot reach the internet, such as ChatGPT Work,
  where the plugin failed because PyYAML could not be installed.
- **The study's files are now JSON.** The knowledge base is
  `.pw-kb/pw-kb.json`, the study's own text for the map and the review sheet
  is `.pw-kb/labels.json`, and the batches, value themes and overview the
  assistant writes are JSON files too.
- **What you do about a study made with 0.7.0 or earlier:** nothing by hand.
  The first time you use it, the assistant runs `kb_tool migrate` once. That
  one time needs PyYAML, as before; the assistant tells you if it is missing.
  The YAML files are kept in `.pw-kb/backups/`, and old batch files in
  `patches/` stay as they are. If people share a study through git, update
  the plugin for everyone at the same time: an older version cannot read the
  JSON files.
- `.docx` transcripts no longer need python-docx; the text is read exactly as
  before, so quotes and checks are unchanged. `.pdf` transcripts still use
  pypdf when it is installed. Without it, the assistant saves the PDF's text,
  word for word, as a `.txt` file in `.pw-kb/transcripts/` and quotes that.
- Each discovery map is about 110 KB smaller: it no longer carries a YAML
  reader. Its "Open file" button opens `pw-kb.json`, and says what to do when
  given a YAML file from an earlier version. A study in another language
  shows three of the map's messages about opening a file in English until the
  assistant translates them again.
- `kb_tool` 0.11.0, KB schema 3. A JSON file that will not load now gets an
  error with the line, the column and the line itself, so the assistant can
  fix it. If you copied the tool into `.pw-kb/tools/`, copy the new files and
  delete `kb_tool.py.lock` and `js-yaml.js` there.

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
