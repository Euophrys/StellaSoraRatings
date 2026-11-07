# Gerie / Nazuna / Ridge: which order? (2026-11-03)

Question from the community: Earth (Terra) team as **Gerie (main) / Nazuna / Ridge** or **Nazuna (main) / Gerie / Ridge**?

## Setup

- New kit specs: `specs/trekkers/149.yaml` (Gerie, main + support), `156.yaml` (Nazuna, main + support), `116.yaml` (Ridge, support). All three pools authored. Timings are the user's frame counts (30 fps); every guess is marked `GUESS` in the specs.
- Teams: `teams/gerie_nazuna_ridge.yaml`, `teams/nazuna_gerie_ridge.yaml` (generic enemy, 120 s, **resilience bar off**), plus `teams/bb_*.yaml` (Lithe Beauty, 180 s, breaks on). Filler discs for both, so the comparison is about the kits.
- Pinks (user's): Gerie main Avalanche of Stone + Beyond All Control; Nazuna support Arrow of Affection + Sweetheart Bloom; Ridge Reblossom + Sense the Stir; Nazuna main Small Force + Wobble Dance; Gerie support Deeper into Sin + Sin-Bound Echo.
- `python -m ssr.compare ... --split 30,15,15` (main first).

## Results

| enemy | N=0 | N=30 | N=60 |
| --- | --- | --- | --- |
| generic, 120 s, bar off | 26.4M vs 26.4M (100%) | 206M vs 168M (81%) | **356M vs 258M (73%)** |
| Lithe Beauty, 180 s, breaks | 50.3M vs 51.9M (103%) | 319M vs 280M (88%) | 482M vs 508M (105%) |

(G/N/R first, then N/G/R; the percentage is N/G/R relative to G/N/R.)

- Generic boss: Gerie main wins clearly once potentials are in (+37% at 60 levels; +49% at 180 s with the same builds). Gerie main does 89% of the team's damage (69% autos: the Lethal string + Avalanche extra hits, kept up nearly all fight by Lingering Hunger / Piercing Sorrow).
- Nazuna main: Gerie as support still does 70% (Mark DMG 27%, ult 33%). Nazuna's own damage is small; her value is the penguin's Terra DMG Taken debuff, Touch of Nature (+420% Mark DMG) and squad ATK buffs.
- Lithe Beauty: about even. Its ability (Skill DMG Taken from skill hits) favours the skill-heavy N/G/R. The break timing also swings the totals by ±5–10% per pick: the greedy curves are non-monotonic (G/N/R gains only +1.4M from N=30 to N=40). With the bar off but the ability on, the two final builds are 472M vs 478M.

## Model changes

- `BuffSpec.requires_all` (kit buffs): a buff that needs all of several potentials (Gerie's Lethal with both Lingering Hunger and Piercing Sorrow). Before this change, buffs ignored the key. No existing spec used it on a buff. Test: `tests/test_kit.py::test_buff_requires_all_gerie_lethal`.
- Noya impact: none (no spec change; full `pytest` passes).

## Finding: break timing makes greedy builds noisy

The generic enemy has a 250M resilience bar. In a 120 s fight it breaks once (~89 s). Whether Gerie's 3rd ult (~99 s) lands inside the 10 s window decides ±17M of ult damage. A Ridge potential that moves the break 0.8 s earlier made the total _drop_ 5%. That's why the 120 s team files set `resilience: 0`. Worth a general fix later (e.g. averaging over break phase, or a smoother break model) before greedy builds on breakable enemies are trusted.

## Open questions for the user

1. **Gerie ult hit count**: the text says 3 shovels × 3 hits (modelled: 9 hits); the user saw 4 numbers. If it's really 3 hits, Gerie's ult share drops by ~2/3 in both orders (more in N/G/R, where the ult is 33%).
2. **Avalanche of Stone**: an extra hit per auto _hit_ (modelled; user saw 15 numbers vs 16 expected) or per strike?
3. **Lethal auto string**: modelled at the Lethal speed (2.77 s per string vs 3.5 s outside Lethal). Is Gerie faster in Lethal, or did the slower clip include walking?
4. **Lethal duration**: 12.3 s in the clip = cage + 4 s (Lingering Hunger's text). Did that run have Lingering Hunger? If not, base Lethal is longer than modelled.
5. **Nazuna support raffle odds** with Arrow of Affection (GUESS: 60% full hearts / 40% 2 hearts + 1 penguin).
6. **Nazuna main skill lock** (when autos resume after Plushie Dance): GUESS 0.8 s. **Nazuna ult lock as main**: GUESS 2.9 s.
7. **Gerie support ult on-field time**: GUESS 3 s.
8. **Touch of Nature** "+420% Mark DMG Multiplier": modelled as +420% in the Mark DMG bucket. If it adds to the hit's multiplier instead (125% → 545%), N/G/R's Mark damage is about the same; if it's something smaller, N/G/R drops.
9. Enemy DEF shred (Ridge's Corrosive Vines / Root Grasp) isn't modelled by the engine. It affects both orders equally.

## Update (same day): user's guide build and video data

New from the user: Gerie guide build `AAAAlQAAAJwAAAB0zbYDAAAwBthgMMGwAGwA` (Gerie: Delight in Ruin, No Safeword, Lingering Hunger, Slanderous Strike, Shared Sensation; Nazuna: Love's True Strike, Honeyed Arrow, Lucky Drop, Rain of Passion, Balloonado; Ridge: Corrosive Vines, Bouquet Blast, Root Grasp, Small Changes; all Lv6). Arrow of Affection raffles over 19 rolls: 10 HHH, 9 two hearts + one penguin, so the odds are now 53/47. Nazuna main locks: skill 0.733 s, ult 3.4 s (bolt timings). Gerie's ult: 3 shovels, all three hit in the Gerie clip, so 3 x 3 hits stays. The guide includes Lingering Hunger, which resolves open questions 1, 4, 5 and 6.

Budget 30/30/24 (the guide's). The Boss Blitz greedy run broke down: Gerie-main stayed at 319.5M from N=30 to N=60 because break timing made every pick look negative. So the fixed builds below were scored on each enemy instead:

| build | generic 120 s | Lithe Beauty, breaks | Lithe Beauty, bar off |
| --- | --- | --- | --- |
| G/N/R guide build | 318M | 479M | 537M |
| G/N/R best (bar-off greedy, 84 levels) | 482M | 805M | 892M |
| N/G/R best (bar-off greedy, 84 levels) | 407M | 793M | 733M |

- At equal budgets, Gerie main is ahead by 18% on the generic boss and 22% on Lithe Beauty with the bar off. With breaks on, the two are even (+1.5%). Break timing is a knife-edge in this model (see above), so that gap is within the noise.
- The guide build scores well below the greedy one. Its 12 Ridge levels in Corrosive Vines and Root Grasp (DEF shred) count as 0 here because the engine doesn't model them. It also skips Gerie's ult potentials (Quadrifrons' Lore, Samsara's Judgment), which the sim rates highly because of the 9-hit ult.

## Update 2: enemy DEF reduction

The engine now applies enemy DEF reductions (`stat: 2`, `target: enemy`): effective DEF = max(0, (500 + flat) × (1 + %)) before defAmend (`docs/reference/damage-formula/2.def.c`; the user confirmed DEF 500). Ridge's Corrosive Vines (−30 × 5 stacks from seed hits) and Root Grasp (−151 on Seed Orb targets) use it. A scan of all kits' pools and all discs found no other enemy-DEF modifiers, so other teams don't move. Tests: `tests/test_def_shred.py`; full suite 271 passed.

Budget 30/30/24 again (bar off for the greedy run; fixed builds scored on each enemy):

| build | generic 120 s | Lithe Beauty, breaks | Lithe Beauty, bar off |
| --- | --- | --- | --- |
| G/N/R guide build | 441M (318M before) | 663M | 744M |
| G/N/R best | 631M | 1145M | 1151M |
| N/G/R best | 484M | 965M | 858M |

- Gerie main is now ahead everywhere: +30% generic, +19% Lithe Beauty with breaks, +34% without. DEF reduction scales the bigger damage pool, so it helps G/N/R more.
- Both greedy builds take Corrosive Vines and Root Grasp at Lv6, matching the guide's Ridge.
- The gap between the guide and the greedy build (441M vs 631M) is mostly Gerie's ult potentials (Quadrifrons' Lore, Samsara's Judgment) and Nazuna's Rocket Cart / Double Delight, which the guide skips. Rocket Cart and Double Delight rest on guessed uptimes (Rocket Cart: one stack every 3rd ult hit; Double Delight: 40%).

## Correction: "bar off" overrates Gerie main (No Safeword)

With the bar off, `while:broken` falls back to `unknown_trigger_uptime` (1.0), i.e. **always broken**. Gerie main's No Safeword (+140% Auto DMG vs Broken targets at Lv6) was therefore on all fight in every bar-off number above. G/N/R best build:

| | generic 120 s | Lithe Beauty 180 s |
| --- | --- | --- |
| bar off (always broken) | 631M | 1151M |
| bar off, never broken | 510M | 948M |
| breaks on | — | 1145M (37 s broken of 180) |

Breaks are a clear gain (+21% over never broken). The bar-off "win" over breaks was the fallback. N/G/R has no broken-target potentials, so its numbers are unaffected. Corrected reading: generic ~510M vs 484M (+5%, and the greedy build spent 6 levels on No Safeword because of the inflated value), Lithe Beauty with breaks 1145M vs 965M (+19%). The greedy runs with the bar off need redoing once the fallback is realistic.
