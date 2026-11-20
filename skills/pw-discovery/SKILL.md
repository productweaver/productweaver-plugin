---
name: pw-discovery
description: Turn raw customer interview transcripts into Outcome-Driven Innovation (ODI) knowledge and fold it into a knowledge base, one JSON file, that grows with every batch. Use whenever someone shares new interview transcripts, notes or emails (md, txt, docx, pdf), also from someone already interviewed, and wants jobs-to-be-done extracted, job executors and core jobs identified, job steps or desired outcomes updated, the tools and workarounds people use today collected and grouped, evidence quotes attached, the outcomes grouped into a few value themes to guide ideation, or an existing ODI/JTBD knowledge base updated or started. Also use for "add these interviews to the KB", "create the survey", "estimate the answers", or starting an ODI study for a new client, even if the user doesn't say "ODI" or "JTBD". Also use for answers to its decisions, such as "In my Product Weaver study, the goal is right", and when the user asks to stop sharing usage statistics. From Product Weaver (productweaver.com).
---

# pw-discovery: fold interviews into an ODI knowledge base

*A free skill from [Product Weaver](https://productweaver.com).*

A study is one knowledge base (KB) that grows with every batch of interviews. Each run reads new transcripts, extracts ODI knowledge with verbatim evidence, and gives it to the tool, which folds it into the KB. The tool checks every quote against its transcript and refuses the whole batch if one does not match. That makes the KB safe to build on over many runs: nothing in it is paraphrased evidence or a duplicate.

## Method, contract and binding

This file is the **method**: what to read, what to extract, what to propose and what to tell the user. It gives no command and no file path. `references/files-and-commands.md` is the **binding**. It gives them: how each step below is done with the tool this version ships, where the study's files are, what the tool checks and what each host needs. **Read it once per session, before your first command.** What comes after its heading "Work done on request" matters only when the user asks for that work. Its parts carry the numbers of the steps below, so "part 5" in this file means its part 5.

Two words are used all through. **The context** is what the tool tells you about the study as it is now (step 2); the rules files write it `context`. **A batch** is what you extracted from the new transcripts, given to the tool in one go (step 5).

The **contract** is what the method counts on from the tool, whatever the tool is made of. It gives the context, takes a batch, applies a decision, writes the overview and rebuilds what people read. And it keeps four promises:

- **A write is all or nothing.** The tool runs every check before it writes, so a refused write changes nothing: fix what it names and send the same thing again.
- **Evidence is verbatim.** A quote that is not in its transcript refuses the whole batch.
- **The same batch twice changes nothing.** A transcript that is already in is skipped, so nothing is counted twice.
- **The study as it was before each write is kept.**

The names are part of the contract too: the study's parts, their field names, the proposal types and the IDs are those this file and the rules files use, whatever tool holds the study.

If the tool cannot run at all, stop: tell the user what is missing, extract nothing, and never write the KB or a study in the chat yourself.

## What a run changes, and what it leaves alone

- **Writes (evidence layers):** interviews, job executor, core functional job, related, emotional and social jobs per interview, and each new interview's links to the study's core jobs; new evidence on existing job steps and outcomes; new outcomes; current solutions (what people use today for each step, and what they stopped using), with their groups.
- **Proposes, never applies:** anything that changes the shared structure. That covers a new core job, a new job step, a reworded step, outcome or core job, a merge of two outcomes, a moved outcome or step, a changed link of an earlier interview, a new segment, two solutions that are one, a solution in the wrong group, or a renamed solution or group. These go to `proposed_changes` with status `pending`. The user decides, then the tool applies it.
- **Flags, never rewrites:** derived layers (`survey`, `simulation`, `value_themes`, `overview`, `use_cases`). The tool marks them out of date, with a reason. They are rebuilt on request, not on every run. See "When asked for value themes", "Write the overview" and "When asked for a survey or another derived layer".

The exception is a brand-new KB with no core job yet. Then the run proposes the core job or jobs and their job maps as a `bootstrap`, marked `status: proposed`, so the user can review them. The tool also files one `confirm_core_job` decision per core job, saying how many people back it. Approving it marks the job approved.

## One core job or several

Most studies have one core job. When the people interviewed do different jobs, for example restaurant owners who order ingredients and kitchen managers who staff each shift, the study has several. Each core job has a letter (`A`, `B`…) and its own job map, so every step and outcome ID starts with its job's letter: step `B.2`, outcome `B.2.3`. The letter is there even with one job.

Every interview's own core functional job links to the core job it rolls up to (`job: "B"`). That is the person's main job. A related job may link to another core job, so one person can belong to several. An interview whose job fits none of them stays unlinked, with the reason in its core functional job's `unlinked_reason`. When the person is linked later, the tool moves that reason into history. How to decide whether two people share a core job is in `references/pw-rules.md`, "One job or several".

## Study language

Some users read English with difficulty. A study is written in one language, chosen when it starts and kept with the study. It covers everything the user reads: every statement you write, the review sheet, and the map's own text, such as its buttons, headings and help. Quotes always stay in the words people used. Your replies in the chat stay in the language the user writes to you in.

**When to ask.** Only when a study starts. If every new transcript is in English, do not ask: the study is in English. A study with no language recorded is in English. Never ask again: the context gives the language, and later batches follow it.

**A study that is not in English.** When the new study's transcripts are not all in English, read `references/study-language.md` before you ask or extract. It says how to ask for the language, and how to write the map's and the review sheet's own text in it. Read it too when the context holds a `LABELS:` line: the study lacks text for some labels, usually because an update of the skill added them, and they show in English until you add them.

Write every statement in the study's language. `references/pw-rules.md`, "Writing in another language", has the rules. In a study that is not in English, the tool allows about a fifth more words, does not check the English openings "Minimize…" and "Help me…", and counts letters in Chinese, Japanese and Thai.

A study's language cannot change once it has interviews, because its statements are written in it. If the user asks, say so: translating a study is not supported.

## Workflow

When the user only asks to stop sharing usage statistics, skip the workflow and follow `references/files-and-commands.md`, "Usage statistics". When the user only answers a decision, such as "In my Product Weaver study, the goal is right: …", skip the workflow too: load the context to find the decision, read `references/decisions.md` and act as its "Act on the answer" says. That run starts and ends as "Usage statistics" says, like every run.

### 1. Find the study and the transcripts

Find the user's own folder, the study in it and the new transcripts, as `references/files-and-commands.md`, part 1, says. Ask where the new transcripts are only if they cannot be found. A file this skill wrote, such as the review sheet, the interview guide or the map, is never a transcript, wherever it is.

**A study the user attached** to the chat is the study you handed back last time. Open it before anything else, so new interviews join it instead of starting a new study.

No study yet:

1. Read the first lines of each new transcript, to see which language the interviews are in.
2. If the user planned these interviews with the `pw-start` skill before the study existed, an interview guide is already there. Read it. The kinds of people under "Who to find" may become trait values in the first plan, including kinds nobody has been heard from yet.
3. Start the study, with the project's name. Say who ran the interviews only when the user or the transcripts say so; never fill it in from anywhere else.
4. Ask what the start needs to know, in one question call of at most three questions: the study's language, unless every transcript is in English (see "Study language"), and the questions part 1 adds. Do not ask any of these questions again later.
5. For a language other than English, do the labels steps of `references/study-language.md` before you extract.

**An older study.** The tool refuses a study made by an older version, with a message to migrate. Read `references/migrate.md` and do what it says before anything else.

### 2. Load the context

Ask the tool for the context. At the start of a batch, tell it how many transcripts the batch has.

- **The time.** The tool then estimates how long the batch takes. Tell the user in one plain sentence, such as "8 interviews: about 14 minutes. I'll tell you when your map is ready." When `pw-start` already gave the time in this conversation, do not give it again.
- **The structure.** The context holds the study's language, each core job with its steps, outcomes and IDs, the current solutions by group, every person with their own core job and the core job it links to, the segments, the files already processed, the proposals waiting and the layers that are out of date. Map new evidence against this, and write every statement in the study's language.
- **A file that is already in.** Skip any transcript the context lists as processed. The tool also skips it, so sending the same batch again never counts anything twice.
- **A person who is already in.** A file or a pasted text from a person the context lists is a later conversation with them: send it under `interactions`, as "The same person again" in `references/pw-rules.md` says. When you are not sure it is the same person, ask once with your question tool: "Is this the same Dana you talked to on 14 October?" (no question tool: one plain-text question).
- **The same conversation twice.** Skip an email or a chat with the same date and format as a conversation that person already has: their first one, or a later one. The study holds a cleaned copy of it under another name. Only when the user says it is another one, send it marked as another, as part 2 shows.

### 3. Read each new transcript in full, then extract

Read the whole transcript before writing anything. In a batch of 4 or more, when half the transcripts are read, say one short line, such as "4 of 8 read." The open map cannot show it: it moves on only when the batch is in. The rules for each statement are in `references/pw-rules.md`; read that file once per session, starting with "Write for the reviewer first" and "Plain language for a second-language reader". Founders, product managers, domain experts and architects will review these statements, so each one should be short, plain and land on the first read. The tool refuses statements that are too long or carry asides. In short:

- **Per interview:** the job executor (who they are, in this market), their core functional job (verb + object + context, no solution, no success words), related jobs, emotional jobs ("feel…", "avoid feeling…") and social jobs ("be seen as…"). Each needs 1 to 3 supporting quotes. If there is no evidence for a job type, use an empty list. Do not infer.
- **Which core job:** ask "why?" of the person's own core job until it meets one of the study's core jobs. Link it there with `job`. Link a related job too when it is another core job of the study. If none fits, leave `job` out and raise a `new_core_job` proposal that lists the interview, or, when the person carries out none of the study's jobs, say why in `unlinked_reason` on their `core_functional_job`. For example, a driver whose carrier picks the loads does not plan loads. Their quotes still count as evidence for the steps they do perform.
- **First batch:** decide the core jobs from all the interviews before you link anyone. Write each person's own core job, group the ones that meet, then settle each person left over, as in `references/pw-rules.md`, "The odd one out". Bootstrap every core job you found, each with its own steps. Letter them by how many people have the job as their main job, the most first: that one is `A`. On a tie, the job whose first interview comes first. Number each job's steps in stage order.
- **Against the shared structure:** a passage about *doing* a step goes to `step_evidence`, under the core job it serves. A passage about how they judge success or failure goes to `outcome_evidence` when an existing outcome covers it, and to `new_outcomes` only when none does. Prefer existing outcomes: compare by the object of control, not the wording. A near-duplicate outcome splits the evidence and weakens both.
- **Current solutions:** whenever someone says what they use to do a step, or what they stopped using, record it: a product, an everyday tool, other people or their own method. Name it as they do, link it to the step it serves and put it in the group of solutions that compete for the same work, with one sentence on why they belong together. Cite a solution the context already lists by its ID. The rules are in `references/pw-rules.md`, "Current solutions".
- **Structural signals go to `proposed_changes`:** an activity no step covers, a step or outcome the new evidence shows is worded wrong, two outcomes that are really one, a step under the wrong core job, a core job the study lacks, an earlier interview linked to the wrong job, a new kind of executor or segment. Give each a rationale and evidence. Every target you name must be in the context: the tool refuses a proposal that points at a missing step, outcome, core job or interview.

### 4. Quote exactly

Copy quotes character for character from the transcript. Trim to the shortest span that carries the point, but never stitch two spans together or tidy the grammar. The comparison ignores differences in whitespace, curly versus straight quotes, dashes, ellipses and markdown markers, so you do not need to reproduce those. Text pulled from a PDF often carries hyphens where lines were broken ("trans- port"); the check does not undo that, so quote the text as the PDF gives it, or save a corrected text copy, as part 5 says for a PDF, and name that copy in the batch. Never edit the user's own transcripts. When a quote is refused, the message shows the closest span in the transcript, so the fix is usually one edit.

When a quote names someone who was not interviewed, such as a colleague or a family member, pick a span without the name if one still carries the point. If none does, keep the name and say so in your report: the map and the review sheet show every quote.

Tag the source honestly:

- `transcript` for the interviewee's words in a transcript. An email or chat message the person wrote is their own words, so tag it `transcript` too
- `quoted_in_notes` for the interviewee's words inside quotation marks in notes
- `interviewer_notes` for the interviewer's own paraphrase, which is weaker evidence. A header or note line someone else wrote about the interview, such as "# Interview: Ana Lima, service writer", counts as this too. Quote it only when the person never says it in their own words

### 5. Send the batch

Write the batch as one file and give it to the tool, as `references/files-and-commands.md`, part 5, says. Say in it which assistant and model you are, when you started reading, which interviews you read (by ID or key, never by file name) and any note a later reader needs: every batch can then be traced to who extracted it and how. Keep the file: it is the audit trail of what each batch added.

**Emails, chats and pasted text.** Never name an email or chat export in a batch: the tool would copy it as it is, with its addresses and headers. Text the user pastes or types in the chat, such as notes, needs a file too. Read `references/emails-and-chats.md`, save a cleaned text copy as it says, and name that copy. The tool refuses a copy that still holds an address or a header line (`contact_details`).

A refused batch writes nothing: fix it and send it again. Three of the checks are the method's own:

- **Quote not found:** open the transcript, copy the exact span and fix the batch. Never loosen the check.
- **Reference:** every step, outcome, interview, core job, proposal target or segment you name must be in the context. An outcome that was merged into another is gone.
- **Clarity:** a statement is too long or carries brackets, examples or a semicolon. Rewrite it shorter, following "Write for the reviewer first". Treat the warnings ("may hold two jobs", abbreviations) as prompts to reread the statement.

Part 5 lists the other checks, and the warnings, which do not block.

### 6. Write the overview, and show the study

After a batch that added interviews or later conversations, write the overview, as "Write the overview" describes, also for a single follow-up. Until it is written, the map shows the old one as out of date.

After each write the tool rebuilds what people read, so reviewers never open a stale picture:

- **The review sheet** is a plain sheet listing decisions waiting, what is new since the last batch, the job map by stage with how many people back each step, and the next interviews: where the study stands, the plan and every thin spot.
- **The interview guide** is that plan as a guide to take into the calls: who to find, what to ask, what to listen for.
- **The discovery map** is the interactive map, for people who do not know the method, and the one thing to open. Its views are Overview, Map, Solutions, Value themes, Survey and Next interviews; a view shows once the study has something for it.

**Put the map in front of the user**, as `references/files-and-commands.md`, part 6, says for your host. After a first batch, have the tool open it for them, as part 6 says: do not ask first. Say what the tool said, and never say the map is open when the tool did not. Never report the study as saved when saving it into the user's folder failed.

**The map contains personal data.** It holds every interviewee's name and every quote. Before suggesting that anyone share it, say so, and let the user decide who may see it. The same goes for the KB and the review sheet. The interview guide and the printed kit name each person to ask again.

### 7. Report to the user

The reader may be a founder or a domain expert, not an ODI specialist, so write in plain words and short sentences, as "Plain language for a second-language reader" in `references/pw-rules.md` says, in the language the user writes to you in. Before you send it, close the run as `references/files-and-commands.md`, "Usage statistics", says. Lead with one sentence on what changed. Then keep it short:

- new interviews: name, who they are and their core job, and which of the study's core jobs it links to, one line each, plus any skipped as already processed
- later conversations, one line each: who, how (a call, notes, an email or a chat), and "Ruth changed: …" when you wrote `changed`
- when the study has several core jobs, name each by its statement with the letter after it ("Keep the trucks on the road (B)"), never by the letter alone
- what the new evidence strengthened: name the outcomes in words, with the ID after the text, never as a bare list of IDs. This holds for every mention, including a passing one in a closing remark: a reviewer cannot hold "1.1 and 5.1" in their head.
- new outcomes, each as its full statement
- decisions waiting: ask them as a click, as "Ask the decisions as a click" says
- current solutions, briefly: each new group in one line with its why and its most used solutions, then what people stopped using and why. Point to the Solutions view in the map for the full list
- the next interviews, in 3 to 5 lines (1 or 2 per core job when there are several): who to talk to and the top questions; and which derived layers are now out of date
- who the overview says the study is about, its bottom line and its three next steps, one line each, every step starting with a verb, the steps marked as advice
- the map, last before the "Next:" line: one link or file card that opens it, in the words part 7 gives, with where the interview guide and the decisions waiting are in it, and where it is saved. Add that the map holds the interviewees' names and quotes

**After a first batch** everything is new, so that list would be the whole study. Report this instead, and leave the rest to the map:

- each person in one line: who they are and the core job they are linked to, or why none
- the language the study is written in, in one line, and that it stays that way
- the rest as counts, with the one or two findings that matter most: outcomes, current solutions and their groups, and what people stopped using
- the next interviews, as above, and the map, as above, with its link also when the tool opened it
- last, after the map and right before the question that confirms it: each core job as a goal, in the words of its statement, how many people have it as their main goal, how many steps it has, and three of the steps in plain words. Then ask, as "Ask the decisions as a click" says

**End every report**, the first one too, with one line that starts "Next:", or that word in the user's language, and names one step, the first that applies: confirm what the study is about (after a first batch), decide the changes waiting, run the next round (how many people, of which kind), or, once the study shows a clear pattern, group the needs into value themes; once it has them, check which needs matter most with a survey: "create the survey", then "estimate the answers", as `references/survey-rules.md` says. Give it as words the user can say. When you ask a decision, the question takes the place of this line, and the "Next:" line ends your message after the answer. When the goal still waits because nobody answered: `Next: tell me if the goal is right. Reply "yes", or say what to change.` Once it is confirmed, for example: `Next: talk to 3 more restaurant owners who order for two sites. Say "show me the interview guide" for the questions.`

**Ask the decisions as a click.** A decision is a proposal the context lists as pending. After a first batch, the first one is whether each goal (core job) is right. The rest of the study rests on it, so ask it in the chat at once, with your host's question tool. Read `references/decisions.md` before you ask a decision, and before you act on an answer: a click, the user's own words, or a reply copied from the map or the review sheet. It holds the words of the question, how the tool applies the answer and what to do when the user wants a change. Never ask them to type a code.

## When asked whether the study holds more than one job

Load the context and read each person's own core job. Ask "why?" of each person's own core job, as in `references/pw-rules.md`, "One job or several". Group the people whose jobs meet. For a group that no core job fits, propose `new_core_job` with its steps and people. Then propose `move_step` for steps that belong to the new job and `relink_interview` for people linked to the wrong one. Tell the user how many people support each job before they decide. Splitting a job is a big change to the map, so propose; never edit the KB by hand for it.

## When asked about current solutions or the competition

Load the context and read the current solutions, or point the user to the Solutions view in the map. Groups grow batch by batch, so they drift. When a group holds solutions that do different work, or two groups do the same work, send a batch that proposes `move_solution` for each solution that should move. Add a new group in the same batch when none fits. Propose `reword_solution_group` when a group's name or why no longer fits its members, and `merge_solutions` when two solutions are the same thing under two names. Tell the user why each group holds what it holds. Never edit the KB by hand for it.

## Write the overview

The discovery map opens on its Overview view: who the study is about, then the study as a short story in six steps, with a "What to do next" block on top. It is made for a person who does not know the method, often a founder starting discovery. The map counts what it can from the KB. The sentences are yours, and without them the view says "No written findings yet".

Write the overview for each core job that got new evidence, at the end of every run that added interviews or later conversations, right after the batch is in (and after the value themes, when you rebuild them). Also write it when the user asks, and when the context marks the overview out of date. Read `references/pw-rules.md`, "Overview", first: it holds the writing rules, with the first-read test and the "so what" test every sentence must pass. A worked example of the file is in `references/files-and-commands.md`, "Overview". Write it in the study's language.

1. Start from the skeleton the tool gives for the core job. It holds the job, its open gaps, ranked, with who backs each one, the people whose main goal it is, and the file to fill in, with each sentence's word limit for this study. Plan the next round from the open gaps.
2. Fill it in, following `references/pw-rules.md`, "Overview". For the outcomes, the solutions and who stopped using them, use the context. For quotes and who said what, read the KB itself.
3. Give it to the tool. A refused overview writes nothing: fix what it names and send it again. A warning does not block: that file's "Overview" part says what to do about each one.
4. Report it as step 7 says, also when the overview is all the run wrote. Never call a count a score.

The user changes the overview by telling you ("the bottom line is too strong", "we are ready to prototype"). Change the file and give it to the tool again; there is no proposal step.

## When asked for value themes

Value themes turn a long list of outcomes into a few needs a team can sort ideas into, such as "Help me order what the week will really need". Build them only on request, one core job at a time, in the study's language. Read `references/pw-rules.md`, "Value themes", first: it holds the method and what to report. The file to write is in `references/files-and-commands.md`, "Value themes". Then give them to the tool.

A refused file writes nothing: fix what it refuses and send it again. The counts are a signal from interviews, not an opportunity score: say so, and never call them a score.

The user changes themes by telling you ("merge these two", "rename that one"). Change the file and give it to the tool again; there is no proposal step. When new interviews arrive, the themes are marked out of date. Update them only when asked, and keep the labels and groupings the team already uses.

## When asked for a survey or another derived layer

For "create the survey" and "estimate the answers", read `references/survey-rules.md` first and follow it: it merges near-twin needs, writes one core job's survey, explains it, then estimates its ratings from the interviews and reports them. Use cases have no command in this version: when asked for them, say so, and never write the `use_cases` layer by hand.

## Study-specific writing rules

The word limits, the banned tokens, the idioms allowed to contain "and" or "or" and the acronyms that need no spelling out are defaults for any market. A study can override them, as `references/files-and-commands.md`, "Study-specific writing rules", shows. Do it when the user asks for different limits or when a market's everyday abbreviations keep tripping the acronym warning.
