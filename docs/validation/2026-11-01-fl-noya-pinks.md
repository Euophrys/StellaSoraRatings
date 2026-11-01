# Pink pair search: Firstlight Noya (2026-11-01)

Run: `python -m ssr teams/fl_noya_skill.yaml --pinks` (~70 s for one member).

Each of the 6 pink pairs gets its own greedy reference build of normal potentials (`build_reference`), and the fight total is compared. It's scored twice: with the team file's discs, and with the top 3 main discs re-picked for that pair (C1, each rated alone). With several members named (`--pinks "Firstlight Noya" Firefly Tilia`), members are searched one at a time: each takes the best pair given the earlier winners, and members not named keep their team-file pinks. That's 6 runs per searched member instead of 6^n.

**Expected:** Lucent Blitz + Dawnflare (skill build) and Stardust Descent + Sinbreaker (auto build) on top, the other four markedly worse.

## Results (% of the best pair, own discs)

| Pair                            | ref depth 2 | ref depth 4 |
| ------------------------------- | ----------- | ----------- |
| Lucent Blitz + Dawnflare        | 100.0%      | 100.0%      |
| Stardust Descent + Sinbreaker   | 93.5%       | 92.0%       |
| Lucent Blitz + Sinbreaker       | 93.4%       | 87.7%       |
| Lucent Blitz + Stardust Descent | 92.2%       | 90.1%       |
| Dawnflare + Stardust Descent    | 79.1%       | 71.3%       |
| Dawnflare + Sinbreaker          | 77.4%       | 69.3%       |

Depth 2 = the team file's reference (2 steps × 2 main picks, 4 Noya potentials). Depth 4 = 8 Noya potentials. The re-picked discs came out identical for every pair (My Guiding Star, Ripples of Nostalgia, Midnight Mayhem).

The top two are right. The Dawnflare-without-Blitz pairs are markedly worse. The two Blitz mixes are only 1–5 points behind the auto build, so the auto build isn't clearly separated from them yet.

## Model changes made for this

- **Stardust Descent:** +2 Starfalls per skill, plus 1 Starfall per Mark trigger (1 s ICD). Starfalls use hit 162310008, Auto DMG. Sprint attacks are not modelled.
- **Sinbreaker:** a Judgment Starfall (162100007 ×2, triggers Marks) per 11 Starfalls (count from data). It's added on top of the auto string, not replacing a strike (GUESS), and every Starfall is assumed absorbed. Its Auto DMG stat applies to auto hits.
- **Eclipse Phantom:** the field fires per Judgment Starfall (it used to be one per auto string).
- **Gavel of Absolution:** one lightning bolt per Starfall, 2 s after it lands (GUESS). It used to be one per skill.
- **Dawnflare:** Radiance Flurry now comes per 17 Glows fired (count from data), not "every 2nd skill". With Lucent Blitz that's 7 Flurries per fight vs 6 before. Without Blitz it's far fewer, which is what separates the Dawnflare-without-Blitz pairs.
- Engine: procs take `every: N`, and follow-ups can count events (`followup: {event, every}`).

## Why the auto build is probably undervalued

1. **Enemy DEF is 0**, so Resolve: Sunder (DEF PEN on greatsword hits and Starfalls) is worth nothing, and the reference never picks it. It's a core auto-build normal.
2. **Starfall supply is a guess:** the +2 per skill, absorption (each absorbed Starfall also dissipates for Gavel?) and timing. Judgment Starfall frequency follows directly from it.
3. **Sprint attacks** (Stardust Descent's greatsword sprint + Starfall) aren't modelled; melee range is assumed throughout.
4. **No auto-specific discs:** the re-picked discs are the same as the skill build's, which suggests auto-scaling disc effects are thin or unmodelled.

## Supports (search ran, results not trustworthy)

`--pinks "Firstlight Noya" Firefly Tilia` (117 s) ranks Firefly's Twin Shadow + Firefly last (92.9%) and Tilia's Perfect Spiral + Renewed Spectrum 4th (91.2%). Both are the pairs actually used. The pinks not in the build are rough stubs in `specs/trekkers/115.yaml` and `107.yaml`, as Noya's auto pinks were, so this needs the same spec work before support searches mean anything.
