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
| Proposal rationale | 30 | one sentence: what the evidence shows and how many interviews show it |

The merge enforces these limits and blocks the batch until every new statement fits.

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

- Name no solution: no app, spreadsheet or load board. The statement should have been true 20 years ago and still be true in 10.
- Hold no success metric: no "profitable", "fast", "efficient", "without stress". Those are desired outcomes.
- One verb. "Plan and book" is two jobs.
- Good: "Plan the sequence of loads for the coming week." Bad: "Find profitable loads quickly with an app."

## Core jobs and job maps

A core job is reached by asking "why?" of each person's own core job until the jobs meet. It is neither as broad as "run a business" nor as narrow as one step. Most studies have one core job. A study whose people do different jobs has one per job; see "One job or several" below.

Each core job has its own job map. Its steps sit on the eight universal ODI stages: define, locate, prepare, confirm, execute, monitor, modify, conclude. Each step is verb + object, with no tool and no measure. Aim for 12 to 20 steps in a mature map. Keep step numbers stable once published, because outcome IDs depend on them (outcome `A.6.3` = core job A, step 6, third outcome).

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

Link every person to the core job their own job rolls up to. A person who also does another core job links to it through that related job. A person whose job fits none is a finding: leave them unlinked and say why in `unlinked_reason`.

Each step belongs to exactly one core job. If two jobs have a similar step, write it under each, in each group's own words. Do not share outcomes across jobs either: an outcome measures one job's step.

Say how many interviews support each core job: in a `new_core_job` rationale and in your report to the user. After a bootstrap, the merge writes the count into each job's confirmation. One interview can raise a `new_core_job`, but its rationale must say it rests on one interview, so the team can decide to wait for more.

## Desired outcomes

Form: **direction + metric + object of control + contextual clarifier.**

- Direction is almost always "Minimize". Metrics are time, likelihood or number.
- Good: "Minimize the likelihood of delivering into a destination with no outbound freight."
- Good: "Minimize the time it takes to know your true cost per mile."
- Bad: "Make it easier to find loads" has no metric. "Use a broker score" names a solution. "Minimize stress" is emotional, so it belongs in emotional jobs.
- One outcome = one object of control. Before adding a new outcome, check the step's existing outcomes for the same object. New evidence for an existing outcome is worth more than a near-duplicate.
- An outcome may come from a struggle ("I got stuck there for two days") or from mastery ("I know my cost per mile down to the penny"). Both are evidence that the outcome matters. Mastery also hints the person is well served.

## Related, emotional and social jobs

- **Related job:** another functional job done alongside the core job ("Collect payment for delivered loads"). Same form as a core job.
- **Emotional job:** how they want to feel or avoid feeling ("Avoid feeling that every booking is a gamble").
- **Social job:** how they want others to see them ("Be seen as reliable by shippers").
- An empty list is a finding. Never fill a type to make the record look complete.

## Evidence

- Quotes are verbatim and contiguous, and each one comes from that person's transcript.
- Prefer 1 to 3 strong quotes over many weak ones. The strongest quote describes a specific past event.
- Keep source tags honest. Interviewer notes are a paraphrase: use them, but tag them `interviewer_notes`.
- Never put words in an interviewee's mouth. A question from the interviewer is not evidence.

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

One interview rarely justifies changing the core job. Say how many interviews support the change.

## Common mistakes seen in practice

- Treating load search as the job when the person describes planning a week. Listen for the unit of decision.
- Giving people executor status for a job someone else does for them.
- Forcing two groups under one core job so broad it no longer guides a map ("run a restaurant"). Split it instead.
- Splitting a job because two people use different tools or work at different scale. That is a segment, not a new job.
- Sorting a quote under the outcome that sounds closest instead of the one with the same object of control.
- Swapping IDs: always copy step and outcome IDs from `context` output, never from memory, and keep the job letter (`A.6.3`, not `6.3`).
