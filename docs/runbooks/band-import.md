# Runbook: band import on the Poco X3

How the Xiaomi Smart Band 9 and the Xiaomi scale reach the coach (ADR-0054):
band and scale -> Mi Fitness -> Health Connect -> Health Connect Webhook -> the Pi.
About 20 minutes, once. Everything happens on the phone except step 4.

## 1. Health Connect

Android 12 doesn't have Health Connect built in (it is part of Android from 14 on).

1. Install **Health Connect** by Google from the Play Store.
2. Open it once. It has no icon of its own on Android 12: open it from the Play Store, or
   Settings > Apps > Health Connect.

## 2. Mi Fitness -> Health Connect

1. Open **Mi Fitness**, sync the band so recent data is on the phone.
2. **Profile** > **Third-party data** (on some versions **Health Connect**) > turn it on.
3. Allow at least: **Steps, Sleep, Heart rate, Exercise (workouts), Weight**. Resting heart rate
   too if it is offered (the coach otherwise works it out from your overnight heart rate).
4. In Health Connect, **App permissions > Mi Fitness** should now show those types as allowed
   to write.

## 3. Health Connect Webhook

1. Install **HC Webhook** (Health Connect Webhook, `com.hcwebhook.app`) from the Play Store.
   It is open source: github.com/mcnaveen/health-connect-webhook.
2. Open it, tap **Grant Permissions** and allow reading: **Steps, Sleep, Heart rate, Exercise,
   Weight** (and Resting heart rate if listed). Nothing else is needed; the coach ignores other
   types.
3. Per-type settings:
   - **Steps resolution: Daily.** One total per day; other settings can undercount a day.
   - **Heart rate resolution: 1 minute** (the default).
   - **Sleep: with stages** (not summary only).
4. Keep the app out of battery optimisation, or syncs stop when the phone sleeps:
   Settings > Apps > HC Webhook > Battery saver > **No restrictions**, and on MIUI also
   **Autostart: on**.

## 4. The address and the secret

1. On a computer or the phone, open the coach > **Account** > **Band import** > **Make a
   secret**. You'll be asked for your fingerprint if you signed in more than 10 minutes ago.
2. The page shows the **address** (`https://<your coach>/api/ingest/health-connect`) and the
   **secret** (`tci_...`), once. Keep the page open until step 5 is done. Lost it? Make a new
   one: it replaces the old one.

## 5. The webhook in HC Webhook

1. **Webhooks** > **Add**: URL = the address from step 4. Delivery format: **JSON**.
2. **Custom headers** > add one: name `Authorization`, value `Bearer ` followed by the secret
   (one space after Bearer).
3. **Sync mode: Interval, 30 minutes** (anything from 15 minutes works; less often saves
   battery). Or **Scheduled** at fixed times, e.g. 07:30, 13:00, 21:00.
4. **Save configuration**.

## 6. Check that data arrives

1. In HC Webhook, tap **Sync Now**.
2. Menu > **Webhook Log**: the newest entry should be **200** with a body like
   `{"taken": {"steps": 2, "heart_rate": 1400, ...}, "skipped": {}}`.
   - **401**: the header is wrong. Check `Authorization` and `Bearer <secret>` with one space,
     or make a new secret.
   - **429**: too many tries; wait 10 minutes.
   - **413**: a sync larger than 5 MB. Check heart rate resolution is 1 minute, not Full.
   - "skipped" above 0 for a type: some records didn't make sense (a clock far off, an
     impossible value) and were left out; the rest arrived.
3. In the coach, **Account** > **Band import** shows "Last data arrived ..." and, after a night
   and a walk, Today shows last night's sleep and offers the walk to count.

The app reads the last 48 hours on every sync and sends only what is new since its last good
sync; a failed sync is sent again next time. If the phone was off for longer than 48 hours,
older data doesn't come across.

## Stopping or moving phones

- Stop: **Account** > **Band import** > **Stop band import**. The phone's next sync gets 401.
- New phone: repeat steps 1-5 there, then **Make a new secret** so the old phone can't send.
- Remove data already imported: there is no per-type delete yet; **Account** > erase removes
  everything (ADR-0044).
