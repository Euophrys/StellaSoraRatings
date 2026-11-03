# Mistique + Chixia + Cosette (2026-11-02)

First mixed-element team: Mistique main (Umbra, Versatile, summoner), Chixia (Ignis, Versatile, summoner) and Cosette (Umbra, Support). Team file `teams/mistique_chixia_cosette.yaml`, kits `specs/trekkers/135.yaml`, `142.yaml` (Chixia: `141.yaml`, timings from the Amber team; user: unchanged here).

## Setup

- **Enemy:** Umbra-weak boss (the usual one for this team, user). RES 145 for Umbra (weak 250 minus ~105 baseline PEN, the FL Noya calibration) and 645 for every other element (neutral 750 minus the same PEN), so Chixia's Ignis hits deal ~0.54×. DEF 500. See `docs/assumptions.md` (Element weakness).
- **Pinks** (search vs the Umbra-weak boss):
  - **Mistique:** Defiance Before Deletion + Burst Shooting, the community build (user), ranks first. Defiance + Thread the Needle 96.6%, Defiance + Extended Exposure (the user's test pair) 93.9%.
  - **Chixia:** Crimson Dragon: Convergence + Tiger of the East (search best; nobody runs Chixia here, user). Tiger + Blazing Scales 97.1%.
  - **Cosette:** Eclipse Imprint + Phantom Mark (the user's pair) 94.0%. Phantom Mark + Phantom Inscription ranks first.
- **Main discs:** Wisteria Dream, Witch's Swing, Petals of Blooming Mirage. That's the best C1 trio under the reference build among the team's top 10 discs. Next: Dream Factory of ☆Truth instead of Petals (−1.4%).
- **Neutral-boss version** (single RES 145, the first pass): Chixia 52%. Ignis discs competed there (Snowy Night Surprise led the disc table), and the best trio was Snowy Night Surprise + Wisteria Dream + Witch's Swing.

## User timings and mechanics (30 fps)

- **Mistique auto:** 5 hits (strikes 1, 2, 3×2, 4) at +0.13 / +0.57 / +1.23 / +1.63 / +2.90 s; the string repeats every 3.17 s.
- **Skill (Pumpka Pummel):** the photo hits at +0.17 s and autos resume at +0.87 s. The cooldown starts at the cast. Exposure lasts 15 s: summon ticks at +0.7 s and then every 3 s (5 ticks).
- **Pumpka Phantom:** lives 15 s from its summon. A tick with 4 out replaces the oldest, which counts as vanishing (Defiance explosion 0.87 s after the death animation starts). With Extended Exposure a tick at max refreshes them all, so they last indefinitely.
- **Phantom attacks:** first Swipe 1.43 s after it appears, then Headbutt and Swipe alternate ~0.7 s apart.
- **Thread the Needle:** every Phantom spins (+0.28 s after Mistique's hit), each with its own ICD that starts on cooldown at its summon. That's about one spin per auto string.
- **Burst Shooting:** the extra hit lands at +0.43 s (11285 vs the photo's 5595 = data 185% / 91.6%). Phantoms are re-summoned at the cast (the removed ones explode) and wind up again (Swipe +1.4 s).
- **Ult:** control back at +1.4 s. 8 small hits at +1.1 to +2.83 s, then the phantom's explosion (the big hit) at +5.0 s.
- **Umbra Mark → Dark Burn:** the Mark hit was 1709, and Dark Burn ticks were 30 every 0.5 s. So 135000001 is the 5 s total (10 ticks of 1/10), as the text says.
- **Marks a Phantom triggers** use Mistique's stats (user). The engine already did this.
- **Darkness Devourer:** sacrificed Phantoms count as vanishing (they explode).
- **Cosette skill:** 13 claws (9 base + 4 from Phantom Mark) from +0.97 to +5.43 s; on the field 7.37 s. Each claw mark lasts ~0.85 s.
- **Cosette ult:** hits at +1.23 s, on the field 4.2 s. Casting it during her skill cancels the skill (user). Waiting for the skill to end costs no ult casts in 120 s (2 either way), so the kit waits.

## Engine changes

- **Minion pools** (`minions:` in a kit): summon ticks set off by an event, `max`, `at_max: replace|refresh`, `duration`, `windup`, an alternating attack loop, `sacrifice_on`, `resummon_on`, `speed`. Per-minion `reactions` have their own ICD that starts at the summon. New events: `summon` / `vanish` / `sacrifice` / `minion_tick`. The pool's name is a status counting the minions out. Potentials change a pool with `minion_rules`.
- **Marks per element:** a Trekker applies and triggers Marks of their own element. New events `mark_new:<who>` / `mark_refresh:<who>`.
- **Procs:** `restart: true` (a refreshed DoT drops its pending ticks); base kits can have `procs:`.
- **`wait_on_field: true`** (support): no new cast while still on the field.
- **Who-tokens and targets:** `element<N>`, and intersections with `/` (`support/element6`, `class2/element6`). `element:N` target.
- **Rotation timing:** team-file `hold` rules (`{member, action, until, only_if, max_wait}`), with new conditions `while:cast_within:<member>:<action>:<seconds>`, `while:cd_within:<member>:<action>:<seconds>` and `while:mark:<element>`.
- **Energy Charge Efficiency effects** (EffectType 37) are modelled as a stat (`CHARGE_EFF`) on energy gained: Quick Nightfall (+29% for 10 s per skill cast).
- **Shared level budget:** `budget_total` (team file, build page "Total", `optimize(total=)`, `compare --total`): `budget` becomes per-member caps on a shared pool, and optimize swaps may move levels between members.
- **Element weakness:** `enemy.weak: [<element>]` + `res_neutral` (default 645) in team files: per-element enemy RES (`Enemy.res_by_element`).
- **`every`** as a modifier override key (kits and discs).
- **"The main <Element> Trekker":** disc modifiers tied to the main (a main event or target) in such a text only work when the main has that element. The disc-override key `main_element` covers implied cases (Meowing Cat God's Blazing Armor harmony).
- **Disc specs written for single-element teams** used `hit:any:` / `cast:any:` where the text says "any <Element> Trekker". These are now `element<N>` in Rainy Tune, Voyage Blueprint, Fist of Courage, Sparkling Moment, A Gift for the Journey, Sunlit Blossom, A Moment in the Afternoon, My Guiding Star and Snowy Night Surprise. Soda Shopping ("any Trekker") keeps `any`. Summer Afternoon Rain's shield events are unchanged (not checked).

Tests: `tests/test_mistique_team.py` (14), plus shared-budget tests in `test_compare.py`, `test_guide.py`, `test_web.py`. Two older tests used The Meow as an unspecced disc and now use Deer's Song.

## Disc specs written

Witch's Swing, Petals of Blooming Mirage, Wisteria Dream, Dream Factory of ☆Truth, Those with Ambition, The Meow, The Bud of Change, Phantom of the Banquet, Ride the Waves With Me, Summer March, Sweet Invitation. Meowing Cat God gets `main_element` on harmony 1.

Petals of Blooming Mirage (Dark Sakura) and Phantom of the Banquet (Blossom Glow) need 20 stacks from Umbra Versatile Skill DMG hits within 5 s. Mistique deals 1–2 Skill DMG hits per cast (her Phantoms deal Minion DMG), so their max-stack parts never fire.

## Results

Umbra-weak boss, team pinks, top-3 discs C1, the "≤ 7 s" ult rule (below). Shares (reference build): Mistique 57%, Chixia 26%, Cosette 17%.

| Disc                      | Main C1 / C6  | Support C1 / C6 |
| ------------------------- | ------------- | --------------- |
| Wisteria Dream            | 20.9% / 38.9% | 4.4% / 8.7%     |
| Witch's Swing             | 20.2% / 37.6% | 4.0% / 8.4%     |
| Traces of Starlight       | 15.5% / 20.3% | −4.0% / 0%      |
| Petals of Blooming Mirage | 15.3% / 30.9% | 4.4% / 8.7%     |

Top potentials (Lv6):
- **Mistique:** Chaos Frenzy 35.2%, Darkness Devourer 28.3%, Full Frame Focus 20.4%, Cursed Screech 17.1%, Quick Nightfall 14.0%, Abominable Fester 11.0%. Night Dash −4.7%.
- **Chixia:** Ambush 21.8%, Horn Call 15.4%, Blood Fed 10.8%.
- **Cosette:** Mirage 23.5%, Afterglow 16.0%, Demon Mark 15.7%, Gift of Darkness 14.0%, Hallucination 13.9%, Nether Blaze 13.8%, Void Blessing 13.3%.

Top emblem lines (Mistique, personal): Skill +3 11.9%, ATK% 10.9%, Crit Rate 9.4%, Umbra PEN 8.6%, Ultimate DMG 8.3%, Ult +3 8.2%.

## Rotation timing and Charge Efficiency

The user saw Charge Efficiency (Main) at −16% to −25% on emblem 1 and +9% to +26% on emblem 2. A sweep of Mistique's Charge Efficiency (reference build) found the cause. Ult damage swung between 21M and 58M with no change in ult casts. **Full Frame Focus** (+189% ATK, 15 s) needs the ult to trigger an Umbra Mark, and the only Umbra Mark is Cosette's Gloom. An ult fired the moment energy is full landed in or out of her window by chance.

Per-ult Full Frame Focus triggers: with the ult cast within 3 s of Cosette's skill, every ult triggers it, even with four Phantoms competing (claws re-apply Gloom every ~0.35 s, the Mark ICD is 1 s). With Darkness Devourer it triggers twice. Fired whenever ready, only the first ult triggered it (1, 0, 0). Outside Cosette's window the Phantoms consume the last Gloom within about a second, so Darkness Devourer doesn't save a Mark that isn't there. The model assumes Phantoms hit non-stop; if they often walk around, Gloom could linger longer in game.

**Rule (team file `hold`):** when the ult is ready, wait for Cosette's skill if its cooldown shows ≤ N s (the game shows whole seconds), else fire now; the ult goes out within 3 s of her cast. N was scanned 0–12 against never waiting (reference build, which now includes Quick Nightfall Lv6, since EffectType 37 is modelled):

| Mistique's extra Charge Efficiency | best N (120 s / 180 s) | N = 7 vs never waiting (120 s / 180 s) |
| ---------------------------------- | ---------------------- | -------------------------------------- |
| none                               | 9–12 / 5–8             | +5% / +19%                             |
| 3× gold (+45%)                     | 4–7 / 4–7              | +9% / +4%                              |
| 3× purple (+90%)                   | 7–12 / 7–12            | +30% / +36%                            |

N = 7 is good in all six. At N ≥ 8 the +45% case gives up an ult (−7%); at N ≤ 4 the no-extra case gains nothing in 120 s. With max efficiency, 3 timed ults beat 4 untimed ones. A first pass with a fixed maximum wait (no `only_if`) gave the same picture: the best was to wait ≥ 8.25 s (none) or ≥ 6 s (+90%).

Charge Efficiency's own value stays step-like, since ults snap to Cosette's 12 s skill grid. Read emblem values for it as "does it reach the next breakpoint".

## In-game check (user)

The user's Burst Shooting test build against a neutral-RES boss over 3 minutes dealt Mistique 36.9%, Chixia 51.4%, Cosette 11.6%. The model gives 38.4% / 51.6% / 10.0%. The builds differ (the model uses its reference build over 120 s), but the split matches, including Chixia's large share. In practice the boss is usually Umbra-weak and neutral to Ignis. That's now modelled (`enemy.weak`, below) and is the team's default; it moves the split to 60 / 24 / 16.

**Ink Sigil: Raid** (user): the Dragons are stationary turrets, rarely close to the boss; the Tiger moves with it. Raid now only applies to hits tagged `close`: the Tiger's hits and its Blazing Barrier (`specs/trekkers/141.yaml`). Raid Lv6 here: 17.7% → 15.4%. The Amber team (`teams/amber_flora_chixia.yaml`, Raid in its targets): Chixia's share is 63% (doc: 61%) and Raid Lv6 is 16.1%; the top discs keep their order.

## Noya regression

`teams/fl_noya_skill.yaml`: My Guiding Star 76.6% / 125.8%, Ripples of Nostalgia 43.1% / 60.2%, A Moment in the Afternoon 36.2% / 48.5%. That's identical to before this session, including after the `element5` spec edits (the team is all Lux).

## Open questions (GUESS in the specs)

- **Chixia's share (~50%)** makes Ignis discs competitive in an Umbra team. The user's in-game run confirms it (51.4%).
- **Element weakness:** RES 250 weak / 750 neutral (reference formula bands, user) minus a ~105 baseline PEN. The baseline PEN is assumed the same for off-element Trekkers. Not checked against an in-game Umbra-weak run.
- **Dark Burn re-triggered while running:** refresh (modelled) or a second instance?
- **Exposure re-cast:** a recast restarts the summon schedule (+0.7 s, then every 3 s). This hardly matters, since ticks stay 3 s apart.
- **Thread the Needle's second spin hit:** 0.1 s after the first.
- **Burst Shooting's removed Phantoms:** do their explosions deal damage? The user saw only one damage number at 04,08, and it matched Burst Shooting's hit. Explosions are modelled as dealing damage 0.87 s after removal.
- **Cosette without Phantom Mark:** her on-field time is assumed unchanged (7.37 s).
- **Dream Factory's Corrosion** (35% per hit) is treated as always refreshed. Wisteria Dream's per-summon Minion DMG is treated as a buff while Reverence is up.
- **Mistique's skill interruption** CD refund isn't modelled.
