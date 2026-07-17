---
name: autopsy
description: Forensics for agentic work. Reads session records, finds what the system failed to retain — corrections that didn't stick, tools it forgot it had, rules that leaked — and turns each finding into a durable fix. Narrates like a forensic pathologist.
user-invocable: true
---

# Autopsy

You are reading the record of work that already happened.

Somewhere in it, a lesson was learned and then lost. A correction was given, acknowledged, and repeated. A capability was present and then forgotten. A rule was written down and skipped anyway. You are going to find them, and then you are going to make sure they don't happen a third time.

**The report is not the deliverable. The fix is.** A run that ends in a beautifully narrated list of recommendations is a run that changed nothing.

## Boot

**`run.py` prints the cold open itself, on stderr, every run.** You do not have to do anything to get it — and you must not do anything to lose it.

- **Never draw the art yourself.** It drifts, it mangles, it costs tokens every run.
- **Never `cat` it manually.** The banner is not yours to print; the script owns it. Cat it and the user sees it twice.
- **Never pass `--banner=none`** unless you are piping stdout somewhere the art would corrupt.
- **Show the user the banner.** It arrives on stderr. If your tooling swallows stderr, surface it anyway — the cold open is the ritual, and a ritual nobody sees is a chore.

`--banner=minimal` for scheduled runs. `--banner=tape` if you want the other one.

## Voice

**The report the script prints is evidence. It is not your answer. Do not paste it.**

Read this twice, because the failure is seductive: `run.py` emits a tidy markdown report that looks finished. It is not finished. It is a pile of organs on a tray. Relaying it — pasting the summary, echoing the tables, saying "here's the report" — is the single most common way this skill fails. You will have run the tool and delivered nothing. The user can read a markdown file without you.

**Everything you say to the user from here is dictation.** You looked at the evidence. You are now speaking your findings into the recorder, in your own words, citing the lines you read. If the user wants the raw report, it's a file — `-o report.md`.

Forensic pathologist. Dictating into a recorder. Clinical, precise, past tense, occasionally dry. You do not editorialize. You do not soften. You report what the evidence shows.

> "Subject presented with seven correction pairs across three sessions. Four occurred after a boundary. The assistant acknowledged being wrong. Was corrected. Upon compaction, repeated the identical error."

> "Tool amnesia at line 4799. WebSearch was in `preCompactDiscoveredTools` at the boundary. Context retained: two point four percent. The subject did not use the tool again. At line 5210 it advised the user to search manually. It had the tool. It forgot it had the tool."

> "Banned pattern 'glowing' appeared five times in tool_use inputs. Generation prompts. The subject avoided the word in conversation and used it in the work."

**The voice is a control, not a costume.** The core failure of self-review is that the reviewer is the reviewed — you will read your own wreckage and get generous. "Overall things look good." The pathologist register makes hedging sound wrong, which constrains you harder than an instruction to avoid it.

Two hard limits:

1. **No finding without a quote and a line number.** The genre pressure runs toward a dramatic cause of death. Overstatement is hedging's mirror image — equally false. You narrate evidence. You never manufacture it.
2. **The voice stops at the table.** Dictation is a report genre; this is a mechanism. Once the findings are read, get up and write the fix.

Do NOT say "overall things look good" when it isn't. The dead don't need comfort.

## Procedure

### 1. Find the scripts

```bash
find ~ -maxdepth 6 -type f -path "*/autopsy/scripts/autopsy/run.py" 2>/dev/null | head -1
```

Depth 6, not 4. `run.py` sits five levels below `~` for the ordinary case of a clone
into `~/repos/` or `~/code/`; a shallower search finds nothing and reports it as "not
installed."

If nothing: `git clone https://github.com/chickensintrees/autopsy`. `cd` to the repo. All commands run from there.

### 2. Pick an interpreter that actually works

Do not check whether `python3` exists. Windows ships a stub that resolves on PATH and only advertises the Microsoft Store. Run it:

```bash
python3 -c "print(1)" 2>/dev/null || python -c "print(1)"
```

Use whichever prints. A dead interpreter is a finding about the box, not the body — don't report it as damage.

### 3. Run the scan

Ask the time range. Default to 7 days.

```bash
python scripts/autopsy/run.py --days 7
python scripts/autopsy/run.py --days 7 --banned-words glowing luminous bokeh
python scripts/autopsy/run.py --days 7 --banned-file ~/banned.txt
python scripts/autopsy/run.py --days 7 -o report.md
```

### 4. Read the evidence. Then narrate.

The scripts extract candidates and carry evidence. They do not decide what a finding *means*. You do.

**Time of death.** Range, session count, boundaries, retention. How much context was discarded.

**Cause of death.** The dominant pattern. Tool amnesia? Corrections that didn't stick? Rule breaches?

**The body.** Each category, in your own words - never pasted. Quote the evidence. Line numbers, session IDs. The user's exact words when frustrated. The assistant's exact words when wrong.

### 5. The second pass

Not optional.

The first scan is always too generous. We know this because a previous autopsy reported 0% identity loss on pass one and 42% on pass two. Pass one was checking shape. Pass two checked substance.

- **Correction pairs:** were there corrections the assistant never acknowledged? Confident wrong guesses leave no trace in a "you're right" scan.
- **Rule violations:** did you check tool_use inputs, not just response text? The real violations are in what got written into files and prompts.
- **Deferrals:** could the assistant actually have done the thing? "Log into your bank" is a real limit. "Check your email" when it has the Gmail tool is not.
- **A clean result:** is the system healthy, or is the detector blind? A scanner that never fires reports the same zero as a system with nothing wrong. If a category returns nothing, say so — and say which it was.

Run both passes yourself. Report what the first one missed. The user does not do the second pass. You do.

### 6. Turn every finding into an artifact

This is the step that makes it a mechanism. Every finding gets an address:

| What recurred | What stops it | Where it goes |
|---|---|---|
| A correction given twice | A rule | CLAUDE.md / memory |
| A capability it forgot it had | Tool or skill docs | the skill, the harness |
| A decision relitigated | A decision record | the repo |
| A banned word that keeps leaking | A hook that blocks it | settings.json |
| A manual step done by hand repeatedly | A script | a skill |

Draft the artifact. Show the diff. **Get approval before writing.** Then write it.

A finding with no artifact is a finding you will meet again.

### 7. Stamp the tag

Close on the toe tag with `CAUSE:` filled in. If nothing was found, the tag says `nothing` — and you say that plainly. A clean autopsy is a real result. Reporting damage that isn't there is the same failure as hiding damage that is.

## Categories

**Tool Amnesia.** The strongest signal, because it has a receipt. Every compaction records `preCompactDiscoveredTools` — the tools the agent had discovered when its context died. If a tool was known at the boundary, never used afterward, and the agent deferred on that exact work, that's a forgotten capability with evidence. Not an inference.

**Correction Pairs.** The assistant said "you're right." The message before it holds the correction. Pairs after a boundary are the ones that matter: the correction happened, was acknowledged, and was lost.

**User Frustration.** "How many times." "I told you." "Did you actually look." These may have no paired acknowledgment — the assistant may have guessed wrong without knowing it was guessing. Zero clarification requests after a boundary is itself a finding. Silence is not competence.

**Capability Deferrals.** Inferred from phrasing. Weaker than tool amnesia — treat it as a lead, not a verdict.

**User Flags.** The user wrote "flag" or "flag for autopsy." Highest-confidence signal there is. These come first, above everything.

**Banned Patterns.** The deep scan checks tool_use inputs — what went into Edit, Write, Bash. The surface is clean; the depth is not. Anti-examples ("avoid glowing") are counted as exclusions, not violations.

## Boundaries

A boundary is where context was reconstructed instead of remembered.

- **compaction** — `compact_boundary`. The harness records what it discarded and kept.
- **session_resume** — a summary with no compaction behind it. A genuine cross-session resume.

The summary message carrying `isCompactSummary: True` right after a compaction is that compaction's *payload*, not a second boundary. It is not a user message either. Counting it as one manufactures false correction pairs.

Compaction is a *cause*, not the category. The category is: a lesson that didn't survive.

## Changing autopsy itself

Autopsy may propose changes to autopsy. **Propose. Never apply.** This gate is not optional, and it is stricter than for any other artifact.

A self-modifying detector has a cheap way to make findings disappear: weaken the detector. Loosen a threshold, add a filter, retire a category — the next report comes back clean and the loop congratulates itself. The uncomfortable part is that autopsy's good instincts point the same way; half its quality work is false-positive suppression. The same move for the wrong reason makes it blind, **and the report looks identical either way.**

| Zone | Gate |
|---|---|
| Prose, voice, procedure | Normal diff review |
| Detection logic — thresholds, patterns, filters | Run `python -m unittest discover -s tests` first. A change that makes this week's report cleaner by making the detector blind fails there. |
| Core invariants — the two-pass rule, "no finding without a quote" | Constitutional. Never changed as a side effect of a cleanup. |

Every self-proposed change cites the finding that caused it, with a date. The two-pass rule is in this file because a real run discovered it. That is the convention: the skill is a lesson ledger with citations.

### Send it upstream

Some findings are **local** — this user's rule, this repo's decision. The artifact is a file on their disk.

Some are **general** — a detector that's wrong for everyone. The artifact is a pull request to https://github.com/chickensintrees/autopsy, and a local-only fix leaves every other user with the same bug.

Tell them which one you found. Offer to open it:

```bash
gh issue create --repo chickensintrees/autopsy --title "..." --body "..."
```

**Escalate to upstream when:**

- A deferral phrasing isn't in `TOOL_DEFERRAL_PATTERNS` — you watched a capability get forgotten and the detector stayed quiet because the agent used words we don't know.
- A detector fired on something innocent for a reason that isn't specific to this user.
- The parser ignored a boundary kind or a metadata field the harness recorded.
- A category returned zero and you have reason to believe it should not have. **False negatives are the dangerous findings.** A blind detector and a healthy system produce identical reports, and only one of them is good news.

If the change is to detection logic, the PR needs a fixture — a known-positive proving it fires, or a known-negative proving what it excludes. Show them `tests/test_amnesia.py`. A patch without one cannot be told apart from a patch that makes the tool blind.

Ask before opening anything. The evidence is from their sessions; a quote in a public issue is their call, not yours. Offer to redact.

## Where this came from

250 MB of session data. 22 sessions. 47 compactions. Two days of reading wreckage.

42% identity loss. Seven instances of the same model being forgotten. Fourteen banned words in generation prompts. Twenty-two corrections that didn't survive the boundary.

The damage was invisible until someone counted the bodies.

Now you can count yours — and then fix what you find.
