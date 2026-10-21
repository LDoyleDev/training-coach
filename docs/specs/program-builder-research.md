# Program builder: the research behind the muscle weights, caps and starters

Status: **research, 2026-10-21**, for [program-builder.md](program-builder.md), which holds the
decisions. This file holds the evidence: how much each exercise counts for each muscle, where
isolation work is needed, the overload caps, how the plan compares with Huberman's protocol,
and the coverage of the current plan and the starters. Each source under Sources says how far it
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

- **Lower back (spinal loading).** Squats, RDLs, swings, back extensions, carries and bent-over
  rows all load the spine, though few of them count for lower-back growth. Warn above **8
  spine-loading hard sets in one session**, and when heavy hinges (RDL, deadlift, swings with a
  heavy bell) fall on two days in a row. Today's Legs day has 6, the 4-day starter's Lower 1 has 6.
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

## Coverage

Fractional sets a week; "Days" counts days with at least 2 sets for that muscle; "Most" is the
most in one session. Bands for the ten main muscles: green 10-20 (calves 8-16, side delts 8-20).
Worked out from the weights above.

### The current plan (`seed/plan.toml`): 78 sets, 26 exercises

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
6 in a session (Legs).

**What would turn it green, home kit only** (a suggestion for the owner; nothing changes until
they say so):

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
