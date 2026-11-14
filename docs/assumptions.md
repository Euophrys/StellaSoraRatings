# Modelling assumptions

A running log of every modelling choice that isn't read straight from the game data.

## Data decoding

- **Param `LevelUp` refs:** level n of base id X is row `X + n×10` in the `<Source>Value` table (e.g. `16241001` → Lv1 `16241011`, Lv9 `16241091`). Missing levels clamp to the highest row present. `NoLevel` refs read the named table at the id as given, whatever the level.
- **Formats:** any format starting `10K` is divided by 10000. `HdPct`, `Pct`, `Hd`, `Fixed` are used raw. `Enum,EAT` returns the integer stat id.
- **Stat names (EAT):** `EffectDesc` rows with Id 12xxxx, `Type2ID` 2. Other `EffectDesc` families reuse `TypeID` for skill/potential level-ups.
- **Hit DamageType → slot:** 1 auto, 2 skill, 3 ult, 4 other, 5 mark, **7 minion (Minion DMG, EAT 66; Minion Crit 74/81).** Only summoner Trekkers have DamageType 7 hits (Snowish Laru's Colonel Walnut / General Curly, whose text says "Minion DMG"). Derivative DMG (EAT 68) is a separate stat (its own emblem line) that nothing feeds; what it applies to is unknown.
- **Disc base stats:** `Attribute` row (group `AttrBaseGroupId`, lvl 90, max Break) gives flat ATK/HP/DEF plus one percentage substat: `WEE/FEE/SEE/AEE/LEE/DEE` = Aqua/Ignis/Terra/Ventus/Lux/Umbra DMG, `NORMALDMG/SKILLDMG/ULTRADMG` = Auto/Skill/Ult DMG, value ÷ 10000 (My Guiding Star `LEE 1500` = +15% Lux DMG). Copies n add `DiscExtraAttribute` Break n−1.

## Damage formula

- Gist formula with these extra buckets, each `1 + sum`: general DMG (EAT 49 DMG Dealt + 50 DMG), Final DMG (51 + 52), general DMG Taken on the enemy (53 + 54). Ignore-element-RES (EAT 29–34) scales RES before PEN, as in the decompile.
- RES bands are chosen by effective RES (≤250 low, ≤750 middle, else high); beyond 2000 clamps to 0.99 amend.
- Crit is applied as an expected value: `(1 − p) + p × (critDmg + slotCritDmg)`, `p` capped at 1. "Other" DMG hits get no slot crit.
- `dmgPlus`, `finalDmgPlus`, `perkIntensity`, talent amends: not modelled (gist: unused).

## Effects

- **ATK/DEF/HP flat vs %:** `EffectTypeSecondSubtype` 2 = %, 1 (base) and 3 (flat) = flat. Matches `EffectDesc.Type2ID` (1 Base, 2 %, 3 flat) and data values (subtype 2 values are fractions, 1/3 are integers). For other stats the second subtype is ignored and values are additive. `OnceAdditionalAttribute`: `ParameterType` 2 = % (ATK only in practice).
- **EffectType 52** is treated like 12 (stat add). Every 52 row seen is a slot-DMG / Mark-DMG add.
- **When a potential effect is on:**
  - In the potential's `EffectIdN` with `Trigger` 1 → always on.
  - Listed in some `BuffValue.Effects` → a buff with that row's duration (`Time`/10000 s; `Time` −1 = permanent) and `LaminatedNum` stacks. Its trigger is not in data (scripts apply it), so it is **assumed** until the kit YAML names the event or an uptime.
  - Otherwise (only in Params) → applied by script, condition unknown, **assumed**, noted.
- **Target:** any "DMG Taken" stat (element, slot, general) or an effect whose `Target1` is 2 goes on the enemy; everything else on the owner. Squad-wide effects ("increases the squad's…") are not distinguishable in data; disc effects follow `assumptions.disc_stats_target` and potentials are re-targeted in kit YAML.
- **OnceAdditionalAttribute** modifiers are always on but usually apply only to some hits ("longsword attacks and Glows"); they're flagged `needs_scope` and the kit YAML sets `hit_tags`.
- **Single-level refs:** a `LevelUp` ref whose id has no level rows reads the row at the id itself (e.g. Sinbreaker `16204011`). A ref whose row is missing entirely is noted, not fatal.

## Fight simulation

- Tick 0.05 s, 120 s. Supports cast skill at t=0; the main's first skill at 1.0 s. Afterwards each Trekker casts its ult when energy and cooldown allow, else its skill when off cooldown (supports first, then the main).
- **Main busy time:** after any main cast, another cast can't start for 1.5 s (`DEFAULT_BUSY`, GUESS) or the action's lock, whichever is shorter. Autos stay blocked for the action's `lock` (FL Noya: skill 5 s, ult 4 s, Radiance Flurry 3 s — user-timed).
- **Follow-up actions** (Dawnflare's Radiance Flurry) are cast after every Nth cast of their parent, once the parent's lock ends; they don't use a cooldown. **Extra casts** fire 1.5 s after the original.
- **Autos:** the string loops while the main isn't locked and restarts from strike 1 after every cast.
- **Energy:** each main hit gives `HitDamage.EnergyCharge`/10000, capped per cast by `Skill.GetEnergyLimit` (per strike for autos). Supports receive the same gain × `Character.EnergyConvRatio` (0.75), GUESS. There is no passive energy (user-tested 2026-11-03: standing in a boss fight without attacking gains none), so every kit has `energy_per_second: 0`. Check: Nanoha's sim ult is ready ~60 s after her first hit vs ~76 s in game with ~10 dodges and chasing. Casting the ult empties energy.
- **Marks:** a support hit with `applies_mark` puts a Mark up; a main hit that can trigger Marks consumes it and deals the Mark hit, at most once per `mark_icd` (1 s, corroborated by the Amber timings). One Mark per element at a time (user, 2026-11-13).
- **Hit levels:** `levelTypeData` 1 → that potential's level (pinks Lv1); 3 → skill level of `LevelData` slot (5 auto, 2/1 skill, 4 ult) incl. emblem +N; 4 → ascension (9th entry); none → the casting action's skill level.
- **Modifiers:** triggered buffs add a stack per matching event (refreshing the oldest past `max_stacks`); a new stack resets every stack's timer (`stack_timers`, below). Unknown triggers are a constant `uptime × max_stacks`. Disc stats and disc effects go to the whole team (`disc_stats_target: team`).

## Enemy RES (corrected 2026-11-07)

Enemies use their raw RES: **250 weak**, 750 neutral, 2000 own element. PEN comes only from the build.

Until 2026-11-07 every enemy had 105 taken off (weak 145, neutral 645, own element 1895) to match Maygi's first Lux PEN emblem line (8.65%) from a pinks-only baseline. That 105 was never an enemy property. It's FL Noya's Astral Brilliance at Lv6: 35 Lux PEN × 3 Lux Trekkers (user, 2026-11-07), so Maygi's emblems were most likely measured on a finished build. The old offset also gave every team that PEN whether or not it had the potential, and counted it twice on builds that took Astral Brilliance.

Noya's Lux PEN emblem lines (110 PEN each) at RES 250, `fl_noya_skill`, Maygi's top-3 discs at C1, no emblems (Maygi: 8.65% / 0.05%):

| build                                       | 1st line | 2nd line |
| ------------------------------------------- | -------- | -------- |
| pinks only                                  | 24.34%   | 7.12%    |
| pinks + Astral Brilliance Lv6               | 8.03%    | 0.43%    |
| reference build without Astral Brilliance   | 23.39%   | 9.14%    |
| reference build (has Astral Brilliance Lv6) | 9.79%    | 0.69%    |

The emblem sheet from `python -m ssr` is rated against the reference build (user, 2026-11-07), so PEN lines are valued on top of the PEN the finished build already has.

Check against the in-game Boss Blitz run (1,620M, 4–5 breaks; `bb_noya_shia_tilia_ingame`, whose build has no Astral Brilliance): raw RES gives 1,663M and 5 breaks (+2.7%); the old offset gave 1,779M and 6 breaks (+9.8%).

Enemy DEF 500 (user, 2026-11-01: base enemy DEF; ×0.5 damage). DEF only scales everything equally unless a DEF PEN source is rated. **DEF PEN / Ignore DEF** (EAT 9 / 10, 2026-11-14, user: track it per `2.def.c`): effective DEF = DEF × (1 − Ignore DEF) − DEF PEN, after the enemy's DEF reductions, floored at 0. Before this they were read but ignored, so Resolve: Sunder (FL Noya), Balmy Surf (Suntide Willow), Devouring Shadow (Otoha) and Suntide Willow's DEF PEN talent nodes rated 0. In `fl_noya_skill` only Resolve: Sunder moves (0 → 0.35–1.47%, Lv1–9). Enemy DEF reductions (Ridge's Corrosive Vines / Root Grasp) are flat and subtract from the 500 before defAmend (user confirmed the 500, 2026-11-03), so they're worth more as DEF drops: −150 = +20.5%, −301 = +47.6%.

**Element weakness** (user, 2026-11-02): the reference formula's RES bands are 250 weak, 570 raid, 750 neutral, 2000 resisted. Maygi's PEN numbers fit "weak" (above), so a boss is weak to the team's main element, and off-element Trekkers hit a neutral RES. A team file's `enemy.weak: [Umbra]` keeps `res` (250) for the weak elements and gives every other element `res_neutral` (default 750). Off-element hits then deal ~0.53× with no PEN (0.40 vs 0.75 RES multiplier). Without `weak`, every element uses `res` (all earlier teams are single-element, so nothing changes for them).

## Harmony notes

Each main disc's harmonies are assumed at **Lv1**, and the team gets the notes those harmonies need (user, 2026-11-03). Notes are shared across the run, so each note type's count is the largest any one harmony asks for (not the sum). Requirements come from `SecondarySkill.NeedSubNoteSkills`: 10 of each of 3 types, or 15 of each of 2 types, at Lv1 (25/30 at Lv2 … 70/75 at Lv5). A note's bonus is its `EffectValue` Lv1 value × count. Linear scaling past the 9 levels in data was checked in game by the user. Notes are squad-wide (they follow `disc_stats_target`) and always on.

- Real runs vary a lot. The user's Noya run had 36 Lux and roughly 35–43 of the main types, which put 5 harmonies at Lv2 and 1 at Lv1. Lv1 notes (15 each for that team) are conservative.
- Team assumption `harmony_notes: N` grants the notes for harmony Lv N. `0` turns notes off (the earlier behaviour). Harmony _effects_ stay at Lv1 either way.
- Support-disc starting notes aren't counted on top. They only help reach the requirement, which is already assumed met.

## Discs with scripted effects

46 of 104 discs have a melody or harmony with no `EffectId` (the effect lives in a script, only text + Params in data). These are modelled by `specs/discs/<id>.yaml`; a scripted part without a spec is **listed as "scripted, not modelled"** in the Discs sheet's Notes. Since 2026-11-04 every available disc has a spec and none has an unknown trigger (`python -m ssr.inspect scripted-discs` lists nothing). Some parts still have GUESS uptimes, marked in their spec.

- "Lux Versatile Trekkers" = `Character.Class` 2 (Firefly here; FL Noya is class 1 Vanguard, Tilia class 3 Support).

## Glimmer, on-field time, conditional effects (second pass)

- **Glimmer** (Word 4029 → Effect/BuffValue 3012): Lux DMG Taken +0.5% per stack, 6 s, max 3 stacks. Noya adds one stack per Lucent (Mark trigger). It's tracked as a named status (`name: glimmer` in `specs/trekkers/162.yaml`).
- **EAT 85** = "DMG Multiplier", a separate multiplier on the hit (see Key talents). Resolve: Blitz gets it while any Glimmer is up. Noya's auto attacks get it once per Glimmer stack (`OnceAdditionalAttribute` 16290001 at auto level). Searing Sun's bonus against Glimmer targets is Lux DMG, not EAT 85.
- **EffectType 45** = a stat add under a condition (e.g. "if the main's HP is above 80%"). It's treated as a stat add with an assumed trigger unless a spec pins it down.
- **On the battlefield:** a support is on the field for `on_field` seconds after each skill or ult cast (default 4 s, GUESS). `while:on_field:<who>` effects are active only then.
- **Stellar Crash:** each blade adds as many Lux DMG Taken stacks as the target has Glimmer stacks.

## Amber / Snowish Laru / Flora (2026-11-01)

- **Negative "DMG Taken"** ("reduces DMG taken by the main") is defensive and goes on the owner, not the enemy. It used to decode as an enemy debuff that _lowered_ team damage (10 discs, incl. A Moment in the Afternoon and Sparkling Moment).
- **Duplicate Lv1 rows:** when a potential's Param names a stat through a `NoLevel` ref to the Lv1 row (e.g. Two-Gun Salute `15825011`), that row also decodes as a modifier. Such duplicates are dropped in the kit spec (Lv1 value = the leveled ref's first value).
- **Amber's auto:** 12 shots in ~2 s + ~0.5 s reload (user-timed); every cast restarts it with a full magazine.
- **Supports can skip their ult** (kit leaves it out): Snowish Laru's ult isn't used in the reference video.
- **Snowish Laru on-field 14 s** per skill (user-timed); her skill CD keeps ticking meanwhile.

## Amber / Flora / Chixia: minions (2026-11-01)

- **Which buffs reach minions** (user, from community knowledge of the "minion bug"): buffs scoped to "Trekkers" (e.g. "all Ignis Trekkers' Ignis DMG", "the squad's ATK") **don't** reach minions. Buffs that say "minions" or "friendly/all units" do. Enemy debuffs (DMG Taken) always count. Minion hits get the summoner's stat sheet (base stats, disc stats and emblems), Minion DMG/Crit stats, enemy debuffs and modifiers that reach minions.
- The flag is read from the text (`effects.text_reaches_minions`): it looks at what the sentence naming the stat _increases_ (the part after "increase"), or at the whole text when the stat is only a `&ParamN&` placeholder. Specs set `minions: true|false` where the text names minions differently (Laru's Heart's Edict: "their Crit DMG" = Walnut's and Curly's).
- Team assumption `minion_buffs: all` gives minions every buff again, for comparison. Before the battle-start snapshot rule (below) and the Prayer of Raging Flame drop, the text rule took Chixia's share from 68% to 62%. Since then (2026-11-02) `text` and `all` give the same shares on both minion teams: Chixia 65.1% (test fixture build) / 62.9% (saved build), Laru 54.3%. Every triggered buff in those kits and discs either names minions or doesn't apply to them.
- **Battle-start snapshot** (user, in-game, 2026-11-01): minions summon with the summoner's stat sheet as it was at the start of the battle. So every always-on buff on the summoner reaches minions, whatever its wording (e.g. a disc melody's "Ignis Trekkers' Ignis DMG"). Buffs that come and go (on cast, on hit, while X) reach minions only if they name minions / friendly units, per the rule above. Chixia's triggered self-buffs ("Chixia's ATK", Dragon Blaze) don't reach them. Buffs averaged as `uptime × stacks` (a GUESS uptime or an unknown trigger) count as coming and going, not as always on.
- **Prayer of Raging Flame's ATK buff is not modelled**: in game it only stacks when hitting multiple targets and never fires on a single boss (user-checked, plus community reports). The text doesn't say so. Its ult Ignis Mark still applies.
- **Snowy Night Surprise's Hymn** needs the summoner's own Ode, which comes from her own Skill DMG (Word 6002): `&recent:skill_dmg:12.25`.

## Build guide page: emblems (2026-11-01)

- **Emblem "+N" on a potential not taken in the run** is assumed to give that potential at level N (user, 2026-11-01; real behaviour unknown). With a target it fights at target + N, capped at 9.
- **Charge Efficiency (AttrType 37)** lines: "(Main)" applies only while the trekker is the main, "(Support)" only while a support (Claude's reading; the data names their attributes `EnergyEfficiency` / `EnergyConvRatio`). Each multiplies the energy that trekker gains from the main's hits by `1 + value`; passive energy per second is unchanged. Unconfirmed in game.
- **Emblem stat lines are offered in every slot** (Lv70/80/90); `CharGemAttrValue` has three TypeId groups that look like per-slot pools (the third lacks element PEN and Charge Efficiency), but which group is which slot isn't confirmed, so the page doesn't restrict by them.

## Chitose / Freesia / Teresa (2026-11-01)

- **Stored skill uses:** `Skill.SectionAmount` = stored uses, `UseInterval`/10000 = min seconds between them (Torrent Flash: 2 uses, 0.5 s; the user saw 0.4-0.6 s gaps). One recharge timer refills uses one at a time and keeps its progress across casts (user, in game: at 2.5 uses a cast leaves 1.5).
- **Torrent Flash: Scale** replaces a Torrent Flash cast and spends a use (user): every 3rd cast, every 2nd with Cascade of Ruin (`cycle` on the skill hits). With Returning Tide, every cast after the first is a Scale against a boss (user-observed; a miss breaks the chain, not modelled). The user's build had Flowing Circle (3 uses).
- **Mirror Images** deal their hits at the stated share of Chitose's multiplier (`mult` on the hit). Against the Flow's image triggers Aqua Marks; those Mark hits are full value (GUESS).
- **Chill** (Word 1027) is a pure enemy status stacked by every Aqua Mark Chitose triggers (10 s, 3 stacks). With Marks applied by Teresa's domain, Surge: Ripple and Freesia's skill, it's up ~all fight; Frozen (3 stacks) isn't modelled separately: "Chill/Frozen" conditions test Chill.
- **Freesia's Berserk autos** (support, after her ult) are ult-action hits: first string user-timed, then one string every 3 s (GUESS) until she leaves at +17 s.
- **Surging Shield** appears 0.8 s after the cast and lasts its full duration (8 s with Surge: Infinite, user-timed unhit); boss hits breaking it aren't modelled.
- **Aqua disc specs** (user answers, 2026-11-01): Teresa's Surging Shield counts as "the main gains / has a shield" (Summer Afternoon Rain). Destiny Cards (United by Fate) only exist in a side mode: 0. "Aqua VUL" = Aqua DMG Taken debuffs, assumed always up (Winter's Grip / Wave Breaker). Bosses count as elite or higher. Getting hit (Soda Shopping) is low uptime (10%, GUESS). Main above 80% HP (Steam Syndrome): always. Tide Weave (Fleeting Glimmers) is a disc-only buff with the listed effects; its support-ult Energy refund isn't modelled.
- **Bosses can't be Frozen** (user): "Chill/Frozen" conditions test Chill only.

## Resilience breaks and Boss Blitz enemies (2026-11-03)

Spec: `docs/superpowers/specs/2026-11-03-resilience-break-design.md`. Validation: `docs/validation/2026-11-03-boss-blitz-breaks.md`.

- **The bar:** 250M resilience (`MonsterValueTemplete.Toughness`) for both Boss Blitz bosses and Generic (user). At 0 the enemy is broken for 10 s (`Monster.ToughnessBrokenTime`), then the bar refills to full (`IsToughnessRecorver`). `enemy.resilience: 0` turns it off (regression anchor: `fl_noya_skill` then reproduces the pre-resilience totals exactly).
- **Resilience per hit (inferred, no per-hit table found):** the hit's damage without the break ratio × the hitter's `Attribute.ToughnessDamageAdjust`/10000 (15000 = ×1.5 for Tilia, Firefly, Freesia, Teresa, Cosette, Chitose, Shia, Snowish Laru, FL Noya; ×1.0 otherwise; minions use their owner's) × (1 + Resilience Break Efficiency, EAT 43). Evidence: Noya's ~7.7M DPS × 1.5 fills 250M in ~22 s (user measured ~22–25 s of active time per break); Chitose's team broke once on 239M.
- **Break ratio ×1.5** (`break_ratio`), unverified: the reference tester's "150%"; ×2.5 is the other reading (validation doc compares them). The hit that breaks the bar isn't boosted; only later hits are.
- **Lock (GUESS):** after a break ends, the bar can't be lowered from `lock_delay` 1.3 s for `lock_time` 4.7 s (fight time: the recorded 8.86 s lock minus a 4.2 s frozen Tilia-ult animation inside it). **Open question:** the second recorded lock lasted only ~0.3 s; no rule in the data explains either.
- **Preset RES** = data `{W,F,S,A,L,D}ERFix` as is (weak 250, neutral 750, own element 2000). A team-file `res` override moves the preset's weak elements with it.
- **Boss abilities** use the stats the ability text names (Mark / Skill DMG Taken); the data's EffectType subtype is 53 (generic DMG Taken) on all of them. Count of the Duloos' "main takes +10% DMG" is defensive and not modelled; its Max HP +20% is.
- **Chance procs** use exact expected values: a proc with `chance` p and ICD has, per trigger, p × (1 − proc mass already spent in the ICD window) (`ExpectedICD`). Cosette's Form Breaker: 30% per claw, ICD 0.5 s → ~3.05 procs per 13-claw cast, each removing 0.4/0.5/0.6% of the bar.
- **`while:broken`** with the bar off falls back to `unknown_trigger_uptime` (spec). "Stunned" alternatives count as broken; bosses are stun-immune (Tilia's Enemy Counter already assumes so), so stun-applying potentials (Flora 512642, Tilia 510741, Shia 515528, Mistique 513508, Cosette 514228) don't break or stun the boss.
- **EAT 42 ("Resilience")** lines are the Trekker's own superarmor: not modelled.
- **The web page rates without breaks by default** (user, 2026-11-07; potential grid, emblem tables, pink search and optimizer, not the team total): any damage gain moves the break windows, which can make a plain ATK buff look negative. A no-break fight has `while:broken` off, so break-only lines (Decisive Strike's second line, the "while broken" potentials) and Resilience Break Efficiency are worth nothing in those numbers, while `while:not:broken` lines are always on. "Include breaks" on the page turns breaks back on.

## Every Boss Blitz boss as a preset (2026-11-14)

All 26 levels the 13 `ScoreBossControl` seasons use have a preset (`specs/enemies/<boss>_<yyyy>_<mm>.yaml`; the current season keeps `lithe_beauty` / `count_of_the_duloos`). Names come from `Monster.FAId` → `MonsterSkin.MonsterManual` → `MonsterManual.Name`. `tests/test_enemies.py::test_every_boss_blitz_level_has_a_preset` fails when a patch adds a season.

- **Data:** resilience, DEF, RES per element and break time from the monster, as for the first two. The first season's Lithe Beauty (6310030) has no `Toughness` row: no bar. Fight length 180 s for all (not in the tables).
- **Ability values** come from `ScoreBossAbility` / `EffectValue` / `BuffValue` refs. `ScoreBossAbility` "Pct" values are whole percents (30 = 30%), so those entries carry `times: 0.01`. Where the effect's data subtype is 53 (DMG Taken) but the text names a type, the text wins (as before).
- **"N times within X s"** triggers are approximated as every Nth event (`every`), without the time window. That overrates teams that can't hit that rate in a burst: Devouring Dark Ring (20 hits / 3 s), Call Down the Thunder (20 support Skill hits / 5 s, 3 Mark DMG / 5 s), Focus (2 Marks / 6 s), Aqua Ring, Pyro Blight (3 Marks / 5 s), Blood Pact (3 Mark DMG / 5 s).
- **Alternating forms** (Reality Shift 15 s, Baron Stance 30 s) start with the form the text names first (GUESS: Illusion, Warrior). Not modelled: Reality Shift's form extensions, Baron Stance clearing debuffs at a switch and pausing during breaks.
- **Fervent Combat:** at most one Frenzy removal per 5 s (icd); the +20 Energy per removal is not modelled (undervalues it).
- **The Count's Majesty:** a main Mark clears all Resistance stacks instead of one, so mains that trigger Marks less than once per 5 s are treated too kindly.
- **Fatigue on Hit:** the 80% DMG RES is a −80% in that type's DMG Taken; each 6 main hits of the type give +10%, 12 steps (to +40%).
- **Armor-Piercing Wedge:** squad DEF PEN +50. GUESS: the "+60% with a support on the battlefield" scales the 50 (to 80), rather than being 60% Ignore DEF.
- **Build-Up** (Skillful Refinement, Tailor-Made): a support's own stacks count either support's field time; the main keeps one count per support, as the text says.
- **Not modelled:** Momentum (VUL per player minion on the field: no squad-wide minion count) and Stormy Zeal's trigger (Wind Puffs are the boss's adds), which uses the assumed `unknown_trigger_uptime`. Boss DMG boosts and the squad's DMG Taken are defensive.

## Disc pass: every disc specced (2026-11-04)

- **Dodges** (user): the main dodges once every `dodge_interval` s on average (team assumption, default 10; event `dodge:main`). A dodge needs control: one due during a skill/ult lock (no control, but immune) waits for the lock to end. The schedule keeps its average rate, because the 10 s came from a real fight with locks included. Two dodges are at least 1 s apart (`DODGE_CD`, the dodge cooldown; user corrected 3 s -> 1 s). Each dodge costs 10 frames of attacking (`dodge_time` 0.333 s, pauses the auto string). Fewer auto hits also mean less energy, so ults come later, the supports' too. Zesty Curiosity and every kit dodge potential use it (Decisive Moment, Starlit Dash, Waltz of Ripples, Hunt is On, Swiftstep; Tremble and Fall's instant last strike after a dodge).
- **Dodge-cancel** (user, Nanoha): a chain is 2.40 s without a dodge and 2.13 s with a late dodge after the final throw, so dodging at the end of every auto string is strictly better, even without a dodge potential. The kit's `auto.dodge_cancel: {at: 1.4, duration: 2.0}` emits a dodge at that offset and shortens the string to 2.0 s (the measured 0.267 s saving; a perfectly timed dodge may save ~0.2 s more). Those dodges replace the periodic ones (`dodge_cancel: false` in a team's assumptions turns it off). Nanoha teams +5.6% to +6.6% pinks only; Starlit Dash Lv6 +4.8% -> +13.7%.
- **Dodge-cancel** (user, Amber, Precise Temperature Control): a dodge cuts the hits still to come, and the skill CD starts at the recast's dodge instead of when the recast ends. Timings (30 fps): recast ready 2,10 after the skill (38,12 -> 40,22), first auto 1,25 after the recast (41,03 -> 42,28). The kit dodges each cast at the earliest frame that keeps every hit: the first cast at 1,24 with the recast 0,10 later (41,26 -> 42,06), the recast at 1,13 with autos 0,11 later (39,25 -> 40,06). Both casts take 3,17 instead of 4,05. The 1,13 dodge and the CD start combine clips rather than coming from one. Each dodge takes the place of the next periodic one.
  - **Cutting the third volley loses damage.** Sim vs no dodges, 120 / 180 / 600 s, 3 Amber teams, with and without Grand Finale Lv6: dodging after the last hit +0.69% to +2.40%, cutting the recast's volley -1.77% to -6.29%, cutting both -3.76% to -8.70%. Cutting both only saves 8 more frames per cycle. The recast's big hits give 0.71 Energy each against 23.1 per cast, so cutting its volley also costs ults (16-18 -> 13 in 600 s, against 17-19 with the default dodges).
  - **No gain on autos** (user): dodging before the reload only moves the reload after the dodge, and the reload is too fast to interrupt reliably. Casting on an empty magazine needs no reload, as the string already restarts full after every cast.
- **Amber's recast is its own skill** (user's clips, 2026-11-06): it has its own script and hit rows, and they depend on whether the first cast triggered a Mark. Each clip's crit multiplier is constant across hits (2.416 with Flora's butterflies, Incineration included), so non-crit values can be recovered from crits.
  - **No Mark:** big / small are 13091 / 2106 (106% / 17%, rows `103303004` / `103303003`), with no Precise Temperature Control bonus. The first cast is 11855 / 850 (106% / 7.6%). Not modelled: in the 3 Amber teams every first cast triggers a Mark (52 of 52 in 600 s).
  - **Marked (modelled):** both big hits are equal, and big / volley is 10109 / 7454 and 12801 / 10408, which fits rows `103303001` (22.7%) and `103303003` (17%). The clips' 1.356 and 1.230 sit either side of the rows' 1.335. Row `103303002` (29.7%) isn't seen in game.
  - **The +65% is a separate multiplier (`mult: 1.65` on every recast hit), not DMG bucket.** The stat is EAT 85 "DMG Multiplier". The recast's per-% scale against the first cast's volley just before it is 1.98x and 2.35x in the two clips, which +65% in the bucket can't reach even with nothing else in it.
  - **Why the jump is above 1.65x:** buffs change between the casts. With the clips' Amber build (skill Lv8; Dominant Firepower, Precise Temperature Control, Grand Finale 6, Ardent Trigger 6, Fiery Rhythm 2; sim team Amber / Flora / Chixia), the sim's ratio varies per cycle from 1.41x to 2.24x, against the clips' 1.98x and 2.35x. A bucket bonus would top out near 1.93x on the same timing. This favours the multiplier without proving it: no clip has the same buffs on both casts. The first cast's rise of about 11% after its first hit (21098 -> 23503, 23092 -> 25657) also shows in the sim (8-10%), even without Fiery Rhythm. Its source wasn't traced; the user's guess for these spikes is Chixia's tiger (ATK buffs) or Flora's potential that gives ATK% when the main crits.
  - **Marks:** the recast can trigger them when one is up (Incineration on its shots 1 and 3, `2026-11-01-amber-flora-chixia.md`; on shot 2 in a 2026-11-06 clip).
  - **Grand Finale:** its 2 extra rounds are big hits on the first cast only; its Skill DMG bonus is still applied to the recast.
- **Dodge on cooldown** (user): `dodge_spam: {interval: 3, potentials: [ids]}` makes the main dodge every 3 s, but only in builds with one of those potentials (without them it only costs damage, and a team-wide rate would inflate the potentials' rating). Set for Mistique (Decisive Moment: weak autos), Chitose (Waltz of Ripples) and Nazuna as main (Swiftstep: Gerie does most of the damage). Gerie stays at 10 s (−2.7% at 3 s even with Hunt is On); Nanoha dodge-cancels instead (below). With Tremble and Fall, Chitose's autos become a dodge loop: dodge, last strike +0.833 / +0.933 s, next dodge +0.967 s (user-timed). The Mirror Image and Serpent's Glide follow the dodge strikes.
- **Getting hit** (user): the main is hit about every 20 s (`hit_taken_interval`, event `hit_taken:main`), never while the boss is broken (a broken boss doesn't attack). It depends on the boss and on melee vs ranged. It replaces the 10% GUESS uptime of Soda Shopping, The Shining, Unknown Fragrance, Cage of Roses, ★Rolling Life★ and Delusion, and drives Prayer Beneath Light's shield.
- **Disc shields last their full duration** (user): most boss hits are chip damage, and losing a shield to a big hit is usually a player mistake. Shields (EffectType 42) are tracked as statuses in the disc spec. New Star Prelude's shield is a 20 s timer from battle start (data: `Trigger` 19, condition 29, param 20), so it's up 15 s of every 20 s.
- **Battle-start Energy** (EffectType 34, the 3★ "restore 15 Energy at the start of battle" melodies) starts the receiving Trekkers' Energy at that value (pseudo stat `START_ENERGY`).
- **VUL** = an elemental DMG Taken debuff on the target (user, United by Fate). "vs targets with X VUL" lines use `while:vul:<element>`, which holds while any modifier of that element's DMG Taken (EAT 35–40) is up on the enemy. Slot-only Taken stats (e.g. "Ventus Skill DMG Taken", written as Skill DMG Taken) don't count.
- **"While the main's Ultimate is active"** (Summer Sanctuary, user): until the main regains control after the cast (its ult `lock`), `while:in_action:0:ult`.
- **Fly, O Caged Bird's Starlit Hope** (GUESS, user will test): one stack per second a Ventus Versatile support is on the battlefield (`on_field_1s`). Cyclone / Blossom Marks are Noya's / Nanoha's Ventus Marks (their kits tag the Mark hit).
- **Defensive lines** ("reduces DMG taken by the main") are dropped in the specs. **Kill-based** lines are dropped (single boss). **Destiny Cards:** 0.
- **Per-caster buffs** ("increases their Skill DMG" after any Ventus Trekker's skill): the main's cast buffs the main; any support's cast buffs both supports.
- **Status stacks shared per team:** Touch of Miracle's Assembly and Little Paradise's Loaded are one status for all Terra Vanguards. "Has N stacks" is read as N or more. Their max is 3 because both harmonies are always active in the sim.
- **Chance-based debuffs** (Laceration, Shock: 35% per non-Auto hit, 8 s) fire on every 3rd such hit, so they're near-permanent in practice. Both are named statuses, so their "vs Lacerated / Shocked targets" harmonies test them.
- **One Shot, One Down's ATK ramp** is now simulated (+1 stack every 8 s from 0 s, max 10) instead of the 120 s average. That gives one stack early.

## ATK SPD and windowed cooldown cuts (2026-11-06)

- **ATK SPD** (stat 47) runs the main's whole auto string faster: its clock advances at `1 + ATK SPD`. Skill and ult locks don't change. Only the shots are timed, so the reload scaling with it is a GUESS.
- **Confident Mode** (user, 30 fps): 12 shots take 60 frames at base (12 -> 11 at 2,26, 1 -> 0 at 4,26) and 43 after the skill (36 -> 35 at 12,26, 25 -> 24 at 14,09). That's +39.5%, against 35% in the text and data, and the kit uses the timing. The clip has no other ATK SPD source (user), but the video is 29.97 fps and the game runs at 60 fps, so a reading can be a frame off. The string's base timing stays at the earlier 61 frames, which gives 43.7 frames buffed.
- **Other ATK SPD potentials** use their data values and aren't timed: Flurry Stance (Noya), Gale Rage and Sun Chaser (Nanoha), Speed Surge (Ann), Isn't It Awesome! (Teresa). Minion ATK SPD (Chixia's Crimson Dragon: Chant, Laru's Heart's Trumpet) still isn't modelled, because those summons run on fixed hit timelines.
- **Overloaded Spark** (user): ult, skill, recast, then a 4 s CD instead of 8. The window is 8 s after the ult ends (9.167 s from its cast), and it's checked when the CD starts. With the recast, the first CD after the ult is halved and the next one starts too late, which matches the user's one halved CD per ult. Without the recast the sim can halve more than one per ult: the user has no such build to test, so that case is a GUESS. Its Skill DMG now uses the same window, which it previously started at the ult's cast.
- **The CD cut shifts when ults land**, which can outweigh the extra skill cast. `amber_flora_chixia` gains one skill per 120 s, but its total moves -1.7% (120 s), +1.6% (180 s), -0.6% (300 s) and +2.0% (600 s): the ults catch or miss Flora's and Chixia's buff windows.

## Energy from potentials, movement, projectiles (2026-11-07)

- **Energy from potentials** (procs with `energy`) is flat (Claude's reading, unconfirmed in game): Charge Efficiency isn't applied, since it's described as scaling Energy gained from hits. It goes only to the Trekker the text names. Modelled: Knight's Seal (Tilia), Slash: Windfury! (Noya), Guiding Star (Firstlight Noya, every 1 s while in Starender, including during ult locks). Still not modelled: the Energy on kill-only or projectile-blocking lines, and Fleeting Glimmers' support-ult refund (a disc, which has no procs).
- **Blazing Waltz** (user): Amber can keep moving all fight and stops only for her ult, so it's on except during the ult's `lock`. The ult's own hit lands inside the lock and doesn't get it. Assumes she moves through her skill casts and autos.
- **Downwind Journey** (user's read, not confirmable in game): Nanoha's autos count as projectiles ("surely"), and her shurikens probably do ("they sure feel like it"). Her clones use her attacks, so theirs count too (user). Hits carry a `projectile` tag. Every tagged hit is assumed to pass through a wall while one stands, which makes it an upper bound. Melee mains get nothing.
- **Single-row buffs:** a kit buff whose id is itself a row reads that row. Before this, `level: ult` at Lv10 read id + 100: Buried Past gave Firstlight Noya stat 85 at 36% (another talent's row) instead of Crit DMG +12%. The right row is worth more: pinks only, `fl_noya_t1_firefly_tilia` +2.4% and `fl_noya_t1_shia_tilia` +3.2%.
- **Guiding Star's Energy moves the calibrated team, and the text is trusted (user).** 2.5 Energy/s (text, Lv6) over a 30 s Starender gives FL Noya a 3rd ult in 120 s. Its sheet rating goes from 12.93% to 29.48% (Maygi: B+; 8.45% to 19.37% against pinks only), it takes Astral Brilliance's place in the reference build, and so Noya's Lux PEN emblem lines go from 9.79% / 0.69% to 20.17% / 8.89% (Maygi: 8.65% / 0.05%). Not an edge effect of 120 s: at Lv6 it's worth 17-23% from 120 s to 600 s (pinks only).
  - **User's clip** (`bb_noya_shia_tilia_ingame` build: Lv2, 0.9/s, T0; 30 fps): first Energy 2,23, ult ready 45,12 (42.6 s), cast 47,18, first Energy 48,10 (before the first auto at 51,00, so it starts during the ult), ready again 1:30,24 (43.2 s from the cast). Sim, same build: first cast 42.6 s, then gaps of 40.0 s with Guiding Star and 43-44 s without. The clip's gap is 3 s longer than the sim's and matches its no-Guiding-Star gap, but the user sees variation from the boss moving and dodging (a 3 s difference is 27 of 235 Energy), so one clip can't separate them. It doesn't test Lv6 either: the Lv2-Lv6 scaling comes from data.

## Key talents (2026-11-07)

All from the game text, none checked in game. Stat nodes were already read from data. T5 on all three members (nodes plus key talents) comes to +75% to +207% across the teams; no in-game measurement backs that yet.

- **Not modelled, listed by the sim when unlocked:** Ann's The Watcher in the Rye (needs her ult to destroy a hostile projectile, which depends on the boss). Snowish Laru's Queen's Party (needs the shield from her ult form; her support kit doesn't cast the ult).
- **Worth nothing here (`buffs: []`):** Noya's Today's Bond and Canace's Imminent Dawn (kills), Canace's Yearning for Truth (normal and elite targets, and every preset is a boss).
- **Snowish Laru's ult** (user: the community doesn't use it unless the main is Fuyuka): her support kit sets `ult_only_with: [134]`, so it's only cast with Fuyuka, on untimed hits copied from her main role. Dreams Replayed fires only then, and Queen's Party isn't modelled.
- **"Vs elite or higher-tier" is always on.** Every preset is a boss.
- **HP conditions hold** (Claude's reading): Flora's Fate of Nirvana (main above 50%) and Firstlight Noya's Meeting You at Dawn (above 20%).
- **Readings of unclear text** (Claude's, unconfirmed):
  - Divine Punishment (Tilia) and Withered Flower Show (Flora) say "increases ATK" without saying whose. Modelled on the squad: 8.4% is the size of their other squad buffs.
  - Fate of Nirvana's Skill Crit Rate goes to the main.
  - "Chill and Freeze" (Freesia's The Fugitive: Judgment) tests Chill, as bosses can't be Frozen (user). Teresa's Sturdy Edge is always on, as Demonic Devour assumes.
  - Freesia's roar is the ult's first two hits ("growls furiously"), not the AoE hit after them.
  - Canace's Lost Youth lasts 6.533 s from the cast: the Wreath lands at +0.93 s (user-timed) and works for 6 s (text). Her Flying Leaves are main-role, and that kit is a stub.
  - Canace's Hidden Past ("for each target hit") gives one stack per ult on a single target.
  - Ridge's Bountiful Harvest counts Ult DMG hits by anyone, Ridge included, and then lasts the rest of the fight.
  - Mistique's Truth As You Wish covers every phantom hit during its 12 s, which slightly overrates it: phantoms summoned before it started get it too.
- **"Removed after casting her Ultimate"** (Chitose's Afterrain Clarity, Shia's Beyond the Horizon, GUESS): all of that ult's hits get the stacks, and they clear right after the last one. Clearing at the cast would leave them doing nothing.
- **A chance as a count:** Cosette's Determined to Leave (25% per hit) fires on every 4th hit, the same rate without the randomness.
- **EAT 85 "DMG Multiplier" is now a real multiplier** (`DMG_MULT`, x (1 + value) on the hit), matching what the user's clips showed for Amber's recast. Night Watcher's Duty and Meeting You at Dawn use it. Resolve: Blitz, Surge: Thunderbolt and Firstlight Noya's per-Glimmer autos moved to it too (user, 2026-11-07), so `as_stat` no longer has any users. Lines on one hit add together inside the multiplier, as they did in the bucket. The bucket and the multiplier only differ when something else is in the general DMG bucket (EAT 49 / 50), and `fl_noya_skill`'s workbook has nothing that does: it comes out the same as before the move. Unscoped EAT 85 lines on stub support kits (Nimble Catwalk, Fiendbreaker, Breath of Light) were ignored before and now apply to all their hits; no team uses them.
- **`damage:<who>`:** A Dance with Bullets (Amber T1) now stacks once per hit instead of once per tag and bucket. `amber_flora_chixia` moves -0.02%. No other team's total moved at its current talents.

## Frame data (2026-11-13)

The 60 roles authored on guesses (below) are now timed from the game's own animation data and marked `timing: frames`. The data is read from the installed game's plain Unity bundles (`python -m ssr.frames extract`, cached in `data_src/frames/`). Nothing is decrypted: the Lua, `global-metadata` and `Hotfix.dll` stay untouched, so what Lua decides (summon fire rates, which bullet a script spawns) stays a GUESS. `python -m ssr.inspect frames <char>` prints a character's clips, and `scripts/frames_propose.py <id>` prints them next to the spec. The rules below were calibrated on the user-timed kits (FL Noya, Gerie, Chitose, Mistique, Leafia, Noya), which they match within about 0.1 s:

- **Strings and locks:** the next auto strike, and the main's next action after a skill or ult, starts at the end of the clip's combo window. An auto's `duration` is the chained strikes; a magazine is ammo × the shot clip + the reload's combo-window end.
- **Ult:** the cutscene (TL) clip is used, not the no-cutscene one.
- **Hits:** a hit event lands at its time. A hit window with a detect interval repeats every interval (limited by `damageImmuneDuration`). An area hits `hitDelay` after it spawns, then every `hitInterval` while it lasts.
- **Bullets** fly 3 units to the boss (GUESS; Ann's ult measured +0.97 s fits), so a 40 u/s bullet takes 0.075 s, capped by its lifetime.
- **Supports:** on the field for the skill clip(s) + 1.35 s, or the ult's TL clip + 1.65 s (the exit, calibrated on timed supports).
- **The text wins over data** where it gives a count or rate and the data disagrees (noted in the spec). The user's own timings are kept where they exist.
- **Counts the data can't give** (fans of bullets, Lua-driven summons, "multiple times") stay GUESSes and are marked. Notable ones: Shia's Snow Rabbit fan (2 of 18 bullets), Willow's Bubble Machine strike 3 (1 of 7 bubbles), Shia's skill Rabbits' fire rate, Willow's support bubbles (1/s).
- **Pink-only clips:** where a pink plays a longer clip (Laru's Lance Sweep, Snowish Laru's Whipping Gale, Caramel's Melody Return), the hits follow it but the lock doesn't (potentials can't change a lock); noted in the spec.

## Untimed kits (2026-11-07)

Every Trekker now has both roles. The 60 roles marked `untimed: true` hadn't been timed in game; they're all `timing: frames` now (above), and the table below is what they used before. The rest of this section still applies. Validation: `docs/validation/2026-11-07-untimed-kits.md`. The aim is that timing them moves them up, so each guess sits on the slow side of the kits the user has timed. Each is a default that a measurement replaces.

| Thing | Guess | Timed kits, for comparison |
| --- | --- | --- |
| Main auto string | 1 s per strike, first hit +0.4 s | about 0.6-1.0 s per strike |
| Main skill lock | 2.5 s, or the hits' span if longer; 1-2 s for a shot or summon | 0.37-2.33 s |
| Main ult lock | last hit + about 1 s, up to 6 s; 3 s for summons that keep working | 0.47-5.63 s |
| Main skill CD | starts when the cast ends (`cd_start` = lock), unless stored uses or the text says otherwise | at the cast for most; +2 s for Noya, after the recast for Amber |
| Support on the field | 3 s; longer only where the hits or text need it | 2.6-21.5 s |
| Hit counts | as the text says; a plain "multiple times" counts once | text can undercount (Amber) |
| First hit | skill +0.5-1 s, ult +1 s | |

- **Reused timings:** a role whose other role was timed reuses that role's ult hits, and its on-field time as the main's ult lock.
- **Crits as a count:** "on a crit" effects assume a 50% Crit Rate, as every 2nd event or `chance: 0.5`.
- **HP conditions on the boss:** "below N% HP" holds N% of the fight, as an `uptime`. The Trekker's own HP conditions hold, as in Key talents. "Vs elite or higher" always holds.
- **Nothing rests on the 100% default:** `tests/test_untimed_kits.py` fails on an unscoped modifier or a missing trigger. Lines that can't be pinned are dropped with a comment and are worth 0. So are kill-based, multi-target, ricochet and purely defensive lines.
- **Rotation choices:** Allie casting her ult through her skill and Wide Blade Arc's Mark DMG conversion aren't modelled. Tilia only holds Fortify Stance with a stance pink. Chaton taps her skill unless the build has a Bouncing Bomb pink, as bombs bounce to other targets. Sparkla holds for Rapid Fire unless the build has a Jaws pink. Willow uses Bubble Machine unless the build has a Megaphone pink.
- **Summons that aren't minions:** hits with a non-minion DamageType count (Jinglin's Qilin, Minova's clan, Karin's Boss Shark, Eleanor's Sentries, Sparkla's doll, Shia's Rabbits, Ann's Coco and Wind Bursts, Nanoha's clones). Only DamageType 7 pools are skipped: Firenze's Shadow Clones, Donna's Doll, Caramel's Boombox, Ann's Bubble, Snowish Laru's toys and Mistique's Lanterna Phantoms. What those give besides damage is kept where the text is plain (Bubble's squad ATK, Donna's Agile, Caramel's connection ATK).
- **Sub-actions as long locks:** a state that replaces the autos is written as hits on the action, inside a lock as long as the state, and skills can still be cast: Chaton's Evil Eye, Freesia's Berserk, Donna's Agile, Sparkla's modes, Firefly's Artillery Form, Snowish Laru's Dame Laru. Potentials that lengthen these states aren't modelled.
- **`ult_cost_scale`** (Minova's Urgent Reinforcement, "25% more Energy") multiplies the ult's Energy cost.


## Leafia: Resource Markers and Observation Points (2026-11-13)

Leafia (161) is user-timed in both roles (`specs/trekkers/161.yaml`). Her Observation Points deal her own Auto Attack DMG (DamageType 1), so they use her stat sheet; they're minion pools only for their lifetimes and attack loops. Resource Markers are a kit `resources:` counter (`specs/README.md`).

- **Amplification Crystals replace the strike** (user, 2026-11-13 follow-up clip): with Crystal Overclock a swing is an Amplification Crystal (rows `161100004`–`6`; 200k instead of 60k) when 3 Markers are held (2 with Marker Overload), else a normal strike. The Marker icon on Leafia is the Marker count (Buff `16100011`, up to 20); it empties when a crystal spends the last Markers. The "extra crystal" the user sees next to some of them is Marker Overload's 80% Vector Crystal.
- **Markers come at most once per second** (user: 2 every second attack with Overclock + Focused Penetration). Focused Penetration's extra Marker comes with each generation. Markers are absorbed about one attack after they spawn; the model gives them at once, which shifts which swings are crystals but not how many.
- **6 hits per auto string** (user), cycling the three strike rows (all 185% at Lv10). The text names 3 strikes.
- **Markers are picked up** as they appear in every build (GUESS; Focused Penetration absorbs them).
- **Turret limit:** a new Observation Point at the limit replaces the oldest (user), which costs its 1.8 s windup. Observer Array's limit is 1 / 2 / 3 at Lv1–3 / 4–5 / 6+ (data).
- **Field Echo's waves** come every 3 turret attacks: 3.1 s apart with Field Assault (user), 9 s without (GUESS). Field Assault's Marker comes every 3 shots.
- **Ult interval:** every 3 s (text), every 2 s with Draw Zone Bombardment (user: all trial builds have it, and their ult hits every 2 s).
- **Main skill lock** 1.2 s (user: first auto hit 1.633 s after the cast).
- **Obsidian Field / Observer Array** stack once per turret out.
- **Draw Zone Support:** its +50% Auto DMG ("while the ult is on cooldown or its energy isn't full") is always on; the +10% "in the ult's range" lasts 20 s from the cast. Both go to Terra Vanguard and Versatile Trekkers (so not Nazuna).
- **Support Calibration Marks:** each stack inflicted deals one Calibration hit 1 s later on average: with a Vanguard Strike every second they detonate at 3 stacks, on every 3rd strike (user: the 3rd strike's number is 2.06x the first, the model's strike + 3-stack detonation 1.9x). Calibration Expansion's extra stacks from a Vanguard main aren't modelled. Vanguard Calibration's "expire after 10 s" isn't forced on Co-Draw's longer turrets.
- **Terra DMG Etching does nothing with Calibration Detonation** (user, 2026-11-14): Etching only reaches targets within Tactical Mapping, which Detonation removes. The game let both work until that day's hotfix; the spec's potential-level `excludes` keeps them apart.
- **"In an all-Terra squad"** lines (Co-Draw's debuff, Terra DMG Etching, Mark Etching, Leyline Amp) use `while:squad:3:3`; "only 1 Terra Trekker" uses `while:not:squad:3:2`.
- **Greedy builds look ahead** (`compare.py`, web optimizer): each step also tries jumping a potential straight to its cap, and takes the jump when it gains more per level. Totals inside a jump are interpolated.

## Stack timers and emblem optimizer (2026-11-13)

- **Stack timers** (team assumption `stack_timers`, default `refresh` since 2026-11-13): a new stack of a buff resets every stack's timer (user, in game: Gerie's Delight in Ruin, all 6 stacks drop at once; the Co-Draw clip's Ascending Draw Zone grows to the 6th hit). Nearly every buff row has `BuffValue.TimeSuperposition` 2 (3,555 rows; 72 have 1, one has 3; those may differ, not modelled). `independent` (each stack expires on its own) was the behaviour before.
- **Leafia's tiers reach later turrets only** (user's Co-Draw clip: spawn strike / first mapping hit 0.338, model 0.345 untiered vs 0.192 tiered). Modelled as tiers gained when a turret expires (GUESS).
- **Emblem optimizer** (`greedy_emblems`, `python -m ssr.compare ... --emblems <tier>`): on top of the potential build, it fills each member's 3 emblems × 4 lines one line at a time, taking the line that adds the most team damage. Every line is at one tier (purple = top roll, "+3" on skill / potential lines). A line goes in at most once per emblem, and only in slots it can roll in. Stat lines fill the Lv70 emblem first. All-purple is a ceiling, not real gear (×6.6–8.3 on the Terra teams). The team file's own emblems are ignored.

## Touch of Nature is a separate Mark multiplier (2026-11-13)

- **Touch of Nature** (Nazuna 515612, main only; CN 印记伤害倍率, "Mark DMG Multiplier") is a separate x(1 + value) on Terra Trekkers' Mark hits, not part of the Mark DMG bucket. The data row is EAT 64 (Mark DMG) with second subtype 2, but every other potential whose text says 伤害倍率 uses EAT 85, and the user's test settles it: Nazuna main with Lv6 Touch of Nature, Gerie support's Mark 32864, then 43736 with a +33% Mark DMG emblem on Gerie (x1.331; a shared bucket would give x1.063). Modelled with `as_stat: 85, hit_tags: [mark]`. Mark DMG emblem lines are now worth their full value in Nazuna-main teams.

## Team finder (2026-11-13)

- **Every team at its own build** (`python -m ssr.finder`, the page's Find teams): each candidate team gets new pinks, potentials and emblems; nothing is carried over from the template's members. New members are skill 10/10/10, T0, Lv90, no bonus stats, no emblems. The template's discs (main and support), enemy, fight, assumptions, reference settings and budget apply to every team; its `hold` entries are dropped (they name members by index) and `reference.include` names no new member has are dropped.
- **Pinks are chosen on the per-team reference build** (the template's `reference:`, with its discs, main discs never re-picked), member by member, main first: the same coordinate search as `--pinks`, not on the screen build or the final one.
- **The screen is coarse**: each step takes one potential straight to Lv6 (5 picks on the main, 3 per support = 66 levels, not the real 60 or the template's budget). Teams are ranked by it; only the top N (default 5) get the full optimize (template budget split / total / max level) and greedy emblems. A team close to the cut can rank differently under the full build; the screen table shows every team so it can be checked by hand.
- Ratings run without enemy breaks unless breaks are on, as the page's other jobs.
