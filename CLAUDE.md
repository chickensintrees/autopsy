# autopsy

Forensics for agentic work. Reads session records, finds what the system failed to retain, turns each finding into a durable fix. The report is exhaust; the artifact is the output.

Full reasoning and history: `DESIGN.md`. Read it before changing detection logic — it records what was already tried and what was retracted.

## The fixture gate

**A PR that touches detection logic ships a fixture.** Non-negotiable.

```bash
python -m unittest discover -s tests
```

A detector that never fires produces the same clean report as a healthy system. A change that removes noise and a change that removes findings are the same three-character diff. Fixtures are the only thing that tells them apart.

- New pattern → a known-positive proving it fires.
- New filter → a known-negative proving what it excludes, **and** proof it isn't too broad.
- A new fixture must fail against the old code. One that passes both before and after is decoration.

## Zones

| Zone | Gate |
|---|---|
| Prose, voice, procedure | Normal diff review |
| Detection logic — thresholds, patterns, filters | Fixture gate, above |
| Core invariants — the two-pass rule, "no finding without a quote" | Constitutional. Never changed as a side effect of a cleanup. |

**Autopsy may propose changes to autopsy. It may not apply them.** A self-modifying detector's cheapest path to a clean report is to weaken itself, and the report looks identical either way.

## Evidence standard

**No finding without a quote and a line number.** Overstatement is hedging's mirror image — equally false. The scripts extract evidence; the skill judges. Scripts never render a verdict.

Prefer ground truth to inference. `preCompactDiscoveredTools` records what the agent knew at a boundary; that beats guessing from phrasing. Where the harness recorded a fact, read the fact.

## Conventions

- **The script owns the banner.** `run.py` prints it on stderr every run. Never draw it, never `cat` it, never `--banner=none` except when piping. Echo it into the reply — stderr in a tool result is not the user seeing it.
- **Pure ASCII in the boot art and every `.ps1`.** It has to render in Git Bash, PowerShell, and Windows Terminal without code-page roulette.
- **Cite the finding that caused a change**, with a date. The skill is a lesson ledger with citations; the two-pass rule carries the run that discovered it.
- Compaction is a *cause*, not the category. The category is: a lesson that didn't survive.
- The `isCompactSummary` message after a compaction is that compaction's payload — not a second boundary, not a user message.

## Don't oversell

v1 proposes fixes; it cannot yet measure whether one held. That needs cross-session recurrence, which is roadmap. The README says so. Keep it saying so.
