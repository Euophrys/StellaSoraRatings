# Validation: resilience breaks and Boss Blitz enemies (2026-11-03)

Spec: `docs/superpowers/specs/2026-11-03-resilience-break-design.md`. Plan: `docs/superpowers/plans/2026-11-03-resilience-break.md`.

## Setup

- **Bar** (`src/ssr/resilience.py`): 250M resilience, 10 s break, then a full refill. After the refill, a lock (`lock_delay` 1.3 s, then `lock_time` 4.7 s, GUESS) during which the bar can't be lowered. Damage while broken or locked doesn't lower it. An overkill hit breaks it once, and the excess is lost.
- **Resilience per hit:** the hit's damage without the break ratio × the hitter's `ToughnessDamageAdjust` (×1.5 or ×1.0; minions use their owner's) × (1 + Resilience Break Efficiency). The hit that breaks the bar isn't boosted.
- **Break ratio:** ×1.5 (`break_ratio`, unverified; see below).
- **Presets** (`specs/enemies/`):

| Preset | RES (weak / neutral / own) | DEF | Resilience | Fight | Ability |
| --- | --- | --: | --: | --: | --- |
| `generic` | 145 (all) | 500 | 250M | team file (120) | none |
| `lithe_beauty` | 145 Lux, Terra / 645 / 1895 Ignis | 500 | 250M | 180 s | Ult DMG taken → Mark DMG Taken +4% (15 s, 4 stacks); Skill DMG taken → Skill DMG Taken +12% (15 s, 4 stacks) |
| `count_of_the_duloos` | 145 Lux, Aqua / 645 / 1895 Ventus | 500 | 250M | 180 s | main triggers a Mark → Skill DMG Taken +8% (3 s, 5 stacks); main Max HP +20% |

RES = data `{W,F,S,A,L,D}ERFix` − 105 baseline PEN, the same convention as the hand-written enemies.

> **Update 2026-11-07:** the 105 is gone; presets now use the raw data RES (250 / 750 / 2000) and Generic 250 (`docs/assumptions.md`). This doc's tables are from RES 145. On current code, `bb_noya_shia_tilia_ingame` gives 1,663.0M and 5 breaks (+2.7% vs the in-game 1,620M), against 1,779.2M and 6 breaks at the old RES.

- **Team files:** `bb_noya_shia_tilia` (copy of `fl_noya_t1_shia_tilia` at T0, vs Lithe Beauty, 180 s); `bb_noya_shia_tilia_ingame` (the user's calibration build, Trekker and disc levels 70/80, build-level ATK/HP and emblem rolls as `bonus_stats`, fixed potentials); `chitose_freesia_teresa` now vs Count of the Duloos, 180 s. `fl_noya_skill` stays on Generic.

## Regression anchor: `fl_noya_skill`

With the bar off (`resilience: 0`), the pinks-only total is **239,320,242.148** before and after the change, an exact match (`tests/test_resilience_sim.py::test_bar_off_matches_pre_resilience_totals`). With the bar on (Generic):

| Run                    |  Bar off |            Bar on | Breaks (start, s)    |
| ---------------------- | -------: | ----------------: | -------------------- |
| pinks only, 120 s      |   239.3M |    252.1M (+5.3%) | 1 (85.2)             |
| reference build, 120 s | 1,078.8M | 1,258.0M (+16.6%) | 3 (24.5, 58.6, 92.9) |

The greedy reference build picks the same eight potentials with the bar on or off, so there's no flip-flop on this team.

## Calibration build vs the in-game run (Lithe Beauty, 180 s)

In-game: **1,620M** total (Noya 1.6B, Shia 12M, Tilia 3.7M), 4–5 breaks. The breaks at ~27.6 / 72.8 / 109.8 s are active time (ult freezes excluded).

| `break_ratio` | Total | Noya | Shia | Tilia | Breaks (start, s) |
| --- | --: | --: | --: | --: | --- |
| bar off | 1,547.3M | 1,524.1M | 18.9M | 4.3M | 0 |
| **×1.5** | **1,782.5M** (+10% vs in-game) | 1,755.3M | 22.2M | 4.9M | 5 (30.2, 64.6, 93.8, 125.9, 156.4) |
| ×2.5 | 2,252.8M (+39%) | 2,217.7M | 28.8M | 6.3M | 5 (same) |
| ×1.5, no lock | 1,837.7M | 1,811.1M | 21.6M | 5.0M | 5 (30.2, 62.7, 92.7, 123.9, 154.8) |

- **Break ratio:** ×1.5 lands much nearer 1,620M. The gaps below could explain +10%, but not +39%. **The default stays ×1.5.**
- **Break count:** 5, at the top of the in-game 4–5. The first break comes at 30.2 s (in-game ~27.6 s). Later intervals are ~30–35 s against in-game ~37–45 s of fight time, which includes ult freezes the sim doesn't model.
- **Lock:** the 4.7 s lock costs ~3% (1,837.7M → 1,782.5M) and moves breaks ~1–2 s later. It wasn't retuned: one recorded lock doesn't constrain a rule, and the second recorded lock (~0.3 s) contradicts any fixed rule.
- **Split:** Noya ~98.5% in the sim vs 99% in-game. Shia (22M vs 12M) and Tilia (4.9M vs 3.7M) are both high. Shia's support skill level 1 is modelled; her stats are not (support discs are filler, below).

**Unmodelled gaps, and which way each skews the sim:**

| Gap | Effect on the sim |
| --- | --- |
| Harmony skill levels (all Lv2, Infinite Sunshine Lv1): the engine takes disc effects from copies only | sim **high** (C6 discs with Lv2 harmonies are weaker in-game) |
| Support discs unknown → filler (Lv80 C6 Eternal Brilliance stats) | probably **high** |
| Build-level ATK/HP applied to Noya only (unsure whether it's squad-wide) | slightly **low** for supports |
| Notes not modelled | **low** |
| Movement and missed attacks; RNG | **high** |
| Ult time-stop (in-game the timer freezes; the sim spends fight time on ult locks) | **low** (fewer actions in 180 s) |

The two biggest are probably the harmony levels and movement, and both push the sim high, which fits +10% at ×1.5.

## Other teams

**`bb_noya_shia_tilia`** (T0, reference build vs Lithe Beauty): 2,247.7M, 5 breaks (23.8, 56.0, 91.5, 123.9, 154.5). Pinks only: 388.2M, 2 breaks. The reference build is the max-level greedy build, so it's well above the user's weaker-gear 1,620M, as expected.

**`chitose_freesia_teresa`** vs Count of the Duloos, reference build: 541.2M (Chitose 449.5M, Freesia 78.1M, Teresa 13.7M), 2 breaks (57.5, 129.5).

- **Resilience-per-damage check:** the team dealt **167.5M** before the first break, against an expected 250M ÷ 1.5 ≈ 167M. Resilience dealt in that time was 251.2M (the breaking hit's overkill accounts for the extra).
- The in-game run broke once on 239M. The sim's 2 breaks come from the sim's higher damage (541M vs 239M), not from the bar. Per the calibration policy, this miss isn't tuned away.
- Pinks only: 61.4M, 0 breaks.

**Form Breaker** (Cosette, `mistique_chixia_cosette` on Generic with its target build):

| Fight |    Lv1 |    Lv2 |    Lv3 | Breaks without → with                  |
| ----- | -----: | -----: | -----: | -------------------------------------- |
| 120 s | 0.000% | 0.000% | 0.000% | 0 → 0                                  |
| 180 s | +1.90% | +4.65% | +5.79% | 0 → 1 (151.4 s at Lv1, 150.4 s at Lv3) |

It's worth ~0 where it doesn't add a break, and it adds a real gain where it does, as intended. In the 180 s fight, its expected removal is ~3.05 procs × 0.4–0.6% per 13-claw cast.

**How much each team moved with the bar on** (team-file targets or pinks only, bar off → on):

| Team | Enemy, fight | Bar off | Bar on | Move | Breaks |
| --- | --- | --: | --: | --: | --: |
| amber_flora_chixia | generic, 120 s | 133.3M | 133.3M | 0.0% | 0 |
| amber_laru_flora | generic, 120 s | 26.3M | 26.3M | 0.0% | 0 |
| bb_noya_shia_tilia | lithe_beauty, 180 s | 374.1M | 388.2M | +3.8% | 2 |
| bb_noya_shia_tilia_ingame | lithe_beauty, 180 s | 1,547.3M | 1,782.5M | +15.2% | 5 |
| chitose_freesia_teresa | count_of_the_duloos, 180 s | 61.4M | 61.4M | 0.0% | 0 |
| fl_noya_skill | generic, 120 s | 239.3M | 252.1M | +5.3% | 1 |
| fl_noya_t0_firefly_tilia | generic, 120 s | 239.3M | 252.1M | +5.3% | 1 |
| fl_noya_t1_firefly_tilia | generic, 120 s | 260.0M | 270.1M | +3.9% | 1 |
| fl_noya_t1_shia_tilia | generic, 120 s | 220.1M | 230.2M | +4.6% | 1 |
| mistique_chixia_cosette | generic, 120 s | 159.9M | 159.9M | 0.0% | 0 |

Pinks-only teams under ~250M × 1.5 of resilience don't break in 120 s. With reference builds they do (e.g. `fl_noya_skill` +16.6%, 3 breaks).

## Rating noise from discrete breaks

Breaks are discrete, and the sim keeps them that way (spec anti-goal). A larger stat can move a break so that a weaker stretch of the rotation lands in the ×1.5 window. For example, Veteran's Grit (flat HP) on `fl_noya_skill`, pinks only:

| Level        |    Lv4 |    Lv5 |    Lv6 |    Lv7 |
| ------------ | -----: | -----: | -----: | -----: |
| Gain, bar on | +3.55% | +4.56% | +4.39% | +5.10% |
| Break start  | 81.8 s | 81.5 s | 80.2 s | 79.4 s |

With the bar off, the same rating rises steadily (4.48 / 5.44 / 6.39 / 7.03%). `tests/test_rate.py::test_gains_monotone_for_pure_stat` now runs with the bar off. Level-to-level dips like this are real in the model and are not smoothed.

## Specs changed (Task 6 sweep)

- **`specs/discs/214007.yaml`** (Midnight Mayhem harmony1 "Decisive Strike"): line 1 on the Lux main's skill hits (15 s); line 2 on any hit while the enemy is broken (`hit:any:any&while:broken`, 15 s). Both were "trigger unknown" before.
- **`specs/trekkers/142.yaml`** 514229 Form Breaker: a chance proc (30%, 0.5 s ICD) removing Param1 of the bar.
- **Swept, no change:**
  - Stun-applying potentials in the teams' pools: Flora 512642, Tilia 510741, Shia 515528, Mistique 513508, Cosette 514228. Bosses are stun-immune in this model.
  - Tilia 510725 (Enemy Counter) already assumes a stun-immune boss.
  - The spec's other broken-target potentials (Teresa 512706, Shimiao 511313/511331, Allie 513925, Gerie 514906, 510827/510830) belong to Trekkers or roles without kit specs, so there was nothing to re-spec.
  - No EAT 42/43 lines in these teams' pools. Teresa's efficiency potentials are main-only.

## Open questions

- **Lock rule:** one recorded lock of ~8.9 s (4.7 s of fight time) and one of ~0.3 s. No data rule found.
- **Break ratio ×1.5 vs ×2.5:** the calibration favours ×1.5 clearly, but unmodelled harmony levels and notes leave ~±10% of slack.
- **Boss abilities:** the data's EffectType subtype is 53 (generic DMG Taken) on every line, while the text names Mark / Skill DMG Taken. The text was used.
- **Build-level ATK/HP:** Noya only, or squad-wide?
