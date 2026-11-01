# ADR-0085: Safety questions fit for Europe, answered on the device; the app serves the EU and EEA only

- Status: Accepted; supersedes ADR-0046's storage of the answers
- Date: 2026-10-31
- Deciders: Liam

## Context

Liam (31 Oct 2026): "For safety questions, we need whatever is appropriate in Europe. So research
what the right thing to do there is. And we need to make it so that it can't be used outside of
Europe." The app is fitness, not medical: it isn't interested in conditions or diagnoses, and
people take responsibility for what they feel ready to do (ADR-0083).

The research (`any-level-research.md` Part 4) found:
- **No single European form.** ESC 2020 asks for a symptom self-check and medical checks only for
  inactive or high-risk people planning hard exercise. Germany's DGSP 2024 asks for a doctor's
  exam before intense sport, with a dissent from the GPs' society. The UK 2022 consensus and WHO
  2020 say no routine clearance if people build up gradually.
- **PAR-Q+** isn't adopted as a European standard, and its terms need written permission to
  embed it, even unedited.
- **The medical-device line (MDR, MDCG 2019-11 rev.1):** fitness apps aren't medical device
  software, and the stated intended purpose decides. Risk scores, "cleared", illness warnings
  from heart-rate data, and exercise changed for a declared disease would cross it.
- **GDPR:** answers sent to the server are health data needing explicit consent, even if not
  kept, and a stored note implies health (CJEU C-21/23).
- **Liability:** an EU consumer service can't exclude liability for injury (93/13 Annex 1(a), BGB
  §309 Nr. 7a, and from 9 Dec 2026 the Product Liability Directive).
- **Geo-blocking:** Regulation 2018/302 forbids treating EU and EEA countries differently, not
  refusing people outside them.

ADR-0046 stores readiness answers on the server (`readiness_answers`) as consented health data.

## Decision

- **Ten yes-or-no questions in our own words**, traced to ESC, ACSM, DGSP, PAR-Q+ and the UK
  consensus:
  - recent regular exercise; age 35 or over;
  - a heart condition or event; diabetes or kidney disease; blood pressure high and not
    controlled;
  - chest, neck, jaw or arm pain; unusual breathlessness or a racing heart on light effort;
    fainting or dizzy falls;
  - a doctor's "supervised only"; pregnancy or a birth in the last 6 months.

  "Not sure" counts as yes. Research Part 4, Recommendation 1, has the exact wording.
- **One of three notes, none blocking.** The person can always continue:
  - **A "Talk to a doctor before you start"** (symptoms, or a doctor's restriction; for
    pregnancy, "your midwife or doctor");
  - **B "Start easy, and ask a doctor before hard sessions"** (a known condition, uncontrolled
    blood pressure, or inactive and 35 or over);
  - **C "Start easy and build up."**

  Every note shows the stop signs and says "if your health changes, answer again". The
  questions are offered again after 12 months.
- **The answers stay on the device.** The browser works out the note and keeps the answers in
  memory only. Nothing goes to the server but "answered on <date>, version N", and the note at
  most in the device's own storage. The questions are never asked over Telegram. **This
  supersedes ADR-0046's storage:** `readiness_answers` goes, with Liam's OK before the release
  that drops it. The hard-day reminder becomes generic: "If any of your answers suggested asking
  a doctor before hard sessions, do that first."
- **Words:**
  - Never "cleared", "safe for you", "risk score", "screening result" or "medical clearance",
    and no risk calculation.
  - "We suggest" and "you decide".
  - The app states its intended purpose: a general fitness app that suggests exercise from the
    person's choices. It doesn't diagnose, prevent, monitor, predict, treat or alleviate any
    disease, or assess whether anyone is fit to exercise.
  - The terms and notes say what the service is and isn't, and point to a doctor. They never say
    "at your own risk", "no liability" or "you confirm you are healthy", which are void in EU
    consumer law.
- **Stop signs and the talk test** as in the spec (B7). They are general public-health text, the
  same for everyone. The heart-rate option is "Use the talk test, not heart-rate zones", asked
  without a reason (ADR-0083). The research's condition-specific adaptations (Part 2, "Conditions
  that need adapted exercise") are not built: they are where the app would become a medical
  device.
- **The EU and EEA only:** the 27 EU countries, Iceland, Liechtenstein and Norway, and EU
  territories with their own codes (AX GF GP MQ RE YT MF). Not the UK or Switzerland for now:
  each needs its own representative and rules. Enforced in four layers:
  1. **Cloudflare:** one free WAF custom rule blocks other countries, except the machine-called
     MCP and OAuth paths (`/mcp`, `/oauth/token`, `/oauth/register`,
     `/.well-known/oauth-*`). Claude calls those from the US (ADR-0054). Liam applies it; the
     rule is in the research.
  2. **The app:** it reads `CF-IPCountry`, trusted only from `TC_TRUSTED_PROXIES` like
     `CF-Connecting-IP`, and answers browser routes from elsewhere with its own 451 page,
     "Not available in your region".
  3. **Sign-up:** it asks for the country of residence from the list; "Somewhere else" is
     refused. The terms say the service is for people living in the EU or EEA.
  4. **A "last seen in Europe" date** on the account, set only by a signed-in request from that
     account's own session coming from a listed country, as layer 2 reads it (the header
     believed only from `TC_TRUSTED_PROXIES`), so a direct request can't set it. The bot and the MCP endpoint serve an
     account only within 30 days of it, since neither can see where the person is. The check
     sits in one place each (the bot's `owner_only` filter, the MCP auth dependency), tested
     for the allowed and the expired case.
- **Failure modes.** `XX` (unknown) and `T1` (Tor) are refused like any unlisted country. The
  header is believed only from `TC_TRUSTED_PROXIES`; a request that didn't come through them
  (direct LAN or Tailscale access, the container's own health check) or a trusted request
  without the header is let through, so a missing Cloudflare setting can never lock the owner
  out; Cloudflare's rule is the outer gate. A let-through request never counts as seen in
  Europe: only a listed country read through a trusted proxy refreshes the date, so the 30 days
  can't be kept alive from anywhere. Using the site through Cloudflare once a month keeps the
  bot and AI going; a person on LAN or Tailscale alone would lose them after 30 days, which is
  accepted. A signed-in request with `XX` or `T1` gets the 451 page with the reason ("we can't
  tell where you are, for example behind Tor or some VPNs"), never a silent failure. The 451 gate is listed in the route test (ADR-0036),
  and the threat model records the header trust and that the exempt MCP and OAuth paths are
  reachable from anywhere, so their own auth carries the whole burden. The implementing PR
  updates `docs/security/threat-model.md` and `mcp-threat-model.md` with the header, the 451
  gate and the new field.
- **Acceptance items:** `country` and the last-seen date are in the export, erased with the
  account, and named in the privacy notice; tests that a let-through request doesn't refresh
  the date and that `XX`/`T1` get the 451 page with its reason.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Our own questions, answers on the device (chosen) | No health data on the server; fits EU practice; editable wording | Can't remind per person on hard days; the controller question for on-device processing is unsettled (lawyer) |
| Keep ADR-0046's stored answers | Per-person hard-day note | Health data held and backed up; needs explicit consent |
| Embed PAR-Q+ | Recognised | Needs written permission, maybe a fee; not a European standard |
| Europe as the continent (Cloudflare `EU`) | One condition | Takes in countries outside EU law |
| EU and EEA plus the UK and Switzerland | Wider | Two more legal regimes |

## Consequences

- **Before anyone but Liam uses the app:** a clinician checks the question, note and stop-sign
  wording; a lawyer checks the intended-purpose statement, the on-device design, the terms and
  the liability wording.
- **Migrations:** one drops `readiness_answers` (live data: Pi check, backup and Liam's OK).
  Accounts gain `country` and `last_seen_in_europe`. The export and erase follow.
- **The privacy notice** says the answers are checked on the device and never sent.
- **A VPN gets past every layer.** The residence declaration and the terms are the other
  signals, as Cloudflare advises for compliance uses.
- **Travel:** a member outside Europe loses the website. The bot and their AI keep working for
  30 days after the last visit from Europe.

## Addendum (2026-11-01): the safety wording checked against European sources

`any-level-research.md` Part 5 checks every live safety line against European and public-health
sources (ESC 2020, the UK 2022 consensus, PAR-Q+ 2025, EuropeActive, the Irish Heart Foundation,
the Herzstiftung, NHS) and lists what the clinician and the lawyer must still check. It confirms
this decision's approach. EuropeActive's standards name no questionnaire, and "cleared" is
PAR-Q+'s own word, one more reason to keep our own questions and never call them PAR-Q.

Live now, in `frontend/src/session/safety.ts` unless named:

- **Stop signs:** chest pain on its own, with "Call 112 straight away if it's severe, or if it
  hasn't gone after 5 minutes of rest. Don't drive yourself."; faint, dizzy, breathless, racing
  heart or sight; sharp joint or muscle pain; dark urine, "Get medical help the same day"; a
  fever or feeling ill; pregnancy signs, shown to everyone. A "what's normal" line before them
  and "You know your body best: if something feels wrong, stop." after.
- **One reminder line**, the same on the session page, the tests page and the bot, naming 112,
  with "All stop signs" on the web.
- **Talk test:** "Moderate: … but not sing"; a neutral line in the explainer that heart rate can
  mislead with some heart medicines or rhythms, with no question attached.
- **No "safe":** the last set is "On exercises suited to it".
- **No clearance:** the ADR-0046 readiness page intro says "we suggest talking to a doctor first.
  You decide."
- **The intended-purpose statement** on Account, About.
- **The daily check's rest advice** says to rest, not walk, with a fever or feeling ill.

The gate intro, the three notes, the lines shown with every note, the hard-day line, the Q8
clarifier and the AI prompt and guide lines are written in Part 5 for this ADR's on-device build,
and change only with it.
