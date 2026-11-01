# FL Noya T1 / Shia / Tilia vs FL Noya T0 / Firefly / Tilia (2026-11-01)

Run: `python -m ssr.compare teams/fl_noya_t1_shia_tilia.yaml teams/fl_noya_t0_firefly_tilia.yaml teams/fl_noya_t1_firefly_tilia.yaml --split 30,15,15` (~15 min). All teams: Noya Lucent Blitz + Dawnflare; Tilia Perfect Spiral + Renewed Spectrum; discs My Guiding Star, Ripples of Nostalgia, A Moment in the Afternoon (C1). Shia: Bunny Torrent + Rabbit Flip (user's build). Firefly: Twin Shadow + Firefly.

## Result (second pass, after the Firefly and Shia timings)

| levels         | T1 / Shia | T0 / Firefly | T1 / Firefly |
| -------------- | --------- | ------------ | ------------ |
| 0 (pinks only) | 440.2M    | 478.6M (109%) | 519.9M (118%) |
| 10             | 848.8M    | 926.6M (109%) | 1003.5M (118%) |
| 30             | 1864.6M   | 1968.4M (106%) | 2124.5M (114%) |
| 50             | 2385.5M   | 2778.5M (116%) | 2989.4M (125%) |
| 60             | 2451.2M   | 2976.1M (121%) | 3191.5M (130%) |

T0 Firefly beats T1 Shia by ~21% with a full build. T1 is worth ~+7–9% on the Firefly team.

The first pass (Firefly on the old 4 s on-field / ~30 blade-hit guess) had them within 4% of each other. The user's Firefly clip changed that. She's on the battlefield 21.5 s of her 24 s cooldown, so Domain of Purity's on-field bonus is up ~90% of the fight, and she fires 6 volleys of ~10 blades per cast. Each blade inflicts a Mark, which keeps Noya's Lucent/Glimmer fed.

Shia: Moonfall (+120% Crit DMG to Lux Trekkers at Lv6, user-confirmed) is her only strong potential. Her skill and ult *trigger* Lux Marks, so she uses up Tilia's Marks: Glimmer is up 68 s vs 102 s with Firefly.

T1 (Buried Past): Starender is up 118.5 s of 120 (T0: 90 s), plus +12% Crit DMG in Starender and the 10 stat nodes.

## User timings (frame-timed, 30 fps)

Recorded at the top of `specs/trekkers/162.yaml`, `155.yaml` and `115.yaml`. Noya: auto string 4.7 s (7 greatsword hits, Strike 4, then a sprint attack after the backflip), skill lock 2.1 s (was 5.0), Flurry lock 1.4 s (was 3.0), ult lock 3.23 s (was 4.0). Shia on field 12.83 s (skill) / 8.23 s (ult); one surf hit per pass (text says x2); ~28 ult hits. Tilia 2.93 s / 4.1 s. Firefly (built, both pinks): Giant Sword loop every 5.5 s ×3, 6 blade volleys of ~19 hits (read as 10 blades + 10 Radiance Blade: Firefly bursts), on field 21.53 s (skill) / 6.3 s game time (ult; the cutscene freezes time).

## Model changes

- **Talents:** team member `talents: N`; stat nodes from data, key talents from the kit's `talents:` (Buried Past). `&once` event qualifier.
- **Supports can trigger Marks** when their kit has `mark:` (Shia's Thunderbolt).
- Noya: sprint attack (x3) + Dawnflare's 3 sprint Glows (+ Prism Warp returns) in every auto string; Starender is a named status.
- New kit `specs/trekkers/155.yaml` (Shia, support).
- Firefly: Radiance Blade: Firefly's bursts are now a proc per blade hit; Twin Shadow stacks build per blade hit and reset on the next cast (was a flat half-stack guess).

## Regression (`teams/fl_noya_skill.yaml`, from the Noya timing changes)

My Guiding Star C1/C6 76.6/124.3 → 82.7/135.1 (Maygi 78.4/140.8). Ripples 40.5 → 43.2 (Maygi 32.9). A Moment in the Afternoon 26.6 → 35.6 (Maygi 21.9). Lucent Tide 5.7% → 10.0% (Maygi B, was too low). Argent Mirage 19.6% → 37.5%. Dawnflare now gives 9 Flurries per 12 skills (was ~every 2 skills).

## Open questions

1. **Shia small hits:** bullets/missiles per ride and Rabbit Flip ticks can't be told apart in game (all ~767). They're GUESS, but don't matter.
2. **Does "ride DMG"** (Bunny Torrent, Flow Reversal) include bullets/missiles or only the surf hits? Only Flow Reversal is affected, and Shia's damage share is small.
3. **Firefly volley split:** ~19 hits per volley read as 10 blades + 10 bursts. Stellar Crash's extra blades (one per 3 s) may account for 1–2 of them.
4. **Radiance Flurry frequency:** with 5 Glows per auto string (user-confirmed), it comes 9 times per 12 skills.
5. Discs aren't re-picked per team.
