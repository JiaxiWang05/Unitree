# AI model budget for the Open Day robot: £100 of OpenRouter credit

Prepared 22 November 2026. The full workbook, with every formula and source, is
[`openrouter-budget.xlsx`](openrouter-budget.xlsx).

**Request:** £100 of prepaid credit on [OpenRouter](https://openrouter.ai), one account for models
from OpenAI, Google, Alibaba (Qwen), Mistral, ElevenLabs and others. Prepaid, so spending cannot
exceed it. The team picks the models during development.

Each time a visitor finishes speaking, the robot sends their speech and one camera image, gets a
short text reply, and turns it into speech.

## Cost of one hour of non-stop conversation

| Option | Hears and replies | Sees the camera | Voice | Per hour | Hours for £100 |
|---|---|---|---|---|---|
| A Premium | OpenAI GPT Audio | Gemini 3.8 Flash (GPT Audio takes no images) | ElevenLabs v4 | £4.46 | 21 |
| B High | Gemini 3.8 Flash | same model | ElevenLabs v4 Turbo | £1.35 | 70 |
| C Balanced | Qwen3.8 Omni Flash | same model | Voxtral TTS 3 | £0.36 | 263 |
| D Budget | Qwen3.8 Omni Flash | same model | Kokoro | £0.11 | 844 |

With option A, £100 covers development and testing (about 10 h, £44.64) and one Open Day (about
6 h, £26.78), leaving £23.07 after OpenRouter's 5.5% fee.

## Checked

- Model names, input types and prices: OpenRouter's live model list
  (`https://openrouter.ai/api/v1/models`, and `?output_modalities=speech` for voices), 22 Nov 2026.
- Fee: 5.5% ($0.80 minimum) on credit purchases, non-refundable
  ([OpenRouter FAQ](https://openrouter.ai/docs/faq)).
- Pound to dollar: 1.3125, ECB reference rate, 20 Nov 2026.

## Estimates (editable in the workbook's Assumptions sheet)

240 turns an hour, 7.5 s of visitor speech per turn with the last four turns sent each time,
2,000 text tokens in and 60 out per turn, 27,000 characters of robot speech an hour; audio tokens per
second (OpenAI 10, Gemini 32, Qwen 25) and tokens per image (Gemini 258, Qwen about 400). A real
open-day hour has gaps between visitors, so it costs less. The robot's software logs the real cost
of every conversation.

Visitors' speech and images go through OpenRouter to the chosen provider: cover this in the data
protection and ethics approval.
