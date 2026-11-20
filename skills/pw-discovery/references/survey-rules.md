# Survey rules

A survey asks people to rate each need of one goal twice, from 1 to 5: how much it matters to them, and how well it is served today. Its ratings show which needs are unmet. This file says how to make the survey, and how to estimate its ratings from the interviews. In this version the survey stays in the study: the map's Survey view shows it, and the plugin sends it nowhere.

The files to write and the commands to run are in `files-and-commands.md`, "Survey", under the same part numbers. Read it with this file.

## When

- Make the survey when the user says "create the survey", or asks which needs matter most. Make the estimate when the user says "estimate the answers". With no survey yet, make the survey first: the estimate rates the needs the survey asks.
- Make one survey for one goal (core job). With several goals, take the goal with the most conversations, say which one, and name the other in one line.
- Run `context` first. When its line `level N of 3 after …` (under `OPEN GAPS`) shows 1 or 2, still make the survey, but say first: "The list of needs is still changing. A survey now will miss needs you have not heard yet." Name one other choice in one line: the next round of interviews.

## 1. Merge near-twins first

Two needs are twins when a person could not give them different ratings. A survey with twins asks the same thing twice and splits its ratings.

1. Read every need of the goal in `context`, across all its steps, not only inside one. Compare first the needs about the same thing, such as a supplier's stock or a client's question. For each pair, try to describe one person in one situation who would rate the two differently. When you cannot, they are twins. "Minimize the time it takes to find which supplier has an item in stock" (step 2) and "Minimize the likelihood of having no idea who can deliver an item today" (step 6) are twins: nobody finds the supplier fast yet has no idea who can deliver. Keep the need more people named: its `(iv N)` count is higher.
2. Propose one merge for each pair, and say in it the one need that stays, in plain words: "One need: less time to find which supplier has an item in stock". Give the reason: "A person could not rate these two differently."
3. Approve each proposal, and keep the copy of the study from before the first twin was merged: it is the only way back.

The quotes move to the need that stays, and the map shows one need. Name every merge in your report, in words, in one list, and add one plain line: "If two of these needs should stay apart, say so now." With no twins, skip this part.

**Undo a merge** when the user says two needs should stay apart. Follow `files-and-commands.md`, "Survey", "Undo a twin merge": it says when an undo is still possible, and what to say when it is not.

## 2. Fill in the survey

Start from the skeleton, the file to fill in that the tool prints for the goal. Fill in every empty value. Leave `step`, `plain` and `name` as they are: they help you, and the tool drops them. Write in the study's language.

**The words of a need (`text`).** The person who rates it was not in your interviews, and may read English as a second language. Start from `plain`, and

- start with a verb: "Take less time to", "Lower the risk of", "Send fewer", "Have fewer", "Check fewer". "Less time to…" alone reads as "I have less time";
- write "Wait less for" when the time is spent waiting for someone else: "Wait less for a supplier to confirm a delivery date";
- never write "not" or "cannot": with the scale it reads as a double negative;
- give one word one meaning in the whole survey: "order" is always the order to the supplier;
- explain a tool's word a person may not know: "an automatic reorder level in your stock software";
- do not sound like an accusation: "ordering without checking the shelf first", not "ordering carelessly";
- make it differ clearly from the other needs of its step;
- keep it to at most 160 characters.

**"Explain" (`explain`).** The person sees it only when they tap "Explain". Write one informal sentence of at most 25 words that says the same thing with an example: "For example gloves or a filling material run out in the middle of a busy day." It is a statement, never a question. It may hold a concrete example, but no number or condition that narrows the need: "gloves run out on a busy day", not "gloves run out twice a week". It does not push toward an answer, and it names no person and no quote.

**About the person.**

- `gate`: one check question made from the goal, with `yes` "Yes" and `no` "No", and its `explain`: "Do you order supplies for a dental practice?". "No" ends the survey for that person.
- `profile`: each people trait of the plan becomes one full question, never the trait's name: "Do you order for one site or for several?". Write its `explain`, set `other` to "Something else", and give each value a short `label` a person would pick.
- `frame`: one line, at most 120 characters, shown on every step: "Think of a typical week of orders."

**Length.** A survey asks at most 30 needs. More tire people, and they start to tick 5 down the column. Above 30, first choose the needs to leave out: the ones the fewest people named (the lowest `(iv N)` in `context`), spread over the value themes (or the steps, with no themes). On a tie, leave out the need whose step keeps the most needs. Then ask before you write the survey: name those needs in plain words, then "Should the survey change like this?", with your question tool and the choices "Yes, change it" and "No, keep it". With no question tool, write it in plain text and add "Reply yes, or name the needs to keep." A plain-text question ends your turn, so run `pw_usage.py end` before it. After the answer, put each need left out in `left_out`, with why, such as "Named by one person only.", and write the survey. On "No, keep it", ask in plain text which needs to leave out instead.

## 3. Write it, and explain it

Write the survey into the study. A refused file writes nothing: fix what the tool names and write it again.

Then send one message of at most 8 lines. Take every number from what the commands printed. Give the goal in the words of its `CORE JOB` line in `context`. N is the `interviews=` number of `context`; with several goals, write "the interviews of the people with this goal" in its place.

> Your survey is ready. It asks about 28 needs, in the 8 steps of "keep the practice stocked with supplies".
> For each need, a person says how much it matters and how well it is served today. That takes about 8 minutes.
> The ratings show which needs matter most and which are badly served today.
> Open your discovery map, on "Survey", to read the questions.
>
> I can now estimate the answers from your 8 interviews, here on your machine. It takes about 3 minutes and shows where to look. Sending the survey to real people comes in a later version. Shall I estimate the answers?

Link the map as `references/open-files.md` says, with the words "Open your discovery map" as the link's text. Never add a `#` to the link: name the view in words. Add one line with the twins merged in part 1, if any. The question ends your turn, so run `pw_usage.py end` before it, as `files-and-commands.md`, "Usage statistics", says.

## 4. The estimate

Start from the evidence the tool prints for the goal. It lists each person of the goal, and under each need what they said about it (`said`) and what they said about its step or a tool they use or stopped using there (`context`). A need the person said nothing around is not listed. It is long, about 1,600 lines for 6 people: read it one person at a time.

Work person by person. A rating is one person's two numbers on one need. For each need listed, decide whether the quotes are enough for two ratings, each a whole number from 1 to 5:

- `importance`, "How much it matters": rate it from how the person talks about the need. Money or time lost, how often it happens, and what they did about it raise it.
- `satisfaction`, "How well it is served today": rate it from what the person does today. A tool they stopped, a workaround by hand and words of pain lower it. A method that works for them raises it.
- Never rate from another person's words.
- When you are unsure between two ratings, take the one nearer the middle.

Leave the cell out when it rests on one passing remark, or when the quotes do not speak to this need. A `context` quote is about the whole step, and the same quotes come under every need of that step. Read them for every need with no `said` quote: a tool the person stopped, or a method they built, often shows how well this need is served today. Use one only when it shows what the person does about this need. A cell left out is honest. A guess is not.

For each cell you keep, copy one quote exactly as the evidence printed it. A quote listed under `said` is always given `basis: "said"`, even when it is also listed under `context`. A quote only under `context` gets `basis: "context"`. Write `why` in at most 20 words: why these two ratings, in plain words, with no quote and no other person.

Then write the estimate into the study. A refused file writes nothing: fix the cells the tool names and write it again.

## 5. The report

At most 5 lines. Take every number, ID and name from the lines the tool printed when it stored the estimate: `estimate:`, `most unmet:` and `weakest:`. Never work out a figure yourself. Write each ID as the need's words from your survey file, with the ID after them, and each person by their name alone.

> For 54% of the ratings there is evidence in your interviews: 44% from the person's own words on the need, 10% from what they do at that step. For the rest, your interviews say nothing, so I left them empty.
> The 3 needs that look most unmet: take less time to find which supplier has an item in stock (C.2.1), lower the risk of running out of an item on a treatment day (C.6.2), have fewer orders placed twice by two people (C.5.3).
> The estimate is weakest for Hanna and Luis: under half of their ratings have evidence.
> This is an estimate, not survey answers. Open your discovery map, on "Survey".
> Next: sketch a rough prototype that finds which supplier has an item in stock (C.2.1), and show it to 2 or 3 of these people: it is an estimate, so their reactions check it.

- Give the coverage first, in two parts: from the person's words, and from context. When one part is 0%, give only the other: "For 36% of the ratings there is evidence in your interviews, all from the person's own words on the need."
- Name the needs `most unmet:` lists, at most 3. When it says "none yet", say that no need is ranked yet, because a need needs ratings from 2 or more people.
- Leave the `one person only:` line to the Survey view.
- The prototype step is the "Next:" line only when no earlier step of SKILL.md's step 7 applies: a goal still to confirm, or changes waiting to be decided, come first.
- When `weakest:` says "none", leave that line out. When the `estimate:` line shows under 50%, write "The estimate is thin overall, and thinnest for Hanna and Luis.", with the people `weakest:` names.

## 6. Words

The user reads these words, never the method's:

| Method word | What the user reads |
|---|---|
| importance | "How much it matters" |
| satisfaction | "How well it is served today" |
| underserved outcome | "unmet need" |
| overserved outcome | "served more than needed" |
| simulation, virtual survey | "the estimate", "estimated from your interviews" |
| the estimate's values | "ratings", never "answers" |

Never write "segment", "opportunity score", "importance score", "score", "ODI" or "simulation" to the user. Percentages are allowed in this report and in the Survey view. They stay out of the overview, which refuses them.

## 7. Out of date

`context` prints one `SURVEY` line for each goal with a survey, such as `SURVEY C [out of date]: 2 new needs are not in it; version 1, 28 needs, about 8 minutes, estimate for 93 ratings`. With `[out of date]`, say in one line what the line says, such as "2 new needs are not in your survey", and offer to bring it up to date. Then start from a new skeleton, copy the words of the needs already asked from your last survey file, write the new needs, and write the survey again. When the line said "the estimate is older than the study", or the survey changed, make the estimate again as in part 4.
