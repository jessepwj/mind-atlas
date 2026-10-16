# Levels and sub-agents

Not every mind map has to be as detailed as it can be. Decide the level first, then decide how many sub-agents to use and how long to spend. The reference run was a 700+ node, 16-branch, 7-sub-agent panorama of a large system. That is L4, the most detailed level.

## The four levels side by side

| | L1 Overview | L2 Standard | L3 Detailed | L4 Panorama |
|---|---|---|---|---|
| Purpose | Get a first impression, or explain it to someone | Understand a project or topic, find the obvious problems | Decide something, or rework one part | Optimize the whole, structure it, set the blueprint |
| Depth | 2-3 levels | 3 levels | 4 levels | 4-5 levels |
| Nodes | about 30-80 | about 80-200 | about 200-450 | about 500-1000 |
| Sub-agents | None; when the material is scattered, at most 1 to gather it | You take the trunk; 1-3 read-only sub-agents on the branches you do not know | 3-5 read-only sub-agents, split by module | 6-8 read-only sub-agents, one per line or module, plus cross-cutting ones |
| Sources | Only for key conclusions | For key facts | Status tags and sources on most nodes | Same as L3, and every key status verified against the source |
| Closing branches | May be absent | One short "Problems and next steps" branch | "Problems and improvements" branch | "Problems and improvements" in priority groups, plus "About this map" |
| You write yourself | Everything | Trunk, problems and next steps | Trunk, spot checks of key facts, merging, the problems branch | Purpose, principles, blueprint, progress, who does what; cross-cutting branches; correcting the reports; the problems branch; "About this map" |
| Rough time | 10-20 minutes | 20-30 minutes | 30-40 minutes | 40-60 minutes |

Depth counts the levels below the root: the first-level branches are level 1, and `build.py` prints the deepest as "deepest level N". The numbers are guides, not limits, and the times are rough. L1 and L4 come from real runs; L2 and L3 are scaled estimates. Trust your own measurements over these.

## How to choose

Look at three things:

1. **Purpose**: what the map will be used for next. To understand or explain: L1 or L2. To rework one part: L3. To optimize the whole or set a blueprint: L4.
2. **Scope**: how many lines, files, sessions or modules are involved. A topic that fits on one page does not deserve L4. A system with a dozen lines will have key parts missed by L2.
3. **The user's own words**: "everything", "completely", "in detail", "the whole picture" mean L4; "roughly", "tidy it up", "a quick look" mean L1 or L2.

How to ask:

- For L1 or L2, or when purpose and scope are both clear, decide yourself without interrupting. Say in your first sentence: "Doing this as L2, because (one sentence). Tell me if you want it finer or coarser."
- For L3 or L4 with an unclear purpose, where the two levels differ a lot in time, ask one question and give a recommendation: "Is this map for reworking one part (L3, about half an hour) or for setting the blueprint for the whole thing (L4, about an hour, six or seven sub-agents)? I recommend L3."
- If halfway through the material turns out much larger or smaller than expected, move up or down a level and tell the user in one sentence. A lower-level outline can grow: add more branch pieces and run `build.py` again.

## Using sub-agents

Rules for every level:

- **At most 10 at once.** Use 6-8 for L4 and keep some room for follow-up checks.
- **Research is for a cheap model, and every dispatch names its model.** Clearly defined gathering, tidying and extraction tasks default to the cheapest model that can follow the brief (in Claude Code: the Agent tool with `model: haiku`; in Codex or others: their own sub-agent mechanism). They may read stale documents, so the brief demands sources, and you verify key figures and statuses against the originals.
- **Judgment is not for the cheap model.** Merging reports, correcting statuses, writing the problems and improvements branch, and acceptance are yours. If you want an independent reviewer, use a mid-range model, not the cheapest.
- **The trunk and the purpose must be understood by you.** Do not outsource them.
- After dispatching in parallel, write the trunk outline yourself in the meantime; do not sit and wait.
- The dispatch format is in the [brief template](brief-template.md). Reports go into the work folder as `A-branch-name.md`, `B-branch-name.md`.
- A sub-agent's claim of success is not evidence. Spot-check every report (see below).

### How to cut branches

- **Cut by line or by module; give each sub-agent one block of material that overlaps no other.** In a large system that might be one sub-agent per product line or subsystem, such as one for each of seven lines.
- **Cut the cross-cutting parts separately.** Pipelines, the web layer, conventions and the knowledge layer touch many lines. Give each its own sub-agent rather than squeezing it into one line.
- **Keep the blocks about the same size.** If a block is too big for one sub-agent to read and write, split it in two; if too small, merge it into a neighbor.
- **Write whatever the whole system shares yourself.** Purpose, principles, blueprint, progress, who does what, and cross-cutting branches such as "timeline", "where the data lives" and "current status" only make sense once the blocks are put together. If each sub-agent writes its own, the versions will not match.
- Give every block a concrete list of material and suggested first-level branches. Do not make the sub-agent decide what to read.

### What to do at each level

#### L1 Overview

- Read and write it yourself. If the material is scattered, dispatch at most one sub-agent to collect the relevant files with a one-line description each.
- Add sources only after key conclusions. Not every node needs one.
- Usually 5-8 first-level branches with 2-5 nodes under each.

#### L2 Standard

- Read the core documents and write the trunk yourself. Dispatch 1-3 read-only sub-agents for the branches you do not know; fill in the rest yourself.
- End with a short "Problems and next steps" branch, each problem with a one-line reason where possible.
- Verify key facts against the sources; not every one.

#### L3 Detailed

- Write the trunk (purpose, principles, overall structure) yourself from the originals.
- Cut 3-5 sub-agents by module, running in parallel and read-only, all using the brief template, reports into the work folder.
- Spot-check key facts, above all statuses: fixed or not, verified or not, in use or stopped.
- Most nodes carry status tags and sources. Have a "Problems and improvements" branch, and mark your judgments `[proposal]`.

#### L4 Panorama

- 6-8 sub-agents, one per line, plus the cross-cutting parts.
- You hold the trunk: purpose, principles, blueprint, progress, who does what. Add cross-cutting branches such as "timeline", "where the data lives" and "current status".
- **Correct the reports against the latest progress.** In the reference run this fixed three things: something already fixed was reported as not fixed, something already verified was reported as not verified, and something working normally was reported as in conflict. All three came from sub-agents reading stale documents.
- Group "Problems and improvements" by priority (in the reference run: protect the data first, then consolidate the documents, then tidy the code, then advance the blueprint). Items marked `[proposal]` are the mapper's judgment and not decided.
- End with "About this map": how it was made, what was corrected, how to update it, how to give feedback.

## How to spot-check reports

Go back to the source files; do not just read the report. For each report, check at least:

1. **Statuses**: fixed or not, verified or not, in use or stopped. Compare with the latest progress notes, logs or commit history.
2. **Times, quantities, paths**: pick 3-5 at random from the report and open the files to look.
3. **Anything the report itself marks as unsure**: resolve each against the source. Do not copy it into the map as is.
4. **Contradictions**: when two reports disagree about the same thing, the source and the latest progress win. Say on the node which one you used.

Write what you corrected into "About this map" under "What was corrected", so readers know which parts were fixed.
