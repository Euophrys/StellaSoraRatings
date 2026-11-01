# Amber + Flora + Chixia (2026-11-01)

Run: `python -m ssr teams/amber_flora_chixia.yaml -o out/` → `out/amber_flora_chixia.xlsx` (~90 s). There's no Maygi chart for this team. It's a first model built from the data and the user's frame timings (30 fps, `seconds,frames`).

## User timings

- **Chixia's skill:** cast 02,17, on the field until 12,18 (10.03 s). The teleport-out (to 13,13) isn't counted. Her CD starts at the cast, which is how support CDs always work.
- **Summons**, one every 2 s, in order tiger, dragon, dragon, dragon (with Convergence + Tiger of the East). The tiger is summoned first, but the dragon's summon animation is shorter. In clip 1 the first dragon appears at 06,14 and the tiger is ready at 06,16.
- **Tiger** (clip 2): the roar ends at 08,20. Then a swipe at 09,14 (28k), a pounce hitting at 10,22 (18k, because the boss moved), a swipe at 11,26 (63k), and a double swipe at 13,04 (62k + 44k). After that it repeats swipe, swipe, double swipe, starting with a swipe at 14,18 (51k). It starts to leave at about 22,13. No tail flick was seen.
- **Dragon** (clip 2; from the spacing this is the 2nd dragon): summon starts 09,20, active 10,24. Shots at 11,16 (6k), 13,04 (9k) and 14,18 (8k), then one more, then the charge at 17,26. That's 4 shots and a charge. The clip-1 dragon looked shorter (06,14 → 12,20), so clip 2's fuller timing is used.
- **Chixia's ult:** cast 14,29, first hit 16,12, teleport-out 18,11 (on the field 3.40 s). The hits continue after she leaves.
- **Flora's ult:** 03,12 → teleport 07,28 (4.53 s on the field).
- **Amber's ult:** 03,18 → can attack again 04,23 (1.17 s lock).
- **Blazing Scales** (clip 3; the tiger is ready at 07,03): the barrier appears at 07,09. Ticks at 11,00 (7363, crit), 11,15 (4445) and 12,01 (7363), so 0.5 s apart. The tiger hits 16728 at 07,29, the pounce 12580 at 10,15, the double swipe 22393 ×2 at 11,17.
- **Incineration with PTC** (skill at 1:04,15): Incineration on shot 1 (1:04,22) and shot 3 (1:06,03). The recast starts at 1:06,29 (+2.47 s, with one auto shot in between; key mashed), then Incineration on its shot 1 (1:07,04) and shot 3 (1:08,08). Gaps between Incinerations: 1.37, 1.03 and 1.13 s, which fits the 1 s ICD. Shot 2 never triggers.

**Checking the tiger's damage.** The tiger's +50% Minion DMG stacks were placed at summon +2, +4 and +6 s (summon at cast + 0.8 s). With that, the damage per hit multiplier is the same for each hit: 28k swipe (1 stack), 18k pounce (2 stacks), 63k swipe (3 stacks) all come out at ~0.057 × multiplier at skill Lv4. That also identifies the hit rows: pounce `141523001`, then swipe, swipe and double swipe as `002`, `003` and `004`×2.

**Blazing Scales check.** 4445 per tick is 67 per 1% of `141524001` at skill Lv4. The tiger's double swipe is 126 per 1%. A 1.9× ratio fits the tiger's 3 stacks (+150%) not applying to the barrier. The small `141524002` row would make a tick 2.4× stronger per % than the tiger, which isn't plausible.

**Dragon vs tiger**, per 100% of multiplier: 13.0k vs 24.7k, a ratio of 1.9. The model predicts 1.75: 3 tiger stacks give 2.5 against Convergence's 1.43. That's within crit and Blood Fed noise. The user's account for these numbers: Chixia Lv60, skill Lv4; Ambush r4, Blood Fed r3, Raid r1; discs Fist of Courage, A Gift for the Journey, Scorching Night's End. The absolute numbers weren't reproduced.

## Build used

Pinks from a community "Standard Amber-Flora-Chixia Team" build:

| Member | Pinks                                                            |
| ------ | ---------------------------------------------------------------- |
| Amber  | Precise Temperature Control + Dominant Firepower                 |
| Flora  | Ashes of the Past + Ember of Tomorrow                            |
| Chixia | Crimson Dragon: Convergence + Sigil Unleashed: Tiger of the East |

Main discs: Meowing Cat God, Snowy Night Surprise, Fireworks (this team's top 3 at C1).

**Damage share:** Chixia 61% (minions 53%, ult 8%), Amber 30% (autos 15%, skill 6%, Incineration 5%, ult 4%), Flora 9%. Before the minion buff rule below, Chixia was 68%.

## Pink pairs (% of best)

From `python -m ssr teams/amber_flora_chixia.yaml --pinks Amber Flora Chixia` (~240 s), with the minion buff rule. It ran before the recast timing change, which moves totals by under 1%. ★ marks the community build's pair.

| Amber |  | Flora |  | Chixia |  |
| --- | --- | --- | --- | --- | --- |
| PTC + Echo | 100% | Ember of Tomorrow + Ember Rekindled | 100% | Tiger + Blazing Scales | 100% |
| DF + Bullet Storm | 95.9% | ★ Ember of Tomorrow + Ashes | 90.5% | ★ Convergence + Tiger | 90.4% |
| ★ PTC + DF | 95.9% | Ember of Tomorrow + Spark | 89.5% | Chant + Tiger | 89.6% |
| Bullet Storm + PTC | 95.8% |  |  | without Tiger | ≤ 68.5% |

Tiger of the East is essential, and that agrees with the community. Blazing Scales beats Convergence by about 10 points. Its ticks are now confirmed in game (0.5 s, `141524001`, from 0.2 s after the tiger is ready until it leaves: 27 per cast). The community's PTC + DF for Amber is within ~4% of the best pair, and so is Ashes for Flora within ~10%.

## Discs (main C1 / C6)

| Disc | Main C1 | Main C6 | Support C1 | Notes |
| --- | --- | --- | --- | --- |
| Meowing Cat God | 21.7% | 30.9% | 10.7% | its ATK line names "and their Minions": reaches Chixia's minions |
| Snowy Night Surprise | 21.1% | 34.0% | 11.1% | squad Ignis DMG + Ult DMG only: Chixia's minions can't make Hymn, and squad buffs don't reach them |
| Fireworks | 18.2% | 28.2% | 11.1% |  |
| Mystic Brushstrokes | 17.2% | 27.9% | 10.7% |  |
| The Cat's Treasure | 17.1% | 25.2% | 11.1% |  |
| One Shot, One Down | 13.9% | 24.8% | 7.5% | 0 Destiny Cards; its squad Ignis DMG / ATK don't reach minions |

Disc values are lower than in the Laru team: most disc lines say "squad" or "Ignis Trekkers", and they skip the 53% of damage that comes from minions.

## Potentials (Lv6 gain over the reference build)

Reference: Keen Accent, Grand Finale, Bursting Spark, Soul-Hunting Spark (Amber); Guest Performer, Lethal Inferno (Flora); Prayer of Raging Flame, Ink Sigil: Blood Fed (Chixia).

Top: Prayer of Raging Flame 81%, Trail Seeker 37%, Blood Fed 31% (per-minion ramp), Lethal Inferno 30%, Horn Call 21%. The "units" buffs (Prayer, Horn Call, Ambush) gain from reaching minions. Flame Glow ("Ignis Trekkers") and Dragon Blaze ("Chixia's ATK") lose.

## Model changes

**Engine** (general, documented in `specs/README.md`, tested in `tests/test_chixia_team.py`):

- **Marker hits** (`hit: 0`): no damage. They emit `marker:<who>:<tag>`, for scheduled things like a summon becoming ready or a stack every 2 s.
- **Pure statuses:** a buff with no `effect` or `attribute`. Used for the minion counts (`tiger`, `dragon`).
- **Status sums and thresholds:** `while:status:dragon+tiger`, and `while:status:dragon>=2`, which is only active at 2 or more stacks.
- **`&recent:<tag>:<seconds>` on events:** the member that emitted the event also landed a `<tag>` hit within that many seconds.
- **Minion buff scope** (user, from the community's "minion bug"): buffs scoped to "Trekkers" don't reach minions; "minions" or "friendly/all units" do; enemy debuffs always count. Minion hits get the summoner's stat sheet (base stats, disc stats and emblems), Minion DMG/Crit stats, enemy debuffs and modifiers whose `minions` flag is set. The flag is read from the text (what the sentence naming the stat *increases*), with spec overrides (`minions: true|false`). `minion_buffs: all` in the team's assumptions turns the rule off. See `docs/assumptions.md`.
- **Follow-up `delay` / `autos`:** PTC's recast now starts 0.15 s after the skill's lock ends, with one auto shot in between (user). Its first shot then lands just past the 1 s mark ICD and triggers Incineration, as in game. No gap (perfect play) is within 0.5%.

**Disc fix: Snowy Night Surprise.** Ode only converts into Hymn on minion hits by the Trekker who applied the Ode, and Ode comes from that Trekker's Skill DMG (Word 6002). The spec now uses `hit:any:minion&recent:skill_dmg:12.25`. In this team it drops from 51.4% to 33.3%, because support Chixia deals no Skill DMG. The Laru team is unchanged (Laru's shells are Skill DMG).

**Kits:** new `specs/trekkers/141.yaml` (Chixia, all three pools). Flora's ult on the field goes from 4.0 to 4.53 s, and Amber's ult lock from 1.0 to 1.17 s. In Laru's Heart's Edict, "their Crit DMG" (Walnut's and Curly's) is flagged `minions: true`.

**Effect on Amber + Laru + Flora** (re-rated, `out/amber_laru_flora.xlsx`): Laru 52%, Amber 33%, Flora 15% (before: 53 / 32 / 15). Snowy Night Surprise 56.3% → 53.7%, Mystic Brushstrokes 32.5% → 31.4%, The Cat's Treasure 27.9% → 27.2%. Same top 3. Top potentials are unchanged within ~4 points.

## Effect on the FL Noya calibration

None. Noya was re-run after the summon features, the Snowy Night Surprise fix and the minion buff rule. All 225 Potentials/Discs/Emblems rows match the run before them: Noya's team has no minions, and the follow-up `delay` defaults to 0.

The committed `out/fl_noya_skill.xlsx` (09:42) is older than the previous session's uncommitted engine changes, so it already differs in 74 rows from a fresh run. Those differences aren't from this session.

## Cross-team comparison (vs Amber + Laru + Flora)

Damage shares only show how a team's damage splits. Totals are comparable across teams because every team runs through the same simulator (enemy, fight length, skill levels, stat model). `python -m ssr.compare <teams> --split <main>,<m1>,<m2>` gives each team its pinks for free. It then builds greedily: each step adds +1 level to whichever normal/common potential raises team damage most, within each member's level budget (max Lv6).

Level splits from the user's runs: about 10 potentials per Trekker plus ~30 enhances, biased towards the main, so typically 30/15/15. The user has also had 24/15/20, and the Laru video was 21/22/14.

| Split (main / star support / other) | Levels | Laru team | Chixia team, sim-best pinks | Chixia team, community pinks |
| --- | --- | --- | --- | --- |
| 21 / 22 / 14 (the Laru video) | 50 | 488M | 478M (98%) | 451M (92%) |
| 30 / 15 / 15 (typical) | 60 | 432M | 392M (91%) | 339M (79%) |

With realistic splits the Laru team comes out ahead, as the community says. The gap shrinks as more levels go to the star support. With 60 levels spent anywhere, Chixia's team was 43% ahead, because Chixia has 8 strong potentials in nearly empty buckets and Laru has 5. Per-member budgets cap that. A support-focused run (untested by the user) might still favour Chixia.

Model changes for this comparison:

- **Blood Fed per minion** (user), ramping from each minion's own summon. Minion slots are tagged `s0`..`s3`, and the general `copies` override splits one modifier into per-slot copies.
- **Barrier Construct:** one stack per minion out (user).
- **Laru retimed from a YouTube video** (23 fps; build Fire Downpour, Special Ammo, Two-Gun Salute 6, Fairy Tale Rule 6, Uplifting Shot 6, Ammo Rain 2):
  - shells at +0.7 s, then every 2 s;
  - on the field 15.3 s;
  - a Walnut per shell, max 4, attacking 1/s;
  - Walnuts keep attacking after the next cast. Their life is fitted at ~13.5 s (the data says 10 s) to match the video: all 4 are still out at the next cast and die just before replacements arrive.
  - Schedules are generated for each Two-Gun Salute / Heart's Edict / Promotion Time combination (`scripts/gen_laru_walnuts.py`).

## Open questions

1. **Minion buff scope** is a text rule. A wrong translation would misclassify a buff. ATK% is the stat the community says is "bugged" for minions, so watch it in particular. "Chixia's ATK" (Dragon Blaze) is assumed not to reach her minions.
2. **Walnut lifetime** (13.5 s) is fitted, not timed. A spawn-to-death time for one Walnut would pin it down.
3. **Laru's parting attack** (the backflip off the cannon) isn't modelled.
4. **Chant:** minion ATK SPD isn't modelled.
5. **Dragon Breath and Blazing Vortex timings** are guesses. Prayer of Raging Flame's "when dealing DMG" is read as the ult's DMG.
6. **The tiger's pounce** depends on the boss moving. It's modelled as in clip 2.
7. **Trail Seeker** (confirmed with the recast): one extra attack per minion out. The hit timing is guessed.
