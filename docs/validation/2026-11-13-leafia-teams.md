# Leafia teams (2026-11-13)

Leafia (161, Terra, Versatile) released with patch data pulled today. Three setups, all Terra, filler discs, 120 s, bar off:

- `teams/nazuna_leafia_gerie.yaml`: Nazuna main, Leafia (Tactical Co-Draw + Observer Iteration) and Gerie support. This is the community suggestion.
- `teams/leafia_nazuna_gerie.yaml` and `teams/leafia_nazuna_ridge.yaml`: Leafia main, build 1 (Focused Penetration + Crystal Overclock). Build 2 (Field Assault + Field Echo) was compared from scratch copies of the same files.

Kit: `specs/trekkers/161.yaml`, with the user's timings in its header. Modelling choices: `docs/assumptions.md`, "Leafia: Resource Markers and Observation Points".

## Results

`python -m ssr.compare ... --split 30,15,15` (greedy build, now with lookahead, see below):

| team                                   | N=0   | N=30   | N=60   |
| -------------------------------------- | ----- | ------ | ------ |
| Nazuna / Leafia / Gerie                | 35.2M | 177.8M | 317.9M |
| Leafia (crystal) / Nazuna / Gerie      | 15.1M | 106.1M | 165.2M |
| Leafia (turret) / Nazuna / Gerie       | 10.1M | 112.3M | 196.1M |
| Leafia (crystal) / Nazuna / Ridge      | 15.6M | 119.9M | 243.2M |
| Leafia (turret) / Nazuna / Ridge       | 11.2M | 121.9M | 273.0M |
| Nazuna / Gerie / Ridge (before Leafia) | 15.0M | 98.3M  | 198.2M |
| Gerie / Nazuna / Ridge (before Leafia) | 17.1M | 150.8M | 314.9M |

- **Nazuna main with Leafia support is the best of the new teams** (1.6x Nazuna/Gerie/Ridge at N=60, level with Gerie/Nazuna/Ridge). Leafia's turret does ~70% of the team's damage. Her support build: Leyline Amp (all-Terra squad ATK +60% at Lv6) and Tier 2 Etching at Lv6.
- **As main, Leafia is better with Ridge than with Gerie**, and the turret build edges out the crystal build once Observer Array reaches Lv6 (3 turrets).
- Pink search, main (`leafia_nazuna_ridge`): Field Echo + Field Assault 98.5% / 100% (team discs / own discs), Crystal Overclock + Focused Penetration 100% / 89.5%. Both builds the user named are top.
- Pink search, support (`nazuna_leafia_gerie`): Vanguard Calibration + Calibration Detonation 100%, Co-Draw + Vanguard Calibration 95%, **Co-Draw + Observer Iteration (community) 78.5%**. The Calibration pinks are the least certain part of the kit (below), so this ranking isn't trustworthy yet.

## Model changes

- **Resources** (`specs/README.md`): kit `resources:`, proc `gain` / `cost` / `summon`, `while:resource:<who>:<name>>=N`, pool `at_max: block`. Used for Resource Markers, crystals and marker-built turrets.
- **Greedy lookahead** (`compare.py`, also the web optimizer): each step also tries a potential's jump to its cap. Without it Observer Array (turret limit 1/2/3 at Lv1/4/6) was stuck at Lv1, and the turret build read as 86M / 109M at N=60 instead of 196M / 273M. Other teams barely move (Nazuna/Gerie/Ridge 198.4M → 198.2M at N=60).
- **New discs** in the patch, both Terra: Beneath Billowing Sails (214068) and Emergency Evacuation (214069), specced from their text. The pink search already picks Billowing Sails for Leafia main.
- Leafia's key talents are specced.
- **Regression:** `fl_noya_skill`'s workbook and every existing team's pinks-only total are identical before and after.

## Open questions for the user

1. **Crystal Overclock autos:** are the 6 hits per string all crystals or strikes, or a mix? The model makes a swing a crystal (332%, replacing the 185% strike) whenever 3 Markers are held, which gives ~2/3 crystals with Focused Penetration. Does a crystal also generate Markers? A clip with 6 damage numbers would settle it.
2. **Focused Penetration's extra Marker:** is it on every auto hit, or only when a hit already generates one? (This only matters without Overclock.)
3. **Turret limit:** at the limit, does a new Observation Point replace the oldest, or is it not created? Replacing costs ~1.8 s of windup each time.
4. **Ult interval:** did your ult clip have Draw Zone Bombardment? The text says every 3 s and you saw 2 s.
5. **Main skill:** how long until autos resume after Crystal Vein Survey (lock, guessed 1.5 s)?
6. **Support Calibration pinks:** does Vanguard Calibration fire a full Vanguard Strike (327%, or 786% with Detonation) every second from each turret? How long do Calibration stacks take to detonate in practice? A clip would show whether the pink search's preference for them is real.
7. **Field Echo without Field Assault:** wave timing is guessed (every 9 s).
8. **New discs:** "Support Trekker" in Billowing Sails' harmony 2 is taken as the support slots, and Voyage stacks are shared between the two supports.

## Second pass (same day): user follow-up

The user answered most of the open questions:

- **Turrets replace the oldest.**
- **Ult every 2 s comes from Draw Zone Bombardment**, which every trial build has.
- **Crystals:** an attack-by-attack clip, read in `specs/trekkers/161.yaml`:
  - Markers come 2 at a time, at most once per second.
  - The "stronger" attack is the Amplification Crystal.
  - The "extra crystal" is Marker Overload's Vector Crystal.
  - The skill lock is 1.2 s.
- **Calibration support clip:** a Vanguard Strike every second, with the first 3-stack detonation on the 3rd strike. The model's ratio for that strike is 1.9x the first, against 2.06x seen.

The Marker limit cuts the crystal build: at N=60 it drops from 165M to 134M with Gerie and from 243M to 188M with Ridge. The turret build is now clearly the better main build.

New teams: `teams/nazuna_leafia_ridge.yaml` and `teams/nazuna_leafia_springseek_coronis.yaml`. Springseek Coronis uses Essence Extraction + Vernal Breath, the top pair in the pink search.

`--split 30,15,15`, N=60. Rows marked "Calibration" give Leafia Vanguard Calibration + Calibration Detonation (scratch copies):

| team | N=0 | N=30 | N=60 |
| --- | --- | --- | --- |
| Nazuna / Leafia / Gerie | 35.2M | 177.8M | 317.9M |
| Nazuna / Leafia / Ridge | 33.4M | 181.4M | 315.7M |
| Nazuna / Leafia / Springseek Coronis | 67.3M | 288.2M | 487.9M |
| Nazuna / Leafia Calibration / Gerie | 36.9M | 266.1M | 405.8M |
| Nazuna / Leafia Calibration / Ridge | 35.4M | 276.0M | 485.2M |
| Nazuna / Leafia Calibration / Springseek Coronis | 66.9M | 354.9M | 624.6M |
| Leafia (crystal) / Nazuna / Gerie | 13.1M | 86.2M | 134.4M |
| Leafia (turret) / Nazuna / Gerie | 10.4M | 113.6M | 198.9M |
| Leafia (crystal) / Nazuna / Ridge | 13.4M | 97.0M | 187.6M |
| Leafia (turret) / Nazuna / Ridge | 11.4M | 123.6M | 276.9M |
| Gerie / Nazuna / Ridge | 17.1M | 150.8M | 314.9M |

- **Gerie vs Ridge with Nazuna + Leafia** is a wash on Co-Draw + Observer Iteration. With the Calibration pinks, Ridge is ahead (485M vs 406M).
- **The Calibration support pinks** beat Co-Draw + Observer Iteration by 28–53% at N=60. Their build is Mark Suppression and Calibration Expansion at Lv6. The clip supports the strike cadence and the 3rd-strike detonation.
- **Springseek Coronis** comes out far ahead (57% of the team's damage), but her support kit is untimed. Her number rests on all 6 Rose Vials hitting the boss for their full 6 s, plus Essence Extraction's six 715% hits as the vials expire. Treat it as unverified until her timings are measured.

Still open: questions 6 (partly answered), 7 and 8 above, and Springseek Coronis's support timings (cast to first vial tick, how many vials hit a boss, on-field time).
