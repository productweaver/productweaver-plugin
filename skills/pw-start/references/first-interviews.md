# Plan the first round of interviews

For a user who has no interview transcripts yet. The result is `.pw-kb/interview-guide.md`: a guide they take into their first 5 to 8 conversations. When they bring the transcripts back, `pw-discovery` reads this guide on the first batch, and its `review` step then replaces it with a guide built from what people said.

Write everything, the questions to the user included, in the language the user writes to you in.

## 1. Ask, once

Ask in one plain-text message. These are open questions, so do not use your host's tool for choices. Skip any question the user already answered.

1. Who do you want to learn from? Describe them the way they would describe themselves.
2. What are they trying to get done, where you think things go wrong?
3. What are you thinking of building, or what decision should these talks help you make? This one is optional: say it is used only to keep the idea out of the questions.

When the user says "just guess" or "you decide", propose the answers in 3 short lines and go on unless they correct you. When an answer is vague ("small businesses"), pick the most concrete reading, say it in one line, and go on.

## 2. Decide the round

- **5 to 8 people.** Under 3 conversations, a finding is a hunch. A clear pattern needs 8 or more, with the last 2 adding little that is new.
- **2 or 3 kinds of people**, 2 or 3 people of each kind. Kinds differ in how they do the work: the size of the team, how the work comes in, the tools they use. Never age or city, unless it changes the work.
- **People who did the work recently**, in the last month, so they can tell you about the last time. Not friends who will be polite, and not people who only manage someone who does it.
- **Each person fits exactly one kind.** Kinds must not overlap; when someone could fit two, say which one counts.
- **Contact about three times as many people as you need**, by direct message, and follow up once after a few days. Many will not answer.

## 3. Write the guide

Write `.pw-kb/interview-guide.md`. Create `.pw-kb/` if it is missing, and write nothing else there. Never put a real person's name in the guide. Use these sections, in this order, with the titles in the user's language:

1. **Title and purpose.** "Interview guide: first round", the line "Made on <date>, before the first interview.", and one sentence on what this round should learn, about whom.
2. **Who to find.** The total, then each kind of person: how many, one line on who they are, and one on where to find them (an online group, a trade association, the user's own network, a referral from the last person interviewed). Then: contact about three times as many, by direct message, and before booking, check that they did the work in the last month.
3. **How to ask for a talk.** A message to send, 3 to 4 sentences, that fits every kind of person in the round: who the user is, that they are learning how people do this work and are not selling anything, that it takes 30 minutes by video (a video call can save a transcript), and a thank-you. No idea, no product name.
4. **Before the call.**
   - Get a transcript, not only audio: the plugin reads text. Turn on the call tool's transcript (Zoom, Google Meet and Teams can save one). In person, use a phone app that writes a transcript, or turn the recording into text with a transcription tool.
   - Plan 30 to 45 minutes: ask for 30, and keep 15 more free. Show no product, mockup or slides.
5. **The call.**
   - The opening, at minute 0: who the user is, the time it takes, and permission to record, in honest words that say what will really happen: "May I record this? I'll study the transcript with an AI tool, and I may share quotes with my team." The user changes it to fit what they will do; never promise more privacy than that. Then tell them there is no need to name their clients: "There's no need to name your clients." Then ask the one thing that decides their kind of person ("Do you work alone, or with anyone?"), so the transcript says it. If they say no to recording, take notes with their exact words in quotes and your own summaries marked as yours, and type them up right after the call.
   - 8 to 10 questions that walk the work from start to end: getting ready, doing it, checking it went right, fixing what went wrong, wrapping up. Mark at most 5 of them as must-ask: those fit in 30 minutes. Add: skip any question already answered. A question about the problem the user suspects says when to ask it: ask it only if they brought it up without being asked. Such a question is never must-ask.
   - Each question asks about the last time, and has a *Listen for:* line. Say above the questions that these lines are for the interviewer only: never read them out, and never turn a *Listen for* line into a question.
   - Follow-ups for short or vague answers, the only probes to use: "Last time, specifically?", "Can you give me an example from last month?", "What happened next?", "How long did that take?", "What did that mean for you?", "Why was that?" If they get stuck, wait, or repeat the question; never offer options.
   - One line to steer back when the talk drifts: "Going back to <the last time>, what happened next?"
   - Time: at about minute 25, ask "May I take 10 more minutes?" If not, ask the must-ask questions left and end.
   - What to say if they ask what the user is building: one honest sentence, such as "I'm still learning what the real problem is; I'll tell you more at the end."
   - End with "Is there anything I should have asked?" and "Who else should I talk to?" Then stop the recording. Only then, if they asked, say one sentence about the idea, then stop: no "what do you think", "would you use it" or "would you pay": a kind reaction is not evidence, and it must not reach the transcript.
6. **After the call.** Save each transcript as a `.md`, `.txt`, `.docx` or `.pdf` file in one folder of this workspace, such as `Interviews/`, one file per call, named with the date and a number (`2026-11-20-01.md`). If the call tool saves another format, such as Zoom's `.vtt`, save the text as a `.txt` file. Write down anything that surprised you in a separate notes file, not in the transcript, and keep it outside the folder of transcripts, so your words are never read as theirs. With 3 or more, open your assistant in this folder and say: "Add my interviews to the study."

## 4. Rules for every question

- **Do not build the call around the user's guess.** Walk the whole work first. Questions about the problem the user suspects take at most 3 of the questions, and come after an open one such as "What part of last week took longer than it should have?" If the problem is real, people bring it up on their own.
- **Ask about the last time.** "Tell me about the last time you…", "Walk me through…". People remember what happened. They guess about what usually happens.
- **Never ask what they would want, would do or would pay.** Those answers are polite guesses.
- **Never name the need you are checking.** "Do you lose money on no-shows?" gets a yes to be polite. Ask about the last empty slot, then listen.
- **Never describe the idea.** If they ask, say you will tell them at the end.
- **Never suggest an answer.** When nothing comes, wait or move on. Words you offer become their answer.
- **One question at a time**, short, then follow up: "What happened next?", "How did you notice?", "What did you do about it?"
- **Listen for** what would show the problem is real: what it cost, how often, what they tried. Add what would show it is not, when it fits in a few words. These lines are notes for the interviewer, never questions to read out.

| Before | After |
|---|---|
| "Would you use an app that sends booking reminders?" | It asks for an opinion. "Tell me about the last client who did not show up. What did you do about the empty slot?" |
| "Do no-shows cost you a lot?" | It names the need, so they agree. "Walk me through yesterday's bookings, from the first dog to the last." |
| "How do you usually handle your schedule?" | "Usually" gets a tidy story. "How did you fill next week's calendar? Start from the first booking." |
| "What features do you want?" | They are not designers. "What did you try last time a booking went wrong? How did that go?" |
| "What's your biggest pain point?" | Too vague to answer. "What part of last Saturday took longer than it should have?" |
| "How much would you pay to never have a no-show?" | A guess about money. "What did the last no-show cost you, roughly?" |
| Six questions about no-shows | It assumes the problem. Walk the whole day first; at most 3 questions on no-shows. |

## 5. What to show in the chat

Not the whole guide. Show:

- who to find, one line per kind of person;
- the first 3 questions;
- the full path of the guide: `.pw-kb/` is a hidden folder, so the user cannot easily find it by hand;
- the words to say next: "When you have 3 or more transcripts, put them in one folder here and say: Add my interviews to the study."

With no folder to save in (path D in `SKILL.md`), give the whole guide in the chat and say they can copy it into a document.

## 6. A worked example

The user wrote: "I want to build something for dog groomers. They lose money when clients don't show up." They skipped question 3. The guide:

```markdown
# Interview guide: first round

Made on 2026-11-13, before the first interview.

This round learns how independent dog groomers fill their days and what happens when a booking falls through.

## Who to find

6 groomers in all:
- 3 who work from their own shop. Find them in local groomer groups online.
- 3 who drive a van to the dog's home. Ask the first ones who else they know.
Count each groomer in one kind only: where they groom most days. Message about 18 directly, and follow up once after a few days. Before booking, check that they groomed a dog this week. Not friends, and not salon managers who no longer groom.

## How to ask for a talk

Hi, I'm learning how independent dog groomers run their week, from booking to the last dog of the day. I'm not selling anything. Could I ask you about it for 30 minutes, by video? It would help me a lot. Thank you!

## Before the call

- Get a transcript, not only audio: turn on the call's transcript, or use a phone app that writes one.
- Plan 30 to 45 minutes: ask for 30, and keep 15 more free. Show no product, mockup or slides.

## The call

Open with: "Thanks for your time. This takes about 30 minutes. May I record it? I'll study the transcript with an AI tool, and I may share quotes with my team. There's no need to name your clients." If not, take notes: their exact words in quotes, your own summaries marked as yours.

Then: "Tell me a bit about your work. Do you groom in a shop, or do you drive to the dogs? How long have you been grooming?"

The questions marked ★ are must-ask. Skip any question already answered. The *Listen for* lines are for you: never read them out, and never turn one into a question.

1. ★ Walk me through yesterday, from the first booking to the last dog.
   *Listen for:* how the day was planned, and what changed on the day
2. ★ How did next week's bookings reach you? Start from the first one.
   *Listen for:* every channel they check, and how they keep track
3. ★ What part of last week took longer than it should have?
   *Listen for:* whatever they name. Never suggest an answer; if nothing comes, move on
4. Tell me about the last time a dog took much longer than booked.
   *Listen for:* what it did to the rest of the day
5. How did you get paid by your last three clients?
   *Listen for:* deposits, late payments, cash
6. Tell me about the last client who did not show up. (Ask it only if they brought up missed bookings without being asked.)
   *Listen for:* when they found out, what the empty slot cost, whether they filled it. Or that it rarely happens
7. What did you try last time to cut down on missed bookings? How did it go? (Ask it only if they brought up missed bookings without being asked.)
   *Listen for:* tools they tried and stopped using, and why
8. What did you do the last time a client cancelled the same day? (Ask it only if they brought up cancellations without being asked.)
   *Listen for:* fees, rules, or letting it go

Follow-ups, the only probes to use: "Last time, specifically?", "Can you give me an example from last month?", "What happened next?", "How long did that take?", "What did that mean for you?", "Why was that?" If they get stuck, wait or repeat the question; never offer options.
If the talk drifts: "Going back to yesterday, what happened next?"
At about minute 25: "May I take 10 more minutes?" If not, ask the ★ questions left and end.
If they ask what you are building: "I'm still learning what the real problem is; I'll tell you more at the end."

End with: "Is there anything I should have asked?" and "Who else should I talk to?" Then stop the recording. Only then, if they asked, say one sentence about the idea, then stop: don't ask what they think.

## After the call

- Save the transcript in the Interviews folder, one file per call, named like `2026-11-20-01.md`. Zoom saves a `.vtt` file: save its text as `.txt`.
- Write down anything that surprised you in a separate notes file, not in the transcript, and keep it outside the folder of transcripts.
- With 3 or more, open your assistant in this folder and say: "Add my interviews to the study."
```
