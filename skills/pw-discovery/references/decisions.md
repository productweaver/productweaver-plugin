# Decisions: ask them as a click, then act on the answer

Read this before you ask a decision, and when the user answers one. A decision is a proposal that `context` lists under `PENDING PROPOSALS:`. Below, `kb_tool` stands for the full command line that `files-and-commands.md` gives under "Running the script".

## Ask

1. Right before the question, show each goal in plain words with three of its steps, as the first-batch report says.
2. Ask with your host's question tool: `AskUserQuestion` in Claude Code and Cowork, `ask_user` in Gemini CLI and GitHub Copilot CLI, `request_user_input` in Codex's Plan mode. Use one call with at most 3 questions: one per goal to confirm (`confirm_core_job`), then other decisions, oldest first; the others stay in the map. Ask in the language the user writes to you in. Mark no choice as recommended, and add no "Other" choice: the host adds one for the user's own words.
   - A goal: "These 5 people are all trying to: Order what the kitchen needs for the week. Is that right?", with the choices "Yes, that's it" and "Close, but change it". With one person, start with "This person is trying to:".
   - Any other decision: the change in plain words, then "Should the study change like this?", with the choices "Yes, change it" and "No, keep it".
3. With no question tool, as in Codex's default mode, ask the same question in plain text, one goal per line, and end with "Reply yes, or tell me what to change." This message ends your turn.
4. When nobody can answer, as in a scripted run, or the user closes the question, leave the decision waiting. Say in one line that it is near the top of the map's Overview, under "Decisions for you".

## Act on the answer

The user answers with a click, in their own words, with a code such as "approve P1", or with a reply copied from the map or the review sheet: "In my Product Weaver study, the goal is right: …", "…change the goal to: …", "…make this change: …" or "…don't make this change: …". Find the decision under `PENDING PROPOSALS:` by its words. Act right away:

- **"Yes, that's it" or "Yes, change it":** run the line below, with that decision's code in place of `P1`. It rebuilds the map: say in one line that it is done, with what its `Open the link` line said about a map that is already open.

  ```
  kb_tool apply .pw-kb/pw-kb.json P1 --decision approve --note "confirmed in the chat"
  ```

- **"No, keep it":** the same with `--decision reject`.
- **"Close, but change it", or words of their own, about a goal:** never reject the goal's decision: leave it waiting. If they did not say what to change, ask once, in plain text. Then propose the change in a small patch (`reword_core_job`, or `move_step` and `relink_interview`; the format is in `references/patch-format.md`), and merge it without `--transcripts`. Show the change in plain words as one more question, with the choices "Yes, use it" and "Change it again". On yes, approve that proposal, then the goal's decision. On "Change it again", ask what to change and propose again.
- **A rejected `confirm_core_job`** changes nothing: ask the user what is wrong with the job, then propose the change the same way.

## What `apply` does

- **It checks first.** `apply` re-checks that the proposal's target still exists before it acts. A proposal raised against an outcome that was since merged or moved is refused with a message, not applied blindly.
- **It acts by itself** for `new_step`, `reword_step`, `reword_outcome`, `reword_core_job`, `merge_outcomes`, `move_outcome`, `new_segment`, `new_core_job`, `confirm_core_job`, `move_step`, `relink_interview`, `merge_solutions`, `move_solution`, `reword_solution` and `reword_solution_group`.
- **It keeps the past.** Old wording and old links are kept in `history`. IDs stay stable: new steps get the next free number in their core job, and merged outcomes keep a `merged_into` pointer instead of being deleted. A moved outcome or step gets the next free ID where it lands, the old ID goes to `history`, and pending proposals that cited the old ID are updated.
- **`other` has no automatic action.** First copy `.pw-kb/pw-kb.json` to `.pw-kb/backups/pw-kb.before-edit-<date>-<time>.json`, then edit the KB by hand and run `kb_tool validate .pw-kb/pw-kb.json`.

## After a new core job is approved

An approved `new_core_job` gets the next free letter, its steps are numbered from 1 and the interviews it lists are linked to it. It has no outcomes yet, because outcome IDs need the job to exist. Right after approval, reread those interviews and write a short follow-up patch that cites them by ID and adds the new job's outcomes and step evidence. Also check the `PEOPLE AND THEIR JOBS` block in `context` for earlier interviews whose related job is the new core job, and propose `relink_interview` for them.
