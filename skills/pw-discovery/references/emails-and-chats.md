# Emails, chats and pasted text

Read this before you add an email, a chat export, or text the user pasted or typed in the chat. A transcript file (`.md`, `.txt`, `.docx`, `.pdf`) needs none of it. The reason for the care: the merge copies every file the patch names into the study, and an email or a chat export carries addresses, phone numbers and header lines that do not belong there.

## Save a cleaned copy and name that copy

- Never name an email or chat export in the patch: the merge would copy it as it is.
- Save a text copy as `.pw-kb/transcripts/<id>-<n>-<date>.txt` and name that copy. `<n>` is the next number after the person's conversations in `context` (2 for their first later one). A new person's first contact is `<key>-1-<date>.txt`.
- Text the user pastes or types in the chat, such as notes, is saved the same way.
- In the copy, remove header lines, signature blocks and legal footers. Write `[address]` and `[phone]` for an email address or a phone number inside a sentence. Keep everything else word for word, with who wrote each part.
- The merge refuses a copy that still holds an address or a header line (`contact_details`). Remove it from the copy, never from the user's own file, and merge again.
- Name a patch for one follow-up `<date>-follow-up-<id>.json`.

## What to tell the user

- Say the kinds and counts you removed, such as "4 header lines and a signature". Never repeat the removed text, in the chat or in `provenance.notes`.
- The first time, say in one sentence that the study now holds the text of private messages, and that it travels with the study folder.

Who the person is, what to take from the text and how to tag its quotes are in `pw-rules.md`, "The same person again".
