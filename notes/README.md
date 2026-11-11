# Notes

Working notes from the Claude Code sessions that built this project, kept so a new session
can pick up the history. They are records, not instructions; where they disagree with the
code or `HANDOVER.md`, the code and the hand-over win.

## build/

| File | What it is |
|---|---|
| `build-log.md` | Running hand-over log of the greeter build, 17 Oct to 2 Nov 2026: design decisions, deviations from the design doc, what was verified and what wasn't, procurement findings (camera, cable, mic), bracket history. Paths in it point to a scratch folder that no longer exists; the files themselves are in this repo |
| `helmet-trial-feet-and-pages.md` | How the head-mount trial feet were measured from Unitree's model (4 Nov) |
| `head-arch-v2.md` | Unitree's official head camera mount compared with ours, and the v2 changes (8 Nov) |

## research/ (the Open Day paper plan)

| File | What it is |
|---|---|
| `paper-plan-handover.md` | Start here: summary of the paper plan and of the files below |
| `lit-scan.md` | Related-work scan: 51 references, synthesis, gaps, cautions |
| `venues-deadlines.md` | Venues and deadlines with source links (checked 3 Nov 2026) |
| `ethics-checks.md` | Durham ethics / ICO / OpenAI findings and a paste-ready checklist |
| `draft-rq-and-code.md` | Working draft of the research questions and sample sizes (the paper plan doc supersedes it) |
| `opener-randomisation.patch`, `apply_opener_patch.py` | Study code change: per-visitor opener conditions (`--conditions personal,generic --seed N`) and state logging. **Not applied.** Written against the 3 Nov code, before `--invite anyone/green` and the `hey_there` clip were added, so it will not apply cleanly now: re-do it by hand on the current code if the study needs it |

The paper plan itself is a private Claude document: https://claude.ai/artifact/YVEeY4ABvZDPSY1kt561YR
