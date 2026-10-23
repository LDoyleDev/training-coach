# Cardio from a photo or screenshot: plan

Status: proposal (2026-10-23). Not built. The form it fills is ADR-0067 (PR #295).

## Goal

A run recorded on a watch or phone app becomes a cardio log without typing. The person takes a
screenshot or a photo of the summary screen, and the coach fills in the minutes, distance,
average and highest heart rate and start time. The person picks how it felt (1-10), checks the
numbers and saves. Nothing is saved without that last tap.

## Rules any option must keep (CLAUDE.md, Security rules)

- **What a model reads is untrusted data.** It is parsed into a Pydantic model with
  `extra="forbid"`, then checked with the same bounds as a typed log (`domain/cardio.py`
  `details_problem`, `services/cardio.problem`). Anything that fails is left blank, not guessed.
- **Prefill only.** The numbers land in the cardio form for the person to check. Effort is
  never filled, because only the person knows how it felt. The model has no tools and triggers
  nothing.
- **The image is never stored.** It stays in memory for one request, isn't logged, and logged
  events say only that a prefill ran. Summary screens show a face, a name and a route map,
  which is a home address, so the less that leaves the phone the better.
- **Size limits:** shrink the image on the phone first (longest side 1600 px, JPEG, metadata
  stripped), and cap any upload at 2 MB.
- **Consent:** the first use explains where the picture or its text goes, and the privacy
  notice (`docs/legal/privacy-policy.md`) says so before anything is sent off the phone.

## Options

| Option | How | Effort | Cost | Risks |
| --- | --- | --- | --- | --- |
| A. The person's own AI over MCP (ADR-0058) | Share the screenshot with their connected Claude or ChatGPT and ask it to log the run; it calls `propose_log` with the cardio details; a card on Today waits for Save | 1 small PR, about half a day: add the ADR-0067 details to the cardio shape `propose_log` accepts and show them on the proposal card | None for the coach | Only for people who connect an AI; that AI's provider sees the image under its own terms |
| B. Read the text on the phone, parse it here (recommended in-app path) | Tesseract.js (Apache-2.0, WebAssembly, loaded only when used) reads the text in the browser. A rule parser picks out `hh:mm:ss`, `km`, `bpm`/"Avg HR"/"Max", pace and a clock time. When it can't, only the text goes to Groq's production text model (`openai/gpt-oss-20b`, already used for unreadable logs) with a JSON schema | 2 PRs, about 2-3 days: (1) OCR, rule parser and prefill UI; (2) the Groq text fallback, consent and the privacy notice | None: Groq's free tier, a few calls a day | About 3-5 MB downloaded the first time it's used; photos of a watch face read worse than screenshots; the CSP may need `wasm-unsafe-eval` for WebAssembly, a security review point; layouts differ by app, which the fallback covers |
| C. Send the image to a Groq vision model | The shrunken image goes to `qwen/qwen3.8-27b` with JSON mode, then the same parse and checks | 1-2 PRs, about 1.5-2 days | Free tier: about 30 requests a minute, 1,000 a day, 8,000 tokens a minute, about 2,048 tokens per image (the published Developer-plan base limits; the free plan's are in the account console) | Groq lists it as a **preview** model, "should not be used in production", so it can go away; the whole picture (face, name, route) goes to a US processor; Groq keeps nothing by default but may log for up to 30 days unless Zero Data Retention is on |

## Recommendation

1. **Now: option A.** It is the smallest change, the coach never sees the image, and it works
   today for anyone with a connected AI.
2. **Next, for everyone: option B.** The picture never leaves the phone. Only text goes out,
   and only when the rule parser can't read it, through a model and processor the privacy
   notice already names. A production model, not a preview one.
3. **Option C only if B's reading turns out poor in practice,** and then with Zero Data
   Retention turned on in the Groq console and a consent note that says the picture leaves the
   phone.

## Sources

- Groq vision: https://console.groq.com/docs/vision (models taking images, 20 MB URL limit,
  3 images a request, 2,048 tokens an image, JSON mode with images)
- Groq models: https://console.groq.com/docs/models (`qwen/qwen3.8-27b` under Preview Models)
- Groq rate limits: https://console.groq.com/docs/rate-limits
- Groq data: https://console.groq.com/docs/your-data (no retention by default; logs up to
  30 days for reliability or abuse; Zero Data Retention available)
- Tesseract.js: https://github.com/naptha/tesseract.js
