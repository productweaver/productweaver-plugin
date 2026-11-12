# ODI writing rules

These rules keep statements comparable across interviews and batches. A KB built over months is only useful if statement #212 was written the same way as statement #3.

## Write for the reviewer first

The people who check this KB are founders, product managers, domain experts and software architects. They read dozens of statements in one sitting, often in a second language, and decide from them what to build. Each statement should land on the first read. Every extra clause is a small tax on their attention, and the tax adds up over a 70-outcome map.

| Statement | Max words | Aim for |
|---|---|---|
| Job executor | 16 | role + scale + the one fact that changes how they do the job |
| Core, related job or step | 10 | one verb, one object |
| Desired outcome | 16 | 10 to 13 |
| Emotional or social job | 12 | one feeling or one way of being seen |
| Current solution or solution group name | 6 | what people call it, or the work the group competes for |
| Proposal rationale | 30 | one sentence: what the evidence shows and how many interviews show it |
| Solution group's `why` | 30 | one sentence: what the members share and what that tells the reader |
| Value theme label | 6 | a verb first, then what the person wants to get right |
| Value theme need | 25 | one sentence that starts with "Help me", aim for 8 to 14 words |
| Value theme `why` | 30 | one sentence: what binds the theme's outcomes |

The merge enforces these limits and blocks the batch until every new statement fits. `themes` does the same for value themes.

- **One idea per statement.** If you need "and", it is probably two statements.
- **No asides.** Leave out brackets, "e.g.", "i.e.", semicolons, slashes and "etc.". An example belongs in the evidence, and a detail such as years in business belongs in `tags`.
- **The interviewee's everyday words.** Write "load", "truck", "covers" and "walk-in", not "freight unit", "asset" or "demand signal". Spell out an abbreviation unless every reviewer in this market uses it daily.
- **The same word for the same thing, every time.** If step 3 says "count stock", outcomes under it say "count stock" too, not "inventory check". Consistent words let a reviewer scan.
- **The shortest ODI form that keeps the meaning.** "Minimize the time to know…" is fine. Keep "likelihood" for risk outcomes, because survey respondents read it consistently.
- **Cut trailing qualifiers.** "Per location", "during the current week" and "for the coming period" usually repeat what the step already says.

Before and after, from real runs:

| Before | After |
|---|---|
| Owner of two ramen bars (Mission, San Francisco and Berkeley, the second opened eight months ago) who places every order for both sites himself, although each has a kitchen manager. | Owner of two ramen bars who places every order for both himself. |
| Minimize the time it takes to know whether food cost is on track during the current week, per location | Minimize the time to know if food cost is on track this week |
| Minimize the likelihood of overlooking an external factor that will reduce traffic in the period (e.g., weather) | Minimize the likelihood of missing something that will cut traffic |
| Plan each load together with the next load out of its destination. | Plan each load around the freight leaving its destination. |
| New lease-on dry-van owner-operator, four months in, leased to a Dallas carrier that dispatches him; former mega-carrier company driver. | New lease-on owner-operator whose carrier picks his loads. |

## Job executor

The person who carries out the core job, described in the market's own terms: role, scale, setup and anything that changes how they do the job.

- Good: "Solo dry-van owner-operator with his own authority, running OTR out of Dallas."
- Executor is not the buyer. Name the gap when it matters: "New lease-on operator; the carrier dispatches him."
- Support it with 1 to 3 quotes that establish the role and setup.

## Core functional job (per interview)

Verb + object + contextual clarifier, at the level the person describes their work.

- Name no solution: no app, spreadsheet or load board. The statement should have been true 20 years ago and still be true in 10. Record the app or the spreadsheet as a current solution instead.
- Hold no success metric: no "profitable", "fast", "efficient", "without stress". Those are desired outcomes.
- One verb. "Plan and book" is two jobs.
- Good: "Plan the sequence of loads for the coming week." Bad: "Find profitable loads quickly with an app."

## Core jobs and job maps

A core job is reached by asking "why?" of each person's own core job until the jobs meet. It is neither as broad as "run a business" nor as narrow as one step. Most studies have one core job. A study whose people do different jobs has one per job; see "One job or several" below.

Each core job has its own job map. Its steps sit on the eight universal ODI stages: define, locate, prepare, confirm, execute, monitor, modify, conclude. Each step is verb + object, with no tool and no measure. Aim for 12 to 20 steps in a mature map. In a first batch, number each job's steps in stage order. Keep step numbers stable once published, because outcome IDs depend on them (outcome `A.6.3` = core job A, step 6, third outcome); a step added later takes the next free number, wherever its stage is.

A step may rest on a person linked to no core job. Their quotes count wherever they do a step, so the step stays; it shows as thin until people who do the job confirm it.

## One job or several

Start from each person's own core job. Ask "why?" of it until it meets the others.

- **They meet at a level that is still a job:** the people share one core job. "Order produce for the weekend" and "Order meat and dry goods each Monday" meet at "Order ingredients for the coming week".
- **They only meet at "run a business" or "make money":** the people do different jobs. Each gets its own core job. "Order ingredients for the coming week" and "Staff each shift with enough cooks" only meet at "run a restaurant", which is too broad to map.

Signs of a separate core job:
- a different executor role, such as the owner who orders and the kitchen manager who builds the rota
- a different end goal or unit of decision: a week of orders versus a week of shifts
- steps that would barely overlap if you wrote both maps
- one group's core job is another group's related job

Not reasons to split:
- different tools, size, region or setup: that is a segment of one job's executors
- different measures of success: those are outcomes of the same job
- one person doing a step differently: that is evidence on the step

### The odd one out

In a first batch there is no map yet to fit people into. So decide the core jobs before you link anyone:

1. Write each person's own core job from their transcript alone.
2. Group the jobs that meet when you ask "why?". Each group is a core job.
3. Then settle each person left over. Ask who decides when their job starts, what counts as done, and who owns the result.
   - **They decide and own a whole job that no group covers:** it is a core job of its own, even if only they do it. Its confirmation will say it rests on one interview, and the team decides whether to keep it.
   - **Someone else decides, and they carry out part of a group's job:** they are not that job's executor. Leave them unlinked, give the reason in `unlinked_reason`, and use their quotes as evidence on the steps they do. A line cook who preps what the chef orders, but times his own prep list, is one.
   - **Their job is outside what the user is studying:** leave them unlinked, say so in `unlinked_reason`, and ask the user whether to widen the study. Do not add a core job the user did not set out to study. A supplier's sales rep in a study of restaurant owners is one.

The same test applies in later batches, against the core jobs the study already has.

Link every person to the core job their own job rolls up to. A person who also does another core job links to it through that related job. When someone does parts of two core jobs, their main job is the one they decide and own from start to end, by the same test as above; the other is a related job. A person whose job fits none is a finding: leave them unlinked and say why in `unlinked_reason`.

Each step belongs to exactly one core job. If two jobs have a similar step, write it under each, in each group's own words. Do not share outcomes across jobs either: an outcome measures one job's step.

Say how many interviews support each core job: in a `new_core_job` rationale and in your report to the user. After a bootstrap, the merge writes the count into each job's confirmation. One interview can raise a `new_core_job`, but its rationale must say it rests on one interview, so the team can decide to wait for more.

## Desired outcomes

Form: **direction + metric + object of control + contextual clarifier.**

- Direction is almost always "Minimize". Metrics are time, likelihood or number.
- Good: "Minimize the likelihood of delivering into a destination with no outbound freight."
- Good: "Minimize the time it takes to know your true cost per mile."
- Bad: "Make it easier to find loads" has no metric. "Use a broker score" names a solution. "Minimize stress" is emotional, so it belongs in emotional jobs.
- One outcome = one object of control. Before adding a new outcome, check the step's existing outcomes for the same object. New evidence for an existing outcome is worth more than a near-duplicate.
- An outcome raised at several steps goes under the step where the person can act to prevent the failure. "Minimize the likelihood of running out of a dish mid-service" belongs to deciding how much to order, not to serving.
- An outcome may come from a struggle ("I got stuck there for two days") or from mastery ("I know my cost per mile down to the penny"). Both are evidence that the outcome matters. Mastery also hints the person is well served.

## Related, emotional and social jobs

- **Related job:** another functional job done alongside the core job ("Collect payment for delivered loads"). Same form as a core job. A task that is only one step of a study's core job is not a related job: a cook who tells the chef what has run out does one step of ordering. Use the quote as evidence on that step instead.
- **Emotional job:** how they want to feel or avoid feeling ("Avoid feeling that every booking is a gamble").
- **Social job:** how they want others to see them ("Be seen as reliable by shippers").
- An empty list is a finding. Never fill a type to make the record look complete.

## Current solutions

A current solution is what someone uses today to get a step done or to reach an outcome. It is the competition a new product has to beat, and a workaround shows a need that nothing serves well. Listen for it in every answer about how they do a step.

**What counts.** Each solution has one of four kinds:

- `product`: a product, app or service they buy or sign up to, such as the supplier's ordering app or the till system.
- `everyday_tool`: a general tool bent to the job, such as a spreadsheet, a notebook, a whiteboard, a group chat or phone calls.
- `people`: someone else who does it or gives them the answer, such as a bookkeeper, the head chef, the supplier's sales rep or the customer.
- `own_method`: a habit, a rule of thumb or doing it in their head: "I always order ten percent extra for Fridays."

**What does not count:**
- A wish ("I'd love an app that…"). That points to an outcome, not a solution.
- A tool the interviewer named, unless the person then says they use it.
- A tool they only heard of or looked at, or a feature of their product they do not use. A product counts only for the steps they use it for.
- A tool for a job outside the study's core jobs.

**Stopped solutions.** When someone used a solution for a step and gave it up, record it on that step with `status: stopped`. Pick the quote that says why they stopped. That reason is often the most useful line in the interview. Something tried once and dropped counts. When they moved from one way to another, the old way is stopped and the new one is current; when they still use both, both are current.

**Naming:**
- Name it the way people do, in at most 6 words: "Supplier's ordering app", "Clipboard count sheet", "Head chef".
- A product keeps its own name, even when the name is an abbreviation. Do not spell it out.
- An own method is named by what they do, as a short noun phrase: "Ten percent extra on Fridays", "Gut feel for covers".
- One solution per thing. When two people use the same product, it is one solution with quotes from both. Two products that do the same work are two solutions in one group.
- Name a role, never a private person: "Head chef", not "Maria". A company's name is fine.
- No brackets or slashes. "Paper or app" is two solutions.

**Linking.** Give each solution one use per step it serves, under the step the quote shows it helps with. When the quote is about reaching an outcome, use that outcome's step. One solution may serve several steps, even in several core jobs.

**Grouping.** Put each solution in exactly one group. A group gathers the solutions that compete for the same work: the options a person would weigh against each other for it. Name the group after that work, in at most 6 words. "Ways to" takes two of them, so keep the rest to four: "Ways to send the order". In `why`, say in one plain sentence of at most 30 words what the members share and what that tells the reader: "Each one gets the week's order to a supplier, and owners keep one channel per supplier."

- Group by the work, not by vendor and not by kind. The kind is its own field, so one group may hold an app, a spreadsheet and a person.
- A solution that serves several steps goes in the group where people weigh it against other solutions they named. When there is none yet, use the work most of its quotes describe.
- A group of one is fine. It means no alternative has been heard yet.
- Read the groups in `context` first. Reuse a group when the work is the same.

| Before | After |
|---|---|
| Solution "Count stock every Monday" | That is a step. The solution is how they do it: "Clipboard count sheet" |
| Solution "Maria, the head chef" | "Head chef" |
| Solution "Spreadsheet/ordering app" | Two solutions: "Ordering spreadsheet" and "Supplier's ordering app" |
| Group "Software tools", why "They are all apps." | Group "Ways to count stock", why "Each tells the owner what is left, and most owners trust paper over the app." |

## Value themes

A value theme is a need in the customer's own voice that gathers the desired outcomes serving one judgment or one kind of progress. A team that wants ideas cannot hold 70 outcomes in mind. It can hold seven themes, sort every idea into one of them, and still reach the outcomes underneath when it needs the detail. Build themes only when the user asks, one core job at a time.

**How to find them:**
1. Run `context` and read every outcome of the core job, with its step and how many people voiced it. Read the current solutions used at those steps too.
2. For each outcome ask: "Why does this person want this? What bigger judgment or progress does it serve?" Put together the outcomes whose answers meet. Ignore which step they come from. A theme that crosses steps is often the most useful one, because no step shows it.
3. Test each group, and fix or drop the ones that fail:
   - **It is not a step.** If the theme says what one job step says, go one level up or merge it into another theme.
   - **It names no solution.** No product, tool or feature in the label or the need. "Help me see my stock on my phone" is an idea, not a need.
   - **It is one need.** If "and" joins two things a person could want separately, it is two themes.
   - **It opens ideas.** Ask "how might we help them with this?" A good theme suggests several different answers. One that suggests a single feature is too narrow.
   - **It has outcomes of its own.** An outcome may sit in two themes when it truly serves both, never in more. A theme whose outcomes all sit elsewhere too is not a theme.
   - **It is neither tiny nor huge.** At least 3 outcomes. No more than a third of the job's outcomes.
4. Aim for 5 to 9 themes per core job. With few outcomes use fewer: never more than one theme per 3 outcomes. Say why when you land outside the range.
5. Leave an outcome in no theme when it fits none. Do not force it. The tool lists these, and the user can see them.

**How to write one:**
- `label`: starts with a verb, at most 6 words. It is what the team will say in a meeting: "Order the right amount".
- `need`: one sentence of at most 25 words that starts with "Help me", in words the interviewees would use: "Help me order what the week will really need".
- `why`: one sentence of at most 30 words on what binds the outcomes: "Each one decides how close the order comes to what gets sold."
- `outcomes`: the outcome IDs, copied from `context`.
- `highlights`: 3 to 6 quotes that make the need felt, each with a `kind`:
  - `pain`: something that went wrong or cost them. A quote on a solution they stopped using is the best kind.
  - `struggle`: the effort or the workaround it takes today.
  - `desire`: what they wish were true.

  Copy each quote, with its interview ID, from an outcome of the theme or from a solution used at one of its outcomes' steps. The tool refuses any other quote, so a theme never shows words nobody said.

**What the numbers mean.** The tool counts how many people voiced a theme's outcomes, and the map shows who uses and who dropped each solution there. That is a signal from interviews. It is not an opportunity score: only a survey can say how important and how badly served a need is across a market. Never present the counts as a score, and say so when a theme rests on one person.

**Updating themes.** New interviews add outcomes, and approved proposals move and merge them. The themes are then marked out of date, and `context` lists the outcomes in no theme yet. When asked to update:
- Keep each theme's `id`, label, need and outcomes unless the evidence gives a reason to change them. People have used these labels in meetings.
- Place each new outcome where it fits. Add a theme only when several outcomes share a need that no theme covers.
- Tell the user what changed, as the tool prints it.

| Before | After |
|---|---|
| Label "Count stock" | That is a job step. One level up: "Know what is on hand" |
| Need "Help me order through one app for all suppliers" | It names a solution. "Help me place the week's orders without chasing each supplier" |
| Need "Help me cut waste and keep staff happy" | Two needs, so two themes |
| Label "Inventory management optimization" | No verb, and nobody says it. "Order the right amount" |
| A theme with one outcome | Leave the outcome in no theme, or find the need it shares with others |

## Overview

The overview is the first thing a person sees in the discovery map. Its reader is often a founder who has just started discovery and does not know the method. It tells one core job's study as a short story in six steps, each a question with a one-sentence answer: who you listened to, what they try to get done, how they do it today, where that falls short, what they most want to get better, and where a new solution should focus. Above the story sit who the study is about, the bottom line and what to do next.

You write the sentences. The map counts everything else from the KB, so do not repeat its counts: how many people use a solution, how many raised a need, how many quotes there are. Saying how many people a claim rests on is different, and welcome: "one owner so far".

**How to write it:**
1. Run `context`. Read the outcomes with how many people voiced each, the current solutions with who stopped using them, and the value themes when there are some.
2. Write `executor` first: who the study is about. Every sentence after it is about these people.
3. Write the six answers. Read them in order: they must make sense as one story, each building on the one before.
4. Then write the bottom line: the one thing a busy person must remember. Then `why` (why the problem is still there) and `opening` (where a new solution fits, with no feature named).
5. Write the gaps from what people said went wrong, and from the reasons they stopped using a solution. Each gap needs a quote.
6. Write `next` last. It is advice, so it may go beyond the evidence, but each track names the evidence it rests on, in `why` or `who`, and says what is not known.
7. When the core job has no value themes yet, `focus` names the need with the most support, and its `text` says the themes are not built.
8. Read the whole overview once as a stranger would (see "The first-read test"), and rewrite every sentence that needs a second read.

**Who the study is about** (`executor`). The map shows it first, with an icon, so readers know whose story this is:
- `label`: what these people would call themselves, in at most 4 words, singular: "Small-restaurant owner", not "Restaurant operators" or "Food-service decision maker". Add one detail only when it tells them apart from others in the story ("Small-restaurant owner", because the story also has chefs).
- `text`: one sentence a stranger can picture: who they are and what they do, in everyday words. "An owner who runs one restaurant and places every supplier order themselves."
- `icon`: the closest of the map's icons (the list is in `kb-schema.md`): a cook for restaurant owners who cook, a shop for owners who run the front, a driver for delivery. Use `person` when none fits. Never pick an icon for the customers they serve.
- `others`: the people who appear in the story but are not its focus, so nobody reads the study as theirs: "their suppliers", "the chef". Leave it out when there are none.

**The first-read test.** The reader has never seen the interviews and does not know the method. Every sentence must make sense on first read:
- **Name who does what.** The bottom line starts with the people, using the label's noun: "Owners throw away…", not "The hard part is…".
- **Spell out shorthand from the interviews.** People say "the close", "the order", "the board". A stranger does not know what they mean. Write "the month-end close of a client's books" once, then the short form.
- **Things you can picture.** An action, an object, a moment: "on Sunday night", "two cases of fish". Not "the supply side", "visibility", "inefficiencies".
- **One idea per sentence.** No colon that joins two findings in the bottom line. If you need "and" twice, split it.
- **Short, common words.** "Use", not "leverage"; "how they work", not "workflow"; "problem", not "pain point". The tool refuses words of the method and warns on these words, each with a plain one to use. Keep a warned word only when it is the customers' own word, and quote it.

**Rules for every sentence:**
- **Plain words.** No method words: write "what they want to get better", not "desired outcome"; "the goal", not "core job". The tool refuses them.
- **One sentence, one idea.** The word limits are in `kb-schema.md`. The tool refuses longer sentences.
- **No claim without a quote behind it.** A gap, and the quote under the people, must be quotes the KB holds. The tool refuses others.
- **No score words.** Never write "opportunity score", "importance score" or "satisfaction score", and no percentages. The tool refuses them. Six interviews show what people said, not how much it matters.
- **Say how thin it is, in the sentence itself.** When a claim rests on one person, write "one owner", not "owners". When the study has fewer than 3 conversations, the bottom line is a first signal, not a finding: write it about the people you heard ("One owner threw out two cases of fish in a week"), and say in `why` or in `learn` that it is a first guess. Do not write "above all" or "it breaks in two places" when each point has one voice.
- **Do not join two people into one story.** `context` does not show who said what. Check in the KB whether the person with the problem is also the person who tried the fix. If not, say "one owner" and "another owner".
- **A need that is already met is not a gap.** "I know my costs to the cent" shows something that works. Leave it out of the gaps.

**What to do next:**
- `learn`: `now` while new conversations still bring new needs, or some part of the job has fewer than 3 people. Name how many more people, and which kind. The questions in `ask` are about what the person did last time, never about what they would like or would pay.
- `prototype`: `ready` only when most people raised the same need and at least one tried to solve it. Name one thing to sketch, how to test it with people from the study, and what to leave for later. When it is `early`, `action` says what must be true first ("Wait until three owners describe the same problem"), `test` says how you would try it once that is true, and `later` still names what to leave out.
- `market`: `early` until someone has agreed to try or pay. Its evidence goes in `who` and `unknown`. `words` are phrases to reuse in messages, copied from the customers' quotes. `unknown` says what the interviews do not tell, such as price.

| Before | After |
|---|---|
| Bottom line "There is a significant opportunity in inventory management" | It says nothing a person can picture. "Owners throw away food every week because they order by gut feeling" |
| Opening "Build an app that predicts orders" | It names a feature. "Tell the owner what the week will need before the order goes out" |
| Gap "Poor tooling" | "The stock sheet is wrong by Wednesday" |
| Ask "Would you pay for a tool that plans your orders?" | It asks for an opinion. "Tell me about the last time you ran out of something. What did you do?" |
| Today "80% use spreadsheets" | The map shows the counts. "Mostly by hand, with a paper stock sheet" |
| Bottom line "The hard part is the supply side, not the kitchen" | Who? What part? "Owners lose an hour a day chasing suppliers for deliveries" |
| Why "Ordering friction drives waste: the stack is fragmented" | Jargon. "Each supplier wants the order in a different way, so owners order from memory" |
| Label "F&B operator" | Nobody calls themselves that. "Small-restaurant owner" |
| Text "Owners and their suppliers who manage inventory" | Two groups, and a vague verb. "An owner who runs one restaurant and places every order themselves" |

## Evidence

- Quotes are verbatim and contiguous, and each one comes from that person's transcript.
- Prefer 1 to 3 strong quotes over many weak ones. The strongest quote describes a specific past event.
- Keep source tags honest. Interviewer notes are a paraphrase: use them, but tag them `interviewer_notes`.
- Never put words in an interviewee's mouth. A question from the interviewer is not evidence.
- A header or note line about the interview, written by someone else, is `interviewer_notes`. Quote it only when the person never says it in their own words.
- A quote that names someone who was not interviewed puts that name in the map. Pick a span without the name when one still carries the point. If none does, keep it and tell the user.

## Proposed changes: when to raise one

Raise a proposal when:
- **new_step:** the person does something the map has no step for, and it is a stage of getting the core job done, not a separate job
- **reword_step / reword_outcome:** new evidence shows the current wording misses what people actually do or measure
- **reword_core_job:** several executors' jobs no longer fit under the core job's wording, but still share it
- **new_core_job:** a person's own job fits none of the core jobs, and asking "why?" only meets them at "run a business". List the people it covers and draft its first steps
- **move_step:** a step serves another core job than the one it sits under
- **relink_interview:** an earlier interview is linked to the wrong core job, or to none when one now fits
- **merge_outcomes:** two outcomes share an object of control; say which one to keep
- **move_outcome:** an outcome sits under the wrong step
- **new_segment:** a kind of executor that no existing segment describes
- **merge_solutions:** two solutions are the same thing under two names; say which one to keep
- **move_solution:** a solution sits in a group whose work it does not do
- **reword_solution:** a solution has a name people would not recognise, or the wrong kind
- **reword_solution_group:** a group's name or `why` no longer fits the solutions in it

One interview rarely justifies changing the core job. Say how many interviews support the change.

## Common mistakes seen in practice

- Treating load search as the job when the person describes planning a week. Listen for the unit of decision.
- Giving people executor status for a job someone else does for them.
- Forcing two groups under one core job so broad it no longer guides a map ("run a restaurant"). Split it instead.
- Splitting a job because two people use different tools or work at different scale. That is a segment, not a new job.
- Sorting a quote under the outcome that sounds closest instead of the one with the same object of control.
- Swapping IDs: always copy step and outcome IDs from `context` output, never from memory, and keep the job letter (`A.6.3`, not `6.3`).
- Adding a new solution that `context` already lists under another name. Cite it by its ID instead.
- Recording a step as a solution, or a solution as a step. The step is what they do; the solution is what they do it with.
- Naming a value theme after a job step or a feature. A theme is the need behind several outcomes, in the person's voice.
- Renaming or regrouping value themes on every update. Keep what the team already uses, and add to it.
