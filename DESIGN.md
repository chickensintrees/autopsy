# Autopsy — Design

Status: design settled. Written 2026-07-17.
Name: `autopsy`. Scope: narrow build (see Roadmap for what's deliberately deferred).

This document exists because the conversation that produced it was one compaction
away from being lost, and the tool it describes exists to stop exactly that.

---

## What it is

**Autopsy is a self-improvement mechanism for agentic work.**

It reads the record of how an agent actually behaved, finds what the system failed
to retain or keeps getting wrong, and changes the system so it doesn't happen again.

The goal is that a lesson gets learned **once**. Not relived, not relearned, not
relitigated.

## What it is not

- **Not a compaction tool.** Compaction is one cause of loss, not the category.
- **Not a diagnostic.** A diagnostic reports. A mechanism acts.
- **Not a report generator.** The report is exhaust. The artifact is the output.

---

## Core decisions

### 1. The primitive is recurrence, not compaction

The signal is: the same correction given twice, the same question asked twice, the
same capability forgotten twice, the same decision relitigated months apart.

Recurrence is boundary-agnostic. It doesn't care whether the cause was autocompact,
`/clear`, a cold start, or a rule that was written down and ignored anyway.

**Consequence:** boundary type stops being the thing you scan by and becomes
*metadata on a finding* — "this recurred, and here's what ate it."

This also catches failures that have nothing to do with context loss: knowledge that
was never written down at all, a rule that exists and gets skipped every time, a
capability the harness never advertised.

### 2. Boundaries are causes, and there is more than one

- `compact_boundary` — autocompact or manual compaction (currently detected)
- session-resume — "This session is being continued from a previous conversation"
  (present in the data, currently **discarded as noise** — see Known Issues)
- cold start — a new session with no inherited context at all
- no boundary — the lesson was simply never made durable

### 3. Every finding terminates in an artifact, with an address

| What recurred | What would have stopped it | Where it lives |
|---|---|---|
| A correction given twice | A rule | CLAUDE.md / memory |
| A capability the agent forgot it had | Tool or skill docs | the skill, the harness |
| A decision relitigated | A decision record | the repo |
| A banned word that keeps leaking | A hook that blocks it | settings.json |
| A manual step repeated by hand | A script | a skill |

A run that ends in beautifully narrated recommendations is still a report. The skill
writes the rule, adds the hook, updates the doc — **with approval at the gate**.

### Rank artifacts by durability, not category

**test > hook > lint rule > sidecar > comment.** Added 2026-07-17.

A test is a lesson that cannot rot; it fails when the lesson is forgotten. A hook is a
lesson that cannot be skipped. A sidecar is prose, and prose decays silently into
confident wrongness — worse than absent, because it is still believed. Anything
testable becomes a test. Sidecars carry only the residue that cannot be made
executable: why X over Y, what was already tried, which obvious idea is a trap.

*Evidence for the ranking, from this repo's own first week: the fixture tests have
caught every real defect in the PR loop, while the prose instructions have needed
three corrections (the boot ordering bug, the stderr-visibility gap, and the stale
"sees it twice" rationale orphaned by fixing the second). The executable artifacts
held. The prose kept rotting.*

### Sidecars and breadcrumbs

Content and index; neither works alone. A **sidecar** is durable context beside the
thing it explains. A **breadcrumb** is a one-line pointer at the point of confusion,
aimed at the sidecar. A sidecar nobody points at is never read; a breadcrumb pointing
at nothing is noise. Same shape as a memory index and its files.

Constraints:

- **A breadcrumb is a pointer, not an explanation.** One line, aimed at a file. Not
  license to re-litigate a decision in a comment — that is talking to the reviewer,
  and it is noise the moment the change merges.
- **Anchor to something checkable**: session id, commit SHA, line number, date. The
  two-pass rule carries the run that discovered it. An unanchored breadcrumb is a
  rumor.
- **Sidecars rot**, and that is their defining failure — the same failure as memory: a
  sidecar records what was true when written. A later run finding a sidecar that
  contradicts the code has found a *finding*: the artifact lied, and a lie in the
  record is worse than a gap.

Rejected: putting this in a global rules file. The artifact map is autopsy's output
contract, and a rule the emitting mechanism cannot read is a rule that does not run.

### 4. It is measurable, and that replaces the severity score

The current `Damage Level: SEVERE/HIGH/MODERATE` is a vanity metric. Nothing consumes
it. Replace with:

- **Recurrence rate over time.** A finding produced a rule in July. Did that lesson
  recur in August? Did the fix hold?
- **Coverage.** How many findings have a durable artifact in place.

### 5. Cadence, or it isn't a mechanism

Self-improvement that fires when you remember is a novelty. It runs weekly, in the
background, on a schedule.

### 6. Division of labor: scripts extract, the model judges

Regex can find candidate events and pull evidence with line numbers. It **cannot**
decide whether the correction in session A and the correction in session B are the
same lesson. That's semantic and fuzzy.

- **Scripts:** extract candidates, cluster, carry evidence (session id, line, quote).
- **Skill (the model):** decides "is this the same thing wearing different words,"
  then drafts the artifact.

This is the split the tool already has — scripts give data, the skill gives story.
The reframe changes the last step from *story* to *fix*.

---

## Persona

**Scully dictating an autopsy into her tape recorder.** Clinical, precise, past tense,
occasionally dry. This is UX doing functional work, not decoration.

### Why the voice is a control, not a costume

The core failure of any self-review tool is that **the reviewer is the reviewed**. The
model reads its own wreckage and gets generous: "overall things look good." That is
exactly what the two-pass rule exists to catch — pass one reported 0% identity loss
because it was grading itself.

The pathologist register makes hedging *sound wrong*, which constrains a model far
harder than an instruction saying "don't hedge." Register enforces honesty.

It also buys:

- **Blamelessness by construction.** A pathologist doesn't moralize about the body.
  Findings implicate the user's rules and harness too; clinical detachment lets the
  report be brutal without being an accusation.
- **Evidence discipline.** The genre runs on specifics. Nobody dictates "there were
  vibes of frustration."
- **Skepticism.** Scully is the one who won't accept the tidy explanation. That *is*
  the second pass — refusing to sign off on pass one's clean result.

The name and the voice hold each other up. Kill the metaphor and you kill the control.

### Two guardrails on the voice

1. **It must not swallow the last step.** Dictation is a report genre; the mechanism
   acts. True to source, too: Scully's autopsies are the scene that redirects the
   investigation, not a document that gets filed. Pathologist through the findings,
   then get up from the table and edit CLAUDE.md.
2. **It must not embellish.** Genre pressure runs toward a dramatic cause of death —
   that's hedging's mirror image, overstatement instead of softness, equally false.
   Mechanical guardrail: **no finding without a quote and a line number.** The voice
   narrates evidence; it never manufactures it.

### The banner relay, and why it ended in a hook

The rule "paste the banner into your reply" failed, in the wild, five times across the
first week — and each fix was more prose. The incident (2026-07-17) that produced the
`>>>` relay markers was the fourth. The fifth failure would have been the sixth prose
fix. Instead: a hook.

`hooks/check_banner_relay.py` is a Claude Code Stop hook. It reads the transcript for
"did autopsy produce a banner this turn" and the `last_assistant_message` payload for
"is the art in the reply" (the transcript lags, so the reply must come from the payload
or it false-blocks). If autopsy ran and the art is absent, it blocks the stop once —
`stop_hook_active` guards against looping — and tells the agent to paste it.

This is the durability ranking made concrete: **test > hook > lint > sidecar > comment.**
The relay markers were the sidecar. The hook is the enforcement. The four prose fixes
are the evidence that the sidecar wasn't enough — kept, because deleting them would
invite a sixth.

Scope, and it is a real limit: Stop hooks are Claude Code CLI/desktop only. This does
nothing on web, mobile, Codex, or Cursor. It is defense-in-depth for the surface where
autopsy runs, not reach. Off by default; `hooks/enable.py` registers it idempotently
and reversibly, because editing settings.json is a machine-wide change and a skill
should not do that silently on install.

*Signature robustness note: the hook matches a **majority** of the banner's art lines,
not one signature line. A single line is brittle — it depends on which line is longest
and on the agent pasting that exact one. Majority tolerates a dropped box line and
still refuses a reply that only talks about the banner. Found while writing the fixture:
the first cut keyed on the longest line, which was the REC box, not the ASCII letters.*

### Boot screen

A cold open makes a weekly ritual get run. `Running compaction census...` gets
forgotten.

**Ship the art as a static file the script reads. Never let the model draw it.**
Model-rendered ASCII drifts, mangles, and costs tokens every run. A file boots
identically forever, for free.

*Corrected 2026-07-17: the original said "and `cat` it," meaning the skill should
`cat` the file itself. That was retired in `b8ea720`/`6bfe0cc` — `run.py` prints the
banner on stderr every run, and the skill must NOT `cat` it (a second copy in a tool
result the user never sees). The file lives at `assets/boot-flatline.txt` — not
`boot.txt`, see below. A sidecar that told the reader to run the deleted procedure is
exactly the rot this document's own line on sidecars warns about.*

Pure ASCII only — no box-drawing Unicode. This has to render in Git Bash, PowerShell,
and Windows Terminal without code-page roulette.

**Settled: the run is bookended.** Variant A (the flatline) is the boot. Variant B's
toe tag is the **closing stamp** on the report, with `CAUSE:` filled in.

The tag boots blank and gets stamped at the end. The ritual opens and closes on the
same object, and the empty field creates a small obligation to fill it honestly. A
report that ends with `CAUSE: pending` is a report that found nothing and should say
so plainly.

All four variants ship; `--banner` chooses at launch:

| Flag | Art | Use |
|---|---|---|
| `--banner=flatline` (default) | A | Interactive run. The pulse going flat *is* the thesis. |
| `--banner=tape` | C | Alternate cold open. |
| `--banner=minimal` | D | **Scheduled runs.** Weekly cron shouldn't do the full cold open every Monday. |
| `--banner=none` | — | Piping to a file. |

A is a static file (`assets/boot-flatline.txt`), read and printed by `run.py` on
stderr. The closing tag needs a small script — it carries live fields (subject, intake
path, cause). *File name corrected 2026-07-17: shipped as `boot-flatline.txt`, with
`boot-tape.txt` and `boot-minimal.txt` alongside; there is no `boot.txt`.*

---

## Self-modification

**Autopsy may propose changes to autopsy. Propose — never apply.** Other artifacts can
use a normal approve-the-diff flow. Its own skill file's gate is never optional.

### The specific danger

A self-modifying detector has a cheap way to make findings disappear: **weaken the
detector.** Loosen a threshold, add a filter, retire a category — next report comes
back clean and the loop congratulates itself.

This is uncomfortable because autopsy's *good* instincts point the same direction.
Half its signal-quality work is already false-positive suppression (negation context,
meta-discussion filter, system-text exclusion). Every one made the tool better. The
same move for the wrong reason makes it blind, **and the report looks identical either
way.**

### Zones, by risk

| Zone | Examples | Gate |
|---|---|---|
| Prose, voice, procedure | SKILL.md narration | Normal diff review |
| Detection logic | thresholds, patterns, filters | High bar + fixture test |
| Core invariants | the two-pass rule | Constitutional. Never changed as a side effect of cleanup. |

### The fixture test

The golden set is anonymized synthetic sessions in `tests/fixtures/`, run by
`python -m unittest discover -s tests`. Each detector ships a known-positive proving
it fires and a known-negative proving what it excludes.

**Any proposed change to detection logic runs against them: would this change have
suppressed a finding we already know was true?** If yes, the proposal fails —
regardless of how clean it makes this week's report.

*Corrected 2026-07-17: the original described a `--fixtures` flag pointed at "your own
history" of confirmed reports. That flag was never built; v1 ships static fixtures and
a standard `unittest` discover instead. The recurrence-history version is roadmap, not
present tense.*

### Provenance convention

Every self-proposed change cites the finding that caused it, with a date. The two-pass
rule already does this informally: it explains *why* it exists by describing the run
that discovered it. Make it mandatory and the skill file becomes a lesson ledger with
citations.

### Upstream

A local proposal changes the user's copy. If a finding is *general* — a detector
that's wrong for everyone — the artifact is a PR upstream. The mechanism improves
across users, not just within one.

---

## Proof the mechanism is real

The two-pass rule already **is** this loop, fired once, by accident.

A previous autopsy found pass one reported 0% identity loss and pass two found 42%.
That finding was written into the skill as a permanent instruction. An autopsy produced
a durable artifact that changed how every future autopsy runs.

It has improved itself once already. The build is making it deliberate instead of
annual.

---

## Known issues in the current code

Inherited from `stef-skills`. These are facts verified on 2026-07-17, not guesses.

1. ~~**The cross-session boundary is discarded as noise.**~~ **RETRACTED 2026-07-17.**

   The claim was: the continuation marker is a cross-session boundary signal, and
   `jsonl_parser.py:128` throws it away.

   **This was false.** The marker is the *compaction summary payload*, not a separate
   boundary. Evidence: in session `63653a69`, line 2041 is
   `type=system subtype=compact_boundary`, and line 2042 is `type=user` carrying
   `isCompactSummary: True` with that text. Same adjacency in `d4fd54e1` (2384/2385).
   The "3 files with compact_boundary, 3 files with the marker" observation was one
   boundary type counted twice — they are the same three files.

   Filtering that message out of user-message scans is **correct**. It is not a user
   message. Counting it as one would manufacture false correction pairs. The
   `is_synthetic` filter is the code being right.

   *Lesson, recorded per the provenance convention: the first read was too generous.
   Two adjacent line numbers looked like two events. Pass two opened the lines.*

2. **Everything keys off compaction.** `Message.is_post_compaction` /
   `compaction_index` in the parser; `post_compaction_pairs`,
   `post_compaction_frustrations`, `regressions['post_compaction']` downstream.
   Compaction isn't the emphasis — it's the only boundary the engine can see.

3. **`CompactionBoundary` needs to become `Boundary` with a `kind`.**
   (`compaction` | `session_resume` | `cold_start`), and `is_post_compaction` becomes
   `is_post_boundary` + the kind that preceded it.

4. ~~**The severity score is unconsumed.** `run.py:91-101`. Replace, don't port.~~
   **DONE.** The severity score was dropped in v1; `run.py` now reports how many
   findings need a durable fix. The line reference is stale — those lines are
   `run_full_autopsy` internals today. *Marked done 2026-07-17.*

5. **No corpus-level view.** Sessions are parsed independently. Recurrence detection
   requires ordering sessions by time and matching events *across* them. This is the
   main new engine work.

### What's worth keeping as-is

- `find_sessions` / `parse_session` — solid, handles the JSONL format, filters
  subagent sessions, tolerant of malformed lines.
- The deep scan (tool_use inputs, not just response text). This is the thing that
  finds real violations — words avoided in conversation and used in generation
  prompts three lines later.
- Signal-quality work: negation context, meta-discussion filter, system-text
  exclusion, user flags.
- The two-pass rule.

---

## Scope: the narrow build

v1 generalizes the boundary model and makes findings terminate in artifacts. It does
**not** ship cross-session recurrence detection.

**Reshaped 2026-07-17** after the retraction above. The original v1 was mostly "add
the session_resume boundary kind" — and that item largely evaporated when the evidence
showed the continuation marker is the compaction's payload, not a second boundary. The
inspection that killed it turned up something better.

**Built in v1:**

- **Tool amnesia** (`amnesia.py`) — the best thing in the build. Every compaction
  records `preCompactDiscoveredTools`: the tools the agent had discovered when its
  context died. A finding requires *all three*: known at the boundary, never used
  after, and deferred on that exact work. Ground truth, not inference from phrasing.
  Reports evidence; the skill judges.
- **Boundary model** — `Boundary` with `kind` (`compaction` | `session_resume`),
  retention math, `known_tools`. `is_post_compaction` → `is_post_boundary` + kind.
- **`isCompactSummary` field** instead of string-matching the sentence. The field is
  a contract; the wording is not.
- **Census with real retention** — before/after tokens, percent retained, tokens
  discarded. On the author's own corpus: 3.4% average retention, 2.9M tokens
  discarded.
- **Fixture tests** (`tests/`) — prove each detector fires on a known-positive and
  stays silent on a known-negative. A detector that never fires reports the same zero
  as a healthy system.
- Findings terminate in artifacts, with addresses. The skill proposes; approval gates.
- Persona, boot (A), closing tag stamp (B), `--banner`.
- Self-modification: propose only, zoned, fixture test, provenance.
- Windows + Unix on day one.
- Severity score dropped. The report states how many findings need a durable fix.

**Deliberately not built:** `cold_start` as a message-marking boundary. Every session
begins cold, so marking it would make *every* message post-boundary and the statistic
meaningless. Session entry (`cold` | `resumed`) is session metadata instead. Real
cross-session analysis is the recurrence work, below.

**Honesty constraint on the docs.** v1 can *propose* fixes; it cannot yet *measure
whether a fix held*, because that requires recurrence. The README must describe what
v1 does and put recurrence in the roadmap. Selling the recurrence frame on an engine
that can't measure it is exactly the embellishment the voice guardrails exist to
prevent. Do not oversell.

## Roadmap

### Cross-session recurrence detection (the full build)

Deferred from v1 on purpose. This is the truest expression of the frame — "a lesson
gets learned once" — and the only thing that closes the loop, because it's what can
answer **did the fix hold?**

Requires:
- A corpus-level view. Sessions are currently parsed in isolation.
- Time-ordering across sessions, and candidate clustering.
- The model doing the "is this the same lesson wearing different words" judgment;
  regex cannot.

Unlocks:
- **Recurrence rate over time.** A finding produced a rule in July. Did that lesson
  recur in August?
- Findings that have nothing to do with context loss: a rule that exists and is
  skipped every time; knowledge never written down at all.

### Also deferred

- Default banned-words list (universal AI-isms) so a fresh install has value with zero
  config.
- `autopsy compare` — diff two runs, track improvement or regression.
- Scheduled weekly run, wired to the harness, `--banner=minimal`.

## Settled, for the record

- Public repo, fresh history, autopsy only. No personal history, no inherited branches.
- Keep the voice. Cut the biography.
- MIT.
- Windows and Unix both work on day one: `python` vs `python3` detection must *execute*
  the interpreter, not just resolve the name. Windows ships a `python3` stub that
  resolves on PATH and only advertises the Microsoft Store.

- **No non-ASCII in `.ps1` files.** PowerShell 5.1 reads a BOM-less script as
  Windows-1252. An em dash is UTF-8 `E2 80 94`; the trailing `94` decodes to a curly
  quote in cp1252, which opens a string that never closes. The script dies with
  `TerminatorExpectedAtEndOfString` at a line number nowhere near the em dash.
  *Found 2026-07-17 building this repo. Same family as the python3 stub: it looks
  fine, it dies on Windows.* Pure ASCII in `.ps1` and in the boot art.
