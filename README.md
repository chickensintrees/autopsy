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
| A decision relitigated | A sidecar + a breadcrumb | a dated note, and a one-line pointer to it |
| A banned word that keeps leaking | A hook that blocks it | settings.json |
| A manual step repeated by hand | A script | a skill |

The report is exhaust. The rule is the output. Autopsy drafts the artifact and shows you the diff; you approve it.

**Artifacts are ranked by durability, not category: test > hook > lint rule > sidecar > comment.** A test is a lesson that cannot rot — it fails when the lesson is forgotten. A hook is a lesson that cannot be skipped. A sidecar is prose, and prose decays silently into confident wrongness, which is worse than absent because it's still believed. So anything testable becomes a test; sidecars are only for the residue that can't be made executable — why X over Y, what was already tried, which obvious idea is a trap.

A **sidecar** is durable context beside the thing it explains. A **breadcrumb** is a one-line pointer at the point of confusion, aimed at that sidecar. Neither works alone: a sidecar nobody points at is never read, and a breadcrumb pointing at nothing is noise. Both get anchored to something checkable — a date, a commit, a session, a line. An unanchored breadcrumb is a rumor.

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

## Where it runs

Autopsy is a **Claude Code** tool, specifically and only. It reads Claude Code's own session logs — `~/.claude/projects/*.jsonl` — and every detector depends on fields only Claude Code writes: `compact_boundary`, `isCompactSummary`, `preCompactDiscoveredTools`. It is not a general "any agent" tool, because its evidence exists only where Claude Code produces it.

To run, it needs three things on the same machine: those session logs, a Python 3.8+ interpreter, and a shell.

| Surface | Runs? | |
|---|---|---|
| Claude Code CLI — macOS, Linux, Windows | **Yes** | Windows handled: the installer probes the interpreter by running it (the `python3` Store stub resolves but doesn't run), and every `.ps1` is pure ASCII. |
| Claude Code desktop app / IDE extensions | **Yes** | Same `~/.claude` on the same machine. |
| Claude Code on the web / cloud sandbox | **Not out of the box** | A remote sandbox doesn't have your local session logs. Point `--path` at them if they're reachable; otherwise no. |
| Mobile | **No** | No local shell, Python, or filesystem access to the logs. |
| Codex, Cursor, other assistants | **No** | Different products. They don't write Claude Code's session schema and don't load `SKILL.md`, so the scripts have nothing to read. Supporting them means a new parser per product, not a config flag. |

**It does not install itself on first invocation.** A skill can't install its own discovery file — `SKILL.md` must be in `~/.claude/skills/` before `/autopsy` exists. So the first install is `clone` + `install.sh`. After that it self-heals: the scripts relocate via a breadcrumb the installer drops, and `version_check.py` warns when your clone is behind `origin/main`.

## Or just run the scripts

Examples use `python3`; on Windows that's usually `python`.

```bash
python3 scripts/autopsy/run.py --days 7
python3 scripts/autopsy/run.py --days 7 --banned-words "I'd be happy to" delve
python3 scripts/autopsy/run.py --days 7 --banned-file banned.txt
python3 scripts/autopsy/run.py --days 30 --banner=minimal -o report.md
```

Nothing is sent anywhere. It reads local files and writes local text.

## Optional: enforce the banner with a hook

The banner prints to stderr, and the agent is supposed to paste it into its reply. Four prose fixes each hardened that instruction and none made it certain, because prose can't enforce behavior — a test can, and a hook is a test the harness runs.

`hooks/check_banner_relay.py` is a Claude Code **Stop hook**: if a session runs autopsy and stops without the ASCII art in the reply, it blocks once and tells the agent to paste it. It is silent on every other session, and it nudges exactly once (no loops). Off by default.

```bash
python hooks/enable.py            # register it in ~/.claude/settings.json (idempotent, backs up)
python hooks/enable.py --dry-run  # see the exact change first
python hooks/enable.py --disable  # clean removal
```

Claude Code CLI/desktop only — Stop hooks don't exist on web, mobile, Codex, or Cursor. This is defense for the surface where autopsy runs, not a portability layer.

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

## Contributing

**Please send issues and pull requests. This tool gets better the way it says everything else should get better: a finding becomes a durable fix.**

When you run autopsy against your own sessions, you are testing it against a corpus nobody here has. That's the whole value. Your harness, your tools, your habits, your phrasing — all of it is evidence we don't have.

**Open an issue when:**

- A detector missed something you *know* went wrong. False negatives are the dangerous ones, because a scanner that never fires reports the same clean zero as a healthy system. If you can quote the session line it should have caught, that's a complete bug report.
- A detector fired on something innocent. Paste the quote it flagged and say why it's fine.
- A finding was real but the proposed artifact was wrong — a rule where a hook belonged, or a fix aimed at the wrong file.
- The voice hedged. If a report told you things "look good" when they didn't, that's a bug in the control, and it matters as much as a bug in the code.

**Send a PR when:**

- You have a deferral pattern we don't cover. `TOOL_DEFERRAL_PATTERNS` in `scripts/autopsy/amnesia.py` only knows a handful of tools. Every real phrasing you've seen an agent use to hand work back to you is worth adding.
- You found a boundary kind or a metadata field the parser ignores. The harness records more than we read.
- A detector is wrong for everyone, not just for you.

**One rule for PRs that touch detection logic: include a fixture.**

`tests/fixtures/` holds tiny synthetic sessions; `tests/test_amnesia.py` shows the shape. A new pattern needs a known-positive proving it fires. A new filter needs a known-negative proving what it excludes — *and* the existing tests still have to pass, because the cheapest way to make a report clean is to make the detector blind, and that change looks identical to a real improvement in the diff. The fixtures are how we tell those apart.

```bash
python -m unittest discover -s tests
```

Not a code contributor? Reports are still useful. Run it, and open an issue with what it got wrong about you.

## License

MIT.
