# Noya (Ventus) / Ann / Canace — 2026-11-03

The game's tutorial build, timed by the user's friend. Team file: `teams/noya_ann_canace.yaml` (generic enemy, 180 s). New kits: `specs/trekkers/112.yaml` (Noya), `123.yaml` (Ann), `120.yaml` (Canace). Timings are in the spec headers.

Pinks: Noya Dual Strike + Chain Slash, Ann Gale Bastion + Wind Banish, Canace Efficient Delving + Transformative Insight.

## Model choices

- Noya's skill chain: Sonic Slash, then Devastating Wind, Dragon Slash and Devastating Wind again as followup actions. Autos resume 4.37 s after the cast.
- The skill CD starts 2.0 s after the cast. Both clips fit this, the dash-cancelled one too.
- The Breeze Cyclone is the mark hit plus a 2-hit proc (text says x3).
- Engine: a marker hit (`hit: 0`) with `applies_mark` now inflicts a Mark. Ann's wall uses it. No existing spec had such a hit, so the Noya regression is unaffected. `pytest`: 279 passed.

## Results (no potentials, filler discs)

- Noya 44% of team DMG, Canace 39%, Ann 17%. The skill chain is ~75% of Noya's damage, autos ~7%.
- Dash-cancelling the skill: −6%. That's with a 0.5 s earlier CD start granted, which the clips don't support.
- Waiting before Dragon Slash: −2.3% for 0.5 s, −4.3% for 1.33 s (the clip).
- Greedy 30/15/15 build: Noya ~45%. Biggest gains: Canace Structure Analysis, Ann Turbulent Flow / Wind Erosion Havoc. Noya's own best are Space Splitter, Hero's Instinct, Choreographed Assault, Cloud Swirl, Sandstorm Crush (~10–13% at Lv6).
- Discs (top: Daylight Garden, Sky Flowers Poem) still rely on assumed uptimes or scripted parts that aren't modelled yet.

## Open questions (GUESSes in the specs)

- Gale Bastion: do all 3 walls hit the boss, both on the cast hit and on Wind Banish pulses? The model assumes yes.
- Wind Banish: 6 pulses per wall?
- Wind Slash / Triple Blinks: how many sword auras ("multiple")? The model assumes 3.
- Canace's ult: does the tutorial build include Storm Suppression (17 ticks)? The 0.23 s spacing was assumed for 9 ticks.
- Blade Storm (pink) isn't modelled. ATK SPD (Flurry Stance, Speed Surge) isn't modelled either.

## Update: user answers, pinks, 60-level build

- User: Canace's ult is 17 ticks (Storm Suppression); Ann's walls pulse 8 times; Triple Blinks fires 3 auras per cast;
  Wind Slash fires 4 per Devastating Wind.
- Engine: `cd_start` on an action (its CD starts N s after the cast). Noya's skill uses 2.0 for every pink pair. Before,
  the delay came from Chain Slash's `starts_cd`, so pairs without Chain Slash got 36 skill casts instead of 26.
- Pinks-only search (all 216 combos, no potentials): Noya Dual Strike + Chain Slash (next: Dual Strike + Windfury −4%),
  Ann Gale Bastion + Wind Banish (next −6.5%), Canace Efficient Delving + Speedup Notion (+8% over the tutorial's
  Transformative Insight). Blade Storm isn't modelled, so it ranks low.
- 60 total, caps 30/20/20 (`guide.optimize`): run with the resilience bar off, because one late break makes the greedy
  chase timing noise (adding Hero's Instinct read −0.8%). The build never breaks the bar in 180 s either way.
  Pinks-only 17.6M -> 98.3M (5.6x). Noya 44%, Canace 48%, Ann 8%. Levels end up 20/20/20.
  Noya: Space Splitter 6, Hero's Instinct 6, Sandstorm Crush 4, Choreographed Assault / Wind Slash / Cloud Swirl /
  Triple Blinks 1. Ann: Turbulent Flow 6, Wind Erosion Havoc 6, Windgate Barrier 5, Violent Current / Forest Princess /
  Speed Surge 1. Canace: Structure Analysis 6, Finale Deduction 6, Downwind Area 2, Storm Suppression / Structure
  Shatter / High Pressure Reflux / Cyclone Acceleration / My Thoughts / Conundrum Solving 1.
