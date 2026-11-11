# Paper plan hand-over (2026-11-04)

Deliverable: Claude Docs doc "G1 Open Day greeter: paper plan"
https://claude.ai/artifact/YVEeY4ABvZDPSY1kt561YR (private until the user shares it)
Sections: summary (+ Chinese), related work (about 40 checked refs), 3 RQs with sample sizes, venues + timeline drawing,
ethics checklist, code change, prep checklist, open questions for the supervisor, sources.

## Files in this folder
- lit-scan.md: full related-work scan (51 refs, synthesis, gaps, cautions).
- venues-deadlines.md: all venue deadlines with source URLs (checked 3 Nov 2026).
- ethics-checks.md: Durham / ICO / OpenAI findings + paste-ready checklist A-K.
- opener-randomisation.patch: unified diff against the project as of 3 Nov 2026; `patch -p1` from the repo root
  (dry run on a fresh copy on 4 Nov applies cleanly), or run apply_opener_patch.py <repo dir>.
- apply_opener_patch.py: exact-string patch script (asserts each anchor matches once).
- draft-rq-and-code.md: working draft of the RQ/sample-size numbers (superseded by the doc).

## Code change status
Not applied to the project. Tested on a copy: 151 tests pass (148 old + 3 new), Python 3.8 grammar OK.
Turn on: GREETER_CONDITIONS=personal,generic GREETER_SEED=<n>. Default "personal" = unchanged behaviour.
Adds: per-visit arm drawn in shuffled blocks of 4 at NOTICED; generic opener/close/fallback clip ("hey_there");
state transitions -> day trace.jsonl as {"kind":"state","data":{visit, condition, from, to, reason}};
first line of each visit's events.jsonl = {"kind":"visit","data":{visit, condition}}; --conditions/--seed flags.

## Findings about the current code worth knowing
- README says events.jsonl holds states; the code never wrote them (only the text log). The patch fixes this via trace.jsonl.
- At NOTICED the notice frame goes to OpenAI twice (session open + out-of-band opener) before the passer-by has
  agreed to anything. Ethics plan proposes naming clothing on the robot and sending text only.
- SYSTEM_PROMPT says "adult students"; Open Day visitors are often 16-17.
- botsort_reid.yaml has with_reid: True (short-term appearance matching), so the ethics form must not claim
  "no re-identification of any kind".
- recorder.py saves a frame every 2 s and everyone's tracks at 5 Hz; a study mode should drop both.

## Key external facts (verified by me on 4 Nov 2026)
- HRI 2027 (Santa Clara, 8-12 Mar 2027): demos + SDC 20 Nov 2026, LBR 8 Dec 2026 (non-archival). ICSR 2027 papers 15 Feb 2027.
  RO-MAN 2027 (Waterloo): dates not announced. Durham 2027 Open Days / POVDs: not announced.
- OpenAI Services Agreement 3.3(c): no minors without parent/guardian consent. Realtime: 30-day abuse logs, ZDR-eligible,
  EU residency processes Realtime, UK region does not. Usage policies new version effective 20 Nov 2026.

## Update 2026-11-04: January route (user: ignore ethics, done by early December, publish around January)
Added doc section "January route: a technical paper" (after the Summary). Verdict: yes as a technical system paper,
no visitor data: HRI 2027 LBR 8 Dec 2026 AoE (decision 13 Jan 2027, 4 pages, anonymous, poster in Santa Clara).
Other options checked 4 Nov: HRI demos 20 Nov; RSS 2027 extended abstract 4 Dec 2026 (5 pp + 1 refs, two-stage,
final 16 Apr 2027, Athens 6-11 Jul); RA-L rolling (6+2 pp, first decision <= 3 months); IROS 2027 Florence
~1 Mar 2027 only on third-party listings (iros2027.org did not resolve); ICRA 2027 closed 15 Sep 2026.
Contributions: approach-time out-of-band opener (latency hiding), engagement sensing with own sensors (chest webcam
+ head D435i floor sensor), on-board S2S architecture with fallbacks, open chest mount + code.
Experiments E1-E6 (authors as scripted walkers): opener timing, reply delay (quiet vs crowd noise; realtime vs mini vs
Gemini vs local cascade), perception accuracy + FPS, talk-spot confusion matrix, failure recovery, cost/load.
Code still needed: timestamps for speech end / first reply audio / playback start and notice / opener ready / bid,
plus a log-to-table script. Main risk: never run on the G1 yet; needs to run by ~15 Nov.
