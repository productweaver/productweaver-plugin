# Putting the map in front of the user

Most people who use this plugin are founders and product managers, not developers. They should open the map with one click from your reply, and find it again next week without help. Read this before you point to any file the skill wrote. The examples use a folder called Interviews; use the user's own folder.

## Rules for every host

- Lead with one thing to open: the map, `pw-output/discovery-map.html`. It opens in any browser, works offline, and holds the rest: the Overview, with the decisions waiting under "Decisions for you", and the interview guide, in its Next interviews tab, where it can be printed or copied.
- When your host has a tool that shows a file to the user, use it. Otherwise give a link.
- Check that the file exists before you link it.
- Write the link text in plain words, such as "Open your discovery map", never as a path.
- Never add a `#` part to a link, such as `discovery-map.html` followed by `#next`. A click on a Mac drops it, and Codex reads it as part of the path. To send someone to a tab, name it in words: "then click Next interviews".
- Name `review.md` and `interview-guide.md` only when the user asks for text, or wants to edit, paste or print the guide in another app. They are text copies of what the map shows.
- Never paste a file's content into the chat.
- The map holds every interviewee's name and quote. Say so before anyone shares it.

## By host

| Host | The map | A `.md` copy, when asked |
|---|---|---|
| Cowork, a task that runs on this computer | Call `present_files` with the map's path. The user gets a card that opens it in their browser. | The same. |
| Cowork, a task that runs in the cloud | Send it with `SendUserFile` (fetch the file to your side first), or give `[Open your discovery map](computer:///Users/ana/Interviews/pw-output/discovery-map.html)` with the real path on the user's computer. Never a `/sessions/…` or `/mnt/…` path: those exist only on your side. (Unconfirmed: that a `computer://` click opens on a Mac, and how to write spaces in it.) | The same. It opens in Cowork's document view. |
| claude.ai, or a Claude Desktop chat with uploaded files | Copy the map to `/mnt/user-data/outputs/`, then call `present_files`. | The same, only when asked. |
| Claude Desktop, Code tab | `[Open your discovery map](pw-output/discovery-map.html)`, a path from the workspace. It opens in the Browser pane. (Unconfirmed.) | The same. It opens formatted. |
| Claude Code in a terminal, Copilot CLI | `[Open your discovery map](file:///Users/ana/My%20Study/pw-output/discovery-map.html)`: the address `map` prints after `link:`, with each space as `%20`. A click opens the default browser. | A `file://` link. It opens as plain text. |
| Claude Code in VS Code or JetBrains, Codex in an IDE | A link opens the page's source code, not the page. Say: "Say *show me the map* and I'll open it in your browser", then run `map --open`. Name the folder in words too. | A link opens it in the editor; Cmd+Shift+V (Ctrl+Shift+V) shows it formatted. |
| Codex app, ChatGPT desktop app | `[Open your discovery map](/Users/ana/Interviews/pw-output/discovery-map.html)`: a plain full path, no `file://`. Put `<…>` around a path with spaces: `[Open your discovery map](</Users/ana/My Study/pw-output/discovery-map.html>)`. Or call `open_in_codex`. It opens a preview in the app. (Unconfirmed.) | The same. It opens a preview. |
| Codex CLI, Gemini CLI | The `file:///…` address alone on its own line. The terminal decides whether it can be clicked. | The same. |
| ChatGPT on the web, with uploaded files | `[Download your discovery map](sandbox:/mnt/data/pw-output/discovery-map.html)`, once the file exists. | The same, only when asked. |
| Any other host | A `file://` link, as for a terminal, then the words below. | The same. |

## When nothing can be clicked

Say where the file is in words, in the user's language, then give its full path in a code block, to paste into a browser's address bar:

> In Finder, open your Interviews folder, then pw-output, and double-click discovery-map.html.

On Windows, say File Explorer instead of Finder. When your commands ran on another machine (paths that start with `/sessions/` or `/mnt/`), give the words only: that path does not exist on the user's computer.

## Upload hosts

When no folder is connected and the interviews were uploaded to the chat, the files live in a sandbox that is gone after the chat. Put the map in front of the user first, as the table says for your host. Then hand back the whole `.pw-kb/` folder as step 6 of the skill says. Never say the map is open in their browser.
