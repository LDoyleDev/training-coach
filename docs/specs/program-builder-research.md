# Program builder: the research behind the muscle weights, caps and starters

Status: **research, 2026-10-21**, for [program-builder.md](program-builder.md), which holds the
decisions. This file holds the evidence: how much each exercise counts for each muscle, where
isolation work is needed, the overload caps, how the plan compares with Huberman's protocol,
how long sessions take (time efficiency, 2026-10-23), the trunk and hip muscles the plan misses
(core and hips, 2026-10-23), and the coverage of the current plan and the starters. Each source under Sources says how far it
was read: the full paper, the abstract, or someone else's summary of it.

## Counting: the weight of a set for each muscle

A hard set counts **1** for each muscle it trains as a prime mover, **0.5** for a meaningful
synergist and **0** for a stabiliser. A large meta-regression (67 studies, 2,058 people) found this
fractional count fitted muscle growth better than counting every muscle fully or not at all
(Pelland 2026). The 0.5 is a single default for every pairing; nobody has fitted a different
fraction per pairing. Where growth studies measured a pairing, they mostly agree with 0.5, and
three pairings depart from it:

| Pairing | What was measured | Weight |
| --- | --- | --- |
| Biceps from rows | One-arm rows grew the elbow flexors 5.2%, curls 11.1%, in the same people (Mannarino 2021) | **0.5** (0.47 measured) |
| Biceps from pulldowns | Pulldowns grew the elbow flexors as much as curls in untrained men (6.1% vs 5.8%; Gentil 2015) | **0.5**, conservative; may be more in beginners |
| Triceps from pressing | Bench press only: whole triceps +4.8% (not significant) vs +10.4% from triceps presses; long head +2.1% vs +17.5%; lateral head grew from the bench only (Brandão 2020). Bench press grows the chest about twice as much as the triceps (Ogasawara 2012, as cited by Brandão) | **0.5**, and **0 for the long head** |
| Chest from push-ups | Push-ups at a matched load grew chest and triceps like the bench press (Kikuchi 2017) | **1** |
| Glutes from deep squats | Full squats grew the glutes 6.7%, half squats 2.2% (Kubo 2019); squats grew them as much as hip thrusts (Plotkin 2023) | **1** (changed from the usual 0.5) |
| Glutes from leg press | Leg press grew the glutes 15.4%, three times its quad gain (Kinoshita 2026) | **1** (was 0.5) |
| Adductors from deep squats | Full squats grew the adductors 6.2% (Kubo 2019); squats beat hip thrusts for them (Plotkin 2023) | **1** (was 0.5) |
| Adductors from leg press | Adductor magnus +6.2%, the other adductors not (Kinoshita 2026) | **0.5** |
| Hamstrings from squats, leg press, hip thrusts | No growth after squats (Kubo 2019) or hip thrusts (Plotkin 2023); leg press no more than leg extensions (Kinoshita 2026) | **0** |
| Rectus femoris from squats and leg press | Leg press +1.1% vs leg extension +13.2% (Kinoshita 2026); squats grew it less than leg extensions (Zabaleta-Korta 2021) | **0**: quads count 1, but the map flags the rectus femoris |
| Hamstrings from 45° hip extension | Hip-extension training grew the long head about 12% (Bourne 2017, as cited by Maeo 2021) | **1** (was lower back first) |

Everything else is an estimate from what the muscles do and from EMG studies, which show effort
but not growth. The weight table marks those. **0.25** is used for small contributions that are
more than zero (rear delts from pulldowns, lower back from swings). No study supports a weight
that fine; it keeps a small part from vanishing or from counting as half.

Strength may gain less from indirect sets: about 39% of a direct set in an exploratory fit
(Remmert 2025). The map shows growth coverage, so it uses 0.5.

## Where compounds cover a muscle and where they don't

| Muscle | Covered by compounds? | Direct work |
| --- | --- | --- |
| Quads (vasti) | Yes: squat, leg press and split squat grow the vasti as much as leg extensions (Kinoshita 2026) | Leg extension for the **rectus femoris**, which compounds barely grow |
| Glutes | Yes: deep squats, leg press and split squats count 1 | Not needed; a hip thrust is an alternative to a squat, not an extra |
| Adductors | Yes, from deep squats | Not needed; Copenhagen planks if squats are shallow |
| Hamstrings | **No**: only hinges train them, and squats, leg press and hip thrusts don't | **Needed**: one hinge (RDL or 45° back extension) and one seated leg curl. Seated curls grew the biarticular hamstrings more than lying curls (+14% vs +9%; Maeo 2021) |
| Chest | Yes: presses, push-ups and dips | Fly optional |
| Lats and upper back | Yes: pulldowns, pull-ups and rows | Not needed; a reverse fly helps the rear delts and upper back |
| Front delts | Yes: every press counts 0.5 and the overhead press 1 | **Not needed** (no growth data on front-delt volume) |
| Side delts | **Barely**: the overhead press counts 0.5; bench and rows 0 | **Needed**: lateral raises. Dumbbell and cable raises grew them alike (+3-5% in 8 weeks, trained lifters; Larsen 2025) |
| Rear delts | Partly: rows 0.5, pulldowns 0.25 | Reverse fly or face pull to reach 8 |
| Triceps | Partly: pressing counts 0.5, and **not the long head** (Brandão 2020) | **Needed**: an overhead extension. Overhead grew the triceps 1.4 times as much as pushdowns, the long head most (Maeo 2023) |
| Biceps | Partly: pulls count 0.5 | Curls double the gain from rows (Mannarino 2021); needed above about 6 sets |
| Calves | **No** | **Needed**: standing and bent-knee raises, with the stretched half of the range (Kassiano 2023: +15% vs +7% for full range) |
| Abs, obliques | No: trunk bracing in squats and deadlifts counts 0 | Needed if wanted: crunches, hanging raises, Pallof press |
| Neck, tibialis | No (Conley 1997 for the neck) | Needed: Huberman extras |
| Forearms | Partly: hinges, heavy pulls and hangs | Optional: carries, wrist curls |

So the **main muscles that need direct work** are hamstrings, side delts, triceps (long head),
calves and, above about 6 sets, biceps. Quads need a leg extension only for full coverage of the
rectus femoris. Glutes, adductors, chest, lats, upper back and front delts are covered by
compounds.

**Isolation adds little on top of compounds for a muscle the compounds already train fully.**
Older trials that added curls and triceps extensions to compound programmes found little extra
arm growth in beginners (Gentil 2015 and the review Iversen 2021 cites). Several of those trials
come from an author whose papers were later questioned or retracted (see Sources), so the case
here rests on the trials above, which measured each muscle head.

## Weights by exercise

`1` prime mover, `0.5` synergist, `0.25` small part, `0` or blank not counted. **E** marks a
weight that is an estimate (EMG or anatomy, no growth study); the rest rest on the studies above.
The catalogue (which exercises, kit and simpler options) is in
[program-builder.md](program-builder.md), Decided 5.

**Gym catalogue**

| Exercise | 1 | 0.5 | 0.25 | Basis |
| --- | --- | --- | --- | --- |
| Back or hack squat, deep | quads, glutes, adductors | - | - | Kubo 2019, Plotkin 2023 |
| Bulgarian split squat | quads, glutes | adductors | - | E (EMG and force models; deep, like a full squat) |
| Leg press | quads, glutes | adductors | - | Kinoshita 2026 |
| Leg extension | quads (rectus femoris) | - | - | Kinoshita 2026 |
| Romanian deadlift | hamstrings | glutes, lower back, forearms | - | E for the 0.5s; hamstrings from hip-extension growth (Bourne 2017) and EMG (McAllister 2014) |
| Seated leg curl | hamstrings | - | - | Maeo 2021 |
| Hip thrust | glutes | - | - | Plotkin 2023 (no quad, adductor or hamstring growth beyond the squat's) |
| 45° back extension | hamstrings | glutes, lower back | - | Bourne 2017; E for the 0.5s |
| Copenhagen plank | adductors | obliques | - | E |
| Standing calf raise, paused in the stretch | calves | - | - | Kassiano 2023 |
| Seated calf raise | calves (soleus) | - | - | E |
| Tibialis raise | tibialis | - | - | E |
| DB bench press | chest | front delts, triceps | - | Brandão 2020, Kikuchi 2017 |
| Incline DB press | chest | front delts, triceps | - | as bench |
| Cable fly / pec deck | chest | front delts | - | E |
| Seated DB overhead press | front delts | side delts, triceps | - | E (no growth trial against raises) |
| Cable lateral raise | side delts | - | - | Larsen 2025 |
| Lat pulldown / pull-up | lats | biceps, upper back | rear delts | Gentil 2015 (biceps); E for the rest |
| Chest-supported row | upper back, lats | biceps, rear delts | - | Mannarino 2021 (biceps); E for the rest |
| Reverse pec deck / face pull | rear delts | upper back | - | E |
| Incline DB curl | biceps | - | forearms | Mannarino 2021 (curls); E for forearms |
| Hammer curl | forearms | biceps | - | E |
| Overhead cable triceps extension | triceps (all heads) | - | - | Maeo 2023 |
| Wrist curl / reverse wrist curl | forearms | - | - | E |
| Farmer carry | forearms, upper traps | obliques | - | E |
| Neck flexion / extension / lateral | neck | - | - | Conley 1997 |
| Cable crunch | abs | - | - | E |
| Hanging knee raise | abs, hip flexors | - | forearms | E |
| Pallof press / side plank | obliques | abs | - | E |

**Home exercises in the current plan**

| Exercise | 1 | 0.5 | 0.25 | Basis |
| --- | --- | --- | --- | --- |
| Jump squat | - | quads, glutes | - | E: power work stops far from failure, so it counts half |
| Kettlebell swing, 8 kg | - | glutes, hamstrings | lower back, forearms | E: no growth study; at 8 kg most sets stay far from failure |
| Bulgarian split squat, pistol squat | quads, glutes | adductors | - | as the gym split squat |
| Single-leg RDL | hamstrings | glutes | lower back | E |
| Hamstring curl (towel slide, Nordic) | hamstrings | - | - | Nordic and slider curls grew the hamstrings, the semitendinosus most (Bourne 2017) |
| Single-leg calf raise | calves | - | - | Kassiano 2023 |
| Pull-up, chin-up | lats | biceps, upper back | rear delts, forearms | as pulldowns |
| Dip (chairs) | chest | triceps, front delts | - | E |
| Push-up, diamond push-up | chest | triceps, front delts | - | Kikuchi 2017; diamond as push-up (E) |
| One-arm kettlebell row | upper back, lats | biceps, rear delts | - | Mannarino 2021 |
| Pike push-up | front delts | side delts, triceps | - | E |
| Rear-delt reverse fly | rear delts | upper back | - | E |
| Kettlebell curl | biceps | - | forearms | Mannarino 2021 |
| Kettlebell lateral raise | side delts | - | - | Larsen 2025 |
| Hanging knee/leg raise | abs, hip flexors | - | forearms | E |
| Dead hang | forearms | - | - | E |
| Prone Y-T-W | upper back | rear delts | - | E |
| Back extension (superman) | lower back | glutes | - | E |
| Neck flexion / extension / side bend | neck | - | - | Conley 1997 |
| Chin tuck | - | - | - | A posture drill, not a hard set: counts 0 |

## Overload: caps and warnings

**Per muscle, per week.** More sets keep adding growth with shrinking returns: the best-fitting
curve is a square root, so 6 to 12 sets adds noticeably and 18 to 24 a little (Pelland 2026, from
a summary). In trained men, 30 sets a week grew the triceps and quads more than 6 or 18
(Schoenfeld 2019), so 20-30 is not harmful, only expensive. Strength gains flatten much earlier,
at about 10-15 sets. The bands stay as decided: **green 10-20, blue 20-30, warning over 30**.

**Per muscle, per session.** Growth stopped rising beyond about **11 fractional sets for one
muscle in one session** (Remmert 2025, a preprint, from a summary); for strength the figure was
about 2 direct sets. So the map warns above 11 in a session and suggests moving sets to another
day. Splitting a muscle's sets over two days costs nothing for growth and helps strength
(Pelland 2026: frequency adds to strength, little to growth once volume is equal).

**Recovery between sessions.** After leg press, strength took 48 hours to recover, after leg
extensions 24 (a 2023 trial in untrained men, from a summary). In trained men, curls left the biceps
sore for 72 hours, rows for less (Soares 2015, abstract). The app warns when one muscle gets
**4 or more fractional sets on two days in a row**. Low evidence: a reasoned default.

**Shared stress that muscle counts miss.** No study gives a limit for these; they are reasoned
defaults, marked **no data** in the app, and they warn without blocking:

- **Lower back (spinal loading).** Loaded squats (goblet, back and front squats, a loaded split
  squat), RDLs, swings, back extensions, carries and bent-over rows all load the spine, though
  few of them count for lower-back growth; bodyweight and jump squats don't count. Warn above
  **8 spine-loading hard sets in one session**, and when heavy hinges (RDL, deadlift, swings with
  a heavy bell) fall on two days in a row. Today's Legs day has 6 (swings and RDLs), and up to 13
  on the split squat's and pistol's kettlebell steps; the 4-day starter's Lower 1 has 6.
- **Elbows and the front of the shoulder.** Pressing, dips and triceps work all load the elbow in
  extension, and every press loads the front delts. The front delts need no direct work, so the
  picker says so ("already covered by your presses") rather than offering front raises.
  Triceps over 20 fractional sets gets the blue band like any muscle.
- **Grip.** Grip often limits hinges and pulls before the target muscle tires. No cap; the picker
  offers straps or a lighter grip-free option when a session has more than about 8 grip-heavy
  sets.

## Huberman's protocol against the evidence

Huberman's Foundational Fitness Protocol (built with Andy Galpin) trains each muscle twice a
week, once directly and once indirectly, with two exercises per muscle: one loaded in the
shortened position and one in the lengthened. It alternates monthly between a strength schedule
(3-4 sets of 4-8 reps, 2-4 min rest) and a hypertrophy schedule (2-3 sets of 8-15 reps, about
90 s rest), with 50-60 minutes of hard work per session and 75 at most. The newsletter page
gives no weekly set counts; the day-by-day PDF couldn't be fetched.

| Huberman | Evidence | Verdict |
| --- | --- | --- |
| Each muscle twice a week | ACSM 2026: twice a week; frequency helps strength, is neutral for growth at equal volume (Pelland 2026) | Supported |
| One lengthened exercise per muscle | Lengthened training grew more in the hamstrings (Maeo 2021), triceps (Maeo 2023) and calves (Kassiano 2023) | Supported, and the strongest part |
| One shortened exercise per muscle | No trial shows shortened-position work adds growth | Weakest part; useful only where it trains a region compounds miss (leg extension for the rectus femoris) |
| 2-3 sets of 8-15, or 3-4 of 4-8 | Growth is similar across 6-30 reps near failure (Iversen 2021) | Supported |
| 50-60 min of work | Fits the per-session plateau of about 11 sets per muscle | Supported |
| Weekly volume: two exercises of 2-3 sets, plus indirect work | About 6-9 fractional sets per muscle (the current plan's count, below); the evidence puts more growth at 10 or more | **Departs**: below green for most muscles |

So the builder keeps Huberman's shape (each muscle twice a week; a compound plus a targeted,
lengthened exercise; under an hour) and adds the sets to bring the main muscles to 10.

## Efficiency: the fewest sets for full coverage

- **The floor.** Three compound exercises (a leg press or squat, a row, a bench press) of at
  least 4 hard sets a week each, at 6-15 reps near failure, train most of the body; 10 or more
  sets a week for more growth (Iversen 2021). That floor leaves hamstrings, side delts, calves and
  the triceps' long head untrained.
- **Pick the exercises that count for the most muscles.** Per set: deep squat or leg press 2.5-3
  muscles, row 3, RDL 2.5, pulldown 2.25, press 2, 45° back extension 2. A single-joint exercise
  counts 1, so it is chosen only for a muscle the compounds miss (the list above).
- **Spread a muscle over 2-3 days**; it costs nothing and keeps each session under the 11-set
  plateau.
- **Pair exercises that don't compete** (ADR-0031), so one rests while the other works; the
  plan already does.
- **The result:** about 80 sets a week turns all ten main muscles green, in 19-22 exercises
  (the starters below). The current plan's 78 sets reach green for 3 of the 10, because many sets
  go to work that counts for little (jump squats, light swings, chin tucks) and legs are trained
  once a week.

## Time efficiency: the same work in less time (2026-10-23)

The sets above are what a week needs; this section is how long they take. Most of a session
is rest, so the lever is the rest, not the reps.

**What the studies say.**

| Question | Finding | Read |
| --- | --- | --- |
| Do paired sets (supersets) cost growth? | 19 studies, 313 people: same reps (SMD −0.03) and volume load (0.05), much better kg per minute (1.74); same long-term strength (0.10) and hypertrophy (−0.05, from two studies). Higher lactate (0.94), energy cost and effort (RPE 0.77) (Zhang 2025) | full |
| Which pairs? | Opposing muscles (bench + row) completed *more* reps than straight sets (SMD 0.68). Two exercises for the same muscles lost volume (−1.08). Upper + lower body: reps not clearly lower (−0.46, CI crosses 0) (Zhang 2025) | full |
| How much time? | Six lifts, 3×10, 2 min after each set or group: 42.3 min straight, 24.0 min in pairs, 17.7 min in threes, same volume. Pairs and threes left lactate and creatine kinase higher and jump height still down at 24 h (Weakley 2017) | full |
| | Bench + row paired with 2 min after each pair lifted more total load than the same sets done straight, with more EMG fatigue (Paz 2017). Pairs took about 10 min against 20 (Robbins 2010), and over 8 weeks gave the same strength in half the time (Robbins 2009) | full; abstracts |
| How long to rest? | 9 studies: a small benefit to resting more than 60 s, and nothing more beyond about 90 s; every interval crosses zero (Singer 2024). 3 min beat 1 min in trained men (Schoenfeld 2016), but the gap closes when the short-rest group adds sets to match the volume (Longo 2022). Short rest costs reps most on multi-joint and heavy sets (Senna 2011, 2017) | full; summary; abstract; summary |
| Do heavy, low-rep sets save time? | No. 7×3 with 3 min rest vs 3×10 with 90 s, volume matched: same biceps growth, **70 min vs 17 min** a session, more strength from the heavy routine, and 2 of its 10 men dropped out injured (Schoenfeld 2014). Growth is similar from about 30% to 80% of a one-rep max taken to failure (Schoenfeld 2017; Lasevicius 2018), but light sets must get closer to failure to count (Lasevicius 2020); stopping a rep or two short of failure is as good as failure (Refalo 2023) | full; abstract; summary; abstract; abstract |
| Drop sets? | 5 studies: same strength (ES 0.07) and growth (0.08) as straight sets (Coleman 2022); pooled growth SMD 0.155, not significant (Sødal 2023). One triceps drop set took 145 s against 316 s for 3 sets (Fink); curls 2.1 min against 6.8 (Ozaki). Most studies are isolation exercises on machines | full; full |
| Rest-pause (myo-reps)? | 6 weeks in trained men: 35 min sessions against 57, strength the same (Prestes 2019, as cited by Iversen 2021 and Nuzzo 2024). Same growth as straight sets at matched volume (Enes 2021). No trial of "myo-reps" as such | as cited; summary |
| Cluster sets, pre-exhaustion? | Clusters: same strength and growth (ES −0.05 each), and they add rest (Davies 2021). Pre-exhausting a muscle with an isolation exercise first: no long-term benefit (Fisher 2014; Trindade 2022 review). Neither saves time | abstract; abstract |
| Warm-up? | A general or specific warm-up didn't add reps on submaximal sets; a few specific sets matter above about 80% of a one-rep max (Ribeiro, as cited by Iversen 2021) | as cited |

One correction to the earlier plan: the minimal-dose overview cited as "Fyfe 2022" is Nuzzo,
Pinto, Kirk & Nosaka 2024; it is about strength, not growth, and backs single sets and one
session a week as better than nothing.

**What it means for this plan.** The plan already pairs (ADR-0031), but the guided session
starts its 60 s rest after every set, inside a pair too (`REST_SECONDS` in `services/guided.py`).
So the pairs interleave and save nothing. Timed with the summary page's assumptions (10 s set-up,
about 3 s a rep, 10 s to switch sides, 10 min warm-up):

| Rule | Value | Why |
| --- | --- | --- |
| Between the two exercises of a pair | 15 s, to move | Opposing or unrelated muscles keep their reps in a pair (Zhang 2025) |
| After the pair | 60 s | Each exercise still gets 104 s or more between its own sets, past the 90 s where more rest stops helping (Singer 2024) |
| After a pair that shares a prime mover | 90 s | Same-muscle pairs lose volume (Zhang 2025); pistol squat + single-leg RDL share glutes |
| Straight sets | 90 s compound, 60 s small muscle | Short rest costs most on multi-joint sets (Senna 2011, 2017; Iversen 2021) |
| A third, light exercise in a pair's rest | neck, chin tucks, lateral raises | Fills rest without touching the pair's muscles. Estimate: tri-sets were studied with heavy lifts (Weakley 2017), not fillers |
| Pairing rules | no shared prime mover (or 90 s rest); not two grip-heavy exercises; at most one spine-loading exercise | Zhang 2025 for shared muscles; grip and spine are the overload rules above, estimates |

| Week | As the app runs pairs now | Paired properly | Longest session |
| --- | --- | --- | --- |
| Current plan, 78 sets | 197 min | **162 min** (−35) | 63 → 56 min |
| Proposed plan, 93 sets | 226 min | **187 min** (−39) | 65 → 56 min |

Pairing properly is free and saves more than any kit. It is about 18% here, not the
studies' 40-60%, because the 60 s after each pair stays, and set-up and the warm-up don't
shrink. A 5-minute specific warm-up in place of 10 would save another 15 minutes a week
(Iversen 2021); that is a choice, not a finding for these loads. The cost of pairing is harder
sessions: more effort, lactate and muscle damage, and jump height down a day later (Zhang 2025;
Weakley 2017). The Recovery day after Legs suits that.

Drop sets and rest-pause save time only where rest is long and sets are many. Inside pairs the
rest is already used, and for two or three sets of a small muscle the model shows no saving.
They stay an optional technique for isolation exercises, counted at matched volume, not the
default. With one 8 kg kettlebell a drop set means kettlebell to water bottles.

**Heavier kit saves minutes, not hours.** Bringing high-rep sets into 8-12 reps, over the
current → proposed plan:

| Kit | Minutes a week saved | What else it does | Cost class |
| --- | --- | --- | --- |
| 16 kg kettlebell | 3.6 → 4.3 (swings, one-arm rows, single-leg RDLs, curls, overhead extension) | Swings at 8 kg count half; at 16 kg near failure they can count fully (estimate). Loaded split squats, pistols and goblet squats, which count as spine-loading: Legs passes the 8-set spine limit once both are loaded | low-medium |
| Weighted vest, 10 kg | 5.4 → 7.0 (calf raises, push-ups, dips, diamond push-ups) | Ladders for pull-ups, dips and pistols once they pass 12 reps. A vest on squats or lunges loads the spine too | medium |
| A light dumbbell pair, 2-5 kg | about 0 | Controlled lateral raises and reverse flies instead of bottles; makes drop sets possible | low |
| Dip belt | 0 now | Only useful once pull-ups, chin-ups or dips pass 12 reps, which the vest also covers | low |

Ranked: the kettlebell first (the one place sets don't count fully, the most exercises, the
lowest price), then the vest (the most minutes). Nothing needs buying for the pairing gain.

**What the app needs for this.** Rest per transition from the server: the move inside a pair,
the rest after it, straight-set rest by exercise type. Pairs that can take a third, light item
(the seed allows exactly two neighbours today, ADR-0031). Pairs on the Recovery day. The time
estimate (`_minutes` in `services/guided.py`) using the same rules. Later, a drop-set or
rest-pause set type for isolation exercises.

## Core and hips: the muscles the plan misses (2026-10-23)

The plan from 24 Oct 2026 has all ten main muscles green but leaves the trunk and hips short:
abs 3 sets a week (one day), obliques 0, lower back 3.5 (one day), hip flexors 3, adductors
4.5 (one day), no exercise reaching the rectus femoris, and upper traps 0.

**What the studies show.** Much less than for the limb muscles: no growth trial of crunches,
rollouts, side planks or back extensions in healthy trained adults turned up, and no
dose-response data for any trunk muscle. What there is:

| Question | Finding | Read |
| --- | --- | --- |
| Do compounds train the core? | They work it hard but nobody has measured growth. 67 EMG studies: free-weight lifts gave the highest rectus abdominis, external oblique and erector activity (deadlift erectors about 90% of a maximal contraction, back extension about 63%); a plank with the pelvis tucked gave the highest internal oblique (about 120%), and a suspended rollout about 145% for the upper abs (Oliva-Lozano & Muyor 2020). Free weights beat ball exercises for the multifidus (Martuscello 2013). No longitudinal study of squats or deadlifts and ab growth exists (Contreras, as summarised) | full (first half); abstract; summary |
| Abs: which exercise? | Crunches shortened and thickened the rectus abdominis most in one session, 36% more than leg raises (2023, 15 people, ultrasound). One comparison of 16 exercises found none beat the crunch for the abs; rollout-type exercises rank high in others. Activation only | abstract; abstracts |
| Lower back | Isolated lumbar extension plus motor control grew the erectors and multifidus more than general exercise over 12 weeks, in 50 people with chronic low back pain (Fortin 2023). Lumbar extension strength rose as much training once a week as two or three times, over 12 weeks in 114 adults; every two weeks still gave 26% against 40% (Graves 1990) | full (results, partly); summary |
| Adductors | The Copenhagen adduction exercise raised eccentric adduction strength 35.7% in 8 weeks (24 footballers; Ishøi 2016); twice a week for 6 weeks at a low dose didn't (39 footballers; Dawkins 2021). Adductor longus thickness rose in both groups alike over 8 weeks, so no size benefit was shown (12 players; Alonso-Calvete 2021). Deep squats grew the adductors 6.2% (Kubo 2019) | abstract; abstract; full; abstract |
| Rectus femoris | Leg extension with the hip at 40° grew it more than at 90°, with the vastus lateralis the same (22 men, 10 weeks, preprint): it grows best lengthened, hip extended and knee bent. The reverse Nordic loads it that way and lengthened its fascicles (Alonso-Fernández 2019) | abstract; as cited |
| Hip flexors | Band hip-flexor training raised isometric hip-flexion strength 17% in 6 weeks (33 adults; Thorborg 2016). No growth trial | abstract |
| Upper traps | A 12-week full-body programme that included shrugs, deadlifts and rows didn't grow the upper traps, while adding neck training grew the neck (Conley 1997); no shrug growth trial found | as cited |
| Carries | A suitcase carry (about 25 kg) raised multifidus and back activity on both sides, and the abs and external oblique on the loaded side, more than holding the weight (2024) | abstract |
| After a run? | 43 studies: concurrent training didn't reduce growth (SMD −0.01) or maximal strength (−0.06); explosive strength gained less, more so in the same session (Schumann 2022) | abstract |

**What follows.**

- **Weights.** Compounds keep counting 0 for the abs and obliques and 0.25 for the lower back
  from hinges: high EMG with no growth data is not a set. New exercises: ab rollout abs 1,
  obliques 0.25; Copenhagen plank adductors 1, obliques 0.5; side plank hip dip obliques 1,
  abs 0.25; reverse Nordic quads 1, reaching the rectus femoris. All estimates (E).
- **Bands.** The general 10-20 band comes from limb-muscle growth studies. For the trunk and
  hips, which work in every compound and where strength and robustness matter more than size,
  an own band is the honest choice, marked low evidence: abs 6-12, obliques 4-10, lower back
  4-10 (once a week is enough for strength: Graves 1990), hip flexors 3-8, adductors 4-10.
  These are estimates, not findings. Like the other own bands, one day a week counts as covered;
  the proposal gives abs, obliques, lower back and adductors two anyway.
- **Upper traps:** no direct work. No study shows shrugs grow them, and the neck work already
  trains the neck. They stay grey; a gym version can add farmer carries.
- **Hip flexors:** the hanging raise already moves from knee raises to straight-leg raises and
  toes to bar, and running and sprints use them. Nothing added.
- **Carries:** not at home; with 8 kg a suitcase carry is far lighter than the studied 25 kg,
  and it adds grip and spine load.
- **Order:** core after the run, not before: no growth cost, and the trunk isn't tired for the
  run (estimate).

**Proposal: a core and hips block on two days**, household kit only (an ab wheel is an optional
step, low cost):

| Day | Pair | Sets × reps |
| --- | --- | --- |
| Recovery + posture, after pair 3 | Reverse Nordic + side plank hip dip | 2 × 5-10 + 2 × 10-15 per side |
| Moderate cardio, after the run | Ab rollout + Copenhagen plank | 3 × 8-12 + 2 × 6-12 per side |
| | Back extension + side plank hip dip | 2 × 10-15 + 2 × 10-15 per side |

Ladders: ab rollout (kneeling, towel on a smooth floor, short range → full range → kneeling ab
wheel → standing negatives); Copenhagen plank (knee on a chair, 3 s down → ankle on a chair →
ankle on a chair, 3 s lowering); side plank hip dip (on the knees → straight legs → top leg
raised → holding 8 kg on the hip); reverse Nordic (lean to about 30° → deeper, 3 s lowering →
to the floor, hands push back → no hands). The back extension and hanging raise keep their
ladders. Every pair has at most one spine-loading exercise and none grips.

**Coverage, before → after** (plan from 24 Oct 2026, the app's coverage logic, own bands as
above): abs 3 → 7 (2 days), obliques 0 → 5.75 (2 days), lower back 3.5 → 5.5 (2 days),
adductors 4.5 → 6.5 (2 days), hip flexors 3 (1 day, green on its own band), quads 10.5 → 12.5
with the rectus femoris reached, upper traps 0. All ten main muscles stay green; no session,
back-to-back, spine (at most 6 a session) or grip (at most 5) warning. On the general band the
trunk muscles would show light green, and green would need about 20 more sets: roughly 25
more minutes a week. Hard sets: 93 → 106.

**Time.** By the app's estimator (45 s a set, each side counted, the rest rules of ADR-0065):
Recovery 32 → 39 minutes, and 15 minutes after the moderate cardio (30 → 46 with the run). The
estimator is high for these short sets: at about 25-35 s a set the block is about 4 and 11
minutes. Added: 22 minutes a week by the estimator, about 16 by the shorter sets.

**What the app needs.** Strength items on a conditioning day are already possible in the seed
and the guided session (the time estimate counts them). The gap is counting: once a planned
session's workout is logged, later logs that day are extras (`workout_log.target`), so counting
the run from the band, or logging it in Telegram, closes the session and the block isn't
guided or counted for its ladders. The smallest change: a conditioning session keeps its other
items open for the rest of that day after the cardio is logged, and the guided session offers
them as "after your run", saved with that day's workout. Without that change the block would go
on a strength day (Arms + legs would reach about 68 minutes) or wholly on Recovery (about 54
minutes for the optional day): neither keeps sessions near an hour.

## Coverage

Fractional sets a week; "Days" counts days with at least 2 sets for that muscle; "Most" is the
most in one session. Bands for the ten main muscles: green 10-20 (calves 8-16, side delts 8-20).
Worked out from the weights above.

### The plan before 24 Oct 2026: 78 sets, 26 exercises

The owner applied the changes below, plus the first gap closer (one more curl set and one more
lateral-raise set, both on Torso), as the "Coverage update" plan version: 95 sets, all ten main
muscles green on two days. The numbers now are in `training-plan.md` (Weekly hard sets).

| Muscle | Sets | Days | Most | Band |
| --- | --- | --- | --- | --- |
| Quads | 8.5 | 1 | 8.5 | light green, one day |
| Glutes | 12.5 | 1 | 11.5 | green, but one day and at the session cap |
| Hamstrings | 7.5 | 1 | 7.5 | light green, one day |
| Chest | 9 | 2 | 6 | light green |
| Lats | 10 | 2 | 7 | green |
| Upper back | 10 | 2 | 6.5 | green |
| Triceps | 6 | 1 | 4.5 | light green; no long-head work |
| Biceps | 8 | 2 | 4.5 | light green |
| Side delts | 5.5 | 1 | 4 | light green |
| Calves | 6 | 2 | 3 | light green |

Also: front delts 7.5, rear delts 7.25, neck 7, forearms 6, lower back 3.5, adductors 3.5,
abs 3, tibialis 3, obliques and upper traps 0. No rectus femoris work; spine-loading sets at most
6 in a session (Legs), or 13 once the split squats and pistols hold a kettlebell: over the cap.

**What would turn it green, home kit only** (applied on 24 Oct 2026):

1. Move the low-fatigue work from Arms to Recovery + posture: hanging raises, neck side bends,
   one neck extension set and dead hangs.
2. On Arms, add **3 sets of an overhead kettlebell triceps extension** (a new catalogue exercise),
   **3 sets of Bulgarian split squats** and **3 sets of hamstring curls**, so legs are trained on
   two days. Legs day drops split squats from 4 sets to 3, off the session cap.
3. One more set each: calf raises (both days), kettlebell curls, push-ups, dips; and 2 sets of
   lateral raises on Torso.

That gives 93 sets a week, sessions of 25-27 sets (14 on the optional recovery day), with quads
10.5, glutes 14.5, hamstrings 10.5, chest 11, lats 10, upper back 10, triceps 10 and calves 8,
all on two days; biceps 9 and side delts 7.5 stay one set short of green.

### 3-day full-body starter (gym): 81 sets, 19 exercises, 27 sets a session

| A | B | C |
| --- | --- | --- |
| Back squat 3 | Romanian deadlift 4 | Bulgarian split squat 3 |
| Seated leg curl 3 | Leg press 3 | Seated leg curl 3 |
| DB bench press 3 | Leg extension 2 | DB bench press 3 |
| Chest-supported row 4 | Lat pulldown 4 | Chest-supported row 3 |
| Cable lateral raise 3 | Incline DB press 4 | Cable lateral raise 3 |
| Overhead triceps extension 3 | Cable lateral raise 3 | Overhead triceps extension 2 |
| Standing calf raise 4 | Incline DB curl 3 | Incline DB curl 2 |
| Cable crunch 2 | Reverse pec deck 2 | Seated calf raise 4 |
| Neck 2 | Tibialis raise 2 | Cable crunch 2, Neck 2 |

Quads 11, glutes 11, hamstrings 10, chest 10, lats 11, upper back 10, triceps 10, biceps 10.5,
side delts 9, calves 8: all green, each on 2-3 days, at most 5 in one session. Also rear delts
6.5, adductors 6, front delts 5, abs 4, neck 4, forearms 3.25, tibialis 2. Spine-loading sets at
most 4 a session.

### 4-day upper/lower starter (gym): 82 sets, 22 exercises, 18-24 sets a session

| Lower 1 | Upper 1 | Lower 2 | Upper 2 |
| --- | --- | --- | --- |
| Back squat 3 | DB bench press 3 | Leg press 3 | Incline DB press 3 |
| Romanian deadlift 3 | Chest-supported row 3 | Seated leg curl 3 | Lat pulldown 3 |
| Leg extension 2 | Lat pulldown 2 | Bulgarian split squat 2 | Chest-supported row 3 |
| Seated leg curl 2 | Incline DB press 2 | 45° back extension 2 | DB bench press 2 |
| Standing calf raise 4 | Cable lateral raise 4 | Seated calf raise 4 | Cable lateral raise 4 |
| Cable crunch 2 | Overhead triceps extension 3 | Pallof press 2 | Reverse pec deck 3 |
| Tibialis raise 2 | Incline DB curl 3 | Farmer carry 2 | Overhead triceps extension 2 |
| | Neck 2 | | Incline DB curl 2, Cable crunch 2 |

Quads 10, glutes 10.5, hamstrings 10, chest 10, lats 11, upper back 10, triceps 10, biceps
10.5, side delts 8, calves 8: all green, each on 2 days, at most 6 in one session. Also rear
delts 7.25, adductors 5.5, abs 5, front delts 5, forearms 4.75, obliques 3, neck, tibialis and
upper traps 2. Spine-loading sets at most 6 a session.

Beginners can start one set lower per exercise for the first four weeks (about 4-9 sets a muscle,
light green, which still grows muscle; Iversen 2021) and add the set back when the app's
progression says they're ready.

## Sources

How far each was read: **full** (methods and results read), **abstract**, or **summary** (a
secondary write-up; the paper itself couldn't be reached). SportRxiv and Springer refused
connections, so the two Pelland-group papers rest on summaries.

- Pelland, Remmert, Robinson, Hinson & Zourdos 2026, *Sports Medicine* 56:481-505: fractional
  counting fits best; square-root curve for growth, steeper flattening for strength; frequency
  matters for strength only. **Summary** (train.fitness). https://doi.org/10.1007/s40279-025-02344-w
- Remmert et al. 2025, preprint: about 11 fractional sets per muscle per session for growth, 2
  direct for strength; indirect sets about 39% for strength. **Summary** (Biolayne).
  https://sportrxiv.org/index.php/server/preprint/view/460
- Kinoshita, Maeo et al. 2026, *Medicine & Science in Sports & Exercise*, knee extension vs leg
  press, MRI of 17 muscles. **Full** (accepted manuscript). https://doi.org/10.1249/MSS.0000000000003957
- Brandão et al. 2020, *J Strength Cond Res* 34:1254-1263, bench press vs triceps press, MRI per
  triceps head. **Full.** https://pubmed.ncbi.nlm.nih.gov/32149887/
- Mannarino et al. 2021, *J Strength Cond Res*, row vs curl, within subject. **Full.**
  https://paulogentil.com/pdf/Single-Joint%20Exercise%20Results%20in%20Higher%20Hypertrophy%20of%20Elbow%20Flexors%20Than%20Multijoint%20Exercise.pdf
- Gentil et al. 2015, *Asian J Sports Med*, lat pulldown vs curl. **Full.**
  https://pmc.ncbi.nlm.nih.gov/articles/PMC4592763
- Plotkin et al. 2023, *Frontiers in Physiology*, hip thrust vs squat, MRI. **Full.**
  https://www.frontiersin.org/journals/physiology/articles/10.3389/fphys.2023.1279170/full
- Maeo et al. 2021, *Med Sci Sports Exerc* 53:825-837, seated vs prone leg curl, MRI. **Full**;
  also the source for Bourne 2017's figures. https://pmc.ncbi.nlm.nih.gov/articles/PMC7969179/
- Schoenfeld et al. 2019, *Med Sci Sports Exerc*, 6/18/30 sets in trained men, compound lifts
  only. **Full.** https://pmc.ncbi.nlm.nih.gov/articles/PMC6303131/
- Iversen et al. 2021, *Sports Medicine*, "No time to lift?". **Full** (first two-thirds).
  https://pmc.ncbi.nlm.nih.gov/articles/PMC8449772
- Kubo, Ikebukuro & Yata 2019, *Eur J Appl Physiol*, squat depth, MRI. **Abstract**, percentages
  from summaries. https://doi.org/10.1007/s00421-019-04181-y
- Maeo et al. 2023, *Eur J Sport Sci* 23:1240-1250, overhead vs neutral triceps extension.
  **Abstract**, head-by-head figures from a summary. https://pubmed.ncbi.nlm.nih.gov/35819335/
- Kassiano et al. 2023, *J Strength Cond Res*, calf raise range. **Abstract.**
  https://pubmed.ncbi.nlm.nih.gov/37015016/
- Kikuchi & Nakazato 2017, *J Exerc Sci Fit*, push-up vs bench press. **Abstract.**
  https://pmc.ncbi.nlm.nih.gov/articles/PMC5812864
- Larsen et al. 2025, *Frontiers in Physiology*, dumbbell vs cable lateral raise. **Abstract.**
  https://www.frontiersin.org/journals/physiology/articles/10.3389/fphys.2025.1611468/full
- Bourne et al. 2017, *Br J Sports Med*, Nordic vs 45° hip extension. **As cited** by Maeo 2021.
- Zabaleta-Korta et al. 2021, *J Sports Sci*, squat vs leg extension. **Summary.**
- McAllister et al. 2014, *J Strength Cond Res*, hamstring EMG across exercises. **Abstract.**
- Soares et al. 2015, recovery after rows vs preacher curls in trained men. **Abstract.**
  https://www.paulogentil.com/2017/04/12/dissociated-time-course-of-muscle-damage-recovery-between-single-and-multi-joint-exercises-in-highly-resistance-trained-men/
- Conley et al. 1997, neck training. **Abstract.** https://pubmed.ncbi.nlm.nih.gov/9189733
- ACSM 2026 position stand, from its announcement.
  https://www.newswise.com/articles/acsm-unveils-landmark-2026-resistance-training-guidelines-first-update-in-17-years
- Huberman, Foundational Fitness Protocol, newsletter page (the PDF wasn't reachable).
  https://hubermanlab.com/newsletter/foundational-fitness-protocol

Time efficiency (2026-10-23):

- Zhang, Weakley, Li, Li & García-Ramos 2025, *Sports Medicine*, supersets vs traditional sets,
  19 studies. **Full.** https://eprints.leedsbeckett.ac.uk/id/eprint/11908
- Weakley et al. 2017, *Eur J Appl Physiol*, traditional vs superset vs tri-set. **Full.**
  https://eprints.leedsbeckett.ac.uk/id/eprint/3890
- Paz, Robbins et al. 2017, *J Strength Cond Res*, paired vs traditional bench press and row.
  **Full.** https://paulogentil.com/pdf/Volume%20Load%20and%20Neuromuscular%20Fatigue%20During%20an%20Acute%20Bout%20of%20Agonist-antagonist%20Paired-set%20Versus%20Traditional-set%20Training.pdf
- Robbins et al. 2009, *J Sports Sci*, 8 weeks of paired sets; Robbins et al. 2010, *J Strength
  Cond Res* 24:1782-1789, one session. **Abstracts**, and as cited by Iversen 2021.
  https://pubmed.ncbi.nlm.nih.gov/19967584
- Singer, Schoenfeld et al. 2024, *Front Sports Act Living* 6:1429789, rest
  intervals, Bayesian meta-analysis. **Full.**
  https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2024.1429789/full
- Schoenfeld et al. 2016, *J Strength Cond Res* 30:1805-1812, 1 vs 3 min rest. **Summary.**
- Longo et al. 2022, *J Strength Cond Res*, rest vs volume load. **Abstract.**
  https://pubmed.ncbi.nlm.nih.gov/35622106/
- Senna et al. 2011 and 2017, rest for single- and multi-joint exercises. **Summary**; 2017
  **abstract.** https://pubmed.ncbi.nlm.nih.gov/28828090/
- Schoenfeld et al. 2014, *J Strength Cond Res* 28:2909-2918, 7×3 vs 3×10, volume matched.
  **Full.**
- Schoenfeld, Grgic, Ogborn & Krieger 2017, low vs high load. **Abstract.**
  https://pubmed.ncbi.nlm.nih.gov/28834797/
- Lasevicius et al. 2018, 20-80% of a one-rep max. **Summary.** Lasevicius et al. 2020, failure
  with low and high loads. **Abstract.** https://pubmed.ncbi.nlm.nih.gov/31895290/
- Refalo, Helms, Trexler, Hamilton & Fyfe 2023, *Sports Medicine* 53:649-665, proximity to
  failure. **Abstract.**
- Coleman et al. 2022, *Int J Strength Cond*, drop sets meta-analysis. **Full.**
  https://vuir.vu.edu.au/46296/
- Sødal, Kristiansen, Larsen & van den Tillaar 2023, *Sports Med Open* 9:66, drop sets. **Full**
  (results and the timing of the included studies). https://pmc.ncbi.nlm.nih.gov/articles/PMC10390395/
- Prestes et al. 2019, *J Strength Cond Res* 33:S113, rest-pause. **As cited** by Iversen 2021
  and Nuzzo 2024. Enes et al. 2021, *Appl Physiol Nutr Metab*, rest-pause and drop sets.
  **Summary.**
- Nuzzo, Pinto, Kirk & Nosaka 2024, *Sports Medicine*, minimal-dose strategies. **Full.**
  https://doi.org/10.1007/s40279-024-02009-0
- Iversen, Norum, Schoenfeld & Fimland 2021 (above), for supersets, drop sets, rest and
  warm-ups. **Full.**
- Davies, Tran, Hogan, Haff & Latella 2021, *Sports Medicine* 51:707-736, cluster sets.
  **Abstract.** https://pubmed.ncbi.nlm.nih.gov/33475986/
- Fisher et al. 2014, pre-exhaustion and exercise order, 12 weeks. **Abstract.**
  https://pubmed.ncbi.nlm.nih.gov/25092528/ Trindade et al. 2022, pre-exhaustion review.
  **Abstract.** https://pmc.ncbi.nlm.nih.gov/articles/PMC9022698

Core and hips (2026-10-23):

- Oliva-Lozano & Muyor 2020, *Int J Environ Res Public Health* 17:4306, core muscle EMG during
  fitness exercises, 67 studies. **Full** (first half, with the results by muscle).
  https://pmc.ncbi.nlm.nih.gov/articles/PMC7345922/
- Martuscello et al. 2013, *J Strength Cond Res* 27:1684-1698, core EMG, 17 studies.
  **Abstract.** https://paulogentil.com/pdf/Systematic%20Review%20of%20Core%20Muscle%20Activity%20During%20Physical%20Fitness%20Exercises.pdf
- Contreras, on the lack of trials of squats and deadlifts for ab growth. **Summary.**
  https://bretcontreras.com/?p=16968
- Rectus abdominis segments by ultrasound, crunch vs leg raise vs sit-up, one session, 2023.
  **Abstract.** https://pmc.ncbi.nlm.nih.gov/articles/PMC10824285/ Sixteen exercises vs the
  crunch, ACE-funded EMG study. **Abstract.** https://www.acefitness.org/getfit/studies/BestWorstAbExercises.pdf
- Fortin et al. 2023, *J Clin Med* 12:5920, lumbar extension plus motor control vs general
  exercise, paraspinal MRI, chronic low back pain. **Full** (results, partly).
  https://pmc.ncbi.nlm.nih.gov/articles/PMC10532355/
- Graves et al. 1990, *Spine*, frequency of lumbar extension training. **Summary.**
  https://www.painscience.com/biblio/training-only-once-per-week-will-increase-lumbar-extension-strength.html
- Ishøi et al. 2016, *Scand J Med Sci Sports*, Copenhagen adduction, 8 weeks. **Abstract.**
  https://www.ucviden.dk/en/publications/large-eccentric-strength-increase-using-the-copenhagen-adduction-/
  Dawkins et al. 2021, *Transl Sports Med*, low-dose Copenhagen. **Abstract.**
  https://researchportal.bath.ac.uk/en/publications/effects-of-a-lowdose-copenhagen-adduction-exercise-intervention-o/
- Alonso-Calvete et al. 2021, *Int J Environ Res Public Health*, Copenhagen adduction and adductor
  architecture, RCT. **Full.** https://pmc.ncbi.nlm.nih.gov/articles/PMC8701296
- Leg extension at 40° vs 90° of hip flexion, 10 weeks, SportRxiv preprint 407. **Abstract.**
  https://doi.org/10.51224/SRXIV.407
- Alonso-Fernández et al. 2019, *J Sports Med Phys Fitness* 59:640-647, reverse Nordic and rectus
  femoris architecture. **As cited** (the paper couldn't be reached).
  https://doi.org/10.23736/S0022-4707.18.08873-4
- Thorborg et al. 2016, *Knee Surg Sports Traumatol Arthrosc*, hip-flexor training RCT.
  **Abstract.** https://www.ucviden.dk/en/publications/large-strengthening-effect-of-a-hip-flexor-training-programme-a-r/
- Conley et al. 1997 (above), for the upper traps. **As cited** (Henselmans).
  https://mennohenselmans.com/4-myths-keeping-your-shoulders-small-instead-of-yoked/
- Loaded carries vs holds, EMG, 2024. **Abstract.** https://pubmed.ncbi.nlm.nih.gov/38665162/
- Schumann et al. 2022, *Sports Medicine*, concurrent training, 43 studies.
  **Abstract.** https://doi.org/10.1007/s40279-021-01587-7

**Left out.** Papers by Barbalho and colleagues, including the "ceiling effect" volume study
(retracted) and the squat vs hip thrust study in trained women, after data sleuths called for
seven retractions and journals retracted several (Retraction Watch, 2020-2021). Their numbers
aren't used here.
https://retractionwatch.com/2021/12/17/exercise-researcher-earns-more-retractions-as-investigations-mount/

Earlier sources for the small-muscle bands and the 4-set minimum (Schoenfeld 2017, Baz-Valle 2022,
Bickel 2011, Spiering 2021, Ylinen 2003, Elliott 2021, Daly 2021, Winters 2013, Leong 2015)
were read as abstracts:

- Schoenfeld, Ogborn & Krieger 2017: https://researchgate.net/publication/305455324
- Baz-Valle 2022 (12-20 sets as good as more, except triceps): https://pmc.ncbi.nlm.nih.gov/articles/PMC8884877/
- Bickel 2011: https://pubmed.ncbi.nlm.nih.gov/21131862/; Spiering 2021: https://pubmed.ncbi.nlm.nih.gov/33629972/
- Ylinen 2003, *JAMA*: https://doi.org/10.1001/jama.289.19.2509
- Elliott 2021 and Daly 2021: https://pmc.ncbi.nlm.nih.gov/articles/PMC7838928/
- Winters 2013: https://www.springermedicine.com/treatment-of-medial-tibial-stress-syndrome-a-systematic-review/22253724
- Leong 2015, *Lancet*: https://doi.org/10.1016/S0140-6736(14)62000-6
- A third-party reconstruction of Huberman's protocol: https://www.boostcamp.app/users/andrew-huberman-foundational-fitness-protocol
