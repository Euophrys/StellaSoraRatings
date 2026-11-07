# Nanoha (Ventus, standard banner) / Ann / Canace — 2026-11-03

Nanoha as main with the Noya Ventus team's supports (`teams/noya_ann_canace.yaml`). Team file: `teams/nanoha_ann_canace.yaml` (generic enemy, 180 s). New kit: `specs/trekkers/119.yaml`; the user's timings are in its header. Pinks: Whirling Blade + Bloom Dance (user). Ann and Canace keep the Noya team's pinks.

## Model choices

- Autos: a 2.267 s string, 2-2-3 darts.
- Skill (revised with the user's closer look): 2 shurikens thrown +0.167 / +0.733, each thrown 8 times on a 1.0 s
  round trip, so they last until ~2 s are left on the 10 s CD. Autos resume +1.1 and run while they bounce. The
  shuriken flies ~4 boss-widths, so not every 0.15 s Whirling Blade tick lands: 4 of 6 on a mid-range throw (user),
  4-5 in the perfect case. Modelled: 4 ticks per throw, 64 per cast. CD starts at the cast. Boss/Nanoha movement
  (more uptime while they close in) isn't modelled.
- Ult: the clones are a minion pool (`clone`): 2 summoned at +0.067, first hit +2.067, a 2.3 s attack string (user), 26.5 s base lifetime (from the user's +29.6 with Wind Whispers Lv3). Their hits are Ult DMG rows, so they use Nanoha's stats; the user confirmed they don't benefit from Minion DMG. Clone hits trigger Marks (text).
- Infinite Shade: 3 clones. Wind Whispers: + Param1 s of clone lifetime. Blossom Shower: one shuriken per clone out (up to 2) on each skill cast. Phantom Follower: per clone (max 2), plus a 30 s "ult on cooldown" status.
- Distant Prayer: 50% uptime (user). Sun Chaser: treated as always triggering (many hits per second). Starlit Dash: 50% uptime (user: 10 dodges in ~76 s). ATK SPD lines (Gale Rage, Sun Chaser) are dropped.

## Engine changes

- `_norm_event` now replaces `self` / `main` before an `&...` suffix. `mark:self&recent:...` never matched before; existing specs only used three-part bases, so they're unaffected.
- `minion_rules` keys ending in `_add` add to the key instead of replacing it (`duration_add`).
- Potential overrides take `pct: true` (Blossom Rhyme's clone ATK is a %, but decodes as flat).
- Kits: `energy_per_second` 2.0 -> 0 everywhere (user-tested: no passive energy). The FL Noya regression moved
  239.32M -> 223.70M (−6.5%); see the update in `2026-11-01-fl-noya-skill.md` for all teams. Fixed-number tests
  were re-baselined (ult counts, Starender time, Form Breaker's last cast falling past the fight's end).
- `pytest`: 285 passed (incl. 5 new in `tests/test_nanoha_team.py`).

## Results (pinks only, filler discs)

- 23.3M total. Nanoha 48%: skill 22%, autos 16%, clones 12%, Marks 9%. Canace 30%, Ann 12%. 3 ult casts in
  180 s. The first ult is ready ~60 s after her first hit vs ~76 s in game (~10 dodges at 10 frames each, plus
  chasing a moving boss: the user judges ~60 s right for a stationary target).
- The model changed along the way, pinks only: 21.2M (8 throws, autos resume +4.0), 27.4M (16 throws, 5 ticks),
  26.1M (4 ticks per throw, user), 23.3M (no passive energy, user-tested; applies to every kit).
- Blossom Flurry adds 3 shurikens per auto strike on top of the darts (user, frame by frame), always on (its 10 s
  window equals the skill CD). Its shurikens count for Growth Tempest (hits, user). Blossom Shower's shurikens land
  +0.667 after the skill (user).
- Pink search (reference build: Infinite Shade, Sky Piercer, Wind Whispers, Blossom Shower): Whirling Blade + Bloom
  Dance 100% (the user's pick), Growth Tempest + Blossom Flurry 97.9%, Blossom Flurry + Whirling Blade 97.7%, Growth
  Tempest + Whirling Blade 96.6%, Blossom Flurry + Bloom Dance 95.2%, Growth Tempest + Bloom Dance 94.1%.

## Open questions (GUESSes in the spec)

- Blossom Shower: can the clone shurikens trigger Marks? (modelled: no)
- Blossom Flurry shuriken spacing within a strike (0.033 s, GUESS); shurikens per strike are user-confirmed.

## 60-level build (total 60, caps 30/20/20, `guide.optimize`, bar off)

Pinks only 23.3M -> 188.6M (8.1x). Nanoha 84%, Canace 12%, Ann 3%. Levels end up 30/20/10. Nanoha's damage: ult (clones)
33%, skill 33%, autos 13%, Marks 6%.

- Nanoha: Infinite Shade 6, Sky Piercer 6, Wind Whispers 6, Blossom Shower 6, Splendid Vortex 2, Sun Chaser /
  Gale Rage / Phantom Follower / Distant Prayer 1.
- Ann: Turbulent Flow 6, Windgate Barrier 6, Wind Erosion Havoc 5, Violent Current / Forest Princess' Blessing /
  Speed Surge 1.
- Canace: Structure Analysis 6, Conclusion Analysis / Finale Deduction / Storm Suppression / High Pressure Reflux 1.

The Noya team's 60-level build (98.3M) predates the passive-energy change, so the two totals aren't comparable yet.

## Third-slot comparison (2026-11-04): Canace vs Nazuna vs Tilia, 60 levels, caps 30/20/20, bar off

User: Canace's share looked low; try Nazuna or Tilia (both seen as good in any team), keeping Ann. Team files
`teams/nanoha_ann_nazuna.yaml` (user: Bold Assertion + Feel the Beat; the first run borrowed Arrow of Affection + Sweetheart Bloom from the Gerie team) and
`teams/nanoha_ann_tilia.yaml` (Perfect Spiral + Renewed Spectrum, from FL Noya). Their pinks weren't searched for
this team.

| third | pinks only | 60 levels | vs Canace | shares (Nanoha / Ann / third) | levels |
| --- | --: | --: | --: | --- | --- |
| Nazuna (Bold Assertion + Feel the Beat) | 33.9M | 204.8M | +8.6% | 90 / 4 / 6% | 30 / 20 / 10 |
| Canace | 23.3M | 188.6M | — | 84 / 3 / 12% | 30 / 20 / 10 |
| Tilia | 23.9M | 186.9M | −0.9% | 93 / 5 / 2% | 30 / 20 / 10 |
| Nazuna (Arrow + Sweetheart) | 21.6M | 140.6M | −25.5% | 89 / 4 / 7% | 30 / 20 / 10 |

- Every run caps Nanoha at 30 and Ann at 20; the third member gets the last 10 levels.
- Tilia: Trick Boost 6 (squad buff on ricochet), then Blinding Beam / Knight's Seal / Guardian's Resolve / Revealed
  Flaw 1. Her own damage is small; she works through Perfect Spiral's Skill DMG Taken and Trick Boost. Nanoha's
  build shifts to Splendid Vortex 5 / Wind Whispers 5.
- Nazuna with Bold Assertion + Feel the Beat: the best third slot. Squad buff from Kiss of Penguin plus the statue's
  debuff on the target. Her 10 levels: Jubilant Spin 6 (main buff), Lucky Drop 3, Operation: Pandemonium 1. Nanoha:
  Wind Whispers 5, Splendid Vortex 3.
- Nazuna with Arrow of Affection + Sweetheart Bloom: Lucky Drop 6 buffs only Terra Trekkers (only Nazuna herself here, checked), then Rain of Passion /
  Operation: Pandemonium / Love's True Strike / Rocket Cart 1. Her Terra-only buffs and Terra Marks don't help a
  Ventus team.
