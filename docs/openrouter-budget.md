# AI model budget for the Open Day robot: £100 of OpenRouter credit

Prepared 20 November 2026 for the Unitree G1 Open Day greeter (Durham University).

## What is being bought

**£100 of prepaid credit on [OpenRouter](https://openrouter.ai)**, one account that gives access to
models from OpenAI, Google, Alibaba (Qwen), Mistral, ElevenLabs and others at their published prices.
Credit is prepaid, so spending can never exceed what was bought, and unused credit stays on the
account. The team chooses the models during development; the options below show what the credit buys.

## What the robot sends to the models

Each time a visitor finishes speaking, the robot sends:

- **the visitor's speech** (a few seconds of audio, plus the last three turns for context),
- **one camera image** (640 × 480), so the robot can mention what the visitor is wearing,
- **the conversation so far as text**,

and gets back a short text reply, which a **text-to-speech model** turns into the robot's voice.

## Cost per hour of continuous conversation

Assumptions: one hour of non-stop conversation, visitor and robot each speaking half the time, a
new turn every 15 s (240 turns an hour), about 27,000 characters of robot speech an hour. A real
open-day hour has gaps between visitors, so it costs less. Prices are OpenRouter's listed prices in
US dollars per million tokens or characters on 20 November 2026.

| | Premium | Balanced | Budget |
|---|---|---|---|
| Hears + sees + replies | OpenAI GPT Audio (+ a vision model for the image¹) | OpenAI GPT Audio Mini (+ vision model¹) | Qwen3.8 Omni Flash (hears and sees in one call) |
| Speech in (2 h of audio sent an hour) | $2.30 | $0.04 | $0.03 |
| Images (240 frames) | $0.48 | $0.12 | $0.02 |
| Conversation text in and replies out | $1.34 | $0.32 | $0.08 |
| Voice (text to speech) | ElevenLabs v3: $2.16 | ElevenLabs Flash v2.5: $1.08 | Kokoro: $0.03 |
| **Total per hour** | **about $6.30 (£5)** | **about $1.60 (£1.30)** | **about $0.15 (£0.12)** |
| **Hours of conversation for £100** | **about 19 h** | **about 75 h** | **over 700 h** |

Unit prices used: GPT Audio $32 / M audio-input tokens, $2.50 / M text and image input, $10 / M text
output; GPT Audio Mini $0.60 / M input, $2.40 / M output; Qwen3.8 Omni Flash $0.15 / M input,
$0.47 / M output; ElevenLabs v3 $80, ElevenLabs Flash v2.5 $40, Kokoro $0.99 per million characters.
Token counts: about 10 audio tokens per second (OpenAI), 25 (Qwen); 400-800 tokens per image.
OpenRouter adds a fee of about 5.5% when credit is bought; £100 ≈ $120 of usable credit.

¹ The GPT Audio models take audio and text but not images, so with them the camera frame goes to a separate vision model; the image row prices it at the same input rate. Qwen3.8 Omni Flash takes audio, images and text in one request, which is why the robot's software uses it by default.

## How £100 would be used (premium models, the most expensive case)

| Stage | Conversation time | Cost |
|---|---|---|
| Development and testing on the robot (22 Nov - 4 Dec) | about 10 h, including repeated tests | about $63 (£50) |
| Open Day, one full day | about 6 h of actual conversation | about $38 (£30) |
| Contingency (second day, retests, price changes) | | about $20 (£15) |
| **Total** | | **about £95-100** |

With the balanced or budget models the same £100 lasts several open days.

## Notes

- These are estimates; the robot's software logs the actual cost of every conversation, so real
  figures will be available after the first tests.
- Visitors' speech and images pass through OpenRouter to the chosen model provider. This should be
  covered in the project's data-protection and ethics paperwork. OpenRouter lets an account restrict
  requests to providers that do not train on or keep the data.
- Sources: OpenRouter model pages for
  [GPT Audio](https://openrouter.ai/openai/gpt-audio),
  [GPT Audio Mini](https://openrouter.ai/openai/gpt-audio-mini),
  [ElevenLabs v3](https://openrouter.ai/elevenlabs/eleven-v3),
  [ElevenLabs Flash v2.5](https://openrouter.ai/elevenlabs/eleven-flash-v2.5),
  [Kokoro](https://openrouter.ai/hexgrad/kokoro-82m), and the Qwen3.8 Omni Flash listing.
