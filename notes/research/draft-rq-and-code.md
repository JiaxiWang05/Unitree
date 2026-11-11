# Draft sections (RQs, sample sizes, code change) — working copy for the paper plan

## Shared measures (all RQs)

The robot already moves every visitor through fixed steps, so the log gives a funnel:

noticed → invited (opener played) → accepted → chatting → ended (goodbye / walked away / time cap / long silence / error)

| Measure | Plain meaning | Where it comes from |
|---|---|---|
| Invitation acceptance rate | Of the people the robot invited, how many came: they replied, or stepped onto the talk spot, within the 4 s answer window | `state` records: `open -> converse` with reason `they replied` or `stepped onto the spot` |
| Weak acceptance (secondary) | Kept facing the robot for 1.5 s (the robot then starts talking) | reason `kept facing` |
| Time to accept | Seconds from the end of the invitation to accepting | state timestamps |
| Conversation length | Seconds from the start of the chat to the goodbye line | `converse` → `close` |
| Visitor turns | How many times the visitor spoke | `visitor` events in `events.jsonl` |
| Drop-off | Left without a goodbye (nobody there for 4 s), and where in the funnel people leave | close reason `nobody there`; `noticed -> idle` reasons |
| Talk time per invitation | Conversation length with 0 for people who did not come | combined |
| Optional questionnaire | 2-minute tablet survey after the chat | separate, linked by visit number or time |

Why "talk time per invitation": if the personal opener attracts more hesitant people, the people who come in the two arms are no longer comparable, so comparing chat length only among people who came can mislead. Counting zeros for people who did not come keeps the comparison fair (the randomisation still holds).

## Sample-size numbers (two-sided alpha .05, 80 % power, normal approximation)

RQ1 acceptance, generic -> personal:
- 30 % -> 40 %: 356 per arm, 712 invitations (+10 % for groups/repeat visitors: 784)
- 30 % -> 45 %: 163 per arm, 326 (359)
- 30 % -> 50 %: 93 per arm, 186 (205)

RQ2 start rate, wait -> speak first:
- 5 % -> 25 %: 49 per arm, 98 (108)
- 10 % -> 30 %: 62 per arm, 124 (137)
- 10 % -> 25 %: 100 per arm, 200 (221)

RQ3 talk time / turns (log scale), Cohen's d:
- d = 0.3: 176 per arm, 352 chats
- d = 0.4: 100 per arm, 200 chats
- d = 0.5: 64 per arm, 128 chats

Throughput model: refused invitation ~10 s, accepted chat ~90 s.
- 25 % acceptance: ~120 invitations/h max, 30 chats/h
- 35 %: ~95/h, 33 chats/h
- 50 %: ~72/h, 36 chats/h

Supply (5 effective hours, 50 % of noticed people reach invitation range):
- 150 passers-by/h: 19 (5 % green) – 38 (10 % green) green invitations/day
- 300/h: 38 – 75
- 600/h: 75 – 150
- anyone eligible: limited by the robot itself, roughly 300–500/day

## Code change (tested on a copy, 151 tests pass; patch in this folder)

Files: greeter/dialogue/machine.py, prompts.py, app.py, clips.py, cli.py; tests/test_dialogue.py, tests/test_e2e.py.
Turn on: GREETER_CONDITIONS=personal,generic GREETER_SEED=20270601 (default "personal" = today's behaviour).
