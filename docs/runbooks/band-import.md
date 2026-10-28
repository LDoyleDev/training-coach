# Runbook: band import on the Poco X3

How the Xiaomi Smart Band 9 reaches the coach (ADR-0055, ADR-0070):
band -> Mi Fitness -> Health Connect -> the Coach reader -> the Pi.
About 15 minutes, once. Everything happens on the phone except step 4.

## 1. Health Connect

Android 12 doesn't have Health Connect built in (it is part of Android from 14 on).

1. Install **Health Connect** by Google from the Play Store.
2. Open it once. It has no icon of its own on Android 12: open it from the Play Store, or
   Settings > Apps > Health Connect.

## 2. Mi Fitness -> Health Connect

1. Open **Mi Fitness**, sync the band so recent data is on the phone.
2. **Profile** > **Third-party data** (on some versions **Health Connect**) > turn it on.
3. Allow at least: **Steps, Sleep, Heart rate, Exercise (workouts)**. The coach works out
   resting heart rate from your overnight heart rate. Mi Fitness doesn't offer to write
   **Weight** to Health Connect, so weigh-ins on the Xiaomi scale don't arrive this way: type
   them under **Body**.
4. In Health Connect, **App permissions > Mi Fitness** should now show those types as allowed
   to write.

## 3. The Coach reader

The coach's own app (`android/` in the repo, `docs/specs/android-reader.md`). It reads only
what changed in Health Connect since its last good sync and posts it to the coach.

1. Install **Obtainium** (from its GitHub releases), add the training-coach repository's
   releases with pre-releases included, filtered to tags starting `android-v`, and install
   **Coach reader**. Obtainium offers each new version; a release is made when Liam approves
   it on GitHub.
2. Open the reader and tap **Allow Health Connect to read ...**. Allow **Steps, Heart rate,
   Sleep and Exercise**, nothing else: it never writes. After an update that reads a new type,
   the same button asks for just that one.
3. **In the background:** if this phone's Health Connect lets apps read in the background, the
   button also asks for that, and the reader then syncs by itself about every 12 hours
   (Android picks the time, so it can come hours late). If not, the screen says so and the
   reader syncs only when you open it and tap **Sync now**.
4. Keep the reader and **Mi Fitness** out of battery optimisation, or MIUI stops them:
   Settings > Apps > (each app) > Battery saver > **No restrictions**, and **Autostart: on**.
   In the recent-apps view, long-press both and lock them. For the reader, also turn off
   **Pause app activity if unused** (Android 12 cancels background jobs of an app that is
   rarely opened).

## 4. The secret

1. On a computer or the phone, open the coach > **Account** > **Band import** > **Make a
   secret**. You'll be asked for your fingerprint if you signed in more than 10 minutes ago.
2. The page shows the **secret** (`tci_...`) once. Copy it, paste it into the reader under
   **Secret** and tap **Save the secret**. The reader keeps it encrypted and never shows it
   again. Lost it? Make a new one: it replaces the old one. The reader has the coach's address
   built in, so there's nothing else to type.
3. Tap **Test the secret**: "The secret works" means the coach took it. **401**: the secret is
   wrong or was replaced; make a new one.

## 5. Check that data arrives

1. Open **Mi Fitness** and let it sync the band, then open the reader and tap **Sync now**.
   Keep the screen open until it finishes: Health Connect lets an app read only while it is on
   screen, unless it reads in the background (step 3.3). The result says, per type, what was
   sent and how many Health Connect reads it took: a normal sync takes four, a type's first
   sync two more (it reads the last day once).
   - **401**: the secret is wrong or was replaced (step 4).
   - **429**: too many tries; wait 10 minutes. If the phone isn't syncing that often, someone
     else may have the secret: make a new one.
   - **413** or **422**: the coach refused the sync. The reader tries it again, and after three
     refusals in a row skips it and says how many posts were lost.
   - "Health Connect's read limit was reached": Health Connect's quota. It names the read that
     hit it; try again later. "Stopped after 20 Health Connect reads": the reader's own limit,
     so a read that doesn't end can't use up the quota; nothing was sent.
   - "Couldn't reach the coach": no network, or the Pi is down.
2. **In Health Connect, last 7 days** shows, per type, how much Health Connect has and which
   apps wrote it (four reads, only when tapped). Mi Fitness should be there for steps, heart
   rate, sleep and exercise.
3. Nothing from Mi Fitness for a type: in Mi Fitness, turn sharing with Health Connect off and
   on again for that type (step 2.2), sync the band and look again. Data that stops at the last
   time you opened Mi Fitness, and catches up when you open it: Mi Fitness writes only when it
   syncs with the band. Step 3.4 doesn't change that (on 24 Oct it was already set), so open
   Mi Fitness once or twice a day, or have an automation app open it, before the reader syncs.
4. In the coach, **Account** > **Band import** shows "Last data arrived ..." and "From the Coach
   reader <version>". After a night and a walk:
   - **Home** and **Progress** show last night's sleep, today's steps and resting heart rate;
   - **Today** (and Telegram) offers the walk to count;
   - the daily check has your sleep answer ready (still one tap on the web).

A sync sends only what is new since the last good one, and nothing moves on until the coach has
it, so a failed sync is sent again next time. A night or workout deleted in Health Connect is
deleted on the coach too, unless you already counted the workout. A background sync that sent
nothing is shown on the reader's screen the next time you open it.

## When the coach says band data stopped

The coach checks every hour and tells you once per gap, in Telegram, between 08:00 and 21:00
(not while paused). The rules are in ADR-0055, Consequences. The messages name the app that
sent the last sync.

- **"No band data has arrived for a day."** No sync has reached the coach for 24 hours: the
  phone, the reader or the secret. Open Mi Fitness and sync the band, then the reader and tap
  **Sync now**; its result says what went wrong (step 5.1). Background syncs stopped: check
  step 3.4.
- **"The Coach reader is syncing, but nothing new has come from the band for a day."** Syncs
  arrive but carry no records: the band isn't reaching Health Connect. Open Mi Fitness and sync
  the band; check that Mi Fitness still shares with Health Connect (step 2) and **In Health
  Connect, last 7 days** (step 5.2). Taking the band off for a day causes this too.
- **"Band data is arriving again."** Records came in after one of those; nothing to do.
- **"No sleep or heart-rate data has come from the band for two days, though other band data
  has."** (or steps): syncs carry some kinds but not these. Tap **Sync now** and read the
  result per type, then check the reader may still read them (Health Connect > App permissions
  > Coach reader) and that Mi Fitness still writes them (step 5.2). Workouts and weight aren't
  checked: they come when they happen.
- **"Sleep data is arriving again."** (or steps, heart rate): that kind came back.

**Account** > **Band import** shows when data last arrived and, if later, the last sync, the
app and version that sent it, and the last refused sync with why. A wrong secret can't be shown
there: the coach doesn't know whose phone sent it.

## When the reader closes as the screen turns off

Nothing in the reader closes it: it never finishes its screen or ends its process. A sync runs
until the screen is destroyed, not when it is paused or the screen goes off, and an interrupted
sync loses nothing (it is sent again next time). Keeping the screen on during a sync only stops
the timeout; the power button still turns it off. So find out what closed it, with the phone
plugged into the desktop (USB debugging on) and these in Git Bash:

1. `adb logcat -c`, then leave `adb logcat -b all -v time | grep -i -E "coach\.reader|FATAL"`
   running. Open the reader, tap **Sync now**, press the power button, wait two minutes, unlock.
2. `adb shell pidof com.vybedev.coach.reader` before and after. A number both times: the
   process lived. Nothing after: it was killed.
3. `adb shell dumpsys activity exit-info com.vybedev.coach.reader | head -40`: why the process
   last ended, even if the logcat missed it. `CRASH` or `ANR` is the reader's bug (send the
   stack trace from step 1's `FATAL EXCEPTION` lines); `LOW_MEMORY`, `SIGNALED` or `OTHER`
   with a MIUI name in the description is the phone killing it (step 6).
4. In step 1's output:
   - `wm_on_stop_called` and nothing more: Android stopped the screen as it should; if it
     looked closed on unlock, the lock screen took you home, not the reader.
   - `wm_destroy_activity` or `wm_relaunch` with the process alive: the screen was destroyed
     (a setting in step 5, or a change such as dark mode at lock), which ends a sync in
     progress. That one is the reader's to fix: say so.
   - `am_kill` or `am_proc_died`, or lines from MIUI's process or power manager naming the
     reader: MIUI ended it (step 6).
5. `adb shell settings get global always_finish_activities`: `1` means Developer options >
   **Don't keep activities** is on, which destroys the reader every time the screen goes off.
   Turn it off.
6. MIUI: the settings in step 3.4 (Battery saver **No restrictions**, **Autostart** on, the
   reader locked in recent apps); check them with
   `adb shell cmd appops get com.vybedev.coach.reader RUN_ANY_IN_BACKGROUND` (`ignore` means
   restricted) and `adb shell dumpsys deviceidle whitelist | grep coach.reader` (listed means
   out of battery optimisation). Also look in the Security app's settings for an option that
   cleans up memory when the phone locks, and turn it off for the reader.
7. The background sync, if a 12-hour run seems not to happen:
   `adb shell dumpsys jobscheduler | grep -A 15 coach.reader` shows the job, its network
   constraint and its last run. `adb shell am get-standby-bucket com.vybedev.coach.reader`:
   `40` or `45` (rare, restricted) means Android runs it seldom.

## HC Webhook (retired)

Until October 2026 the bridge was HC Webhook (`com.hcwebhook.app`, ADR-0055). Every version
tried ran out of Health Connect's read quota, and nothing arrived after 19 Oct, so the reader
replaced it (ADR-0070). Uninstall it, so two apps don't spend the quota or send the same data.
The coach still reads its JSON, and Account and the bot still name it if it sends. Its setup
steps are in this file's git history.

## Stopping or moving phones

- Stop: **Account** > **Band import** > **Stop band import**. The phone's next sync gets 401,
  and the coach stops checking for gaps.
- New phone: repeat steps 1-4 there; making a new secret means the old phone can't send.
- Remove data already imported: there is no per-type delete yet; **Account** > erase removes
  everything (ADR-0044).
