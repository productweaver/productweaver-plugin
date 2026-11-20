# When the link to the user's computer drops

Read this when a call to the user's computer fails because the computer, the device or the app cannot be reached, is not connected or timed out. That covers a call that lists, fetches or saves files there, and one that runs a command there. It happens in Cowork, where a task that runs in the cloud reaches the user's folder through the Claude desktop app. The link often drops for a few seconds and comes back by itself, so one failed call is no reason to give up.

## Before it drops

Fetch every file the run needs in one request, when your tool takes several, and work on those copies. Save them back in one request too. Fewer calls give the link fewer chances to fail.

## Retry, then tell the user

1. Do not stop and do not tell the user yet. Wait about 15 seconds (`sleep 15` in your own shell) and make the same call again.
2. If it fails again, wait 30 seconds, then 60.
3. Only when all three retries fail, tell the user in one or two lines: the link to their computer dropped, nothing is lost, check that the Claude app is open and the computer awake, and say "Try again".
4. When they do, go on from the call that failed. Keep the files you fetched and the answers you got; do not start over or ask again.

## What is not a dropped link

A missing file, or a folder you are not allowed to open, is not a dropped link: do not retry those.

## When the save still fails

If saving the study into the user's folder still fails after the retries, never report the study as saved. Say it is ready but not yet in their folder, and give the words to say: "Save the study".
