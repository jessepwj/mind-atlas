# Brief template (branch research)

Use this when you dispatch a sub-agent to "map one branch". It is distilled from seven real briefs of about 40 lines each. Replace everything in `{{ }}` with the specifics of the job and keep the rest of the rules as they are.

## Before you dispatch

- **Name the model.** Research defaults to the cheapest model that can follow a clear brief (Claude Code: the Agent tool with `model: haiku`; other agents: their own sub-agent mechanism). Merging, acceptance and judgment are not for the cheapest model.
- **Make the material list concrete**: file paths, folders, keywords to grep. If you leave "what to read" to the sub-agent, it will miss things and read stale documents.
- **Give the suggested first-level branches.** The sub-agent does not know the structure you want. Give 6-12 suggested branches; the last two are always "Known problems, pitfalls and lessons" and "Unfinished work and room to improve".
- **One brief, one branch, no overlap.** How to cut them: see [levels](levels.md).
- **Dispatch several together**: send all the dispatches in one message so they run in parallel. Then go and write the trunk; do not wait.
- The status tags are in [outline-format](outline-format.md); list in the brief only the few this job will use.

## The template

Put the whole block below into the sub-agent's prompt.

````
You are helping with a full-picture mapping of "{{project name}}" and own one branch: **{{branch name}}** ({{what this branch is, one or two sentences, so you know its scope}}). Today is {{date}}. The main agent will assemble all branches into one multi-level mind map for {{reader}}, to be used for {{purpose, e.g. later optimization and structuring / making a decision / explaining it to others}}.

## Rules (mandatory)
- Read-only: change no file (except the one output file named below) and run no command with side effects ({{list the forbidden actions for this job, e.g. do not restart, load or unload any service; do not send messages; do not make write-type network requests; do not run scripts that change data; do not commit code}}). You may use cat, sed, grep, ls and find to look at files, {{the read-only commands allowed in this job, e.g. read the tail of logs, look at configuration, do read-only GETs against local services}}.
- Never copy a password, token, key or cookie value; say only which file holds it and with what permissions. {{If the material has private content, add: do not copy chats, conversations or personal records; describe structure and orders of magnitude only.}}
- Write in {{language}}. Write each node as a short, complete sentence or noun phrase. **Do not truncate with an ellipsis** (neither the single character nor three dots), and do not report only a count without saying what the things are.
- Verify key facts (paths, times, quantities, statuses, owners) against the source file before writing them, and put the source file path in brackets after the node.
- Where the material contradicts itself or is clearly out of date, write both versions and say which is newer and why. Do not pick one and call it fact.

## Material to read (start here, follow leads as needed)
- {{material 1: path + what to look at, e.g. "read it all", "only the introduction and the main function", "structure and a few samples only, do not read the whole large file"}}
- {{material 2}}
- {{material 3}}

## What to produce
Write it to the file `{{absolute path of the output file, e.g. <workdir>/A-<branch>.md}}` as a Markdown nested list (two spaces per level), {{number of levels, e.g. 4-5}} levels, as complete as you can. Suggested first-level branches:
1. {{suggested branch 1}}
2. {{suggested branch 2}}
3. {{suggested branch 3}}
{{add more to suit this branch; the last two are always the following}}
{{N-1}}. Known problems, pitfalls and lessons (from documents, logs, code comments)
{{N}}. Unfinished work and room to improve (only what you have evidence for, with the source)
Mark status with tags: {{the few this job uses, e.g. [active] [stopped] [in progress] [todo] [issue]}}.

## Check your work before you hand it in
When you have finished writing, go back and check. Hand it in only when you have found nothing wrong and are satisfied; do not report the moment you stop writing. Check: {{the kinds of mistake this job is most prone to, e.g. is every time correct, does every path exist, is anything truncated with an ellipsis, did you miss files in the folder that clearly belong to this branch}}. In your final message give: the output file path, which facts you verified (5-10 items, each with evidence such as the command and a snippet of its output), and what you are unsure about. Do not repeat the whole content in the message.
````

Every `{{ }}` in the template is a note to whoever fills it in. Replace all of them with the specifics before you dispatch; never send them as they are.

## How to fill it in

| Placeholder | How to fill it |
|---|---|
| Forbidden actions | Think through the operations in this job that change state just by looking: restarting a service, loading a scheduled job, sending a message, submitting a form, running a collection script. List each one. That helps far more than "no side effects". |
| Material list | Browse the folder yourself first and write concrete paths. Mark important documents "read it all" and large files "introduction only". |
| Suggested first-level branches | Most are variations of the questions "what is it / how does it run / where does the data go / what is scheduled and how does it connect / known problems / unfinished". |
| Self-check items | Pick the fact types this branch gets wrong most easily (times, paths, statuses) and have the sub-agent verify them. |

## After dispatching

1. While the sub-agents work, write the trunk outline and the cross-cutting branches yourself.
2. When a report comes back, read the parts it is unsure about first, then check against the sources with the spot-check list in [levels](levels.md).
3. Rewrite the report as `outline-<id>.md`: brackets with sources become `[src: ...]`, statuses corrected against the latest progress, duplicates merged, over-long titles split (syntax in [outline-format](outline-format.md)). Keep the report itself in the work folder as raw material; do not paste it into the page.
4. If a sub-agent broke the rules (read something it should not have, printed a secret, changed a file it should not have), write it down immediately and tell the user in one sentence in your reply. Do not hide it.
