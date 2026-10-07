# Proposal: a web app beside Telegram, a standalone app, and wearable health data

Status: **proposal for discussion, not agreed.** Nothing here changes the product spec or any
ADR until Liam answers the questions at the end. Research date: 2026-10-07; provider terms
change often, so anything marked *verify* gets checked again before it becomes an ADR.

## 1. Where we are

- One user (ADR-0009), Telegram-first, one process on a Raspberry Pi 5 with SQLite (ADR-0002,
  0003, 0010). The dashboard is planned to sign in through Telegram (ADR-0012).
- The code is already split so that a second front end is cheap: `bot/` and `api/` are thin
  adapters over `services/` and `domain/`, and import-linter enforces it. Logging, targets,
  progression, bests and backups don't know about Telegram.
- What's missing for a web app: sign-in without Telegram, web screens for the daily loop
  (today, log and confirm, progress, settings), and a way to notify without Telegram.

## 2. Three levels of "an app"

Each level builds on the previous one; we can stop at any of them.

| | L1. Your web app | L2. Invite-only, a few people | L3. A public app |
| --- | --- | --- | --- |
| Who | You | You plus family or friends you invite | Anyone, from the app stores |
| Where it runs | The Pi | The Pi (dozens of users is fine) | EU cloud (managed Postgres, backups, monitoring) |
| Telegram | Optional; same data both ways | Optional per person | Optional |
| Health data from phones | Bridge apps push to the Pi (section 4) | Same, per person | Our own app reads Health Connect / HealthKit |
| Legal | Your own data: no GDPR duties to others | You're the controller of their health data: consent, privacy notice, DPIA | Full Art. 9 GDPR, DPIA, store health-data policies, support |
| Rough effort | 1 phase | +1 phase (multi-user data model) | Several phases, plus ongoing cost and review |

### L1. A web app without Telegram (recommended next)

- **Same app, two front ends.** The React dashboard becomes a full PWA (installable on the home
  screen, works offline for viewing): Today with targets, log by typing or speaking, the same
  confirm-before-save screen, progress, settings. Telegram keeps working; both write to the
  same services, so a workout logged in one shows in the other.
- **Voice in the browser.** The browser records audio (MediaRecorder) and posts it to the API,
  which uses the existing Groq pipeline and limits (ADR-0008, 0023). Nothing new on the model
  side.
- **Sign-in.** Passkeys (WebAuthn: Face ID, fingerprint, or a security key) as the main way in,
  no passwords. ADR-0012's Telegram sign-in stays as a second way, and is also how the web app
  works as a Telegram Mini App. Recovery: a one-time login link from the bot, or a printed
  recovery code.
- **Notifications without Telegram.** Web Push from the Pi (VAPID keys, no third party besides
  the browser's push service). It works on Android, and on iPhone (iOS 16.4+) only once the web
  app is added to the home screen; Apple kept home-screen web apps in the EU after reversing its
  2024 plan to drop them. Per-channel settings: morning message by Telegram, push or both.
- **Code shape.** A `notify` service with Telegram and Web Push behind one interface, used by
  the morning message, nudge, weekly review and backup alerts. New `api/` routes over the
  existing services; no logic copied from `bot/`.
- **Security.** New internet-facing writes (logging over HTTP), so: passkey or session auth on
  every route, CSRF protection, rate limits, the confirm token pattern from the bot, and new
  threat-model rows. The public plan page stays as it is (ADR-0019).

### L2. Invite-only multi-user

- Every table gets a `user_id`, and every query is scoped by it (tests enforce it, the way
  import-linter enforces layering). Plans become per user (each person can have their own
  `plan.toml` or start from yours).
- Invites by link; each person signs in with a passkey and can connect their own Telegram.
- Groq usage grows per person; still free-tier sized for a handful of people (*verify* limits).
- You become the controller of other people's health data: written consent, a short privacy
  notice, export and delete, and a DPIA (German regulators treat health apps as high-risk
  processing).
- **Cheap now, expensive later:** adding a `users` table with your account as the only row when
  the web sign-in lands makes L2 a migration rather than a rewrite. Recommended either way.

### L3. A public app

- **Why a native app at all:** Apple Health (HealthKit) and Android's Health Connect can only
  be read by an app on the phone; there is no cloud API for either. A wrapper (Capacitor)
  around the same React app gives us one codebase for iOS, Android and the web, plus plugins
  for HealthKit and Health Connect.
- Hosting moves to an EU cloud; the Pi stays your personal instance or goes away.
- Store review: Google Play requires a Health Connect permissions declaration; Apple has
  HealthKit rules (no health data for advertising, a privacy policy, a purpose for each type).
- GDPR Art. 9: explicit, specific consent per data category; DPIA; data processing agreements
  with every provider; German regulators also expect health apps to be usable without cloud
  features where possible.
- Stay a fitness app, not a medical one: no diagnoses or treatment advice, or the EU Medical
  Device Regulation applies.
- This is a business decision (cost, support, liability) more than a technical one. Not
  recommended until L1 has been used daily for a while.

## 3. Health data worth having

Chosen for this plan (Huberman's protocol has three cardio days and leans on sleep), not
everything a watch can measure.

| Metric | Why it matters here | Typical source |
| --- | --- | --- |
| Cardio workouts: type, duration, distance, average and max heart rate | Thu moderate cardio, Fri high intensity, Sun long zone 2 can be logged automatically | Watch, Strava |
| **Time in heart-rate zones** per workout and per week | Zone 2 minutes vs the plan's 45-75 min Sunday; Thursday's 75-80% effort | Watch (or computed by us from heart-rate samples) |
| Sleep: bed time, wake time, duration, stages | Regularity matters as much as length; recovery context for hard days | Watch, ring |
| Steps per day | General activity on rest and recovery days | Phone, watch |
| Resting heart rate, HRV | Trends show fitness and fatigue; a raised RHR before a hard day is worth a note | Watch, ring |
| VO2 max estimate | The best single marker of cardio fitness; slow trend | Watch |
| Weight, body fat | Already planned as manual measurements (2-B); a smart scale fills them in | Scale |
| SpO2, respiratory rate, skin temperature | Illness early warning; low priority | Watch, ring |

Not proposed: GPS routes (privacy, little value here), nutrition (separate product), ECG and
blood pressure (medical territory).

**Zones.** Watches use different zone models. To compare weeks fairly, we'd store the raw
heart-rate samples or the per-zone minutes plus the model used, and compute our own zones from
your max heart rate (tested, or estimated) and optionally resting heart rate (Karvonen). Zone 2
is roughly 60-70% of max heart rate, the "can still talk" pace.

## 4. Ways to get the data in

| Route | Covers | Fits | Notes |
| --- | --- | --- | --- |
| **Google Health API** (cloud, OAuth) | Fitbit and Pixel Watch today | L2-L3 with a Fitbit or Pixel | Replaces the Fitbit Web API, which switches off on 2026-10-30. Restricted scopes: production use needs Google's verification and a security assessment (weeks). Unverified "testing" apps get refresh tokens that expire after 7 days, so a personal setup means re-consenting weekly. Polling; webhooks are announced but not there yet (*verify*). |
| **Health Connect** (on the Android phone) | Anything that writes to it: Samsung Health, Fitbit, Oura, Withings, many others (*verify* your watch's app writes to it) | L1 via a bridge app; L3 via our app | No cloud API. For L1, the open-source "Health Connect Webhook" app reads chosen types and POSTs them to a URL on a schedule. Google Fit's APIs are being shut down in 2026; Health Connect is the replacement on phones. |
| **Apple Health** (on the iPhone) | Apple Watch, plus anything that writes to Apple Health | L1 via a bridge app; L3 via our app | No cloud API. For L1, "Health Auto Export" (premium subscription) POSTs JSON to a URL on a schedule. |
| **Vendor clouds** | Oura (OAuth), Polar AccessLink (free), Withings (free plan, starts capped at 10 users), Whoop, Strava (workouts and heart-rate streams) | L1-L3 | One integration each. Garmin's Health API is for approved businesses only and was reported paused in 2026 (*verify*). Strava's 2026 API terms narrowed third-party use (*verify* before relying on it). |
| **Aggregators** | 100+ devices behind one API | L3 | Terra from about $399/month, Junction about $0.50 per user per month (minimum $300). Open Wearables is MIT-licensed and self-hosted: free, but we run and maintain it. |

### Recommendation

- **For you (L1):** an **ingest endpoint on the Pi** that accepts pushes from a bridge app on your
  phone (Health Connect Webhook on Android, Health Auto Export on iPhone). No cloud OAuth, no
  provider approval, no cost on Android; data goes from your phone to your Pi only.
- One **normalized schema** in our database (daily metrics, sleep sessions, workouts with zone
  minutes), deduplicated by source and the source's own id. Raw payloads are not kept.
- If L3 ever happens, our own app writes to the same endpoint and schema, so nothing built for
  L1 is thrown away.
- **Security for the endpoint:** a per-device token stored hashed (like share links), strict
  schema validation and size limits, rate limiting, payloads never logged, and a new
  threat-model row. Health metrics stay out of share views by default.

### What it unlocks in the plan

- **Cardio sessions log themselves.** When a watch workout lands on a cardio day (or matches the
  next cardio session in the queue), the bot asks "Log Sunday's zone 2 from your watch: 62 min,
  48 in zone 2?" with Save / Not this one. Confirm before save, as with every log (ADR-0007).
- **Targets for cardio:** zone 2 minutes per week, Thursday time at 75-80%, Friday's intervals
  done; shown next to strength volume in the weekly review.
- **Context, not alarms:** "Resting heart rate 6 above your 30-day average" on the morning
  message, never "don't train today".

## 5. The combined dashboard

Builds on D1 (the dashboard design still comes first). Screens:

| Screen | Shows |
| --- | --- |
| Today | Today's session and targets; last night's sleep; resting HR and HRV vs your trend |
| Week | Sessions done vs planned; hard sets per muscle vs 10-20; zone minutes vs targets; steps; sleep regularity (bed and wake times as a strip) |
| Training | Per exercise: ladder step, bests, sets over time |
| Cardio | Zone distribution per week; VO2 max trend; resting HR trend |
| Sleep | Duration and timing over 4-12 weeks; consistency score |
| Body | Weight, girths, photos (owner only), baseline vs retests |

The weekly review message (D6) is a text version of the Week screen.

## 6. Suggested order

1. **Phase 2 as drafted**, with 2-F/2-G widened to L1: passkey sign-in, a `users` table with one
   row, the PWA with logging, Web Push. Telegram keeps working.
2. **Phase 3: health data** (new): ingest endpoint and schema, cardio auto-logging with confirm,
   zone targets, sleep and steps on the dashboard and in the weekly review.
3. **Later, only if wanted:** L2 (invites, per-user plans, consent) and L3 (native wrapper,
   cloud, store review).

## 7. Questions for you

Each has my recommendation; a one-line answer per question is plenty.

1. **Devices.** Which phone (Android or iPhone), which watch or ring, and do you use a smart
   scale? This decides the data route more than anything else.
2. **Audience.** Just you (L1), you plus a few invited people (L2), or a public app (L3)? And is
   L3 a real goal or a maybe? *Recommendation: build L1 now, ready for L2.*
3. **Telegram's role.** Should the web app do everything Telegram does (my recommendation), or
   be for viewing only with Telegram staying the daily tool?
4. **Sign-in.** Passkeys plus Telegram sign-in, with a bot-sent link to recover? Or do you want
   email sign-in too (needs a mail provider)?
5. **Notifications.** Is Web Push enough when not using Telegram (on iPhone, only after adding
   the app to the home screen)?
6. **Which health data.** Of the table in section 3, which matter to you? *Recommendation:
   workouts with zone minutes, sleep times, steps, resting HR, HRV, VO2 max, weight.*
7. **Cardio auto-logging.** Should watch workouts complete the plan's cardio sessions, with a
   confirm step?
8. **Zones.** Do you know your max heart rate, or should we estimate it and offer a test?
   Percentage of max, or Karvonen (uses resting HR)?
9. **Bridge apps.** OK to use a third-party bridge app on your phone for L1 (open source on
   Android; a paid subscription on iPhone), rather than building our own phone app first?
10. **Where data lives.** Keep everything on the Pi behind the Cloudflare tunnel, including
    health data from the phone? Any data you never want stored?
11. **Budget.** Any monthly spend you're OK with (aggregators, a cloud host, Apple's developer
    fee at about $99/year)? *Default: zero, as today.*

## Sources

- Google Health API and the Fitbit Web API shutdown:
  [Google Health API newsletter](https://developers.google.com/health/newsletters),
  [scopes](https://developers.google.com/health/scopes),
  [OAuth setup](https://developers.google.com/health/setup),
  [Terra's guide to the new API](https://tryterra.co/blog/everything-you-need-to-know-about-google-health-new-api),
  [shutdown date moved to 30 October](https://gadgetsandwearables.com/2026/09/28/fitbit-api-migration-deadline-october-30/)
- Google Fit shutdown and Health Connect:
  [Fit migration guide](https://developer.android.com/health-and-fitness/health-connect/migration/fit),
  [what replaces the Fit APIs](https://sahha.ai/blog/google-fit-api-sunset-migration/),
  [Health Connect data types](https://developer.android.com/health-and-fitness/health-connect/data-types)
- Google OAuth testing mode (7-day refresh tokens, 100 users):
  [Unipile](https://www.unipile.com/google-oauth-refresh-token/)
- Bridge apps:
  [Health Connect Webhook](https://github.com/mcnaveen/health-connect-webhook),
  [Health Auto Export](https://apps.apple.com/app/id1115567069),
  [Apple Health ingester](https://github.com/irvinlim/apple-health-ingester)
- Vendor APIs:
  [Garmin Health API](https://developer.garmin.com/gc-developer-program/health-api/),
  [Garmin program paused (Terra)](https://tryterra.co/blog/garmin-connect-developer-program-pause),
  [Strava rate limits](https://developers.strava.com/docs/rate-limits/),
  [Oura API](https://support.ouraring.com/hc/en-us/articles/4415266939155-The-Oura-API),
  [Polar AccessLink](https://www.polar.com/blog/introducing-polar-open-accesslink-api/),
  [Withings API plans](https://developer.withings.com/developer-guide/v3/withings-solutions/withings-api-plans/)
- Aggregators:
  [Terra alternatives and pricing](https://sahha.ai/compare/terra-alternatives/),
  [Open Wearables](https://openwearables.io/compare)
- Web apps on iPhone:
  [PWA push on iOS](https://www.magicbell.com/blog/pwa-ios-limitations-safari-support-complete-guide),
  [Apple keeps home-screen web apps in the EU](https://9to5mac.com/2024/03/01/apple-home-screen-web-apps-ios-17-eu/)
- GDPR and health apps:
  [German regulators on health apps](https://www.oppenhoff.eu/en/news/detail/health-apps-data-protection-and-data-security),
  [Art. 9 and consent](https://www.themomentum.ai/blog/gdpr-consent-requirements-health-data)
