# Autopsy

**Forensics for agentic work.** Reads the record of what your coding agent actually did, finds what it failed to retain, and turns each finding into a durable fix.

The point is that a lesson gets learned **once**. Not relived, not relearned, not relitigated three sessions later.

```
    _     _   _  _____   ___   ____   ____  __   __
   / \   | | | ||_   _| / _ \ |  _ \ / ___| \ \ / /
  / _ \  | | | |  | |  | | | || |_) |\___ \  \ V /
 / ___ \ | |_| |  | |  | |_| ||  __/  ___) |  | |
/_/   \_\ \___/   |_|   \___/ |_|    |____/   |_|

  _/\__/\__/\__/\_______________________________________
       working memory              context boundary
```

## The problem

Long agent sessions hit context boundaries. When they do, the harness summarizes what it can and discards the rest. Here are three real compactions, read from real session logs:

| Tokens before | After | Retained |
|---|---|---|
| 1,004,717 | 19,073 | **1.9%** |
| 1,004,919 | 24,575 | **2.4%** |
| 999,705 | 60,067 | **6.0%** |

Ninety-eight percent of the working context, gone. The summary keeps the facts and loses the corrections. You told it the model name. You told it twice. After the boundary it asks again — or worse, doesn't ask, and guesses.

The damage is invisible unless you count it. This counts it.

## What it is

**A self-improvement mechanism, not a report generator.**

A diagnostic tells you the cause of death. A mechanism changes the system so it doesn't happen again. Every finding here terminates in an artifact with an address:

| What recurred | What stops it | Where it goes |
|---|---|---|
| A correction you gave twice | A rule | CLAUDE.md / memory |
| A capability it forgot it had | Tool or skill docs | the skill, the harness |
| A decision relitigated | A decision record | the repo |
| A banned word that keeps leaking | A hook that blocks it | settings.json |
| A manual step repeated by hand | A script | a skill |

The report is exhaust. The rule is the output. Autopsy drafts the artifact and shows you the diff; you approve it.

## Install

macOS / Linux:

```bash
git clone https://github.com/chickensintrees/autopsy.git
cd autopsy
./install.sh
```

Windows (PowerShell):

```powershell
git clone https://github.com/chickensintrees/autopsy.git
cd autopsy
.\install.ps1
```

Then run `/autopsy` in Claude Code.

Python 3.8+. Standard library only, no dependencies. Sessions are read from `~/.claude/projects/`.

## Or just run the scripts

Examples use `python3`; on Windows that's usually `python`.

```bash
python3 scripts/autopsy/run.py --days 7
python3 scripts/autopsy/run.py --days 7 --banned-words "I'd be happy to" delve
python3 scripts/autopsy/run.py --days 7 --banned-file banned.txt
python3 scripts/autopsy/run.py --days 30 --banner=minimal -o report.md
```

Nothing is sent anywhere. It reads local files and writes local text.

## What it finds

**Tool amnesia** — the strongest signal, because it comes with a receipt. Every compaction records `preCompactDiscoveredTools`: exactly which tools the agent had discovered when its context died. If a tool was known at the boundary, never used again, *and* the agent then told you to go do that work yourself — that's a forgotten capability with evidence attached, not an inference from phrasing.

**Correction pairs** — you corrected it, it agreed, the boundary ate the correction, it did the same thing again.

**User frustration** — "how many times," "I told you," "did you actually look." Sometimes with no acknowledgment at all, because it never realized it was guessing.

**User flags** — write "flag" or "flag for autopsy" in a session and it surfaces first, above everything. Highest-confidence signal there is: you called it out yourself.

**Banned patterns** — words that should never appear in your output. The deep scan checks what went *into* Edit, Write, and Bash calls, not just what was said to you. That's where the real violations hide: avoided in conversation, used in a generation prompt three lines later.

**Capability deferrals** — inferred from phrasing. Weaker than tool amnesia. A lead, not a verdict.

## The persona is a control

Autopsy narrates like a forensic pathologist dictating into a tape recorder. That's not decoration.

The core failure of any self-review tool is that **the reviewer is the reviewed**. A model reading its own wreckage gets generous — "overall things look good." The pathologist register makes hedging sound wrong, which constrains a model harder than an instruction saying "don't hedge." It also forces evidence, because nobody dictates "there were vibes of frustration," and it stays blameless, because a pathologist doesn't moralize about the body.

Two hard limits, enforced in the skill: **no finding without a quote and a line number**, and the voice stops when the findings end — then it writes the fix.

## The two-pass rule

The first scan is always too generous.

We learned this the hard way. Pass one reported 0% identity loss and we almost believed it. Pass two checked substance instead of shape and found 42%. Same data, same run.

Same story with banned words: pass one found 13 hits and classified them all as already remediated. Pass two tracked what went into `tool_use` inputs and found 14 real violations that made it into actual file writes.

The skill runs both passes and reports what the first one missed.

**A clean result gets the same scrutiny.** A detector that never fires produces the exact same zero as a system with nothing wrong. That's why the detectors ship with fixture tests that prove they fire on known-positive cases:

```bash
python -m unittest discover -s tests
```

If you weaken a pattern or add a filter, run those first. A change that makes this week's report cleaner by making the detector blind will fail there. That's the point.

## Boundaries

A boundary is where context was reconstructed instead of remembered.

- **compaction** — a `compact_boundary` record. The harness logs what it discarded, what it kept, and which tools were known.
- **session_resume** — a summary with no compaction behind it: a real cross-session resume.

The summary message carrying `isCompactSummary: True` immediately after a compaction is that compaction's *payload*, not a second boundary — and not a user message. Counting it as one manufactures false correction pairs. Autopsy doesn't.

Compaction is a **cause**, not the category. The category is: a lesson that didn't survive.

## Scope, honestly

v1 finds what didn't survive a boundary **within** a session, and proposes fixes.

It does **not** yet do cross-session recurrence — "you corrected this in July, and here it is again in August." That's the truest form of the idea and it's the next build, because it's the only thing that can answer *did the fix hold?* It needs a corpus-level view that doesn't exist yet. See `DESIGN.md`.

Also unshipped, and honest about it: the `session_resume` detector is implemented and unit-tested, but it has not been verified against a real corpus containing one. Every resume in the sessions we tested against was compaction-adjacent.

## Changing autopsy itself

Autopsy can propose changes to autopsy. It may not apply them.

A self-modifying detector has a cheap way to make findings go away: weaken the detector. The report comes back clean either way — that's what makes it dangerous. Detection logic changes have to clear the fixture tests; the two-pass rule and "no finding without a quote" are constitutional and don't get edited as a side effect of a cleanup.

If a finding is general rather than local, the artifact is a PR here.

## License

MIT.
