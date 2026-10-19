# ADR-0055: Band data through Health Connect Webhook

- Status: Accepted
- Date: 2026-10-11
- Deciders: Liam

## Context

Liam wears a Xiaomi Smart Band 9 and weighs himself on a Xiaomi scale, both in Mi Fitness on a
Poco X3 NFC (Android 12). Mi Fitness can share steps, sleep, heart rate and workouts with
Health Connect (not weight, it turned out: `docs/runbooks/band-import.md`), which has no
cloud API: something on the phone has to send the data to the Pi. The platform proposal
(`docs/specs/platform-and-health-data-proposal.md`, sections 3, 4 and 7) and `ux-flow-plan.md` (A4) set the direction. Liam's answers (2026-10-11):

- **Data (Q6):** workouts with heart-rate zones; sleep (times and stages); steps and resting
  heart rate (derived from overnight heart rate); weight from the scale.
- **Cardio (Q7):** an imported workout counts only after a confirm tap ("Walk, 46 min, 38 in
  zone 2 - count it?" on Today and in Telegram); one tap saves; undoable.
- **Zones (Q8):** Karvonen (heart-rate reserve) with resting heart rate from sleep or overnight
  data; max heart rate estimated as 208 - 0.7 x age, raised automatically when a workout peaks
  higher, and Liam can type his own.
- **Bridge (Q9):** the open-source Health Connect Webhook app posting to the Pi with its own
  secret; no app of our own yet.
- **Where (Q10, default):** everything stays on the Pi behind the Cloudflare tunnel; raw
  payloads are not kept.

### What the bridge actually sends

Health Connect Webhook ([mcnaveen/health-connect-webhook], v1.9.22, AGPL-3.0; checked
2026-10-11 against [docs/webhook.md], [docs/usage.md] and the code that builds the JSON,
`SyncManager.buildJsonPayload` and `HealthConnectManager`):

- `POST` with `Content-Type: application/json; charset=utf-8`. A body is one object:
  `timestamp`, `app_version`, then one array per data type that has records in this batch
  (`steps`, `sleep`, `heart_rate`, `resting_heart_rate`, `exercise`, `weight` and 25 more).
  Empty arrays are left out, never sent.
- The **Test** button posts made-up records (`MockPayloadBuilder.build`) with a top-level
  `"test": true` that real syncs never send. The ingest checks the secret, notes the sync as
  one that got through (`last_used_at`, not `last_taken_at`) and stores none of it.
- **No built-in authentication:** each webhook can carry custom headers, which is how a secret
  is sent.
- **Schedule:** an interval (at least 15 minutes, WorkManager) or fixed times of day
  (AlarmManager; 08:00 and 21:00 by default), plus "Sync now".
- **Retries:** any 2xx is success; otherwise up to 3 attempts with exponential backoff, then
  the next sync tries again. Each type has a watermark (its last successful sync), and every
  sync reads a rolling 48-hour window and sends records newer than the watermark, so a failed
  sync is sent again, and a refused one forever.
- **Shapes:** times are ISO-8601 UTC (`Instant.toString()`). `steps`: `count`, `start_time`,
  `end_time` (resolution: every record, N-minute buckets or one per local day). `sleep`:
  `session_end_time`, `duration_seconds`, `stages` of `stage` (the AndroidX stage constant as a
  string: 1 awake, 2 sleeping, 3 out of bed, 4 light, 5 deep, 6 REM, 7 awake in bed),
  `start_time`, `end_time`, `duration_seconds`. `heart_rate`: per sample `bpm`, `time`, or per
  N-minute bucket (1 minute by default) `time` (bucket start), `avg`, `min`, `max` and `bpm`
  (= avg). `resting_heart_rate`: `bpm`, `time`. `exercise`: `type` (the AndroidX exercise
  constant as a string, 79 walking, 56 running...), optional `title`, `start_time`,
  `end_time`, `duration_seconds`, optional distance and steps. `weight`: `kilograms`, `time`.
  Most records carry `metadata` with `data_origin` (the writing app's package, e.g.
  `com.mi.health`) and `recording_method`. **The JSON carries no record id** (only the
  Protobuf form does), so a record is identified by its source and start time.

## Decision

### Ingest endpoint

- `POST /api/ingest/health-connect`, the only public route that writes. It takes the JSON form
  above; other fields and types are ignored, unknown keys never fail a payload (the app adds
  types over time).
- **Authenticated by a per-person ingest secret** sent as `Authorization: Bearer <secret>`:
  32 random bytes (`tci_` + URL-safe base64), made on Account ("Band import"), shown once,
  stored only as its SHA-256 (`ingest_keys`, one per person; making a new one replaces the old,
  removing it stops imports). The hash found is compared with `hmac.compare_digest`. Making or
  removing one needs a sign-in in the last 10 minutes and is alerted on Telegram, like the AI
  key (ADR-0047).
- **No cookies:** the route never reads the session cookie and sets none; the request guard's
  origin check passes it because the app sends no `Origin`.
- **Size:** the body is read up to 5 MB and refused beyond (413). The first sync of 48 hours of
  per-minute heart rate with metadata is about 0.7 MB; the cap must stay well above that,
  because a refused sync is sent again forever.
- **Rate limit:** per client address (CF-Connecting-IP from a trusted proxy, as for sign-in),
  at most 60 requests per 10 minutes and 10 failed secrets per 10 minutes, kept in memory;
  429 beyond. The app syncs at most every 15 minutes, so this only stops guessing and floods.
- **Validation:** every record is parsed into a Pydantic model with bounds (heart rate 25-250,
  weight 30-250 kg as for measurements, steps 0-200,000 a day, sessions up to 24 hours,
  times within the last 30 days and not in the future); a record that fails is skipped and
  counted, the rest are saved, and the answer says how many of each were taken. The whole
  payload is rejected (422) only when it is not a JSON object.
- **Nothing that is health data is logged:** the log line says how many records of each type
  came in and how many were skipped, never values or times. The payload is not stored.

### Where the data goes

All tables are per person (`Owned`, ADR-0029), so the export (ADR-0044's zip) includes them
and erasing everything removes them by the `user_id` cascade.

- **`health_days`**: one row per local day (`settings.tz`): `steps` and `resting_hr`.
  - Steps: the app's "Daily" steps resolution is the one to use (runbook). Each sync's step
    records are summed per local day and the day keeps the larger of what it had and that
    sum. A daily record grows during the day and a partial day at the window's edge is
    smaller, so the larger one is always right; with per-record or bucket resolution an
    incremental sync is a partial sum, so the day can be too low but never double counted.
  - Resting heart rate: a `resting_heart_rate` record wins when Health Connect has one;
    otherwise it is derived from heart rate (below).
- **`heart_rate_samples`**: per-minute heart rate (`at`, `bpm`, and the bucket's `low` and
  `high`), unique per person and minute, **kept 8 days**. Needed because a workout and its
  heart rate can arrive in different syncs, and to derive resting heart rate; per-minute rows
  are about 1,440 a day, written once per sync in one transaction. Older ones are deleted on
  each ingest.
- **`sleep_sessions`**: start, end, the local day it ended on, and minutes asleep, awake,
  light, deep and REM (stage constants above; "sleeping" with no detail counts as light).
  Identified by source and start; a session sent again is updated.
- **`imported_workouts`**: start, end, the local day it started on, the Health Connect type,
  what it was as a cardio activity (walk, hike, run, bike, swim, row, stairs; other types
  are kept but never offered as cardio), minutes, average and max heart rate and minutes in
  zones 1-5 from the heart-rate samples in its window, a status (`new`, `counted`,
  `dismissed`) and the workout it was counted as. Identified by source and start; the
  heart-rate figures are filled in again when more samples arrive.
- **Weight** goes to the existing body measurements (`bodyweight`, ADR-0039's
  `measurements`): the first reading of a local day, never replacing a value already there
  (a typed value or the morning weigh-in wins).

### Zones (domain logic, pure)

- Karvonen: zone *n* runs from `rest + reserve x low` to `rest + reserve x high`, with
  `reserve = max - rest` and the bands 50-60, 60-70, 70-80, 80-90 and 90-100% (zone 2 is
  60-70% of reserve). Below 50% is no zone.
- **Resting heart rate** for a night: the lowest per-minute average inside its sleep session,
  or, with no sleep session, between 00:00 and 06:00 local time. The value used for zones is
  the median of the last 7 nights that have one; with none, zones fall back to 60 bpm.
- **Max heart rate:** Liam's own number when he types one in settings (120-230); otherwise the
  higher of the estimate 208 - 0.7 x age (from an optional birth year in settings; 190 without
  one) and the highest heart rate any imported workout reached. Changing either setting
  recomputes the zone minutes of workouts whose heart rate is still kept.
- Zone minutes of a workout: each minute with a sample in the workout's window counts toward
  the zone of that minute's average.

### Counting an import as cardio (confirm before save, ADR-0007)

- An imported workout of a cardio type, at least 10 minutes long, from the last 7 days, that
  would count for at least 5 minutes, is offered on Today (until answered) and once in Telegram
  (a job checks every 10 minutes and sends at most 3 at a time, from today and yesterday only;
  an offer counts as sent only once Telegram took it; nothing is sent while paused):
  "Walk, 46 min, 38 in zone 2 - count it?" with **Count it** / **Not this one** (Telegram buttons carry the import's id only and check the
  sender first, `owner_only`; a stranger's press gets nothing).
- **What it counts as:** zone 2 cardio when it has heart rate and at least as many minutes in
  zone 2 as in zones 3-5, logged as **its zone 2 minutes** (so the week's zone 2 total gets the
  real zone 2 time, not the whole walk); moderate cardio when zones 3-5 dominate, logged as its
  full minutes. Without heart rate, a walk, hike, bike ride, swim or row counts as zone 2 and a
  run or stairs as moderate, for the full minutes.
- One tap saves through the existing cardio log (`services.cardio.log`, `workout_log.save`):
  the planned session when it is on today and today's planned session is that kind, an extra
  otherwise. The log token is derived from the import's id, so a double tap or a second
  surface changes nothing; it is undone with the existing undo, after which the import is
  offered again. "Not this one" marks it dismissed.

### Display

- Home and Progress show last night's sleep, today's and yesterday's steps and the resting
  heart rate (against the usual one) small, and the weight lands in Body by itself.
- The daily check (ADR-0053) suggests the sleep answer from last night's imported sleep
  (7 hours or more: good; 6 to 7: OK; less: poorly), but the answer is always Liam's own tap:
  the web highlights the suggestion and asks to confirm, and the morning Telegram message says
  "Your band: 7 h 20 min asleep last night. That looks like "Slept well": tap it if it's
  right." with nothing ticked. The advice depends on it, so a band estimate never counts
  without a tap.

## Options considered

| Option | Pros | Cons |
| --- | --- | --- |
| Health Connect Webhook to an ingest endpoint on the Pi (chosen) | Open source, no cost from its GitHub releases (runbook step 3), no cloud account, the data goes phone to Pi only | A third-party app on the phone; Android only; no record ids in JSON |
| Our own Android app writing to the same endpoint | Full control, record ids | An app to build, sign and maintain; later (L3) |
| Google Health API (cloud) | No phone app | Doesn't cover Mi Fitness; restricted scopes need Google's verification; 7-day tokens when unverified |
| Protobuf/gRPC delivery from the same app | Record ids and time zones | gRPC through the Cloudflare tunnel and a second protocol stack for one user |
| Store the raw payloads | Re-derive anything later | A health diary of everything the phone knows; Liam chose not to |
| Store per-minute heart rate for good | Re-derive zones with new settings | About 525,000 rows a year on an SD card; 8 days covers late workouts and resting HR |
| Zones as % of max only | Needs no resting HR | Liam chose Karvonen, which fits his own resting HR |

## Consequences

- The threat model gets a row for the ingest endpoint; the runbook
  `docs/runbooks/band-import.md` covers installing and configuring the app on the Poco X3.
- Health data is personal (GDPR Art. 9): never logged, never on the `/share` picture, in the
  export, erased with everything; the privacy notice draft lists it.
- If the app ever sends record ids in JSON, they become the identity instead of source + start.
- **Band data stopping is told on Telegram** (approved 2026-10-12). Every stored sync is noted
  on the person's `ingest_keys` row (`last_used_at`; a refused sync is not), and so is the last
  sync that took at least one record (`last_taken_at`), each at most hourly on its own clock.
  An hourly job tells the person once per gap: "no band data for a day" when no sync got
  through for 24 hours, or "syncing, but nothing new" when syncs get through but none took a
  record for 24 hours; then "arriving again" once records follow. `alerted_at` holds the gap
  told. A new secret starts the clock again; no secret, no alerts. Messages go 08:00-21:00
  local time only and not while paused, and carry no health values. Account shows "Last data
  arrived" from `last_taken_at`. What each message means and what to do:
  `docs/runbooks/band-import.md`.
- **So is one kind stopping while the rest flows** (approved 2026-10-19). Steps, sleep and heart
  rate come every day the band is worn; HC Webhook can drop one it can't read in time
  (Health Connect's read quota) while still sending the others. Each has a `band_feeds` row:
  the last sync that took a record of it, at most hourly, and when its gap was told. A kind
  missing for 48 hours is told once, so one night without the band isn't a gap, then told
  again when it comes back. Never while a gap in all band data is due or told: that message
  covers every kind. A kind never seen counts from when the secret was made; a new or removed
  secret drops the rows. Workouts, weight and resting heart rate aren't watched: the first two
  come when they happen, and resting heart rate is derived from heart rate when it's missing.
- Built as four PRs: ingest and schema; zones; count it; display and runbook.

[mcnaveen/health-connect-webhook]: https://github.com/mcnaveen/health-connect-webhook
[docs/webhook.md]: https://github.com/mcnaveen/health-connect-webhook/blob/main/docs/webhook.md
[docs/usage.md]: https://github.com/mcnaveen/health-connect-webhook/blob/main/docs/usage.md
