# Validation: Firstlight Noya skill build vs Maygi (2026-11-01)

Run: `python -m ssr teams/fl_noya_skill.yaml -o out/` → `out/fl_noya_skill.xlsx` (~35 s). Compared with the left half of `example.jpeg`. Enemy RES 145 (calibrated, see `docs/assumptions.md`), DEF 0, skill levels 10, discs at C1 unless stated.

> **Update 2026-11-15: the fight opens with a sprint attack** (user: Noya walks to the boss; `specs/trekkers/162.yaml` main `procs`). This team's opener is the longsword sprint + Dawnflare's 3 Glows. Use these for regressions:
>
> - **Pinks-only total:** 223.3M (was 216.4M, +3.2%): the extra energy moves the rotation, and Noya's skill damage rises 8%.
> - **Potentials at Lv1 (main):** Prism Warp 5.81% (was 10.29%), Argent Mirage 9.93% (was 11.91%), Astral Brilliance 12.13% (was 12.65%), Guiding Star 2.97% (was 1.82%).
> - `bb_noya_shia_tilia_ingame`: 1,777.5M, +9.7% against the in-game 1,620M (was 1,819.1M, +12.3%).
> - Same day, auto build only (no move here): Stardust Descent turns the string's sprint into the greatsword sprint + 1 Starfall, and Sinbreaker's greatsword attacks trigger Lux Marks. The user's auto run shows ~4.4 Judgment Starfalls/min (sword gauge caps at 9.2, 25.0, 36.2, 49.2, 64.2 s); the sim gives 3.7/min, first at 13.6 s.

> **Update 2026-11-07: enemy RES is now the raw 250, not 145.** The 105 was FL Noya's Astral Brilliance Lv6, not an enemy property (`docs/assumptions.md`). The tables below are the original 2026-11-01 run at RES 145. For regressions, use these numbers (`fl_noya_skill`, 120 s, current code):
>
> - **Pinks-only total:** 203.1M (250.3M at RES 145 on the same code).
> - **Reference build:** Argent Mirage, Astral Brilliance, Resolve: Blitz, Prism Warp (Noya); Domain of Purity, Stellar Crash (Firefly); Enemy Counter, Trick Boost (Tilia).
> - **Noya potentials, Lv6:** Argent Mirage 36.74%, Resolve: Blitz 20.85%, Astral Brilliance 18.75%, Prism Warp 18.35%, Guiding Star 12.93%, Lucent Tide 10.42%, Searing Sun 9.70%, Veteran's Grit 7.59%.
> - **Discs:** Spearman against Maygi's 11 discs is 0.818 (main C1), 0.809 (main C6), 1.0 (support C1).
> - **Lux PEN emblem:** 9.79% / 0.69% against the reference build, which is what `python -m ssr` rates against (Maygi 8.65% / 0.05%); 24.34% / 7.12% against pinks only.
>
> **Update 2026-11-13, later: Astral Brilliance is always in the reference** (`reference.include`, user: its 105 Lux PEN is in every FL Noya build, so emblem PEN lines are rated on top of it). Use these for regressions:
>
> - **Reference build:** Astral Brilliance, Guiding Star, Argent Mirage, Resolve: Blitz, Prism Warp (Noya); Domain of Purity, Stellar Crash (Firefly); Enemy Counter, Revealed Flaw (Tilia). Total 1,839.8M.
> - **Lux PEN emblem:** 9.75% / 0.53% (Maygi 8.65% / 0.05%), against 31.51% / 8.39% without Astral Brilliance in the reference.
> - Pinks-only total unchanged (216.4M).

> **Update 2026-11-13: stacks refresh together** (`stack_timers: refresh`, now the default; user-tested on Gerie's Delight in Ruin: all 6 stacks drop at once). A new stack resets every stack's timer, so stacking buffs reach higher counts. Use these for regressions:
>
> - **Pinks-only total:** 216.4M (was 203.1M, +6.6%).
> - **Reference build total:** 1,429.1M (was 1,112.4M, +28%). Tilia's Revealed Flaw (10 s ×4, about one stack every 7 s: 2 stacks before, 4 now) replaces Trick Boost; the rest is unchanged.
> - **Lux PEN emblem:** 31.51% / 8.39% against the reference build (Maygi 8.65% / 0.05%). Pinks only it's 23.75% (was 24.34%): the move comes from the reference build, not the line.
> - Stacking potentials gain most: Lucent Tide Lv1 +2.0% → +9.1%, Searing Sun −1.1% → +6.0%, Veteran's Grit +1.4% → +5.1%.
> - `bb_noya_shia_tilia_ingame`: 1,819.1M, +12.3% against the in-game 1,620M (was +4.7%). The user's in-game build is weaker than the sim's.

> **Update 2026-11-07, later: potentials can grant Energy.** Guiding Star now restores its 2.5 Energy/s during Starender, which moves this team. The numbers above are the last ones before that. The user's Lv2 clip shows the Energy starting during the ult but can't measure the amount, and the user trusts the text (`docs/assumptions.md`). This is further from Maygi on the emblems. The pinks-only total and disc ratings don't change. Use these for regressions:
>
> - **Reference build:** Argent Mirage, Guiding Star, Resolve: Blitz, Prism Warp (Noya); Domain of Purity, Stellar Crash (Firefly); Enemy Counter, Trick Boost (Tilia). Guiding Star replaces Astral Brilliance.
> - **Potentials, Lv6:** Enemy Counter 55.69%, Domain of Purity 45.26%, Argent Mirage 44.78%, Guiding Star 29.48%, Resolve: Blitz 24.30%, Prism Warp 23.64%, Astral Brilliance 17.29%, Trick Boost 7.26%, Stellar Crash 6.97%, Lucent Tide 6.59%.
> - **Lux PEN emblem:** 20.17% / 8.89% (Maygi 8.65% / 0.05%), because the reference build no longer has Astral Brilliance's PEN.

> **Update 2026-11-07, later still: EAT 85 is a separate multiplier** (Resolve: Blitz, the per-Glimmer autos; user). The workbook comes out the same, so the Guiding Star numbers above stay the regression numbers. Moving only Resolve: Blitz gave different ratings (Prism Warp 22.99%), since autos then multiplied the two lines instead of adding them. That was never the intended model.

**Summary.** Disc rank order matches well: Spearman 0.84 (main C1), 0.78 (main C6), 1.0 (support C1). My Guiding Star lands within 2 points at C1. Potential order mostly matches; Lucent Tide and Stellar Crash come out too low. Emblem order is close, and Skill Crit Rate matches exactly (4.73%).

## Discs

| Disc | Maygi main C1 / C6 | Ours main C1 / C6 | Maygi support C1 / C6 | Ours support C1 / C6 |
| --- | --- | --- | --- | --- |
| My Guiding Star | 78.4% / 140.8% | 76.6% / 124.3% | 7.5% / 8.1% | 9.6% / 10.5% |
| Ripples of Nostalgia | 32.9% / 51.3% | 40.5% / 57.4% | 7.5% / 8.1% | 9.6% / 10.5% |
| A Moment in the Afternoon | 21.9% / 27.4% | 26.6% / 37.6% | 7.4% / 8.0% | 9.5% / 10.5% |
| Summer Sanctuary | 20.6% / 28.9% | 19.0% / 26.0% | 6.1% / 6.6% | 6.6% / 7.5% |
| Sparkling Moment | 18.6% / 26.5% | 22.0% / 38.5% | 6.1% / 6.6% | 6.6% / 7.5% |
| Midnight Mayhem | 17.0% / 24.7% | 29.6% / 45.9% | 7.4% / 8.0% | 9.5% / 10.5% |
| Good Night | 16.4% / 24.9% | 7.1% / 14.8% | 4.2% / 4.5% | -1.9% / -1.4% |
| Stellar Destination | 16.0% / 18.9% | 17.0% / 21.5% | 7.5% / 8.1% | 9.6% / 10.5% |
| Prayer Beneath Light | 13.9% / 15.7% | 18.1% / 20.9% | 6.1% / 6.6% | 6.6% / 7.5% |
| Eternal Brilliance | 13.2% / 18.6% | 10.5% / 18.8% | 5.2% / 5.8% | -0.9% / 0.0% |
| Seed Alike | 11.7% / 13.6% | 9.5% / 11.6% | 6.1% / 6.6% | 6.6% / 7.5% |
| main C1 spearman 0.836 |
| main C6 spearman 0.782 |
| support C1 spearman 1.0 |

Rank correlation is computed over Maygi's 11 discs. Our support values run about 1–2 points high for discs with a Lux DMG substat; the order is the same.

## Potentials (Lv6 gain over the reference build)

Glimmer is modelled as of the second pass (see below). Our reference build (2 steps, top 2 main / top 1 per support at Lv6): Empyrean Starfall, Argent Mirage, Prism Warp, Guiding Star (Noya); Domain of Purity, Blade Flash (Firefly); Enemy Counter, Trick Boost (Tilia). For a potential that's in the reference, the gain is measured against the reference with it removed.

| Potential                   | Maygi   | Ours Lv6 | In ref |
| --------------------------- | ------- | -------- | ------ |
| Argent Mirage: Legion's End | S       | 19.60%   | yes    |
| Prism Warp                  | A       | 19.35%   | yes    |
| Resolve: Blitz              | B+      | 12.39%   |        |
| Astral Brilliance           | B+      | 7.13%    |        |
| Guiding Star                | B+      | 12.70%   | yes    |
| Lucent Tide                 | B       | 5.69%    |        |
| Searing Sun                 | B       | 8.57%    |        |
| Veteran's Grit              | C       | 6.54%    |        |
| Domain of Purity            | S       | 25.58%   | yes    |
| Stellar Crash               | A       | 4.08%    |        |
| Blade of Falling Petals     | C       | 0.80%    |        |
| Lightforged Blade           | C       | 0.76%    |        |
| Enemy Counter               | S       | 51.37%   | yes    |
| Blinding Beam               | C       | 2.18%    |        |
| Knight's Seal               | varies  | 2.32%    |        |
| Banner of Glory             | (thumb) | 0.00%    |        |

FL Noya order. Ours: Argent Mirage > Prism Warp > Guiding Star > Resolve: Blitz > Searing Sun > Astral Brilliance > Veteran's Grit > Lucent Tide. Maygi: S > A > B+ (Resolve, Astral, Guiding) > B (Lucent Tide, Searing) > C (Veteran's). The top two and the bottom group are in the right place. **Lucent Tide** is too low, and **Astral Brilliance** is a bit low.

Supports: Domain of Purity and Enemy Counter are S for us too, by a wide margin. Stellar Crash (Maygi A) is still low at 4.1%.

## Emblems (FL Noya, Lv70 stat lines, personal gain)

| Line             | Maygi         | Ours               |
| ---------------- | ------------- | ------------------ |
| HP%              | 11.03%        | 10.43%             |
| Crit Rate        | 10.25%        | 8.48%              |
| Lux PEN          | 8.65%         | 8.65% (calibrated) |
| Skill DMG        | 7.29%         | 8.05%              |
| Skill Crit       | 4.73%         | 4.73%              |
| Lux DMG          | 3.99%         | 6.65%              |
| Crit DMG         | 3.86%         | 6.50%              |
| Lux PEN 2nd line | 0.05%         | 0.49%              |
| Skill +3 (Lv80)  | 10.23% (team) | 9.65% (team)       |
| Ult +3 (Lv80)    | 6.07% (team)  | 4.33% (team)       |

Order: ours HP% > Lux PEN > Crit Rate > Skill DMG > Lux DMG > Crit DMG > Skill Crit. Maygi: HP% > Crit Rate > Lux PEN > Skill DMG > Skill Crit > Lux DMG > Crit DMG.

## Largest discrepancies and likely causes

1. **Midnight Mayhem main 29.7% vs 17.0%** and **Prayer Beneath Light 18.2% vs 13.9%.** All their conditional buffs have an unknown trigger in data, so they run at an assumed 100% uptime (listed in the Notes column). A disc spec pinning down their triggers would fix this, like the one for Ripples.
2. **Good Night 7.1% / 14.8% vs 16.4% / 24.9%.** EffectType 45 (conditional Skill DMG) is now modelled. The melody bonus counts as always on (the main's HP stays above 80%), and harmony 1 applies only while a support is on the battlefield (4 s per support cast, GUESS, `on_field` in the support kits). A longer on-field time raises it.
3. **My Guiding Star C6 124% vs 141%.** The 3-Starwish-stack guess (`specs/discs/214066.yaml`) and the Skill DMG Taken uptime come from hit events. Maygi may count stacks differently.
4. **Ripples of Nostalgia 40.5% vs 32.9%.** Harmony 2's squad Lux DMG fires every 30 Skill DMG hits. Noya lands many Skill DMG hits (Glows), so its uptime is high. The hit counts per Glow volley are `# GUESS` values in `specs/trekkers/162.yaml`.
5. **Lucent Tide too low.** Its first buff (Skill Crit Rate) fires on skill cast and lasts 12 s with 2 stacks; the second now goes to Firefly (class Versatile) per the text. Glows triggering Marks adds little because Marks are limited by the 1 s ICD and Mark availability (one Mark at a time, consumed on trigger, a GUESS). If Marks aren't consumed in game, Mark-related values (Lucent Tide, Stellar Crash, Knight's Seal, My Guiding Star's Crit Rate) all rise.
6. **Crit DMG / Lux DMG emblems too high, Crit Rate too low.** Our baseline has fewer Lux DMG and Crit DMG sources than Maygi's (we rate emblems against pinks plus discs only, no potentials). That makes the buckets emptier, so each line is worth more, and crit DMG is still at base 150%. Rating emblems on the reference build would probably move these toward Maygi's.
7. **Stellar Crash still low.** Each proc now adds as many debuff stacks as the target has Glimmer stacks (max 3). It's capped by its 3 s ICD, not by Noya's hit count, so extra Glow hits don't raise it.

## Second pass (after user feedback)

- **Marks are consumed when triggered** (user-confirmed), as already modelled.
- **On the battlefield:** supports count as on the field for `on_field` seconds per skill or ult cast (default 4 s, GUESS). Good Night harmony 1 and Firefly's Domain of Purity on-field bonus use it.
- **Glimmer** (Word 4029) is now tracked as a debuff from data: Lux DMG Taken +0.5% per stack, 6 s, max 3 stacks, one stack per Lucent. It's up ~87% of the fight.
  - EAT 85 is read as "DMG vs targets with Glimmer". It's used by Noya's autos (+12% per stack at skill 10), Resolve: Blitz and Searing Sun, which previously assumed it was always on.
- **Prism Warp's returning Glows** are Skill DMG hits (HitDamage DamageType 2), one on the way out and one on the way back.

## Inputs to tune first (all `# GUESS` in the specs)

- `specs/trekkers/162.yaml`: auto string duration (3 s), Glow hit counts, whether the ult is always in longsword form under Resolve: Blitz.
- Mark model: consumed on trigger, 1 s ICD (`mark_icd` in the team file).
- `on_field` seconds per support cast (4 s).
- `energy_per_second` (2/s for everyone) and supports' 75% share of the main's energy. These set ult frequency: Noya 3 ults, Firefly 2, Tilia 3.
- Firefly Sword Form cadence and blade counts (`specs/trekkers/115.yaml`).

## Resilience bar (2026-11-03)

The sim now models resilience breaks (`docs/validation/2026-11-03-boss-blitz-breaks.md`). With the bar off (`enemy.resilience: 0`), every number above reproduces exactly (pinks-only total 239,320,242.148, tested). The new baseline is Generic, with a 250M bar, a 10 s ×1.5 break and the lock defaults:

| Run (120 s)     |  Bar off |            Bar on | Breaks (start, s)    |
| --------------- | -------: | ----------------: | -------------------- |
| pinks only      |   239.3M |    252.1M (+5.3%) | 1 (85.2)             |
| reference build | 1,078.8M | 1,258.0M (+16.6%) | 3 (24.5, 58.6, 92.9) |

The reference build's picks are unchanged by the bar.

## Update 2026-11-03: no passive energy

The user tested in game: standing in a boss fight without attacking gains no ult energy. Every kit's `energy_per_second` went from 2.0 (GUESS) to 0. This team, pinks only, bar off: 239.32M -> 223.70M (−6.5%). Ult casts went from 3/2/3 to 2/1/2. Other teams, pinks only: Noya (Ventus) / Ann / Canace −7.6%, FL Noya / Shia / Tilia −9.6%, Chitose −8.7%, Gerie / Nazuna / Ridge −17.5%, Amber / Laru / Flora −3.0%, Mistique −4.2%. Numbers above this section predate the change.

## Update 2026-11-04: every disc specced

`docs/validation/2026-11-04-disc-pass.md`. This team's discs changed in two ways. Ripples of Nostalgia's harmony 1 bonus (+4.5% Auto/Skill DMG for 6 s after the main's Skill DMG) used to be assumed always on and now has its real trigger. A Moment in the Afternoon's Shock is now a named status, so "Skill DMG vs Shocked targets" is tested against it instead of assumed. Pinks only, bar on: 261.05M -> 259.68M (−0.53%). Bar off, no notes (the regression anchor): 223.70M -> 222.42M (−0.57%). Ult casts unchanged.
