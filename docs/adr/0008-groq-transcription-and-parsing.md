# ADR-0008: Groq for voice transcription and fallback parsing

- Status: Accepted
- Date: 2026-09-29
- Deciders: Liam

## Context

Logging is by Telegram voice note. Telegram does not give bots transcripts. Requirements from
Liam: no running cost and little maintenance.

## Decision

Transcribe with Groq's `whisper-large-v3-turbo` and use a Groq-hosted open model for fallback
parsing, both on the free tier (2,000 requests and 28,800 audio seconds per day at time of
writing; expected use is a few requests a day). A dedicated API key, separate from Vybe's.
If Groq is unavailable, the bot asks the user to type the log. Voice files are deleted after
transcription.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Groq free tier (chosen) | Zero cost, best accuracy on numbers, 1-2 s | External dependency, needs internet |
| whisper.cpp on the Pi | Fully local | Tiny model mishears numbers; ~6 s per 10 s audio |
| whisper.cpp on desktop GPU | Fast, accurate | Only when the desktop is on |
| Claude Haiku for parsing | Very accurate | Small cost per call |

## Consequences

- Transcription sits behind an interface so a local backend can be swapped in later.
- Free-tier limits are checked in the Groq client; exceeding them triggers the typed fallback.
