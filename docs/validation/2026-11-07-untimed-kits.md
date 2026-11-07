# Untimed kits for every remaining role (2026-11-07)

Every Trekker can now be simulated in both roles. 21 Trekkers had no spec at all, and 18 roles of existing Trekkers were stubs or missing. All 60 roles written here have `untimed: true`, and the build page warns about them. No timing in them comes from a new measurement. The rules for the guesses are in `docs/assumptions.md`, Untimed kits.

- **New Trekkers (both roles):** Kasimira, Firenze, Iris, Shimiao, Chaton, Jinglin, Coronis, Donna, Minova, Nazuka, Fuyuka, Eleanor, Allie, Sparkla, Wraith, Otoha, Caramel, Laru, Karin, Springseek Coronis, Suntide Willow.
- **New main roles:** Tilia, Firefly, Ridge, Canace, Ann, Freesia, Flora, Teresa, Chixia, Cosette, Snowish Laru, Shia.
- **New support roles:** Amber, Noya, Nanoha, Mistique, Chitose, Firstlight Noya.
- **Snowish Laru's support ult:** authored for the Fuyuka pairing, and only cast in a squad with Fuyuka (`ult_only_with`). It's untimed too.
- **Engine:** the `untimed` role status, `ult_only_with` and `ult_cost_scale`. Nothing else changed in `src/`.
- **Tests:** `tests/test_untimed_kits.py` simulates every untimed kit with each potential and at T5, and fails on a missing hit row, a missing tag, an unscoped modifier, a missing trigger, or a proc that re-triggers itself. 622 tests pass.

## Regression

All 19 files in `teams/` simulate to exactly the same total as before this work (compared against `3070d91`). The full `fl_noya_skill` rating matches it cell for cell on the Potentials, Discs, Emblems and Breakdown sheets, so nothing moved against `docs/validation/2026-11-01-fl-noya-skill.md`. Only existing teams were checked: no in-game number backs any untimed kit.

## Bugs the checks caught

- **Willow's Rhythmic Bubbles** re-triggered itself (+1044%).
- **Coronis's Medical Research** read the 36% ATK value as its share of the resilience bar.
- **Donna's Coast Crusher** had duplicate Lv1 rows (the known pitfall).

## Main roles with no potentials

Filler discs, pinks and potentials off, RES 250, 120 s, same-element timed supports where they exist. "Own" is the Trekker's own damage. This is only a sanity check of base kits, not a ranking: Firstlight Noya's total depends on her Max HP scaling, and pinks change a lot.

```
Firstlight Noya        ok       own  29.0M team  33.8M skills  12 ults 3
Gerie                  ok       own   7.8M team  10.7M skills   9 ults 2
Wraith                 untimed  own   7.2M team   8.7M skills  42 ults 1
Sparkla                untimed  own   6.4M team   8.7M skills   8 ults 1
Eleanor                untimed  own   6.0M team   7.6M skills  11 ults 1
Nanoha                 ok       own   4.9M team   6.4M skills  12 ults 2
Allie                  untimed  own   4.8M team   6.6M skills  13 ults 1
Karin                  untimed  own   3.5M team   4.5M skills  10 ults 2
Firenze                untimed  own   3.3M team   4.0M skills  21 ults 1
Otoha                  untimed  own   2.7M team   3.7M skills  22 ults 1
Freesia                untimed  own   2.6M team   2.9M skills  10 ults 2
Chaton                 untimed  own   2.6M team   3.7M skills  15 ults 1
Springseek Coronis     untimed  own   2.5M team   4.2M skills   8 ults 1
Fuyuka                 untimed  own   2.2M team   3.8M skills   8 ults 1
Shia                   untimed  own   2.2M team   5.7M skills   8 ults 0
Nazuna                 ok       own   2.1M team   3.0M skills  15 ults 2
Chitose                ok       own   2.1M team   4.0M skills  16 ults 2
Minova                 untimed  own   2.0M team   6.9M skills   7 ults 1
Nazuka                 untimed  own   1.8M team   3.3M skills  10 ults 2
Firefly                untimed  own   1.8M team   2.3M skills   6 ults 0
Canace                 untimed  own   1.7M team   2.0M skills  10 ults 1
Mistique               ok       own   1.7M team   2.7M skills  11 ults 2
Chixia                 untimed  own   1.6M team   2.0M skills  12 ults 1
Noya                   ok       own   1.5M team   3.0M skills  18 ults 1
Laru                   untimed  own   1.5M team   6.1M skills   9 ults 2
Amber                  ok       own   1.4M team   2.9M skills  15 ults 3
Jinglin                untimed  own   1.2M team   6.3M skills  23 ults 1
Shimiao                untimed  own   1.1M team   2.9M skills   6 ults 1
Coronis                untimed  own   1.0M team   2.0M skills   9 ults 1
Ridge                  untimed  own   1.0M team   1.9M skills  10 ults 1
Suntide Willow         untimed  own   0.9M team   2.3M skills   4 ults 0
Flora                  untimed  own   0.9M team   1.7M skills  10 ults 1
Caramel                untimed  own   0.9M team   1.8M skills  11 ults 1
Donna                  untimed  own   0.8M team   2.0M skills   5 ults 1
Tilia                  untimed  own   0.8M team   3.7M skills  13 ults 2
Cosette                untimed  own   0.8M team   1.2M skills   9 ults 1
Snowish Laru           untimed  own   0.8M team   2.3M skills  12 ults 2
Kasimira               untimed  own   0.7M team   1.8M skills  26 ults 1
Ann                    untimed  own   0.6M team   1.7M skills   8 ults 2
Teresa                 untimed  own   0.6M team   2.2M skills  12 ults 1
Iris                   untimed  own   0.5M team   1.8M skills  15 ults 1
```

## Open questions, for when these get timed

**Numbers most likely to be too high.** They come out above most timed mains, even on slow guesses:

- **Wraith:** the data gives 1,700% per cast every 3 s, and stored uses keep the rate up (42 casts in 120 s). Check the hit counts, and whether holding really keeps that rate.
- **Sparkla:** her autos are 861% per volley in the data, about 6x other Trekkers'. I used one volley every 3 s and a Rapid Fire burst every 1.5 s, both pure guesses.
- **Eleanor:** 24 auto hits per string, and a Vigil hit every 2 s is a guess.
- **Allie:** 4,731% per skill cast (x3 and x3, from the text).

**Numbers that are low because of skipped minions.** Don't use these for comparing teams until the minions are modelled: Caramel (main), Snowish Laru (main), Mistique (support, whose skill does nothing without a damage potential), Firenze, Donna, Ann.

**No ult in 120 s without potentials:** Shia, Firefly and Suntide Willow as mains. Their Energy from hits is low on these guessed hit counts, so check how many bullets a strike really fires. Shia's are read from the Energy cap per strike.

**Counts the data doesn't give (`# GUESS` in the spec):**

- Kasimira's pellets per volley (10).
- Nazuka's tornado hits (1 each).
- Otoha's parasol spin hits (20).
- Chaton's Dark Burst rate (5 shots/s).
- Karin's Shark Ambush lunges (1 per 2 s).
- Sentry rates for Eleanor, and Bubble Frog's lifetime for Willow (12 s).

**Choices to confirm:**

- Chaton: tap (Dark Ray) by default, hold only with a bomb pink.
- Sparkla: hold (Rapid Fire) by default.
- Tilia: tap by default, with a full 8 s hold only with a stance pink.
- Whether a Fortify Stance block should count at 1 cast in 4.
- Whether "enters combat" (Shimiao's Irrigation Mastery) means once per fight.
