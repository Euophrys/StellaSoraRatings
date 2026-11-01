# Validation: Firstlight Noya skill build vs Maygi (2026-11-01)

Run: `python -m ssr teams/fl_noya_skill.yaml -o out/` → `out/fl_noya_skill.xlsx` (~35 s).
Compared with the left half of `example.jpeg`. Enemy RES 145 (calibrated, see `docs/assumptions.md`), DEF 0, skill levels 10, discs at C1 unless stated.

**Summary.** Disc rank order matches well: Spearman 0.84 (main C1), 0.78 (main C6), 1.0 (support C1). My Guiding Star lands within 2 points at C1. Potential order mostly matches; Lucent Tide and Stellar Crash come out too low. Emblem order is close, and Skill Crit Rate matches exactly (4.73%).

## Discs

| Disc | Maygi main C1 / C6 | Ours main C1 / C6 | Maygi support C1 / C6 | Ours support C1 / C6 |
|---|---|---|---|---|
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
main C1 spearman 0.836
main C6 spearman 0.782
support C1 spearman 1.0

Rank correlation is computed over Maygi's 11 discs. Our support values run about 1–2 points high for discs with a Lux DMG substat; the order is the same.

## Potentials (Lv6 gain over the reference build)

Glimmer is modelled as of the second pass (see below). Our reference build (2 steps, top 2 main / top 1 per support at Lv6): Empyrean Starfall, Argent Mirage, Prism Warp, Guiding Star (Noya); Domain of Purity, Blade Flash (Firefly); Enemy Counter, Trick Boost (Tilia). For a potential that's in the reference, the gain is measured against the reference with it removed.

| Potential | Maygi | Ours Lv6 | In ref |
|---|---|---|---|
| Argent Mirage: Legion's End | S | 19.60% | yes |
| Prism Warp | A | 19.35% | yes |
| Resolve: Blitz | B+ | 12.39% |  |
| Astral Brilliance | B+ | 7.13% |  |
| Guiding Star | B+ | 12.70% | yes |
| Lucent Tide | B | 5.69% |  |
| Searing Sun | B | 8.57% |  |
| Veteran's Grit | C | 6.54% |  |
| Domain of Purity | S | 25.58% | yes |
| Stellar Crash | A | 4.08% |  |
| Blade of Falling Petals | C | 0.80% |  |
| Lightforged Blade | C | 0.76% |  |
| Enemy Counter | S | 51.37% | yes |
| Blinding Beam | C | 2.18% |  |
| Knight's Seal | varies | 2.32% |  |
| Banner of Glory | (thumb) | 0.00% |  |

FL Noya order. Ours: Argent Mirage > Prism Warp > Guiding Star > Resolve: Blitz > Searing Sun > Astral Brilliance > Veteran's Grit > Lucent Tide. Maygi: S > A > B+ (Resolve, Astral, Guiding) > B (Lucent Tide, Searing) > C (Veteran's). The top two and the bottom group are in the right place. **Lucent Tide** is too low, and **Astral Brilliance** is a bit low.

Supports: Domain of Purity and Enemy Counter are S for us too, by a wide margin. Stellar Crash (Maygi A) is still low at 4.1%.

## Emblems (FL Noya, Lv70 stat lines, personal gain)

| Line | Maygi | Ours |
| --- | --- | --- |
| HP% | 11.03% | 10.43% |
| Crit Rate | 10.25% | 8.48% |
| Lux PEN | 8.65% | 8.65% (calibrated) |
| Skill DMG | 7.29% | 8.05% |
| Skill Crit | 4.73% | 4.73% |
| Lux DMG | 3.99% | 6.65% |
| Crit DMG | 3.86% | 6.50% |
| Lux PEN 2nd line | 0.05% | 0.49% |
| Skill +3 (Lv80) | 10.23% (team) | 9.65% (team) |
| Ult +3 (Lv80) | 6.07% (team) | 4.33% (team) |

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
